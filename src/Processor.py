#!/usr/bin/env python3
from amplpy import AMPL
import amplpy
from SchedulerModel import SchedulerModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# TODO: rozpoznawanie dni tygodnia
# TODO: kolorowanie dni tygodnia w arkuszu wynikowym
# TODO: strimlite: hello world
# TODO: strimlite: wybór credentials.json
# TODO: strimlite: wybór arkusza
# TODO: strimlite: wybór zakładki
# TODO: generowanie harmonogramu
# TODO: preferowane weekendowe
# TODO: preferowane tygodniowe
# TODO: strimlite: instrukcje, helpy, autorzy itp.
# TODO: github

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

def process_worksheet( worksheet ) :
    fixed_shifts = {}  # (doctor, day_index) -> "0" / "1"
    day_cost = {}
    date_labels = []   # tylko informacyjnie

    # Wczytaj dane jako lista list
    data = worksheet.get_all_values()

    # Identyfikatory lekarzy (nagłówek, pierwsza kolumna pomijamy)
    doctors = data[0][1:]
    doctors.append("Void")
    
    # Wiersze danych z domyślną obsługą braków
    min_shifts = dict(zip(doctors, parse_int_with_default(data[1][1:], DEFAULT_MIN)))
    preferred_shifts = dict(zip(doctors, parse_int_with_default(data[2][1:], DEFAULT_PREFERRED)))
    max_shifts = dict(zip(doctors, parse_int_with_default(data[3][1:], DEFAULT_MAX)))

    prefer_sparse     = dict(zip(doctors, [val.upper() == 'TRUE' for val in data[6][1:]]))
    prefer_dense      = dict(zip(doctors, [val.upper() == 'TRUE' for val in data[7][1:]]))


    day_index = 0
    for row in data[8:]:
        if not any(cell.strip() for cell in row):
            continue  # pomiń puste wiersze

        date_str = row[0].strip()
        if not date_str:
            continue

        date_labels.append(date_str)
        entries = row[1:]

        for i, entry in enumerate(entries):
            doctor = doctors[i]
            value = entry.strip().lower()

            if value == "nie":
                fixed_shifts[(doctor, day_index)] = "0"
            elif value == "tak":
                fixed_shifts[(doctor, day_index)] = "1"
            # else :
            #     fixed_shifts[(doctor, day_index)] = "."

            if value == "chętnie":
                day_cost[(doctor, day_index)] = COST_WILLING
            elif value == "niechętnie":
                day_cost[(doctor, day_index)] = COST_UNWILLING
            else:
                day_cost[(doctor, day_index)] = BASE_COST
        
        # fixed_shifts[("Void",day_index)] = "."
        # day_cost[("Void",day_index)] = COST_VOID

        day_index += 1

    days = list(range(day_index))

    for d in doctors:
        for day in days:
            if (d, day) not in day_cost or day_cost[(d,day)] == None:
                day_cost[(d, day)] = BASE_COST

    # Pozostałe stałe:
    cost_per_dense_window = 1
    cost_per_sparse_window = 1

    # Dodajemy sztucznego lekarza Void

    # Parametry dla Void-a
    min_shifts["Void"] = 0
    preferred_shifts["Void"] = 0
    max_shifts["Void"] = 10000
    prefer_dense["Void"] = False
    prefer_sparse["Void"] = False

    model = SchedulerModel()

    model.set_data(
        doctors = doctors,
        days = days,
        day_cost = day_cost,
        min_shifts = min_shifts,
        max_shifts = max_shifts,
        preferred_shifts = preferred_shifts,
        prefer_dense = prefer_dense,
        prefer_sparse = prefer_sparse,
        cost_per_dense_window = COST_WRONG_FREQUENCY,
        cost_per_sparse_window = COST_WRONG_FREQUENCY,
        penalty_for_not_preferred_shifts = COST_NOT_PREFERRED_SHIFTS,
        fixed_shifts = fixed_shifts )
    
    # print("Min shifts:")
    # for d in doctors:
    #     print(f"  {d}: min={min_shifts.get(d)}, days={[i for (doc, i) in fixed_shifts if doc == d]}")
    # print(">>> DEBUG MakA")
    # print("Min shifts:", min_shifts["MakA"])
    # print("Zakazane dni (fixed_shift=0):", [i for (d, i), v in fixed_shifts.items() if d == "MakA" and v == "0"])
    for d in doctors:
        missing = [day for day in days if (d, day) not in day_cost]
        if missing:
            print(f"⚠️  {d} brakuje kosztu dla dni: {missing}")


    model.solve()

    # print("=== AFTER SOLVE, MakA ===")
    # var_x = model.ampl.get_variable("x")
    # x_vals = var_x.get_values().to_pandas()
    # makA_rows = x_vals.loc[x_vals.index.get_level_values(0) == "MakA"]
    # print(">>> x[MakA,*] dostępne zmienne:")
    # print(makA_rows)
    # print("~~~~~~~~~~~~~~~~~~~~~~~~~")

    print(model.get_schedule())
    print("Total Cost:", model.get_total_cost())
    return date_labels, doctors, model.get_schedule()

