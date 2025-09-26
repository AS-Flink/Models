import pandas as pd
import numpy as np

class NetPeakShavingSizer:
    """
    Calculates the minimum battery size for a NET peak shaving application.
    It ensures the power drawn FROM THE GRID (net load) stays below a threshold.
    This model operates on a daily cycle.
    """
    def __init__(self, grid_import_threshold_kw, time_step_h=0.25):
        """
        Initializes the sizer with a clear grid import target.

        Args:
            grid_import_threshold_kw (float): The target power level (in kW).
                Any net load from the grid above this will be shaved by the battery.
            time_step_h (float): The time resolution of the data in hours (e.g., 0.25 for 15-min).
        """
        if grid_import_threshold_kw <= 0:
            raise ValueError("Grid import threshold must be a positive number.")
        self.grid_threshold_kw = grid_import_threshold_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        """
        Analyzes the load data and returns the required battery size.
        """
        df = input_df.copy()

        # Step 1: Calculate Net Load (the power exchange with the grid before the battery)
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0

        # Step 2: Determine Battery Power (Discharging & Charging)
        # --- CORRECTED DISCHARGING LOGIC ---
        # Discharging is triggered when the NET LOAD (grid import) exceeds the threshold.
        discharge_needed = df["net_load"] > self.grid_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_threshold_kw)

        # Charging is triggered by surplus solar power (negative net load).
        charge_needed = (df["net_load"] < 0) & (~discharge_needed)
        df.loc[charge_needed, "battery_power"] = -df["net_load"]

        # Step 3: Calculate Energy Flow and Daily SOC
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        soc_continuous = df["energy_through_battery"].cumsum()
        
        # This calculates the SOC swing within each day to size for daily cycles.
        df["soc_kwh_daily_reset"] = soc_continuous.groupby(df.index.date).transform(lambda x: x - x.iloc[0])
        df["soc_kwh"] = soc_continuous # Keep for plotting

        # Step 4: Determine Minimum Required Battery Size
        # Capacity is the largest single-day energy swing needed.
        required_capacity_kwh = df["soc_kwh_daily_reset"].max() - df["soc_kwh_daily_reset"].min()

        # Power is the single largest discharge event needed.
        required_power_kw = df["battery_power"].abs().max()

        # Bonus: Calculate what the grid sees AFTER the battery is installed
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

        return required_capacity_kwh, required_power_kw, df
