# # analyzers.py

# import pandas as pd

# class NetPeakShavingSizer:
#     """
#     Calculates battery size to stay within grid limits using selectable sizing methods.
    
#     This unified class can operate in two modes:
#     1. 'worst_day': Sizes the battery for the most challenging 24-hour period (a practical estimate).
#     2. 'guaranteed': Sizes the battery for the entire year's energy range (for 100% violation avoidance).
#     """

#     def __init__(self, grid_import_threshold_kw, grid_export_threshold_kw=0, time_step_h=0.25):
#         """
#         Initializes the sizer with grid limits and data timestep.

#         Args:
#             grid_import_threshold_kw (float): The maximum power (kW) allowed to be imported from the grid. Must be positive.
#             grid_export_threshold_kw (float, optional): The maximum power (kW) allowed to be exported. Must be zero or negative. Defaults to 0.
#             time_step_h (float, optional): The duration of each time step in hours. Defaults to 0.25 (15 minutes).
#         """
#         if grid_import_threshold_kw <= 0:
#             raise ValueError("Grid import threshold must be a positive number.")
#         if grid_export_threshold_kw > 0:
#             raise ValueError("Grid export threshold must be zero or a negative number.")
            
#         self.grid_import_threshold_kw = grid_import_threshold_kw
#         self.grid_export_threshold_kw = grid_export_threshold_kw
#         self.time_step_h = time_step_h

#     def run_analysis(self, input_df: pd.DataFrame, sizing_mode: str = 'worst_day', window: str = '24H'):
#         """
#         Runs the sizing analysis using the selected method.

#         Args:
#             input_df (pd.DataFrame): DataFrame with a DatetimeIndex and columns for 'load' and 'pv_production'.
#             sizing_mode (str, optional): The sizing method to use. Can be 'worst_day' or 'guaranteed'. Defaults to 'worst_day'.
#             window (str, optional): The rolling window duration for the 'worst_day' method. Defaults to '24H'.

#         Returns:
#             tuple: A tuple containing required_capacity_kwh, required_power_kw, and the detailed output DataFrame.
#         """
#         df = input_df.copy()

#         # --- Part 1: Common Calculations (Dispatch and SOC) ---
#         df["net_load"] = df["load"] - df["pv_production"]
#         df["battery_power"] = 0.0

#         discharge_needed = df["net_load"] > self.grid_import_threshold_kw
#         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_import_threshold_kw)

#         charge_needed = df["net_load"] < self.grid_export_threshold_kw
#         df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.grid_export_threshold_kw)

#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
#         df['battery_soc_kwh_cumulative'] = df['energy_through_battery'].cumsum()

#         # --- Part 2: Conditional Sizing Logic (The "Knobs") ---
#         if sizing_mode == 'worst_day':
#             # Sizes based on the max energy swing in any continuous window (e.g., 24H)
#             rolling_soc_swing = (
#                 df['battery_soc_kwh_cumulative'].rolling(window, min_periods=1).max() -
#                 df['battery_soc_kwh_cumulative'].rolling(window, min_periods=1).min()
#             )
#             required_capacity_kwh = rolling_soc_swing.max()
        
#         elif sizing_mode == 'guaranteed':
#             # Sizes based on the total range of the SOC over the entire year
#             required_capacity_kwh = (
#                 df['battery_soc_kwh_cumulative'].max() - 
#                 df['battery_soc_kwh_cumulative'].min()
#             )
#         else:
#             raise ValueError("Invalid sizing_mode. Choose either 'worst_day' or 'guaranteed'.")

#         # --- Part 3: Final Calculations ---
#         required_power_kw = df["battery_power"].abs().max()
#         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

#         return required_capacity_kwh, required_power_kw, df

# class EconomicDispatchSizer:
#     """
#     Calculates the minimum battery size for a PRICE ARBITRAGE application.
#     It charges the battery from excess solar when prices are low and
#     discharges to serve the load when prices are high.
#     """
#     def __init__(self, high_price_threshold, low_price_threshold, time_step_h=0.25):
#         if high_price_threshold <= low_price_threshold:
#             raise ValueError("High price threshold must be greater than low price threshold.")
#         self.high_price = high_price_threshold
#         self.low_price = low_price_threshold
#         self.time_step_h = time_step_h

#     def run_analysis(self, input_df: pd.DataFrame):
#         if 'price' not in input_df.columns:
#             raise ValueError("Input DataFrame must contain a 'price' column for economic dispatch.")
            
#         df = input_df.copy()
#         df["net_load"] = df["load"] - df["pv_production"]
#         df["battery_power"] = 0.0

#         # --- NEW ECONOMIC DISPATCH LOGIC ---

#         # 1. Discharge to serve the load when prices are HIGH
#         # We only discharge if there is a load to serve (net_load > 0)
#         discharge_needed = (df["price"] > self.high_price) & (df["net_load"] > 0)
#         df.loc[discharge_needed, "battery_power"] = -df["net_load"]

