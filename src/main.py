#!/usr/bin/env python3
from amplpy import AMPL
import amplpy
from SchedulerModel import SchedulerModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# TODO: empty preferred_shifts
# TODO: preferowane weekendowe
# TODO: preferowane tygodniowe

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Domyślne wartości
DEFAULT_MIN = 0
DEFAULT_PREFERRED = 3
DEFAULT_MAX = 10000
DAY_COST = 1000
BASE_COST = 1000
COST_WILLING = 700
COST_UNWILLING = 1300


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
    
    # Wiersze danych z domyślną obsługą braków
    min_shifts = dict(zip(doctors, parse_int_with_default(data[1][1:], DEFAULT_MIN)))
    preferred_shifts = dict(zip(doctors, parse_int_with_default(data[2][1:], DEFAULT_PREFERRED)))
    max_shifts = dict(zip(doctors, parse_int_with_default(data[4][1:], DEFAULT_MAX)))

    prefer_sparse     = dict(zip(doctors, [val.upper() == 'TRUE' for val in data[5][1:]]))
    prefer_dense      = dict(zip(doctors, [val.upper() == 'TRUE' for val in data[6][1:]]))

    day_index = 0
    for row in data[7:]:
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

            if value == "chętnie":
                day_cost[(doctor, day_index)] = COST_WILLING
            elif value == "niechętnie":
                day_cost[(doctor, day_index)] = COST_UNWILLING
            else:
                day_cost[(doctor, day_index)] = BASE_COST

        day_index += 1

    days = list(range(day_index))

    # Pozostałe stałe:
    cost_per_dense_window = 1
    cost_per_sparse_window = 1

    # Dodajemy sztucznego lekarza Void
    doctors.append("Void")

    # Dla każdego dnia dodajemy koszt np. 1000
    for day in days :
        day_cost[("Void", day)] = 100000

    # Parametry dla Void-a
    min_shifts["Void"] = 0
    preferred_shifts["Void"] = 0
    max_shifts["Void"] = 10000
    prefer_dense["Void"] = False
    prefer_sparse["Void"] = False

    print( "Day costs:" )
    print( day_cost )

    # Wywołanie Twojej funkcji
    # model.set_data(
    #     doctors=doctors,
    #     days=days,
    #     day_cost=day_cost,
    #     min_shifts=min_shifts,
    #     max_shifts=max_shifts,
    #     preferred_shifts=preferred_shifts,
    #     prefer_dense=prefer_dense,
    #     prefer_sparse=prefer_sparse,
    #     cost_per_dense_window=cost_per_dense_window,
    #     cost_per_sparse_window=cost_per_sparse_window
    # )

def access_spreadsheets() :
    # sheet = client.open("Graf Lekarzy").worksheet("Dane")  # Arkusz musi istnieć
    print("Spreadsheets:")
    for ss in client.openall():
        print(f"    {ss.title} – {ss.id}")
        for worksheet in ss.worksheets():
            print(f"        🗂️ Processing sheet: {worksheet.title}")
            process_worksheet( worksheet )


