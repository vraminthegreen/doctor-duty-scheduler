#!/usr/bin/env python3
from amplpy import AMPL
import amplpy
from SchedulerModel import SchedulerModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from gspread_formatting import CellFormat, TextFormat, format_cell_ranges
import Params

# Domyślne wartości


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

    def __init__(self ):
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
        self.enabled = dict(zip(self.doctors, [val.upper() == 'TRUE' for val in data[1][1:]]))
        self.min_shifts = dict(zip(self.doctors, parse_int_with_default(data[2][1:], Params.DEFAULT_MIN)))
        self.preferred_shifts = dict(zip(self.doctors, parse_int_with_default(data[3][1:], Params.NO_PREFERENCE)))
        self.max_shifts = dict(zip(self.doctors, parse_int_with_default(data[4][1:], Params.DEFAULT_MAX_SHIFTS)))
        self.preferred_shifts_weekday = dict(zip(self.doctors, parse_int_with_default(data[5][1:], Params.NO_PREFERENCE)))
        self.preferred_shifts_weekend = dict(zip(self.doctors, parse_int_with_default(data[6][1:], Params.NO_PREFERENCE)))
        prefer_sparse     = dict(zip(self.doctors, [val.upper() == 'TRUE' for val in data[7][1:]]))
        prefer_dense      = dict(zip(self.doctors, [val.upper() == 'TRUE' for val in data[8][1:]]))

        day_index = 0
        for row in data[9:]:
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

                if value == "nie" or value == "must not" :
                    self.fixed_shifts[(doctor, day_index)] = "0"
                elif value == "tak" or value == "must" :
                    self.fixed_shifts[(doctor, day_index)] = "1"
                    print("MUST: {}, {}".format(doctor, day_index) )
                if value == "chętnie" or value == "willing" :
                    self.day_cost[(doctor, day_index)] = Params.BASE_COST - Params.PENALTY_MODIFIER_WILLING
                elif value == "niechętnie" or value == "reluctant" :
                    self.day_cost[(doctor, day_index)] = Params.BASE_COST + Params.PENALTY_MODIFIER_WILLING
                else:
                    self.day_cost[(doctor, day_index)] = Params.BASE_COST
            
            day_index += 1

        self.days = list(range(day_index))

        for d in self.doctors:
            for day in self.days:
                if (d, day) not in self.day_cost or self.day_cost[(d,day)] == None:
                    self.day_cost[(d, day)] = Params.BASE_COST

        # Dodajemy sztucznego lekarza Void
        # Parametry dla Void-a
        self.min_shifts["Void"] = 0
        self.preferred_shifts["Void"] = 0
        self.preferred_shifts_weekday["Void"] = Params.NO_PREFERENCE
        self.preferred_shifts_weekend["Void"] = Params.NO_PREFERENCE
        self.max_shifts["Void"] = Params.DEFAULT_MAX_SHIFTS
        prefer_dense["Void"] = False
        prefer_sparse["Void"] = False

        # Usuń lekarzy wyłączonych z grafiku
        disabled_doctors = [d for d in self.doctors if not self.enabled.get(d, True)]
        for d in disabled_doctors:
            self.doctors.remove(d)
            self.min_shifts.pop(d, None)
            self.preferred_shifts.pop(d, None)
            self.preferred_shifts_weekday.pop(d, None)
            self.preferred_shifts_weekend.pop(d, None)
            self.max_shifts.pop(d, None)
            prefer_dense.pop(d, None)
            prefer_sparse.pop(d, None)
            # Usuwanie złożonych struktur
            self.fixed_shifts = {
                k: v for k, v in self.fixed_shifts.items() if k[0] != d
            }
            self.day_cost = {
                k: v for k, v in self.day_cost.items() if k[0] != d
            }        

        model = SchedulerModel()

        weekend_param = {day: val for day, val in zip(self.days, self.weekend)}

        model.set_data(
            doctors = self.doctors,
            days = self.days,
            day_cost = self.day_cost,
            min_shifts = self.min_shifts,
            max_shifts = self.max_shifts,
            preferred_shifts = self.preferred_shifts,
            preferred_shifts_weekday = self.preferred_shifts_weekday,
            preferred_shifts_weekend = self.preferred_shifts_weekend,
            prefer_dense = prefer_dense,
            prefer_sparse = prefer_sparse,
            fixed_shifts = self.fixed_shifts,
            weekend_param = weekend_param )
        
        for d in self.doctors:
            missing = [day for day in self.days if (d, day) not in self.day_cost]
            if missing:
                print(f"⚠️  {d} brakuje kosztu dla dni: {missing}")

        model.solve()

        print(model.get_schedule())
        print("Total Cost:", model.get_total_cost())
        print("Server log:", model.get_server_log())
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
        header = ["Date"] + self.doctors
        values = [header]

        # Upewnij się, że index0/index1 to kolumny, nie indeks
        self.schedule_df = self.schedule_df.reset_index()
        # Budujemy macierz wyników (1 –> TAK, 0 –> "")
        for i, date in enumerate(self.date_labels):
            row = [date]
            present = False
            for doctor in self.doctors:
                val = self.schedule_df.loc[
                    (self.schedule_df["index0"] == doctor) & 
                    (self.schedule_df["index1"] == i), "x.val"
                ]
                if not val.empty and val.values[0]==1 :
                    present = True
                row.append("YES" if not val.empty and val.values[0] == 1 else "")
            values.append(row)
            if not present :
                print("Suspicious row for date {}:".format(date))
                print(self.schedule_df[self.schedule_df["index1"] == i])

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

        values = [["Date", "On-call"]]

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

def process_spreadsheets( client ) :
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
    # process_spreadsheets()

