#!/usr/bin/env python3
from amplpy import AMPL
import amplpy
from SchedulerModel import SchedulerModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from gspread_formatting import CellFormat, TextFormat, format_cell_ranges

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Domyślne wartości
DEFAULT_MIN = 0
DEFAULT_PREFERRED = 3
DEFAULT_MAX = 10000
DAY_COST = 1000
BASE_COST = 1000
COST_WILLING = 970
COST_UNWILLING = 1030
COST_VOID = 100000
COST_WRONG_FREQUENCY = 1
COST_NOT_PREFERRED_SHIFTS = 100


def parse_int_with_default(values, default):
    return [int(v) if v.strip().isdigit() else default for v in values]

def parse_date_flex(date_str):
    # Usuń spacje, zamień nietypowe separatory na '-'
    cleaned = ''.join(c if c.isalnum() else '-' for c in date_str.strip())
    # Przykładowe formaty dat
    formats = [
        "%Y-%m-%d",  # 2025-05-01
        "%d-%m-%Y",  # 01-05-2025
        "%m-%d-%Y",  # 05-01-2025 (ostrożnie, bo kolizja z dd-mm)
        "%d-%b-%Y",  # 01-May-2025
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Jeśli nie udało się sparsować
    return None

class Processor :

    def __init__(self):
        self.fixed_shifts = {}  # (doctor, day_index) -> "0" / "1"
        self.day_cost = {}
        self.date_labels = []
        self.dates = []
        self.weekend = []

    def process_worksheet( self, spreadsheet, worksheet ) :

        # Wczytaj dane jako lista list
        self.spreadsheet = spreadsheet
        self.worksheet = worksheet
        data = worksheet.get_all_values()

        # Identyfikatory lekarzy (nagłówek, pierwsza kolumna pomijamy)
        self.doctors = data[0][1:]
        self.doctors.append("Void")
        
        # Wiersze danych z domyślną obsługą braków
        self.min_shifts = dict(zip(self.doctors, parse_int_with_default(data[1][1:], DEFAULT_MIN)))
        self.preferred_shifts = dict(zip(self.doctors, parse_int_with_default(data[2][1:], DEFAULT_PREFERRED)))
        self.max_shifts = dict(zip(self.doctors, parse_int_with_default(data[3][1:], DEFAULT_MAX)))

        prefer_sparse     = dict(zip(self.doctors, [val.upper() == 'TRUE' for val in data[6][1:]]))
        prefer_dense      = dict(zip(self.doctors, [val.upper() == 'TRUE' for val in data[7][1:]]))

        day_index = 0
        for row in data[8:]:
            if not any(cell.strip() for cell in row):
                continue  # pomiń puste wiersze

            date_str = row[0].strip()
            if not date_str:
                continue

            self.date_labels.append(date_str)

            parsed_date = parse_date_flex(date_str)
            if parsed_date:
                self.dates.append(parsed_date)
                self.weekend.append(1 if parsed_date.weekday() >= 5 else 0)  # 5=Saturday, 6=Sunday
            else :
                print(f"⚠️ Could not parse date '{date_str}', skipping row.")
                self.dates.append(None)
                self.weekend.append(0)
            entries = row[1:]

            for i, entry in enumerate(entries):
                doctor = self.doctors[i]
                value = entry.strip().lower()

                if value == "nie":
                    self.fixed_shifts[(doctor, day_index)] = "0"
                elif value == "tak":
                    self.fixed_shifts[(doctor, day_index)] = "1"
                # else :
                #     fixed_shifts[(doctor, day_index)] = "."

                if value == "chętnie":
                    self.day_cost[(doctor, day_index)] = COST_WILLING
                elif value == "niechętnie":
                    self.day_cost[(doctor, day_index)] = COST_UNWILLING
                else:
                    self.day_cost[(doctor, day_index)] = BASE_COST
            
            # fixed_shifts[("Void",day_index)] = "."
            # day_cost[("Void",day_index)] = COST_VOID

            day_index += 1

        self.days = list(range(day_index))

        for d in self.doctors:
            for day in self.days:
                if (d, day) not in self.day_cost or self.day_cost[(d,day)] == None:
                    self.day_cost[(d, day)] = BASE_COST

        # Pozostałe stałe:
        cost_per_dense_window = 1
        cost_per_sparse_window = 1

        # Dodajemy sztucznego lekarza Void

        # Parametry dla Void-a
        self.min_shifts["Void"] = 0
        self.preferred_shifts["Void"] = 0
        self.max_shifts["Void"] = 10000
        prefer_dense["Void"] = False
        prefer_sparse["Void"] = False

        model = SchedulerModel()

        model.set_data(
            doctors = self.doctors,
            days = self.days,
            day_cost = self.day_cost,
            min_shifts = self.min_shifts,
            max_shifts = self.max_shifts,
            preferred_shifts = self.preferred_shifts,
            prefer_dense = prefer_dense,
            prefer_sparse = prefer_sparse,
            cost_per_dense_window = COST_WRONG_FREQUENCY,
            cost_per_sparse_window = COST_WRONG_FREQUENCY,
            penalty_for_not_preferred_shifts = COST_NOT_PREFERRED_SHIFTS,
            fixed_shifts = self.fixed_shifts )
        
        for d in self.doctors:
            missing = [day for day in self.days if (d, day) not in self.day_cost]
            if missing:
                print(f"⚠️  {d} brakuje kosztu dla dni: {missing}")

        model.solve()

        print(model.get_schedule())
        print("Total Cost:", model.get_total_cost())
        self.schedule_df = model.get_schedule()

    def export_schedule_to_full_sheet(self):
        # Nowa nazwa zakładki
        print("Doctors: {}".format(self.doctors))
        new_sheet_name = f"{self.worksheet.title}-full-sched"

        # Sprawdź, czy zakładka już istnieje – jeśli tak, usuń
        try:
            existing = self.spreadsheet.worksheet(new_sheet_name)
            self.spreadsheet.del_worksheet(existing)
        except:
            pass  # nie istnieje, to dobrze

        # Utwórz nowy worksheet o odpowiednim rozmiarze
        num_rows = len(self.date_labels) + 1  # +1 na nagłówek
        num_cols = len(self.doctors) + 1      # +1 na kolumnę z datą
        result_sheet = self.spreadsheet.add_worksheet(title=new_sheet_name, rows=str(num_rows), cols=str(num_cols))

        # Przygotuj nagłówek
        header = ["Data"] + self.doctors
        values = [header]

        # Upewnij się, że index0/index1 to kolumny, nie indeks
        self.schedule_df = self.schedule_df.reset_index()
        # Budujemy macierz wyników (1 –> TAK, 0 –> "")
        for i, date in enumerate(self.date_labels):
            row = [date]
            for doctor in self.doctors:
                val = self.schedule_df.loc[
                    (self.schedule_df["index0"] == doctor) & 
                    (self.schedule_df["index1"] == i), "x.val"
                ]
                row.append("TAK" if not val.empty and val.values[0] == 1 else "")
            values.append(row)

        # Wpisujemy dane
        result_sheet.update(values)
        self.format_weekends( result_sheet )
        print(f"✅ Exported schedule to full sheet: {new_sheet_name}")

    def export_schedule_to_short_sheet(self):
        new_sheet_name = f"{self.worksheet.title}-short-sched"

        try:
            existing = self.spreadsheet.worksheet(new_sheet_name)
            self.spreadsheet.del_worksheet(existing)
        except:
            pass

        # Zakładamy, że schedule_df ma MultiIndex (doctor, day)
        self.schedule_df = self.schedule_df.reset_index()

        values = [["Data", "Dyżurny"]]

        for i, date in enumerate(self.date_labels):
            # Filtrujemy rząd z x.val == 1 dla danego dnia
            row = self.schedule_df[(self.schedule_df["index1"] == i) & (self.schedule_df["x.val"] == 1)]

            # Sprawdź czy ktoś miał dyżur (teoretycznie zawsze powinien ktoś być)
            doctor = row["index0"].values[0] if not row.empty else "???"
            values.append([date, doctor])

        result_sheet = self.spreadsheet.add_worksheet(title=new_sheet_name, rows=str(len(values)), cols="2")
        result_sheet.update(values)
        self.format_weekends( result_sheet )

        print(f"✅ Exported short schedule to short sheet: {new_sheet_name}")
    
    def format_weekends( self, result_sheet ) :

        # Komórki z datami zaczynają się od drugiego wiersza (bo pierwszy to nagłówek)
        red_text = CellFormat(textFormat=TextFormat(foregroundColor={"red": 1, "green": 0, "blue": 0}))

        # Zakładamy, że lista weekend ma tyle samo elementów co date_labels
        ranges_to_format = []
        for i, is_weekend in enumerate(self.weekend):
            if is_weekend:
                # Wiersze w Sheets zaczynają się od 1, więc +2 (bo nagłówek i 0-indeks)
                row = i + 2
                ranges_to_format.append((f"A{row}", red_text))

        format_cell_ranges(result_sheet, ranges_to_format)

def process_spreadsheets() :
    # sheet = client.open("Graf Lekarzy").worksheet("Dane")  # Arkusz musi istnieć
    print("Spreadsheets:")
    for ss in client.openall():
        print(f"    {ss.title} – {ss.id}")
        for worksheet in ss.worksheets():
            if worksheet.title.endswith("-sched") : continue
            print(f"        🗂️ Processing sheet: {worksheet.title}")
            processor = Processor()
            processor.process_worksheet( ss, worksheet )
            processor.export_schedule_to_full_sheet()
            processor.export_schedule_to_short_sheet()

if __name__ == "__main__":
    print("Alive")
    process_spreadsheets()