def solve_optimization2():
    ampl = AMPL()

    # Ustawienie solwera na HiGHS
    ampl.setOption("solver", "highs")

    # Definicja modelu AMPL
    ampl.eval(r"""
    set DOCTORS;
    set DAYS;
    param day_cost {DOCTORS, DAYS} >= 0;
    param min_shifts {DOCTORS} >= 0;
    param max_shifts {DOCTORS} >= 0;
    param preferred_shifts {DOCTORS} >= 0;
    param prefer_dense {DOCTORS} binary;
    param prefer_sparse {DOCTORS} binary;
    param cost_per_dense_window >= 0;
    param cost_per_sparse_window >= 0;
    param day_cost_modifier {DOCTORS, DAYS};
    var x {DOCTORS, DAYS} binary;
    set REST_WINDOW_STARTS within DAYS;
    set WINDOW_STARTS within DAYS;
    
    minimize Total_Cost:
        sum {d in DOCTORS, day in DAYS} day_cost[d, day] * x[d, day]
            + sum {d in DOCTORS} 1 * abs(sum {day in DAYS} x[d, day] - preferred_shifts[d])
            - sum {d in DOCTORS, t in WINDOW_STARTS} (
                if prefer_dense[d] = 1 and sum {k in 0..4} x[d, t + k] >= 2
                then cost_per_dense_window
                else 0
              )
            + sum {d in DOCTORS, t in WINDOW_STARTS} (
                if prefer_sparse[d] = 1 and sum {k in 0..4} x[d, t + k] >= 2
                then cost_per_sparse_window
                else 0
              );
              
    subject to Restr1 { day in { 0, 6 } }:
        x["Natalka", day] = 0;
              
    subject to One_Doctor_Per_Day {day in DAYS}:
        sum {d in DOCTORS} x[d, day] = 1;

    subject to Min_Shifts {d in DOCTORS diff {"Void"}}:
        sum {day in DAYS} x[d, day] >= min_shifts[d];

    subject to Max_Shifts {d in DOCTORS diff {"Void"}}:
        sum {day in DAYS} x[d, day] <= max_shifts[d];

    subject to Min_Rest_Period {d in DOCTORS diff {"Void"}, day in REST_WINDOW_STARTS}:
        x[d, day] + x[d, day + 1] + x[d, day + 2] <= 1;              
              
    """)

    # Przypisanie wartości
    ampl.eval(r"""
    data;
    set DOCTORS := Asia Ania Natalka Gosia Void;
    set DAYS := 0 1 2 3 4 5 6 7 8 9 10 11;
    set REST_WINDOW_STARTS := 0 1 2 3 4 5 6 7 8 9;
    set WINDOW_STARTS := 0 1 2 3 4 5 6 7;
    param min_shifts := Asia 1 Ania 1 Natalka 1 Gosia 1 Void 0;
    param max_shifts := Asia 3 Ania 6 Natalka 6 Gosia 6 Void 1000;
    param cost_per_dense_window := 1;              
    param cost_per_sparse_window := 1;
    param preferred_shifts :=
        Asia 2
        Ania 4
        Natalka 6
        Gosia 0
        Void 0;
    param prefer_dense :=
        Asia 0
        Ania 0
        Natalka 0
        Gosia 0
        Void 0;
    param prefer_sparse :=
        Asia 1
        Ania 0
        Natalka 0
        Gosia 0
        Void 0;
    param day_cost : 
        0   1   2   3   4   5   6   7   8   9   10 11 :=
        Asia     10   10   10  10   10   10   10   7   7   7   7 10
        Ania     10   10   10  10   10   10   10   10   10   10   10 10
        Natalka  10   7   10  13   10   7   10   10   10   10   10 10
        Gosia    10   10   10   10   10   10   10   10   10   10   10 10
        Void     1000   1000   1000   1000   1000   1000   1000   1000   1000   1000   1000 1000;
    """)

    # Rozwiązanie problemu
    ampl.solve()

    # Pobranie i wydrukowanie wyników
    x_values = ampl.getVariable("x").getValues()
    print(x_values)

    # Pobranie wartości funkcji celu
    total_cost = ampl.getObjective("Total_Cost").value()
    print(f"Total Cost: {total_cost}")

def solve_optimization() :
    model = SchedulerModel()
    doctors=["Asia", "Ania", "Natalka", "Gosia", "Void"]
    dcm = {}
    for doc in doctors :
        for day in range(0,11) :
            if doc == 'Void' :
                dcm[(doc,day)] = 1000
            else :
                dcm[(doc,day)] = 10
    dcm[('Asia',6)] = 7
    dcm[('Asia',7)] = 7
    dcm[('Asia',8)] = 7
    dcm[('Asia',9)] = 7
    dcm[('Natalka',1)] = 7
    dcm[('Natalka',3)] = 13
    dcm[('Natalka',5)] = 7

    model.set_data(
        doctors=doctors,
        days=list(range(11)),
        day_cost=dcm,
        min_shifts={"Asia": 1, "Ania": 1, "Natalka": 1, "Gosia": 1, "Void": 0},
        max_shifts={"Asia": 3, "Ania" : 3, "Natalka": 5, "Gosia": 6, "Void": 1000},
        preferred_shifts={"Asia": 2, "Ania" : 2, "Natalka": 3, "Gosia": 1, "Void": 0},
        prefer_dense={"Asia": 1, "Ania" : 1, "Natalka": 0, "Gosia": 0, "Void": 0},
        prefer_sparse={"Asia": 0, "Ania" : 1, "Natalka": 0, "Gosia": 0, "Void": 0},
        cost_per_dense_window=1,
        cost_per_sparse_window=1,
    )
    model.solve()
    print(model.get_schedule())
    print("Total Cost:", model.get_total_cost())



if __name__ == "__main__":
    print("Alive")
    # solve_optimization2()
    access_spreadsheets()
    # solve_optimization()

