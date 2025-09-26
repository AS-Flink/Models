# analyzers.py

import pandas as pd
import numpy as np

# # --- Class for "Strict Grid Limits" mode ---
# class BatteryShavingAnalyzer:
#     def __init__(self, import_limit_kw, export_limit_kw, time_step_h=0.25):
#         if import_limit_kw < 0:
#             raise ValueError("Import limit must be a positive number.")
#         if export_limit_kw > 0:
#             raise ValueError("Export limit must be a negative number or zero.")

#         self.import_limit_kw = import_limit_kw
#         self.export_limit_kw = export_limit_kw
#         self.time_step_h = time_step_h

#     def run_analysis(self, input_df: pd.DataFrame):
#         df = input_df.copy()
#         df["net_load"] = df["load"] - df["pv_production"]
#         df["battery_power"] = 0.0
        
#         discharge_needed = df["net_load"] > self.import_limit_kw
#         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

#         charge_needed = df["net_load"] < self.export_limit_kw
#         df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
#         df["soc_kwh"] = df["energy_through_battery"].cumsum()

#         required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min() if not df["soc_kwh"].empty else 0.0
#         required_power_kw = df["battery_power"].abs().max()

#         return required_capacity_kwh, required_power_kw, df

import pandas as pd

class BatteryShavingAnalyzer:
    """
    Battery sizing tool for strict grid import/export limits.

    Parameters
    ----------
    import_limit_kw : float
        Maximum grid import allowed (kW).
    export_limit_kw : float
        Minimum grid export allowed (kW), must be <= 0.
    time_step_h : float
        Time resolution of input data (hours per step), e.g., 0.25 for 15 min.
    """

    def __init__(self, import_limit_kw: float, export_limit_kw: float, time_step_h: float = 0.25):
        if import_limit_kw <= 0:
            raise ValueError("Import limit must be a positive number.")
        if export_limit_kw > 0:
            raise ValueError("Export limit must be zero or negative (since export = negative net load).")

        self.import_limit_kw = import_limit_kw
        self.export_limit_kw = export_limit_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        """
        Run the grid peak shaving analysis.

        Parameters
        ----------
        input_df : pd.DataFrame
            Must contain 'load' (kW) and 'pv_production' (kW) columns.

        Returns
        -------
        required_capacity_kwh : float
            Minimum battery energy capacity required (kWh).
        required_power_kw : float
            Minimum battery power rating required (kW).
        df : pd.DataFrame
            Input dataframe with added columns for analysis.
        """

        df = input_df.copy()

        # Net load = demand - PV
        # Positive -> grid import, Negative -> grid export
        df["net_load"] = df["load"] - df["pv_production"]

        # Initialize battery dispatch
        df["battery_power"] = 0.0

        # Case 1: Net load exceeds import limit (too much grid import) → discharge battery
        discharge_needed = df["net_load"] > self.import_limit_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

        # Case 2: Net load below export limit (too much grid export) → charge battery
        charge_needed = df["net_load"] < self.export_limit_kw
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

        # Energy through battery per step (kWh)
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h

        # State of charge (SOC) tracking (continuous, not reset daily)
        df["soc_kwh"] = df["energy_through_battery"].cumsum()

        # Required battery sizing
        required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min() if not df.empty else 0.0
        required_power_kw = df["battery_power"].abs().max()

        # Net grid import/export after battery
        df["grid_with_battery"] = df["net_load"] + df["battery_power"]

        return required_capacity_kwh, required_power_kw, df

# # --- Class for "Net Peak Shaving" mode ---
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

#         discharge_needed = df["net_load"] > self.grid_threshold_kw
#         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

#         charge_needed = (df["net_load"] < 0) & (~discharge_needed)
#         df.loc[charge_needed, "battery_power"] = -df["net_load"]

#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
#         soc_continuous = df["energy_through_battery"].cumsum()
        
#         df["soc_kwh_daily_reset"] = soc_continuous.groupby(df.index.date).transform(lambda x: x - x.iloc[0])
#         df["soc_kwh"] = soc_continuous

#         required_capacity_kwh = df["soc_kwh_daily_reset"].max() - df["soc_kwh_daily_reset"].min()
#         required_power_kw = df["battery_power"].abs().max()
#         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

#         return required_capacity_kwh, required_power_kw, df
class NetPeakShavingSizer:
    def __init__(self, grid_import_threshold_kw, time_step_h=0.25):
        if grid_import_threshold_kw <= 0:
            raise ValueError("Grid import threshold must be a positive number.")
        self.grid_threshold_kw = grid_import_threshold_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        df = input_df.copy()
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0

        # Battery discharge: limit grid import to threshold
        discharge_needed = df["net_load"] > self.grid_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

        # Battery charging: absorb excess PV (optional logic)
        charge_needed = (df["net_load"] < 0) & (~discharge_needed)
        df.loc[charge_needed, "battery_power"] = -df["net_load"]

        # Energy flow through battery
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h

        # --- NEW LOGIC ---
        # For each continuous discharge period, calculate required energy
        required_capacity_kwh = 0
        running_energy = 0
        for e in df["energy_through_battery"]:
            if e < 0:  # discharging
                running_energy += -e   # add positive kWh
                required_capacity_kwh = max(required_capacity_kwh, running_energy)
            else:  # not discharging → reset counter
                running_energy = 0

        # Required power is still max discharge power
        required_power_kw = df["battery_power"].abs().max()

        # Grid import after battery
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

        return required_capacity_kwh, required_power_kw, df

