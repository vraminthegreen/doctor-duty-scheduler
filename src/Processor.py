#!/usr/bin/env python3
from amplpy import AMPL
import amplpy
from SchedulerModel import SchedulerModel
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from gspread_formatting import CellFormat, TextFormat, format_cell_ranges
import Params
from collections import Counter
from datetime import timedelta


# Domyślne wartości


def parse_int_with_default(val, default):
    try:
        return int(val)
    except:
        return default
    
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
        self.log = lambda l : print(l)

    def set_logging( self, logging ) :
        self.log = logging

    def load_worksheet( self, spreadsheet, worksheet ) :
        self.log("Loading worksheet ...")
        # Read data as list of lists
        self.spreadsheet = spreadsheet
        self.worksheet = worksheet
        data = worksheet.get_all_values()

        # Doctor identifiers (we skip the first header column)
        self.doctors = data[0][1:]
        self.doctors.append("Void")

        self.enabled = {}
        self.min_shifts = {}
        self.preferred_shifts = {}
        self.max_shifts = {}
        self.preferred_shifts_weekday = {}
        self.preferred_shifts_weekend = {}
        self.prefer_sparse = {}
        self.prefer_dense = {}

        # Recognized parameter rows mapped to variables and parsers
        param_rows = {
            "enabled": (self.enabled, lambda val: val.upper() == 'TRUE'),
            "min_shifts": (self.min_shifts, lambda val: parse_int_with_default(val, Params.DEFAULT_MIN)),
            "preferred_shifts": (self.preferred_shifts, lambda val: parse_int_with_default(val, Params.NO_PREFERENCE)),
            "max_shifts": (self.max_shifts, lambda val: parse_int_with_default(val, Params.DEFAULT_MAX_SHIFTS)),
            "preferred_shifts_weekday": (self.preferred_shifts_weekday, lambda val: parse_int_with_default(val, Params.NO_PREFERENCE)),
            "preferred_shifts_weekend": (self.preferred_shifts_weekend, lambda val: parse_int_with_default(val, Params.NO_PREFERENCE)),
            "prefer_sparse": (self.prefer_sparse, lambda val: val.upper() == 'TRUE'),
            "prefer_dense": (self.prefer_dense, lambda val: val.upper() == 'TRUE'),
            "validation_result": (None, None)  # handled separately
        }

        # Dynamically parse parameter rows by header
        self.param_row_indices = {}
        start_of_schedule = None
        for i, row in enumerate(data[1:], start=1):
            label = row[0].strip().lower()
            if label in param_rows:
                self.param_row_indices[label] = i
                target, parser = param_rows[label]
                if target is not None:
                    target.update(zip(self.doctors, [parser(val) for val in row[1:]]))
            else:
                start_of_schedule = i
                break  # First unrecognized label = start of scheduling rows

        self.validation_result_row_index = self.param_row_indices.get("validation_result", None)

        if start_of_schedule is None:
            raise Exception("No schedule section found in the worksheet")
        
        day_index = 0
        for row in data[start_of_schedule:]:
            if not any(cell.strip() for cell in row):
                continue  # skip empty rows

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
                    self.day_cost[(d, day)] = 10 * Params.BASE_COST if d == "Void" else Params.BASE_COST

        # add Void doctor with parameters
        self.min_shifts["Void"] = 0
        self.preferred_shifts["Void"] = 0
        self.preferred_shifts_weekday["Void"] = Params.NO_PREFERENCE
        self.preferred_shifts_weekend["Void"] = Params.NO_PREFERENCE
        self.max_shifts["Void"] = Params.DEFAULT_MAX_SHIFTS
        self.prefer_dense["Void"] = False
        self.prefer_sparse["Void"] = False

        print("day_cost for {}: {}".format(self.doctors[0],
            [ self.day_cost.get((self.doctors[0], day), None) for day in self.days ]))

    def validate_log(self, doc, message) :
        idx = self.doctor_index.get(doc)
        if idx is not None:
            if self.validation_row[idx]:
                self.validation_row[idx] += "\n"
            self.validation_row[idx] += message

    def validate_disabled_doctors( self ) :    
        for doc in self.doctors[:-1]:
            if not self.enabled.get(doc, True):
                self.validate_log(doc, "⚠️ doctor disabled")

    def validate_shift_ranges(self):
        for doc in self.doctors[:-1]:
            min_val = self.min_shifts.get(doc)
            preferred_val = self.preferred_shifts.get(doc)
            max_val = self.max_shifts.get(doc)

            if min_val > max_val:
                self.validate_log(doc, f"🚫 min_shifts > max_shifts ({min_val} > {max_val})")

            if preferred_val is not None and preferred_val >= 0:
                if min_val > preferred_val:
                    self.validate_log(doc, f"⚠️ min_shifts > preferred_shifts ({min_val} > {preferred_val})")

            if preferred_val is not None and preferred_val >= 0:
                if preferred_val > max_val:
                    self.validate_log(doc, f"⚠️ preferred_shifts > max_shifts ({preferred_val} > {max_val})")

    def validate_preference_conflict(self):
        for doc in self.doctors[:-1]:  # skip 'Void'
            ps = self.preferred_shifts.get(doc, Params.NO_PREFERENCE)
            psw = self.preferred_shifts_weekday.get(doc, Params.NO_PREFERENCE)
            pswe = self.preferred_shifts_weekend.get(doc, Params.NO_PREFERENCE)
            all_set = all(p != Params.NO_PREFERENCE for p in [ps, psw, pswe])
            if all_set and ps != psw + pswe:
                self.validate_log(doc, f"🚫 preferred_shifts ({ps}) != preferred_shifts_weekday ({psw}) + preferred_shifts_weekend ({pswe})")

    def validate_sparse_dense_conflict(self):
        for doc in self.doctors[:-1]:  # skip 'Void'
            if self.prefer_sparse.get(doc, False) and self.prefer_dense.get(doc, False):
                self.validate_log(doc, "🚫 both sparse and dense preferences set")

    def validate_minimum_active_doctors(self, minimum_required=3):
        active_doctors = [doc for doc in self.doctors[:-1] if self.enabled.get(doc, True)]
        if len(active_doctors) < minimum_required:
            for doc in self.doctors[:-1]:
                self.validate_log(doc, f"🚫 not enough active doctors ({len(active_doctors)} total)")

    def validate_duplicate_doctor_names(self):
        name_counts = Counter(self.doctors[:-1])  # pomijamy "Void"
        for i, doc in enumerate(self.doctors[:-1]):
            if name_counts[doc] > 1:
                self.validate_log(doc, "🚫 duplicate name") 

    def validate_dates(self):
        if not self.dates:
            return

        # 1. Nieparsowalne daty
        for i, date in enumerate(self.dates):
            if date is None:
                self.log(f"🚫 unparseable date: {self.date_labels[i]}")

        # 2. Sprawdzenie ciągłości
        parsed_dates = [d for d in self.dates if d is not None]
        parsed_dates_sorted = sorted(parsed_dates)
        missing_days = []
        for i in range(1, len(parsed_dates_sorted)):
            expected = parsed_dates_sorted[i - 1] + timedelta(days=1)
            if parsed_dates_sorted[i] != expected:
                # Szukamy wszystkich brakujących dni między datami
                current = expected
                while current < parsed_dates_sorted[i]:
                    missing_days.append(current)
                    current += timedelta(days=1)

        if missing_days:
            missing_str = ", ".join(d.strftime("%Y-%m-%d") for d in missing_days)
            self.log(f"⚠️ Missing dates in schedule: {missing_str}")

    def manual_shift_days(self, doctor):
        return [day for day in self.days if self.fixed_shifts.get((doctor, day)) == "1"]

    def validate_manual_shift_spacing(self):
        # manual shifts may be closer than the rest period - the model allows it, but warn
        for doctor in self.doctors[:-1]:
            if not self.enabled.get(doctor, True):
                continue
            manual = self.manual_shift_days(doctor)
            for a, b in zip(manual, manual[1:]):
                if b - a <= 2:
                    message = f"⚠️ manual shifts too close: {self.date_labels[a]} & {self.date_labels[b]}"
                    self.validate_log(doctor, message)
                    self.log(f"{doctor}: {message}")

    def validate_min_feasibility(self):
        for doctor in self.doctors[:-1]:
            if not self.enabled.get(doctor, True):
                continue
            min_required = self.min_shifts.get(doctor, 0)
            if min_required <= 0:
                continue
            # manual shifts count as given; greedily add others respecting rest period
            taken = self.manual_shift_days(doctor)
            for day in self.days:
                if len(taken) >= min_required:
                    break
                if self.fixed_shifts.get((doctor, day), ".") == "0" or day in taken:
                    continue
                if all(abs(day - t) > 2 for t in taken):
                    taken.append(day)
            possible = len(taken)
            if possible < min_required:
                self.validate_log(doctor, f"🚫 only {possible} feasible days for min={min_required}")            

    def validate_input(self):
        self.log("Validate input ...")
        if self.validation_result_row_index is None:
            self.log("WARNING: validation row missing")
            return  # No validation row to write into

        num_columns = len(self.doctors)
        empty_row = ["validation_result"] + [""] * (num_columns - 1)
        self.worksheet.update(
            f"A{self.validation_result_row_index + 1}:{chr(65 + num_columns - 1)}{self.validation_result_row_index + 1}",
            [empty_row]
        )

        # Initialize empty warning list for each doctor (excluding Void)
        self.validation_row = ["validation_result"] + ["" for _ in self.doctors[:-1]]

        # Build a map: doctor → column index in validation_row
        self.doctor_index = {doc: i + 1 for i, doc in enumerate(self.doctors[:-1])}

        self.validate_disabled_doctors()
        self.validate_shift_ranges()
        self.validate_preference_conflict()
        self.validate_sparse_dense_conflict()
        self.validate_minimum_active_doctors()
        self.validate_duplicate_doctor_names()
        self.validate_dates()
        self.validate_manual_shift_spacing()
        self.validate_min_feasibility()

        self.worksheet.update(
            f"A{self.validation_result_row_index + 1}:{chr(65 + num_columns - 1)}{self.validation_result_row_index + 1}",
            [self.validation_row]
        )

    def remove_disabled_doctors(self) :
        disabled_doctors = [d for d in self.doctors if not self.enabled.get(d, True)]
        for d in disabled_doctors:
            self.doctors.remove(d)
            self.min_shifts.pop(d, None)
            self.preferred_shifts.pop(d, None)
            self.preferred_shifts_weekday.pop(d, None)
            self.preferred_shifts_weekend.pop(d, None)
            self.max_shifts.pop(d, None)
            self.prefer_dense.pop(d, None)
            self.prefer_sparse.pop(d, None)
            self.fixed_shifts = {
                k: v for k, v in self.fixed_shifts.items() if k[0] != d
            }
            self.day_cost = {
                k: v for k, v in self.day_cost.items() if k[0] != d
            }      

    def solve_model( self ) :
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
            prefer_dense = self.prefer_dense,
            prefer_sparse = self.prefer_sparse,
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
        self.solve_result = model.get_solve_result()
        self.schedule_df = model.get_schedule()
        self.find_schedule_problems()

    def find_schedule_problems(self):
        # solver output may break constraints when the model is infeasible - list what's wrong
        self.day_problems = {}  # day index -> [messages]
        self.doctor_problems = []
        df = self.schedule_df.reset_index()
        on_duty = df[(df["x.val"] > 0.5) & (df["index0"] != "Void")]
        self.on_duty = {day: [] for day in self.days}
        for doctor, day in zip(on_duty["index0"], on_duty["index1"]):
            self.on_duty[day].append(doctor)

        def problem(day, message):
            self.day_problems.setdefault(day, []).append(message)

        for day, doctors in self.on_duty.items():
            if not doctors:
                problem(day, "no doctor")
            elif len(doctors) > 1:
                problem(day, f"{len(doctors)} doctors on duty")
            for doctor in doctors:
                if self.fixed_shifts.get((doctor, day)) == "0":
                    problem(day, f"{doctor}: MUST NOT day")

        for (doctor, day), val in self.fixed_shifts.items():
            if val == "1" and doctor in self.doctors and doctor not in self.on_duty[day]:
                problem(day, f"{doctor}: MUST not assigned")

        for doctor in self.doctors[:-1]:
            days = sorted(day for day, doctors in self.on_duty.items() if doctor in doctors)
            for a, b in zip(days, days[1:]):
                manual_pair = self.fixed_shifts.get((doctor, a)) == "1" and self.fixed_shifts.get((doctor, b)) == "1"
                if b - a <= 2 and not manual_pair:
                    problem(b, f"{doctor}: too close to {self.date_labels[a]}")
            if len(days) < self.min_shifts[doctor]:
                self.doctor_problems.append(f"{doctor}: {len(days)} shifts < min {self.min_shifts[doctor]}")
            if len(days) > self.max_shifts[doctor]:
                self.doctor_problems.append(f"{doctor}: {len(days)} shifts > max {self.max_shifts[doctor]}")

    def is_complete(self):
        return self.solve_result == "solved" and not self.day_problems and not self.doctor_problems

    def problem_report(self):
        lines = [f"{self.date_labels[day]}: {'; '.join(msgs)}" for day, msgs in sorted(self.day_problems.items())]
        return lines + self.doctor_problems

    def process_worksheet( self, spreadsheet, worksheet ) :
        self.load_worksheet( spreadsheet, worksheet )
        self.validate_input()
        self.remove_disabled_doctors()
        self.solve_model()

    def export_schedule_to_full_sheet(self):
        # new worksheet name
        print("Doctors: {}".format(self.doctors))
        new_sheet_name = f"{self.worksheet.title}-full-sched"

        # if worksheet exists - remove it
        try:
            existing = self.spreadsheet.worksheet(new_sheet_name)
            self.spreadsheet.del_worksheet(existing)
        except:
            pass

        # create adequately sized worksheet
        num_rows = len(self.date_labels) + 1
        num_cols = len(self.doctors) + 1
        result_sheet = self.spreadsheet.add_worksheet(title=new_sheet_name, rows=str(num_rows), cols=str(num_cols))

        header = ["Date"] + self.doctors
        values = [header]

        self.schedule_df = self.schedule_df.reset_index()
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

        values = [["Date", "On-call"] + (["Problem"] if self.day_problems else [])]

        for i, date in enumerate(self.date_labels):
            doctor = " / ".join(self.on_duty[i]) or "???"
            row = [date, doctor]
            if self.day_problems:
                row.append("; ".join(self.day_problems.get(i, [])))
            values.append(row)

        result_sheet = self.spreadsheet.add_worksheet(title=new_sheet_name, rows=str(len(values)), cols=str(len(values[0])))
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

def process_spreadsheets( client, logging ) :
    # sheet = client.open("Graf Lekarzy").worksheet("Dane")  # Arkusz musi istnieć
    print("Spreadsheets:")
    for ss in client.openall():
        print(f"    {ss.title} – {ss.id}")
        for worksheet in ss.worksheets():
            if worksheet.title.endswith("-sched") : continue
            print(f"        🗂️ Processing sheet: {worksheet.title}")
            processor = Processor()
            processor.set_logging( logging )
            processor.process_worksheet( ss, worksheet )
            processor.export_schedule_to_full_sheet()
            processor.export_schedule_to_short_sheet()

if __name__ == "__main__":
    print("Alive")
    # process_spreadsheets()

