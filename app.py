%%writefile app.py

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(layout="wide")

# --- COMPLETE Hardcoded default values based on the business case ---
HARDCODED_DEFAULTS = {
    # General & Financial
    'project_term': 10, 'inflation': 0.02, 'wacc': 0.1,
    'depr_period_battery': 10, 'depr_period_pv': 15,
    'tax_threshold': 200000, 'tax_rate_1': 0.19, 'tax_rate_2': 0.258,

    # --- BESS Parameters ---
    # Technical Inputs (Yellow Cells)
    'bess_power_kw': 2000, 'bess_capacity_kwh': 4000,
    'bess_min_soc': 0.05, 'bess_max_soc': 0.95,
    'bess_charging_eff': 0.92, 'bess_discharging_eff': 0.92,
    'bess_annual_degradation': 0.04, 'bess_cycles_per_year': 600,
    # CAPEX Unit Cost Inputs (Yellow Cells)
    'bess_capex_per_kwh': 116.3, 'bess_capex_civil_pct': 0.06,
    'bess_capex_it_per_kwh': 1.5, 'bess_capex_security_per_kwh': 5.0,
    'bess_capex_permits_pct': 0.015, 'bess_capex_mgmt_pct': 0.025, 'bess_capex_contingency_pct': 0.05,
    # Income Inputs (Yellow Cells)
    'bess_income_trading_per_mw_year': 243254, 'bess_income_ctrl_party_pct': 0.1,
    'bess_income_supplier_cost_per_mwh': 2.0,
    # OPEX Inputs (Yellow Cells)
    'bess_opex_om_per_year': 4652.0, 'bess_opex_asset_mgmt_per_mw_year': 4000.0,
    'bess_opex_insurance_pct': 0.01, 'bess_opex_property_tax_pct': 0.001,
    'bess_opex_overhead_per_kwh_year': 1.0, 'bess_opex_other_per_kwh_year': 1.0,

    # --- PV Parameters (Unchanged for now) ---
    'pv_power_per_panel_wp': 590, 'pv_panel_count': 3479, 'pv_full_load_hours': 817.8,
    'pv_annual_degradation': 0.005, 'pv_capex_per_wp': 0.2, 'pv_capex_civil_pct': 0.08,
    'pv_income_ppa_per_kwh': 0.0, 'pv_opex_insurance_pct': 0.01
}

# --- Session State Initialization ---
if 'inputs' not in st.session_state:
    st.session_state.inputs = HARDCODED_DEFAULTS.copy()
    st.session_state.project_type = "BESS & PV"