#         # 2. Charge from excess solar when prices are LOW
#         # We only charge if there is excess PV (net_load < 0)
#         charge_needed = (df["price"] < self.low_price) & (df["net_load"] < 0)
#         df.loc[charge_needed, "battery_power"] = -df["net_load"]

#         # --- Sizing logic is the same "daily cycle" as before ---
        
#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
#         df['battery_soc_kwh'] = df.groupby(df.index.date)['energy_through_battery'].cumsum()

#         daily_soc_range = df.groupby(df.index.date)['battery_soc_kwh'].agg(['max', 'min'])
#         daily_kwh_swing = daily_soc_range['max'] - daily_soc_range['min']

#         required_capacity_kwh = daily_kwh_swing.max()
#         required_power_kw = df["battery_power"].abs().max()
#         df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

#         return required_capacity_kwh, required_power_kw, df

import pandas as pd

class NetPeakShavingSizer:
    """
    Calculates battery size to stay within grid limits using selectable sizing methods.
    
    This unified class can operate in two modes:
    1. 'worst_day': Sizes the battery for the most challenging 24-hour period (a practical estimate).
    2. 'guaranteed': Sizes the battery for the entire year's energy range (for 100% violation avoidance).
    """
    def __init__(self, grid_import_threshold_kw, grid_export_threshold_kw=0, time_step_h=0.25):
        if grid_import_threshold_kw <= 0:
            raise ValueError("Grid import threshold must be a positive number.")
        if grid_export_threshold_kw > 0:
            raise ValueError("Grid export threshold must be zero or a negative number.")
            
        self.grid_import_threshold_kw = grid_import_threshold_kw
        self.grid_export_threshold_kw = grid_export_threshold_kw
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame, sizing_mode: str = 'worst_day', window: str = '24H'):
        df = input_df.copy()

        # Part 1: Dispatch Logic
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0
        discharge_needed = df["net_load"] > self.grid_import_threshold_kw
        df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.grid_import_threshold_kw)
        charge_needed = df["net_load"] < self.grid_export_threshold_kw
        df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.grid_export_threshold_kw)

        # Part 2: Sizing Logic
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        df['battery_soc_kwh_cumulative'] = df['energy_through_battery'].cumsum()

        if sizing_mode == 'worst_day':
            rolling_soc_swing = (
                df['battery_soc_kwh_cumulative'].rolling(window, min_periods=1).max() -
                df['battery_soc_kwh_cumulative'].rolling(window, min_periods=1).min()
            )
            required_capacity_kwh = rolling_soc_swing.max()
        elif sizing_mode == 'guaranteed':
            required_capacity_kwh = (
                df['battery_soc_kwh_cumulative'].max() - 
                df['battery_soc_kwh_cumulative'].min()
            )
        else:
            raise ValueError("Invalid sizing_mode. Choose either 'worst_day' or 'guaranteed'.")

        # Part 3: Final Calculations
        required_power_kw = df["battery_power"].abs().max()
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']

        return required_capacity_kwh, required_power_kw, df

# --- NEW PV SELF-CONSUMPTION SIZER ---

class SelfConsumptionSizer:
    """
    Calculates battery size to maximize PV self-consumption.
    
    Capacity is sized based on a percentile of the daily solar surplus energy.
    Power is sized based on the maximum load when PV is not available.
    """
    def __init__(self, percentile: float = 0.90, time_step_h: float = 0.25):
        if not 0 < percentile <= 1:
            raise ValueError("Percentile must be between 0 and 1.")
        self.percentile = percentile
        self.time_step_h = time_step_h

    def run_analysis(self, input_df: pd.DataFrame):
        df = input_df.copy()

        # 1. Determine Ideal Dispatch for 100% Self-Consumption
        df["net_load"] = df["load"] - df["pv_production"]
        df["battery_power"] = 0.0
        
        # Discharge whenever PV is insufficient for the load
        discharge_needed = df["net_load"] > 0
        df.loc[discharge_needed, "battery_power"] = -df["net_load"]

        # Charge with any and all excess PV
        charge_needed = df["net_load"] < 0
        df.loc[charge_needed, "battery_power"] = -df["net_load"]

        # 2. Size the Battery
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h

        # Required Power (kW): The maximum discharge required (typically the evening peak load)
        required_power_kw = df.loc[df['battery_power'] < 0, 'battery_power'].abs().max()

        # Required Capacity (kWh): Sized on a percentile of daily solar surplus
        charging_energy = df.loc[df['energy_through_battery'] > 0, 'energy_through_battery']
        daily_surplus_kwh = charging_energy.groupby(charging_energy.index.date).sum()
        
        # Calculate the capacity based on the specified percentile to avoid oversizing
        required_capacity_kwh = daily_surplus_kwh.quantile(self.percentile)

        # 3. Final Calculations for Charting
        df['grid_import_with_battery'] = df['net_load'] + df['battery_power']
        # Use a daily reset for the SOC chart, as it's more intuitive for this mode
        df['battery_soc_kwh_cumulative'] = df.groupby(df.index.date)['energy_through_battery'].cumsum()

        return required_capacity_kwh, required_power_kw, df
