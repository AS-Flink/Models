# battery_shaving_core.py
import pandas as pd
import numpy as np

class BatteryShavingAnalyzer:
    """
    A refactored class to perform peak shaving analysis.
    It now accepts a DataFrame and returns a results DataFrame,
    making it suitable for use in a web app like Streamlit.
    """
    def __init__(self, import_limit_kw, export_limit_kw, time_step_h=0.25):
        if import_limit_kw < 0:
            raise ValueError("Import limit must be a positive number.")
        if export_limit_kw > 0:
            raise ValueError("Export limit must be a negative number or zero.")

        self.import_limit_kw = import_limit_kw
        self.export_limit_kw = export_limit_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        """
        Analyzes the provided DataFrame to determine the required battery size
        for peak shaving.

        Args:
            input_df (pd.DataFrame): Must contain 'load' and 'pv_production' columns.
                                     The index should be datetime objects.

        Returns:
            tuple: A tuple containing:
                - required_capacity_kwh (float)
                - required_power_kw (float)
                - results_df (pd.DataFrame) with detailed calculations
        """
        df = input_df.copy()

        # 1. Calculate Net Load (Grid exchange without battery)
        df["net_load"] = df["load"] - df["pv_production"]

        # 2. Determine Battery Power needed for shaving
        # Positive battery_power = charging, Negative = discharging
        df["battery_power"] = 0.0

        # Condition for discharging: Net load is above the import limit
        discharge_needed = df["net_load"] > self.import_limit_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

        # Condition for charging: Net load is below the export limit (more negative)
        charge_needed = df["net_load"] < self.export_limit_kw
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

        # 3. Calculate Energy and State of Charge (SOC)
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        df["soc_kwh"] = df["energy_through_battery"].cumsum()

        # 4. Determine required size from the analysis
        if not df["soc_kwh"].empty:
            required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min()
        else:
            required_capacity_kwh = 0.0

        required_power_kw = df["battery_power"].abs().max()

        return required_capacity_kwh, required_power_kw, df
