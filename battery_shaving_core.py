# # battery_shaving_core.py
# import pandas as pd
# import numpy as np

# class BatteryShavingAnalyzer:
#     """
#     A refactored class to perform peak shaving analysis.
#     It now accepts a DataFrame and returns a results DataFrame,
#     making it suitable for use in a web app like Streamlit.
#     """
#     def __init__(self, import_limit_kw, export_limit_kw, time_step_h=0.25):
#         if import_limit_kw < 0:
#             raise ValueError("Import limit must be a positive number.")
#         if export_limit_kw > 0:
#             raise ValueError("Export limit must be a negative number or zero.")

#         self.import_limit_kw = import_limit_kw
#         self.export_limit_kw = export_limit_kw
#         self.time_step_h = time_step_h

#     def run_analysis(self, input_df: pd.DataFrame):
#         """
#         Analyzes the provided DataFrame to determine the required battery size
#         for peak shaving.

#         Args:
#             input_df (pd.DataFrame): Must contain 'load' and 'pv_production' columns.
#                                      The index should be datetime objects.

#         Returns:
#             tuple: A tuple containing:
#                 - required_capacity_kwh (float)
#                 - required_power_kw (float)
#                 - results_df (pd.DataFrame) with detailed calculations
#         """
#         df = input_df.copy()

#         # 1. Calculate Net Load (Grid exchange without battery)
#         df["net_load"] = df["load"] - df["pv_production"]

#         # 2. Determine Battery Power needed for shaving
#         # Positive battery_power = charging, Negative = discharging
#         df["battery_power"] = 0.0

#         # Condition for discharging: Net load is above the import limit
#         discharge_needed = df["net_load"] > self.import_limit_kw
#         df.loc[discharge_needed, "battery_power"] = -(df["net_load"] - self.import_limit_kw)

#         # Condition for charging: Net load is below the export limit (more negative)
#         charge_needed = df["net_load"] < self.export_limit_kw
#         df.loc[charge_needed, "battery_power"] = -(df["net_load"] - self.export_limit_kw)

#         # 3. Calculate Energy and State of Charge (SOC)
#         df["energy_through_battery"] = df["battery_power"] * self.time_step_h
#         df["soc_kwh"] = df["energy_through_battery"].cumsum()

#         # 4. Determine required size from the analysis
#         if not df["soc_kwh"].empty:
#             required_capacity_kwh = df["soc_kwh"].max() - df["soc_kwh"].min()
#         else:
#             required_capacity_kwh = 0.0

#         required_power_kw = df["battery_power"].abs().max()

#         return required_capacity_kwh, required_power_kw, df


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

    def run_analysis(self, input_df: pd.DataFrame, max_battery_capacity_kwh=None):
        """
        Analyzes the provided DataFrame to determine the required battery size
        for peak shaving.

        Args:
            input_df (pd.DataFrame): Must contain 'load' and 'pv_production' columns.
                                     The index should be datetime objects.
            max_battery_capacity_kwh (float): Optional maximum battery capacity for 
                                            constrained analysis. If None, calculates
                                            minimum theoretical requirement.

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

        # 3. Calculate Energy and State of Charge (SOC) - CORRECTED APPROACH
        df["energy_through_battery"] = df["battery_power"] * self.time_step_h
        
        # NEW: Realistic SOC tracking (iterative approach)
        soc_history = []
        current_soc = 0.0
        
        for energy_flow in df["energy_through_battery"]:
            # Update SOC based on energy flow
            current_soc += energy_flow
            
            # If we're constraining the battery size, apply limits
            if max_battery_capacity_kwh is not None:
                current_soc = max(0, min(current_soc, max_battery_capacity_kwh))
            
            soc_history.append(current_soc)
        
        df["soc_kwh"] = soc_history

        # 4. Determine required size from the analysis
        if max_battery_capacity_kwh is None:
            # Theoretical minimum capacity needed (unconstrained)
            required_capacity_kwh = max(df["soc_kwh"]) - min(df["soc_kwh"])
        else:
            # For constrained analysis, use the provided capacity
            required_capacity_kwh = max_battery_capacity_kwh

        required_power_kw = df["battery_power"].abs().max()

        # 5. Add some useful metrics to the results
        df["shaving_applied"] = np.where(
            (df["net_load"] > self.import_limit_kw) | (df["net_load"] < self.export_limit_kw), 
            True, False
        )

        return required_capacity_kwh, required_power_kw, df

    def run_analysis_iterative(self, input_df: pd.DataFrame, efficiency=0.95):
        """
        Alternative method with battery efficiency and more realistic constraints.
        
        Args:
            input_df (pd.DataFrame): Input data with load and pv_production
            efficiency (float): Round-trip efficiency (0-1)
            
        Returns:
            tuple: (capacity_kwh, power_kw, results_df)
        """
        df = input_df.copy()
        
        # Calculate net load
        df["net_load"] = df["load"] - df["pv_production"]
        
        # Initialize variables for iterative simulation
        soc = 0.0
        soc_history = []
        battery_power_history = []
        actual_shaving_history = []
        
        charge_efficiency = np.sqrt(efficiency)  # Charge component
        discharge_efficiency = np.sqrt(efficiency)  # Discharge component
        
        for net_load in df["net_load"]:
            # Determine required shaving power
            if net_load > self.import_limit_kw:
                required_power = net_load - self.import_limit_kw  # Discharge needed
            elif net_load < self.export_limit_kw:
                required_power = net_load - self.export_limit_kw  # Charge needed
            else:
                required_power = 0.0
            
            # Apply battery constraints
            if required_power > 0:  # Discharge needed
                # Check if we have enough SOC
                available_energy = soc / self.time_step_h * discharge_efficiency
                actual_power = min(required_power, available_energy)
                energy_change = -actual_power * self.time_step_h / discharge_efficiency
            elif required_power < 0:  # Charge needed
                # Check available charging capacity (simplified)
                actual_power = required_power  # Negative for charging
                energy_change = actual_power * self.time_step_h * charge_efficiency
            else:
                actual_power = 0.0
                energy_change = 0.0
            
            # Update SOC
            soc += energy_change
            soc = max(0, soc)  # Prevent negative SOC
            
            # Store results
            soc_history.append(soc)
            battery_power_history.append(actual_power)
            actual_shaving_history.append(required_power - actual_power if required_power != 0 else 0)
        
        df["soc_kwh"] = soc_history
        df["battery_power"] = battery_power_history
        df["shaving_deficit"] = actual_shaving_history
        
        # Calculate requirements
        required_capacity_kwh = max(soc_history) - min(soc_history)
        required_power_kw = max(abs(power) for power in battery_power_history)
        
        return required_capacity_kwh, required_power_kw, df
