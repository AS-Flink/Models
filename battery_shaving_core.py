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


# In your app.py file

def show_battery_sizing_page():
    """Displays the UI for the Battery Net Peak Shaving Sizing Tool."""
    display_header("Battery Sizing Tool for Peak Shaving 🔋")

    with st.sidebar:
        st.header("⚙️ Sizing Configuration")
        uploaded_file = st.file_uploader("Upload Your Data (CSV)", type="csv")
        st.info("Set a target for your maximum power draw from the grid.")
        grid_import_threshold = st.number_input("Target Max Grid Import (kW)", min_value=1, value=80, step=5)
        run_button = st.button("🚀 Run Sizing Analysis", type="primary")
        
        st.header("Navigation")
        if st.button("⬅️ Back to Home"):
            if 'sizing_results' in st.session_state:
                del st.session_state['sizing_results']
            st.session_state.page = "Home"
            st.rerun()

    if run_button and uploaded_file is not None:
        try:
            input_df = pd.read_csv(uploaded_file)
            input_df["Datetime"] = pd.to_datetime(input_df["Datetime"], dayfirst=True)
            input_df.set_index("Datetime", inplace=True)

            analyzer = NetPeakShavingSizer(grid_import_threshold_kw=grid_import_threshold)
            capacity, power, results_df = analyzer.run_analysis(input_df)
            
            st.session_state['sizing_results'] = {
                "capacity": capacity, "power": power, "df": results_df,
                "grid_import_threshold": grid_import_threshold
            }
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred: {e}")

    elif run_button and uploaded_file is None:
        st.warning("Please upload a file to run the analysis.")

    if 'sizing_results' in st.session_state:
        results = st.session_state['sizing_results']
        
        st.subheader("💡 Calculated Battery Size")
        col1, col2 = st.columns(2)
        col1.metric("Required Power", f"{results['power']:,.2f} kW")
        col2.metric("Required Energy Capacity", f"{results['capacity']:,.2f} kWh")
        
        display_recommendations(results['power'], results['capacity'])

        # --- Charting Section ---
        st.subheader("📊 Analysis Charts")
        df = results['df']
        grid_import_threshold = results['grid_import_threshold']

        # Chart 1: Net Load
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df.index, y=df['net_load'], mode='lines', name='Original Net Load', line=dict(color='lightgray')))
        fig1.add_trace(go.Scatter(x=df.index, y=df['grid_import_with_battery'], mode='lines', name='Final Grid Import', line=dict(color='royalblue', width=2)))
        fig1.add_hline(y=grid_import_threshold, line_dash="dash", line_color="red", annotation_text="Target Threshold")
        fig1.update_layout(title="Net Load vs. Peak Shaving Threshold", yaxis_title="Power (kW)")
        st.plotly_chart(fig1, use_container_width=True)

        # Chart 2: Battery Power Profile
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df.index, y=df['battery_power'].clip(lower=0), mode='lines', name='Charging Power', fill='tozeroy', line=dict(color='green')))
        fig2.add_trace(go.Scatter(x=df.index, y=df['battery_power'].clip(upper=0), mode='lines', name='Discharging Power', fill='tozeroy', line=dict(color='red')))
        fig2.update_layout(title="Required Battery Power Profile", yaxis_title="Power (kW)")
        st.plotly_chart(fig2, use_container_width=True)
        
        # --- NEW: Chart 3: Cumulative SOC ---
        # This plot shows the long-term energy balance trend in the battery.
        fig3 = px.line(df, x=df.index, y='soc_kwh', 
                       title="Cumulative Battery State of Charge (SOC) Trend",
                       labels={"soc_kwh": "Energy (kWh)", "index": "Time"})
        fig3.update_traces(line_color='purple')
        st.plotly_chart(fig3, use_container_width=True)

    else:
        st.info("Upload a file and set your target grid import to get started.")