# --- BESS KPI Calculation Function ---
def calculate_bess_kpis(i):
    """Calculates all derived 'white cell' BESS values."""
    kpis = {}
    # Technical
    kpis['bess_capacity_factor'] = i['bess_capacity_kwh'] / i['bess_power_kw'] if i['bess_power_kw'] > 0 else 0
    kpis['bess_soc_available'] = i['bess_max_soc'] - i['bess_min_soc']
    kpis['bess_usable_capacity_kwh'] = i['bess_capacity_kwh'] * kpis['bess_soc_available']
    kpis['bess_c_rate'] = i['bess_power_kw'] / kpis['bess_usable_capacity_kwh'] if kpis['bess_usable_capacity_kwh'] > 0 else 0
    kpis['bess_rte'] = i['bess_charging_eff'] * i['bess_discharging_eff']
    # Energetic
    kpis['bess_offtake_kwh_y1'] = i['bess_cycles_per_year'] * kpis['bess_usable_capacity_kwh'] / i['bess_charging_eff']
    # CAPEX
    kpis['bess_capex_purchase_costs'] = i['bess_capacity_kwh'] * i['bess_capex_per_kwh']
    kpis['bess_capex_civil_works'] = kpis['bess_capex_purchase_costs'] * i['bess_capex_civil_pct']
    kpis['bess_capex_it'] = i['bess_capacity_kwh'] * i['bess_capex_it_per_kwh']
    kpis['bess_capex_security'] = i['bess_capacity_kwh'] * i['bess_capex_security_per_kwh']
    capex_base_for_pct = kpis['bess_capex_purchase_costs'] + kpis['bess_capex_civil_works'] + kpis['bess_capex_it'] + kpis['bess_capex_security']
    kpis['bess_capex_permits'] = capex_base_for_pct * i['bess_capex_permits_pct']
    kpis['bess_capex_mgmt'] = capex_base_for_pct * i['bess_capex_mgmt_pct']
    kpis['bess_capex_contingency'] = capex_base_for_pct * i['bess_capex_contingency_pct']
    kpis['bess_total_capex'] = capex_base_for_pct + kpis['bess_capex_permits'] + kpis['bess_capex_mgmt'] + kpis['bess_capex_contingency']
    # Income
    kpis['bess_base_trading_income'] = (i['bess_power_kw'] / 1000) * i['bess_income_trading_per_mw_year']
    kpis['bess_ctrl_party_costs_y1'] = kpis['bess_base_trading_income'] * i['bess_income_ctrl_party_pct']
    kpis['bess_supplier_costs_y1'] = (kpis['bess_offtake_kwh_y1'] / 1000) * i['bess_income_supplier_cost_per_mwh']
    # OPEX
    kpis['bess_opex_asset_mgmt_y1'] = (i['bess_power_kw'] / 1000) * i['bess_opex_asset_mgmt_per_mw_year']
    kpis['bess_opex_insurance_y1'] = kpis['bess_total_capex'] * i['bess_opex_insurance_pct']
    kpis['bess_opex_property_tax_y1'] = kpis['bess_total_capex'] * i['bess_opex_property_tax_pct']
    kpis['bess_opex_overhead_y1'] = i['bess_capacity_kwh'] * i['bess_opex_overhead_per_kwh_year']
    kpis['bess_opex_other_y1'] = i['bess_capacity_kwh'] * i['bess_opex_other_per_kwh_year']
    kpis['bess_total_opex_y1'] = i['bess_opex_om_per_year'] + kpis['bess_opex_asset_mgmt_y1'] + kpis['bess_opex_insurance_y1'] + kpis['bess_opex_property_tax_y1'] + kpis['bess_opex_overhead_y1'] + kpis['bess_opex_other_y1']
    return kpis