def export_schedule_to_full_sheet(spreadsheet, original_sheet, date_labels, doctors, schedule_df):
    # Nowa nazwa zakładki
    print("Doctors: {}".format(doctors))
    new_sheet_name = f"{original_sheet.title}-full-sched"

    # Sprawdź, czy zakładka już istnieje – jeśli tak, usuń
    try:
        existing = spreadsheet.worksheet(new_sheet_name)
        spreadsheet.del_worksheet(existing)
    except:
        pass  # nie istnieje, to dobrze

    # Utwórz nowy worksheet o odpowiednim rozmiarze
    num_rows = len(date_labels) + 1  # +1 na nagłówek
    num_cols = len(doctors) + 1      # +1 na kolumnę z datą
    result_sheet = spreadsheet.add_worksheet(title=new_sheet_name, rows=str(num_rows), cols=str(num_cols))

    # Przygotuj nagłówek
    header = ["Data"] + doctors
    values = [header]

    # Upewnij się, że index0/index1 to kolumny, nie indeks
    schedule_df = schedule_df.reset_index()
    # Budujemy macierz wyników (1 –> TAK, 0 –> "")
    for i, date in enumerate(date_labels):
        row = [date]
        for doctor in doctors:
            val = schedule_df.loc[
                (schedule_df["index0"] == doctor) & 
                (schedule_df["index1"] == i), "x.val"
            ]
            row.append("TAK" if not val.empty and val.values[0] == 1 else "")
        values.append(row)

    # Wpisujemy dane
    result_sheet.update(values)
    print(f"✅ Exported schedule to full sheet: {new_sheet_name}")

def export_schedule_to_short_sheet(spreadsheet, original_sheet, date_labels, doctors, schedule_df):
    new_sheet_name = f"{original_sheet.title}-short-sched"

    try:
        existing = spreadsheet.worksheet(new_sheet_name)
        spreadsheet.del_worksheet(existing)
    except:
        pass

    # Zakładamy, że schedule_df ma MultiIndex (doctor, day)
    schedule_df = schedule_df.reset_index()

    values = [["Data", "Dyżurny"]]

    for i, date in enumerate(date_labels):
        # Filtrujemy rząd z x.val == 1 dla danego dnia
        row = schedule_df[(schedule_df["index1"] == i) & (schedule_df["x.val"] == 1)]

        # Sprawdź czy ktoś miał dyżur (teoretycznie zawsze powinien ktoś być)
        doctor = row["index0"].values[0] if not row.empty else "???"
        values.append([date, doctor])

    result_sheet = spreadsheet.add_worksheet(title=new_sheet_name, rows=str(len(values)), cols="2")
    result_sheet.update(values)

    print(f"✅ Exported short schedule to short sheet: {new_sheet_name}")    

def process_spreadsheets() :
    # sheet = client.open("Graf Lekarzy").worksheet("Dane")  # Arkusz musi istnieć
    print("Spreadsheets:")
    for ss in client.openall():
        print(f"    {ss.title} – {ss.id}")
        for worksheet in ss.worksheets():
            if worksheet.title.endswith("-sched") : continue
            print(f"        🗂️ Processing sheet: {worksheet.title}")
            date_labels, doctors, schedule = process_worksheet( worksheet )
            export_schedule_to_full_sheet(ss, worksheet, date_labels, doctors, schedule)
            export_schedule_to_short_sheet(ss, worksheet, date_labels, doctors, schedule)

if __name__ == "__main__":
    print("Alive")
    process_spreadsheets()

