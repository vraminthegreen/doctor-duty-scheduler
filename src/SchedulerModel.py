from amplpy import AMPL

class SchedulerModel:
    def __init__(self):
        self.ampl = AMPL()
        self.ampl.setOption("solver", "highs")
        self._build_model()

    def _build_model(self):
        self.ampl.eval(r"""
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
        param penalty_for_not_preferred_shifts >= 0;
        param day_cost_modifier {DOCTORS, DAYS};
        param fixed_shift {DOCTORS, DAYS} symbolic;
        var x {DOCTORS, DAYS} binary;
        set REST_WINDOW_STARTS within DAYS;
        set WINDOW_STARTS within DAYS;
        
        minimize Total_Cost:
            sum {d in DOCTORS, day in DAYS} day_cost[d, day] * x[d, day]
                + sum {d in DOCTORS} penalty_for_not_preferred_shifts * abs(sum {day in DAYS} x[d, day] - preferred_shifts[d])
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
                
        subject to One_Doctor_Per_Day {day in DAYS}:
            sum {d in DOCTORS} x[d, day] = 1;

        subject to Min_Shifts {d in DOCTORS diff {"Void"}}:
            sum {day in DAYS} x[d, day] >= min_shifts[d];

        subject to Max_Shifts {d in DOCTORS diff {"Void"}}:
            sum {day in DAYS} x[d, day] <= max_shifts[d];

        subject to Min_Rest_Period {d in DOCTORS diff {"Void"}, day in REST_WINDOW_STARTS}:
            x[d, day] + x[d, day + 1] + x[d, day + 2] <= 1;
                       
        subject to Fixed_Shifts_Zero {d in DOCTORS, day in DAYS: fixed_shift[d, day] = "0"}:
            x[d, day] = 0;

        subject to Fixed_Shifts_One {d in DOCTORS, day in DAYS: fixed_shift[d, day] = "1"}:
            x[d, day] = 1;
                
        """)

    def set_data(self, doctors, days, day_cost, min_shifts, max_shifts,
                 preferred_shifts, prefer_dense, prefer_sparse,
                 cost_per_dense_window, cost_per_sparse_window, penalty_for_not_preferred_shifts,
                 fixed_shifts ):
        self.ampl.set['DOCTORS'] = doctors
        self.ampl.set['DAYS'] = days

        self.ampl.set['WINDOW_STARTS'] = list(range(max(days) - 3))
        self.ampl.set['REST_WINDOW_STARTS'] = list(range(max(days) - 1))

        self.ampl.param['day_cost'].setValues(day_cost)
        self.ampl.param['min_shifts'].setValues(min_shifts)
        self.ampl.param['max_shifts'].setValues(max_shifts)
        self.ampl.param['preferred_shifts'].setValues(preferred_shifts)
        self.ampl.param['prefer_dense'].setValues(prefer_dense)
        self.ampl.param['prefer_sparse'].setValues(prefer_sparse)
        self.ampl.param['cost_per_dense_window'] = cost_per_dense_window
        self.ampl.param['cost_per_sparse_window'] = cost_per_sparse_window
        self.ampl.param['penalty_for_not_preferred_shifts'] = penalty_for_not_preferred_shifts
        self.ampl.param['fixed_shift'].setValues(fixed_shifts)

    def solve(self):
        self.ampl.solve()

    def get_schedule(self):
        return self.ampl.getVariable("x").to_pandas()

    def get_total_cost(self):
        return self.ampl.getObjective("Total_Cost").value()