# --- Core Financial & Charting Functions (Unchanged) ---
def run_financial_model(inputs, project_type):
    # This function is now simpler as it receives fully calculated inputs
    years = np.arange(1, int(inputs['project_term']) + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'
    is_bess = 'BESS' in project_type; is_pv = 'PV' in project_type
    # ... (rest of financial model is the same)
    df['inflation_factor'] = (1 + inputs['inflation']) ** (df.index - 1)
    df['bess_degradation_factor'] = (1 - inputs['bess_annual_degradation']) ** (df.index - 1) if is_bess else 1
    df['pv_degradation_factor'] = (1 - inputs['pv_annual_degradation']) ** (df.index - 1) if is_pv else 1
    df['bess_trading_income'] = (inputs.get('bess_base_trading_income', 0) * df['bess_degradation_factor']) if is_bess else 0
    df['bess_control_party_costs'] = -df['bess_trading_income'] * inputs.get('bess_income_ctrl_party_pct', 0)
    df['bess_supplier_costs'] = -inputs.get('bess_supplier_costs_y1', 0) * df['bess_degradation_factor'] * df['inflation_factor']
    df['pv_ppa_income'] = (inputs.get('pv_production_y1',0) * df['pv_degradation_factor'] * inputs.get('pv_income_ppa_per_kwh',0) * df['inflation_factor']) if is_pv else 0
    df['bess_opex'] = -inputs.get('bess_total_opex_y1', 0) * df['inflation_factor'] if is_bess else 0
    df['pv_opex'] = -inputs.get('pv_total_opex_y1', 0) * df['inflation_factor'] if is_pv else 0
    income_cols = ['bess_trading_income', 'bess_control_party_costs', 'bess_supplier_costs', 'pv_ppa_income', 'bess_opex', 'pv_opex']
    df['ebitda'] = df[income_cols].sum(axis=1)
    annual_depr_battery = (inputs.get('bess_total_capex', 0) / inputs['depr_period_battery']) if is_bess else 0
    annual_depr_pv = (inputs.get('pv_total_capex', 0) / inputs['depr_period_pv']) if is_pv else 0
    df['depreciation'] = 0
    if is_bess: df.loc[df.index <= inputs['depr_period_battery'], 'depreciation'] += annual_depr_battery
    if is_pv: df.loc[df.index <= inputs['depr_period_pv'], 'depreciation'] += annual_depr_pv
    df['profit_before_tax'] = df['ebitda'] - df['depreciation']
    df['corporate_tax'] = np.where(df['profit_before_tax'] <= inputs['tax_threshold'], df['profit_before_tax'] * inputs['tax_rate_1'], (inputs['tax_threshold'] * inputs['tax_rate_1']) + ((df['profit_before_tax'] - inputs['tax_threshold']) * inputs['tax_rate_2']))
    df.loc[df['profit_before_tax'] < 0, 'corporate_tax'] = 0
    df['corporate_tax'] = -df['corporate_tax']
    df['net_cash_flow'] = df['ebitda'] + df['corporate_tax']
    total_capex = inputs.get('bess_total_capex', 0) + inputs.get('pv_total_capex', 0)
    cash_flows = [-total_capex] + df['net_cash_flow'].tolist()
    irr = npf.irr(cash_flows) if total_capex > 0 else 0
    df['cumulative_cash_flow'] = df['net_cash_flow'].cumsum() - total_capex
    try:
        payback_year = df[df['cumulative_cash_flow'] > 0].index[0]
        cash_flow_last_negative_year = df.loc[payback_year - 1, 'cumulative_cash_flow'] + total_capex
        payback_period = (payback_year - 1) + (-cash_flow_last_negative_year / df.loc[payback_year, 'net_cash_flow'])
    except IndexError: payback_period = "Not reached"
    metrics = {"Total Investment": total_capex, "Project IRR": irr, "Payback Period (years)": payback_period if isinstance(payback_period, str) else f"{payback_period:.2f}", "Final Cumulative Cash Flow": df['cumulative_cash_flow'].iloc[-1]}
    return df, metrics

def generate_interactive_charts(df_results, total_capex):
    # This function is unchanged
    fig1 = px.bar(df_results, x=df_results.index, y='net_cash_flow', title="Annual Net Cash Flow", labels={'net_cash_flow': 'Net Cash Flow (€)', 'Year': 'Project Year'})
    fig1.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    cumulative_data = pd.DataFrame({'Year': np.arange(0, len(df_results) + 1), 'Cumulative Cash Flow': np.concatenate([[-total_capex], df_results['cumulative_cash_flow'].values])})
    fig2 = px.line(cumulative_data, x='Year', y='Cumulative Cash Flow', title="Cumulative Cash Flow", markers=True)
    fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    fig2.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    return fig1, fig2

# --- Main Application UI and Logic ---
st.title('Comprehensive BESS & PV Financial Model ☀️🔋')

st.sidebar.title("Configuration")
st.session_state.project_type = st.sidebar.selectbox("Select Project Type", ["BESS & PV", "BESS-only", "PV-only"])
i = st.session_state.inputs # Shortcut

# --- BESS INPUTS (Conditional Display) ---
if 'BESS' in st.session_state.project_type:
    st.sidebar.header("🔋 Battery Energy Storage System")
    with st.sidebar.expander("Technical Inputs (BESS)", expanded=True):
        i['bess_power_kw'] = st.number_input("Power (kW)", value=i['bess_power_kw'], help="The maximum charge/discharge power of the battery.")
        i['bess_capacity_kwh'] = st.number_input("Storage Capacity (kWh)", value=i['bess_capacity_kwh'], help="The total nominal energy capacity of the battery.")
        c1, c2 = st.columns(2)
        i['bess_min_soc'] = c1.number_input("Min SoC", value=i['bess_min_soc'], help="Minimum State of Charge to preserve battery health.")
        i['bess_max_soc'] = c2.number_input("Max SoC", value=i['bess_max_soc'], help="Maximum State of Charge to preserve battery health.")
        i['bess_charging_eff'] = st.slider("Charging Efficiency", 0.8, 1.0, i['bess_charging_eff'], help="Efficiency when charging the battery (AC to DC).")
        i['bess_discharging_eff'] = st.slider("Discharging Efficiency", 0.8, 1.0, i['bess_discharging_eff'], help="Efficiency when discharging the battery (DC to AC).")
        i['bess_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 10.0, i['bess_annual_degradation'] * 100) / 100
        i['bess_cycles_per_year'] = st.number_input("Cycles per Year", value=i['bess_cycles_per_year'], help="Estimated number of full equivalent cycles per year.")

    with st.sidebar.expander("CAPEX Assumptions (BESS)"):
        i['bess_capex_per_kwh'] = st.number_input("BESS Price (€/kWh)", value=i['bess_capex_per_kwh'], help="Cost of the battery cells and enclosure per kWh.")
        i['bess_capex_civil_pct'] = st.slider("Civil/Installation Works (%)", 0.0, 20.0, i['bess_capex_civil_pct'] * 100, help="Cost of civil and installation works as a % of BESS purchase cost.") / 100
        i['bess_capex_it_per_kwh'] = st.number_input("IT/Control (€/kWh)", value=i['bess_capex_it_per_kwh'], help="Cost of IT, software, and control systems.")
        i['bess_capex_security_per_kwh'] = st.number_input("Security (€/kWh)", value=i['bess_capex_security_per_kwh'], help="Cost of security measures.")
        i['bess_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['bess_capex_permits_pct'] * 100, help="Cost of permits as a % of the main investment subtotal.") / 100
        i['bess_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['bess_capex_mgmt_pct'] * 100, help="Cost of project management as a % of the main investment subtotal.") / 100
        i['bess_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['bess_capex_contingency_pct'] * 100, help="Budgetary contingency as a % of the main investment subtotal.") / 100

    with st.sidebar.expander("Income Assumptions (BESS)"):
        i['bess_income_trading_per_mw_year'] = st.number_input("Trading Income (€/MW/year)", value=i['bess_income_trading_per_mw_year'])
        i['bess_income_ctrl_party_pct'] = st.slider("Control Party Costs (% of Income)", 0.0, 25.0, i['bess_income_ctrl_party_pct'] * 100, help="Fee for the party managing market trading, as a % of trading income.") / 100
        i['bess_income_supplier_cost_per_mwh'] = st.number_input("Energy Supplier Costs (€/MWh)", value=i['bess_income_supplier_cost_per_mwh'], help="Costs for grid offtake, imbalance, etc.")

    with st.sidebar.expander("OPEX Assumptions (BESS)"):
        i['bess_opex_om_per_year'] = st.number_input("O&M (€/year)", value=i['bess_opex_om_per_year'])
        i['bess_opex_asset_mgmt_per_mw_year'] = st.number_input("Asset Management (€/MW/year)", value=i['bess_opex_asset_mgmt_per_mw_year'])
        i['bess_opex_insurance_pct'] = st.slider("Insurance (% of Total CAPEX)", 0.0, 5.0, i['bess_opex_insurance_pct'] * 100, help="Annual insurance cost as a % of total initial investment.") / 100
        i['bess_opex_property_tax_pct'] = st.slider("Property Tax (% of Total CAPEX)", 0.0, 2.0, i['bess_opex_property_tax_pct'] * 100, format="%.3f") / 100
        i['bess_opex_overhead_per_kwh_year'] = st.number_input("Overhead (€/kWh/year)", value=i['bess_opex_overhead_per_kwh_year'])
        i['bess_opex_other_per_kwh_year'] = st.number_input("Other (€/kWh/year)", value=i['bess_opex_other_per_kwh_year'])

# --- PV INPUTS (Conditional Display) ---
if 'PV' in st.session_state.project_type:
    st.sidebar.header("☀️ Solar PV System")
    # (PV sections would go here, unchanged for now)

# --- General Financial Inputs ---
st.sidebar.header("General & Financial")
# (General sections would go here, unchanged for now)

# --- RUN MODEL BUTTON ---
if st.sidebar.button('Run Model', type="primary"):
    inputs_to_run = i.copy()
    
    # --- Final Assembly of Inputs for the Model ---
    # BESS Calculations
    if 'BESS' in st.session_state.project_type:
        bess_kpis = calculate_bess_kpis(i)
        inputs_to_run.update(bess_kpis) # Add all calculated KPIs to the inputs
    
    # PV Calculations (simplified for now)
    if 'PV' in st.session_state.project_type:
        pv_total_kwp = (i['pv_power_per_panel_wp'] * i['pv_panel_count']) / 1000
        pv_base_capex = pv_total_kwp * 1000 * i['pv_capex_per_wp']
        inputs_to_run['pv_total_capex'] = pv_base_capex * (1 + i['pv_capex_civil_pct'])
        inputs_to_run['pv_production_y1'] = pv_total_kwp * i['pv_full_load_hours']
        inputs_to_run['pv_total_opex_y1'] = inputs_to_run['pv_total_capex'] * i['pv_opex_insurance_pct']
    
    # --- Run Model and Display Results ---
    results_df, metrics = run_financial_model(inputs_to_run, st.session_state.project_type)
    
    st.header('Financial Metrics')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Investment", f"€{metrics['Total Investment']:,.0f}")
    col2.metric("Project IRR", f"{metrics['Project IRR']:.2%}")
    col3.metric("Payback Period", f"{metrics['Payback Period (years)']} years")
    col4.metric("Final Cumulative Cash Flow", f"€{metrics['Final Cumulative Cash Flow']:,.0f}")

    # --- NEW: Display BESS KPI Results ---
    if 'BESS' in st.session_state.project_type:
        st.header("🔋 BESS - Key Performance Indicators")
        bess_kpis = inputs_to_run # KPIs were added to this dict
        
        st.subheader("Technical")
        kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5 = st.columns(5)
        kpi_c1.metric("Usable Capacity", f"{bess_kpis['bess_usable_capacity_kwh']:,.0f} kWh", help="Storage Capacity × (Max SoC - Min SoC)")
        kpi_c2.metric("Capacity Factor", f"{bess_kpis['bess_capacity_factor']:.2f} h", help="Storage Capacity / Power. How many hours the battery can discharge at max power.")
        kpi_c3.metric("C-Rate", f"{bess_kpis['bess_c_rate']:.2f}", help="Power / Usable Capacity. How quickly the battery can be fully discharged.")
        kpi_c4.metric("RTE", f"{bess_kpis['bess_rte']:.2%}", help="Round Trip Efficiency. Charging Eff × Discharging Eff.")
        kpi_c5.metric("Grid Offtake Y1", f"{bess_kpis['bess_offtake_kwh_y1']:,.0f} kWh", help="Energy needed from the grid in Year 1 to perform cycles.")

        st.subheader("CAPEX Breakdown")
        kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
        kpi_c1.metric("Purchase Costs", f"€{bess_kpis['bess_capex_purchase_costs']:,.0f}", help="Capacity × Price per kWh")
        kpi_c2.metric("Civil, IT, Security", f"€{bess_kpis['bess_capex_civil_works'] + bess_kpis['bess_capex_it'] + bess_kpis['bess_capex_security']:,.0f}")
        kpi_c3.metric("Soft Costs (Mgmt, etc.)", f"€{bess_kpis['bess_capex_permits'] + bess_kpis['bess_capex_mgmt'] + bess_kpis['bess_capex_contingency']:,.0f}")
        kpi_c4.metric("Total BESS CAPEX", f"€{bess_kpis['bess_total_capex']:,.0f}", delta_color="off")
        
        st.subheader("Income & OPEX (Year 1)")
        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        kpi_c1.metric("Gross Trading Income", f"€{bess_kpis['bess_base_trading_income']:,.0f}", help="Power in MW × Trading Income per MW")
        kpi_c2.metric("Trading Costs", f"€{bess_kpis['bess_ctrl_party_costs_y1'] + bess_kpis['bess_supplier_costs_y1']:,.0f}", help="Control Party + Energy Supplier costs.")
        kpi_c3.metric("Total OPEX", f"€{bess_kpis['bess_total_opex_y1']:,.0f}", help="Sum of all annual operational expenditures.")

    st.header('Interactive Charts')
    fig1, fig2 = generate_interactive_charts(results_df, metrics['Total Investment'])
    st.plotly_chart(fig2, use_container_width=True) # Cumulative chart is often more important
    st.plotly_chart(fig1, use_container_width=True)
    
    st.header('Annual Projections Table')
    display_df = results_df[['ebitda', 'depreciation', 'net_cash_flow', 'cumulative_cash_flow']].copy()
    st.dataframe(display_df.style.format("€{:,.0f}"), use_container_width=True)
else:
    st.info('Adjust inputs in the sidebar and click "Run Model" to see the results.')
