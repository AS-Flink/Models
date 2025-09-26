# peak_shaving_core.py
import pandas as pd
import numpy as np

class PeakShavingAnalyzer:
    """
    An analyzer to determine battery size for a percentile-based peak shaving strategy.
    """
    def __init__(self, peak_percentile, export_limit_kw, time_step_h=0.25):
        if not 0 < peak_percentile < 100:
            raise ValueError("peak_percentile must be between 0 and 100.")
        if export_limit_kw > 0:
            raise ValueError("Export limit must be a negative number or zero.")

        self.peak_percentile = peak_percentile
        self.export_limit_kw = export_limit_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        """
        Analyzes the DataFrame to size a battery for shaving the top load peaks.
        """
        df = input_df.copy()

        # 1. Calculate the dynamic peak threshold based on the percentile
        # This is the core change for a true peak shaving model
        peak_threshold_kw = df["load"].quantile(self.peak_percentile / 100.0)
        print(f"Calculated Peak Shaving Threshold: {peak_threshold_kw:.2f} kW (shaving loads above this)")

        # 2. Calculate Net Load (still needed for charging logic)
        df["net_load"] = df["load"] - df["pv_production"]
        
        # 3. Determine Battery Power
        df["battery_power"] = 0.0

        # --- DISCHARGING LOGIC (CHANGED) ---
        # Discharge when the building's load exceeds the dynamic peak threshold
        discharge_needed = df["load"] > peak_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["load"] - peak_threshold_kw)

        # --- CHARGING LOGIC (REMAINS SIMILAR) ---
        # Charge when there is excess solar power to export
        # We only charge where the battery is not already busy discharging
        charge_needed = (df["net_load"] < self.export_limit_kw) & (~discharge_needed)
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

        # 4. Calculate Energy and State of Charge (SOC)
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        df["soc_kwh"] = df["energy_through_battery"].cumsum()

        # 5. Determine required size
        if not df["soc_kwh"].empty:
            required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min()
        else:
            required_capacity_kwh = 0.0

        required_power_kw = df["battery_power"].abs().max()

        return required_capacity_kwh, required_power_kw, df
