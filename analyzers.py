# # analyzers.py

# import pandas as pd
# import numpy as np

# # # --- Class for "Strict Grid Limits" mode ---
# # class BatteryShavingAnalyzer:
# #     def __init__(self, import_limit_kw, export_limit_kw, time_step_h=0.25):
# #         if import_limit_kw < 0:
# #             raise ValueError("Import limit must be a positive number.")
# #         if export_limit_kw > 0:
# #             raise ValueError("Export limit must be a negative number or zero.")

# #         self.import_limit_kw = import_limit_kw
# #         self.export_limit_kw = export_limit_kw
# #         self.time_step_h = time_step_h

# #     def run_analysis(self, input_df: pd.DataFrame):
# #         df = input_df.copy()
# #         df["net_load"] = df["load"] - df["pv_production"]
# #         df["battery_power"] = 0.0
        
# #         discharge_needed = df["net_load"] > self.import_limit_kw
# #         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

# #         charge_needed = df["net_load"] < self.export_limit_kw
# #         df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

# #         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
# #         df["soc_kwh"] = df["energy_through_battery"].cumsum()

# #         required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min() if not df["soc_kwh"].empty else 0.0
# #         required_power_kw = df["battery_power"].abs().max()

# #         return required_capacity_kwh, required_power_kw, df


# # # --- Class for "Net Peak Shaving" mode ---
# # class NetPeakShavingSizer:
# #     def __init__(self, grid_import_threshold_kw, time_step_h=0.25):
# #         if grid_import_threshold_kw <= 0:
# #             raise ValueError("Grid import threshold must be a positive number.")
# #         self.grid_threshold_kw = grid_import_threshold_kw
# #         self.time_step_h = time_step_h

# #     def run_analysis(self, input_df: pd.DataFrame):
# #         df = input_df.copy()
# #         df["net_load"] = df["load"] - df["pv_production"]
# #         df["battery_power"] = 0.0

# #         discharge_needed = df["net_load"] > self.grid_threshold_kw
# #         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

# #         charge_needed = (df["net_load"] < 0) & (~discharge_needed)
# #         df.loc[charge_needed, "battery_power"] = -df["net_load"]

# #         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
# #         soc_continuous = df["energy_through_battery"].cumsum()
        
# #         df["soc_kwh_daily_reset"] = soc_continuous.groupby(df.index.date).transform(lambda x: x - x.iloc[0])
# #         df["soc_kwh"] = soc_continuous

# #         required_capacity_kwh = df["soc_kwh_daily_reset"].max() - df["soc_kwh_daily_reset"].min()
# #         required_power_kw = df["battery_power"].abs().max()
# #         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

# #         return required_capacity_kwh, required_power_kw, df
# class NetPeakShavingSizer:
#     def __init__(self, grid_import_threshold_kw, time_step_h=0.25):
#         if grid_import_threshold_kw <= 0:
#             raise ValueError("Grid import threshold must be a positive number.")
#         self.grid_threshold_kw = grid_import_threshold_kw
#         self.time_step_h = time_step_h

#     def run_analysis(self, input_df: pd.DataFrame):
#         df = input_df.copy()
#         df["net_load"] = df["load"] - df["pv_production"]
#         df["battery_power"] = 0.0

#         # Battery discharge: limit grid import to threshold
#         discharge_needed = df["net_load"] > self.grid_threshold_kw
#         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

#         # Battery charging: absorb excess PV (optional logic)
#         charge_needed = (df["net_load"] < 0) & (~discharge_needed)
#         df.loc[charge_needed, "battery_power"] = -df["net_load"]

#         # Energy flow through battery
#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h

#         # --- NEW LOGIC ---
#         # For each continuous discharge period, calculate required energy
#         required_capacity_kwh = 0
#         running_energy = 0
#         for e in df["energy_through_battery"]:
#             if e < 0:  # discharging
#                 running_energy += -e   # add positive kWh
#                 required_capacity_kwh = max(required_capacity_kwh, running_energy)
#             else:  # not discharging → reset counter
#                 running_energy = 0

#         # Required power is still max discharge power
#         required_power_kw = df["battery_power"].abs().max()

#         # Grid import after battery
#         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

#         return required_capacity_kwh, required_power_kw, df



# analyzers.py

import pandas as pd
import numpy as np

class BatteryShavingAnalyzer:
    """
    STRICT GRID LIMITS MODEL
    Calculates battery size to never exceed fixed import/export limits.
    Capacity is sized based on the single largest continuous discharge event.
    """
    def __init__(self, import_limit_kw, export_limit_kw, time_step_h=0.25):
        self.import_limit_kw = import_limit_kw
        self.export_limit_kw = export_limit_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        df = input_df.copy()
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0
        
        discharge_needed = df["net_load"] > self.import_limit_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

        charge_needed = df["net_load"] < self.export_limit_kw
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        
        # --- CAPACITY CALCULATION (NEW LOGIC) ---
        # Step A: Identify all moments of discharging.
        is_discharging = df['battery_power'] < 0

        # Step B: Assign a unique ID to each continuous block of discharging.
        # The counter increases every time the status changes from charging/idle to discharging or vice-versa.
        discharge_event_id = (is_discharging != is_discharging.shift()).cumsum()
        
        # Step C: Calculate the total energy for each continuous discharge event.
        # We group by the event ID and sum the energy. We only care about discharge events.
        discharge_streaks_kwh = df['energy_through_battery'].groupby(discharge_event_id[is_discharging]).sum()

        # Step D: The required capacity is the absolute largest of these event totals.
        # If there are no discharge events, the capacity is 0.
        required_capacity_kwh = discharge_streaks_kwh.abs().max() if not discharge_streaks_kwh.empty else 0.0

        # The power requirement is still the single highest power spike.
        required_power_kw = df["battery_power"].abs().max()

        return required_capacity_kwh, required_power_kw, df


class NetPeakShavingSizer:
    """
    NET PEAK SHAVING MODEL
    Calculates battery size to cap grid import below a target threshold.
    Capacity is sized based on the single largest continuous discharge event.
    """
    def __init__(self, grid_import_threshold_kw, time_step_h=0.25):
        self.grid_threshold_kw = grid_import_threshold_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        df = input_df.copy()
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0

        discharge_needed = df["net_load"] > self.grid_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

        charge_needed = (df["net_load"] < 0) & (~discharge_needed)
        df.loc[charge_needed, "battery_power"] = -df["net_load"]

        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        
        # --- CAPACITY CALCULATION (NEW LOGIC) ---
        # Step A: Identify all moments of discharging.
        is_discharging = df['battery_power'] < 0

        # Step B: Assign a unique ID to each continuous block of discharging.
        discharge_event_id = (is_discharging != is_discharging.shift()).cumsum()
        
        # Step C: Calculate the total energy for each continuous discharge event.
        discharge_streaks_kwh = df['energy_through_battery'].groupby(discharge_event_id[is_discharging]).sum()

        # Step D: The required capacity is the absolute largest of these event totals.
        required_capacity_kwh = discharge_streaks_kwh.abs().max() if not discharge_streaks_kwh.empty else 0.0

        # The power requirement is still the single highest power spike.
        required_power_kw = df["battery_power"].abs().max()
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

        return required_capacity_kwh, required_power_kw, df
