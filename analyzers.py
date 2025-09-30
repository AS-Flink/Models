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

# import pandas as pd

# class NetPeakShavingSizer:
#     """
#     Calculates the minimum battery size for a NET peak shaving application.
#     It ensures the power drawn FROM THE GRID (net load) stays below a threshold.
#     Capacity is sized based on the single largest continuous discharge event.
#     """
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
#         df['battery_soc_kwh'] = df['energy_through_battery'].cumsum()

#         is_discharging = df['battery_power'] < 0
#         discharge_event_id = (is_discharging != is_discharging.shift()).cumsum()
#         discharge_streaks_kwh = df['energy_through_battery'].groupby(discharge_event_id[is_discharging]).sum()
        
#         required_capacity_kwh = discharge_streaks_kwh.abs().max() if not discharge_streaks_kwh.empty else 0.0
#         required_power_kw = df["battery_power"].abs().max()
#         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

#         return required_capacity_kwh, required_power_kw, df

import pandas as pd

class NetPeakShavingSizer:
    """
    Calculates the minimum battery size to keep grid exchange within set import and export thresholds.
    Capacity is now sized based on the maximum energy range required (SOC max - SOC min).
    """
    def __init__(self, grid_import_threshold_kw, grid_export_threshold_kw=0, time_step_h=0.25):
        if grid_import_threshold_kw <= 0:
            raise ValueError("Grid import threshold must be a positive number.")
        if grid_export_threshold_kw > 0:
            raise ValueError("Grid export threshold must be zero or a negative number.")
            
        self.grid_import_threshold_kw = grid_import_threshold_kw
        # By convention, export is negative power. 0 means no export allowed.
        self.grid_export_threshold_kw = grid_export_threshold_kw
        self.time_step_h = time_step_h

    # def run_analysis(self, input_df: pd.DataFrame):
    #     df = input_df.copy()
    #     df["net_load"] = df["load"] - df["pv_production"]
    #     df["battery_power"] = 0.0

    #     # --- REVISED DISPATCH LOGIC ---
        
    #     # 1. Discharge when net_load is ABOVE the import threshold
    #     discharge_needed = df["net_load"] > self.grid_import_threshold_kw
    #     df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_import_threshold_kw)

    #     # 2. Charge ONLY when net_load is BELOW the export threshold
    #     # This prevents the battery from charging with all excess PV.
    #     charge_needed = df["net_load"] < self.grid_export_threshold_kw
    #     df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.grid_export_threshold_kw)

    #     # --- REVISED SIZING LOGIC ---
        
    #     df["energy_through_battery"] = df["battery_power"] * self.time_step_h
    #     df['battery_soc_kwh'] = df['energy_through_battery'].cumsum()

    #     # The required capacity is the difference between the highest and lowest
    #     # points of the SOC curve. This is the true "size" of the energy tank we need.
    #     # We add a small buffer (1e-9) to handle cases with no battery usage.
    #     required_capacity_kwh = df['battery_soc_kwh'].max() - df['battery_soc_kwh'].min() + 1e-9
        
    #     # Required power is still the max absolute power in or out
    #     required_power_kw = df["battery_power"].abs().max()
        
    #     df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

    #     return required_capacity_kwh, required_power_kw, df
def run_analysis(self, input_df: pd.DataFrame):
    df = input_df.copy()
    df["net_load"] = df["load"] - df["pv_production"]
    df["battery_power"] = 0.0

    # Dispatch logic remains the same
    discharge_needed = df["net_load"] > self.grid_import_threshold_kw
    df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_import_threshold_kw)

    charge_needed = df["net_load"] < self.grid_export_threshold_kw
    df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.grid_export_threshold_kw)

    df["energy_through_battery"] = df["battery_power"] * self.time_step_h

    # --- ROLLING WINDOW SIZING LOGIC ---

    # 1. Calculate the true, continuous SOC for the entire period.
    df['battery_soc_kwh_cumulative'] = df['energy_through_battery'].cumsum()

    # 2. Define the window. '24H' is standard for daily cycles. You could use '48H'
    #    to be more conservative and account for challenging multi-day events.
    window = '24H'

    # 3. Calculate the SOC swing (max - min) within each rolling window.
    #    This requires a DatetimeIndex, which you already have.
    rolling_soc_swing = (
        df['battery_soc_kwh_cumulative'].rolling(window).max() -
        df['battery_soc_kwh_cumulative'].rolling(window).min()
    )

    # 4. The required capacity is the maximum swing found across all windows.
    #    We add a small buffer for floating point precision.
    required_capacity_kwh = rolling_soc_swing.max() + 1e-9

    # Required power is still the max absolute power in or out
    required_power_kw = df["battery_power"].abs().max()

    df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

    return required_capacity_kwh, required_power_kw, df








class EconomicDispatchSizer:
    """
    Calculates the minimum battery size for a PRICE ARBITRAGE application.
    It charges the battery from excess solar when prices are low and
    discharges to serve the load when prices are high.
    """
    def __init__(self, high_price_threshold, low_price_threshold, time_step_h=0.25):
        if high_price_threshold <= low_price_threshold:
            raise ValueError("High price threshold must be greater than low price threshold.")
        self.high_price = high_price_threshold
        self.low_price = low_price_threshold
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        if 'price' not in input_df.columns:
            raise ValueError("Input DataFrame must contain a 'price' column for economic dispatch.")
            
        df = input_df.copy()
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0

        # --- NEW ECONOMIC DISPATCH LOGIC ---

        # 1. Discharge to serve the load when prices are HIGH
        # We only discharge if there is a load to serve (net_load > 0)
        discharge_needed = (df["price"] > self.high_price) & (df["net_load"] > 0)
        df.loc[discharge_needed, "battery_power"] = -df["net_load"]

        # 2. Charge from excess solar when prices are LOW
        # We only charge if there is excess PV (net_load < 0)
        charge_needed = (df["price"] < self.low_price) & (df["net_load"] < 0)
        df.loc[charge_needed, "battery_power"] = -df["net_load"]

        # --- Sizing logic is the same "daily cycle" as before ---
        
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        df['battery_soc_kwh'] = df.groupby(df.index.date)['energy_through_battery'].cumsum()

        daily_soc_range = df.groupby(df.index.date)['battery_soc_kwh'].agg(['max', 'min'])
        daily_kwh_swing = daily_soc_range['max'] - daily_soc_range['min']

        required_capacity_kwh = daily_kwh_swing.max()
        required_power_kw = df["battery_power"].abs().max()
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

        return required_capacity_kwh, required_power_kw, df

