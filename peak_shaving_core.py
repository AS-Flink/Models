import pandas as pd
import numpy as np

class PeakShavingAnalyzer:
    """
    An analyzer to determine battery size for a percentile-based peak shaving strategy.
    V2: Includes a daily SOC reset to prevent seasonal charge accumulation.
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
        df = input_df.copy()

        peak_threshold_kw = df["load"].quantile(self.peak_percentile / 100.0)
        print(f"Calculated Peak Shaving Threshold: {peak_threshold_kw:.2f} kW (shaving loads above this)")

        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0

        discharge_needed = df["load"] > peak_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["load"] - peak_threshold_kw)

        charge_needed = (df["net_load"] < self.export_limit_kw) & (~discharge_needed)
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        
        # --- LOGIC CORRECTION STARTS HERE ---

        # 1. First, calculate the continuous SOC as before
        df["soc_kwh_continuous"] = df["energy_through_battery"].cumsum()

        # 2. THEN, create a daily-reset SOC for a realistic capacity calculation
        # This prevents the bug of accumulating charge over seasons.
        # It calculates the SOC swing within each day, relative to the start of that day.
        df["soc_kwh_daily_reset"] = df.groupby(df.index.date)['soc_kwh_continuous'].transform(lambda x: x - x.iloc[0])

        # We will keep the continuous SOC for plotting, but use the daily for sizing.
        df.rename(columns={'soc_kwh_continuous': 'soc_kwh'}, inplace=True)

        # 3. Determine required size using the daily-reset SOC
        if not df["soc_kwh_daily_reset"].empty:
            # The required capacity is the largest single-day swing needed
            required_capacity_kwh = df["soc_kwh_daily_reset"].max() - df["soc_kwh_daily_reset"].min()
        else:
            required_capacity_kwh = 0.0
        
        # --- LOGIC CORRECTION ENDS HERE ---

        required_power_kw = df["battery_power"].abs().max()

        return required_capacity_kwh, required_power_kw, df
