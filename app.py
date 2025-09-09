
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(layout="wide")

# --- COMPLETE Hardcoded default values based on the provided business case ---
HARDCODED_DEFAULTS = {
    # General
    'project_term': 10, 'inflation': 0.02, 'wacc': 0.1,
    'depr_period_battery': 10, 'depr_period_pv': 15,
    # Tax
    'tax_threshold': 200000, 'tax_rate_1': 0.19, 'tax_rate_2': 0.258,
    # Financing
    'equity_fraction': 1.0, 'debt_fraction': 0.0, 'interest_rate_debt': 0.06,

    # --- BESS Parameters ---
    # Technical
    'bess_power_kw': 2000, 'bess_capacity_kwh': 4000,
    'bess_min_soc': 0.05, 'bess_max_soc': 0.95,
    'bess_charging_eff': 0.92, 'bess_discharging_eff': 0.92,
    'bess_annual_degradation': 0.04,
    # CAPEX Unit Costs
    'bess_capex_per_kwh': 116.3, 'bess_capex_civil_pct': 0.06,
    'bess_capex_it_per_kwh': 1.5, 'bess_capex_security_per_kwh': 5.0,
    'bess_capex_permits_pct': 0.015, 'bess_capex_mgmt_pct': 0.025, 'bess_capex_contingency_pct': 0.05,
    # Income
    'bess_income_trading_per_mw_year': 243254, 'bess_income_ctrl_party_pct': 0.1,
    'bess_income_supplier_cost_per_mwh': 2.0, 'bess_cycles_per_year': 600,
    # OPEX
    'bess_opex_om_per_year': 4652.0, 'bess_opex_asset_mgmt_per_mw_year': 4000.0,
    'bess_opex_insurance_pct': 0.01, 'bess_opex_property_tax_pct': 0.001,
    'bess_opex_overhead_per_kwh_year': 1.0, 'bess_opex_other_per_kwh_year': 1.0,

    # --- PV Parameters ---
    # Technical
    'pv_power_per_panel_wp': 590, 'pv_panel_count': 3479,
    'pv_full_load_hours': 817.8, 'pv_annual_degradation': 0.005,
    # CAPEX Unit Costs
    'pv_capex_per_wp': 0.2, 'pv_capex_civil_pct': 0.08,
    'pv_capex_security_pct': 0.02, 'pv_capex_permits_pct': 0.01,
    'pv_capex_mgmt_pct': 0.025, 'pv_capex_contingency_pct': 0.05,
    # Income
    'pv_income_ppa_per_kwh': 0.0,
    # OPEX
    'pv_opex_insurance_pct': 0.01, 'pv_opex_property_tax_pct': 0.001,
    'pv_opex_overhead_pct': 0.005, 'pv_opex_other_pct': 0.005
}

# --- Session State Initialization ---
if 'inputs' not in st.session_state:
    st.session_state.inputs = HARDCODED_DEFAULTS.copy()
    st.session_state.project_type = "BESS & PV"

# --- Core Calculation and Charting Functions ---
def run_financial_model(inputs: dict, project_type: str):
    years = np.arange(1, int(inputs['project_term']) + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'

    # --- Conditional Calculations based on Project Type ---
    is_bess_active = 'BESS' in project_type
    is_pv_active = 'PV' in project_type

    # Degradation & Inflation
    df['inflation_factor'] = (1 + inputs['inflation']) ** (df.index - 1)
    df['bess_degradation_factor'] = (1 - inputs['bess_annual_degradation']) ** (df.index - 1) if is_bess_active else 1
    df['pv_degradation_factor'] = (1 - inputs['pv_annual_degradation']) ** (df.index - 1) if is_pv_active else 1

    # Income Streams
    df['bess_trading_income'] = (inputs['bess_base_trading_income'] * df['bess_degradation_factor']) if is_bess_active else 0
    df['bess_control_party_costs'] = -df['bess_trading_income'] * inputs['bess_income_ctrl_party_pct']
    df['bess_supplier_costs'] = -inputs['bess_supplier_cost_mwh_total'] * df['bess_degradation_factor'] * df['inflation_factor']
    df['pv_ppa_income'] = (inputs['pv_production_y1'] * df['pv_degradation_factor'] * inputs['pv_income_ppa_per_kwh'] * df['inflation_factor']) if is_pv_active else 0

    # OPEX
    df['bess_opex'] = -inputs['bess_total_opex_y1'] * df['inflation_factor'] if is_bess_active else 0
    df['pv_opex'] = -inputs['pv_total_opex_y1'] * df['inflation_factor'] if is_pv_active else 0

    # EBITDA
    income_cols = ['bess_trading_income', 'bess_control_party_costs', 'bess_supplier_costs', 'pv_ppa_income', 'bess_opex', 'pv_opex']
    df['ebitda'] = df[income_cols].sum(axis=1)

    # Depreciation
    annual_depr_battery = (inputs['bess_total_capex'] / inputs['depr_period_battery']) if is_bess_active else 0
    annual_depr_pv = (inputs['pv_total_capex'] / inputs['depr_period_pv']) if is_pv_active else 0
    df['depreciation'] = 0
    if is_bess_active:
        df.loc[df.index <= inputs['depr_period_battery'], 'depreciation'] += annual_depr_battery
    if is_pv_active:
        df.loc[df.index <= inputs['depr_period_pv'], 'depreciation'] += annual_depr_pv

    # Financials
    df['profit_before_tax'] = df['ebitda'] - df['depreciation']
    df['corporate_tax'] = np.where(
        df['profit_before_tax'] <= inputs['tax_threshold'],
        df['profit_before_tax'] * inputs['tax_rate_1'],
        (inputs['tax_threshold'] * inputs['tax_rate_1']) + ((df['profit_before_tax'] - inputs['tax_threshold']) * inputs['tax_rate_2'])
    )
    df.loc[df['profit_before_tax'] < 0, 'corporate_tax'] = 0
    df['corporate_tax'] = -df['corporate_tax']
    df['net_cash_flow'] = df['ebitda'] + df['corporate_tax']
    
    total_capex = (inputs['bess_total_capex'] if is_bess_active else 0) + (inputs['pv_total_capex'] if is_pv_active else 0)
    cash_flows = [-total_capex] + df['net_cash_flow'].tolist()
    
    irr = npf.irr(cash_flows) if total_capex > 0 else 0
    df['cumulative_cash_flow'] = df['net_cash_flow'].cumsum() - total_capex
    try:
        payback_year = df[df['cumulative_cash_flow'] > 0].index[0]
        cash_flow_last_negative_year = df.loc[payback_year - 1, 'cumulative_cash_flow'] + total_capex
        payback_period = (payback_year - 1) + (-cash_flow_last_negative_year / df.loc[payback_year, 'net_cash_flow'])
    except IndexError: payback_period = "Not reached"
        
    metrics = {
        "Total Investment": total_capex, "Project IRR": irr,
        "Payback Period (years)": payback_period if isinstance(payback_period, str) else f"{payback_period:.2f}",
        "Final Cumulative Cash Flow": df['cumulative_cash_flow'].iloc[-1]
    }
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

# --- Project Type Selector ---
st.sidebar.title("Configuration")
project_type = st.sidebar.selectbox(
    "Select Project Type",
    ["BESS & PV", "BESS-only", "PV-only"],
    key='project_type'
)
i = st.session_state.inputs # Shortcut

# --- BESS INPUTS (Conditional Display) ---
if 'BESS' in st.session_state.project_type:
    st.sidebar.header("🔋 Battery Energy Storage System")
    with st.sidebar.expander("Technical Specs"):
        i['bess_power_kw'] = st.number_input("Power (kW)", value=i['bess_power_kw'])
        i['bess_capacity_kwh'] = st.number_input("Capacity (kWh)", value=i['bess_capacity_kwh'])
        i['bess_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 10.0, i['bess_annual_degradation'] * 100) / 100
    with st.sidebar.expander("CAPEX Assumptions"):
        i['bess_capex_per_kwh'] = st.number_input("BESS Price (€/kWh)", value=i['bess_capex_per_kwh'])
        i['bess_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['bess_capex_civil_pct'] * 100) / 100
        i['bess_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['bess_capex_contingency_pct'] * 100) / 100
    with st.sidebar.expander("Income Assumptions"):
        i['bess_income_trading_per_mw_year'] = st.number_input("Trading Income (€/MW/year)", value=i['bess_income_trading_per_mw_year'])
        i['bess_cycles_per_year'] = st.number_input("Cycles per Year", value=i['bess_cycles_per_year'])
    with st.sidebar.expander("OPEX Assumptions"):
        i['bess_opex_om_per_year'] = st.number_input("O&M (€/year)", value=i['bess_opex_om_per_year'])
        i['bess_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['bess_opex_insurance_pct'] * 100) / 100

# --- PV INPUTS (Conditional Display) ---
if 'PV' in st.session_state.project_type:
    st.sidebar.header("☀️ Solar PV System")
    with st.sidebar.expander("Technical Specs"):
        i['pv_panel_count'] = st.number_input("Number of Panels", value=i['pv_panel_count'])
        i['pv_power_per_panel_wp'] = st.number_input("Power per Panel (Wp)", value=i['pv_power_per_panel_wp'])
        i['pv_full_load_hours'] = st.number_input("Full Load Hours (kWh/kWp)", value=i['pv_full_load_hours'])
        i['pv_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 2.0, i['pv_annual_degradation'] * 100, format="%.2f") / 100
    with st.sidebar.expander("CAPEX Assumptions"):
        i['pv_capex_per_wp'] = st.number_input("PV Price (€/Wp)", value=i['pv_capex_per_wp'])
        i['pv_capex_civil_pct'] = st.slider("PV Civil/Installation (%)", 0.0, 20.0, i['pv_capex_civil_pct'] * 100) / 100
    with st.sidebar.expander("Income Assumptions"):
        i['pv_income_ppa_per_kwh'] = st.number_input("PPA Tariff (€/kWh)", value=i['pv_income_ppa_per_kwh'], format="%.4f")
    with st.sidebar.expander("OPEX Assumptions"):
        i['pv_opex_insurance_pct'] = st.slider("PV Insurance (% of CAPEX)", 0.0, 5.0, i['pv_opex_insurance_pct'] * 100) / 100

# --- General Financial Inputs ---
st.sidebar.header("General & Financial")
with st.sidebar.expander("Project Term, Depreciation & Finance"):
    i['project_term'] = st.slider('Project Term (years)', 5, 30, i['project_term'])
    i['depr_period_battery'] = st.slider('BESS Depreciation Period', 5, 20, i['depr_period_battery'])
    i['depr_period_pv'] = st.slider('PV Depreciation Period', 10, 30, i['depr_period_pv'])
    i['wacc'] = st.slider('WACC (%)', 5.0, 15.0, i['wacc'] * 100) / 100
with st.sidebar.expander("Inflation & Tax"):
    i['inflation'] = st.slider('Annual Inflation Rate (%)', 0.0, 10.0, i['inflation'] * 100) / 100
    i['tax_threshold'] = st.number_input('Tax Threshold (€)', value=i['tax_threshold'])
    i['tax_rate_1'] = st.slider('Tax Rate 1 (%)', 10.0, 30.0, i['tax_rate_1'] * 100) / 100
    i['tax_rate_2'] = st.slider('Tax Rate 2 (%)', 10.0, 30.0, i['tax_rate_2'] * 100) / 100

# --- LIVE CALCULATIONS ---
st.sidebar.subheader("Live Calculated Values")
inputs_to_run = i.copy()

# BESS Calculations
if 'BESS' in st.session_state.project_type:
    bess_base_capex = i['bess_capacity_kwh'] * i['bess_capex_per_kwh']
    bess_total_capex = bess_base_capex * (1 + i['bess_capex_civil_pct'] + i['bess_capex_contingency_pct']) # Simplified
    bess_base_trading_income = (i['bess_power_kw'] / 1000) * i['bess_income_trading_per_mw_year']
    bess_usable_kwh = i['bess_capacity_kwh'] * (i['bess_max_soc'] - i['bess_min_soc'])
    bess_supplier_cost_mwh_total = i['bess_cycles_per_year'] * bess_usable_kwh * i['bess_income_supplier_cost_per_mwh'] / 1000
    bess_total_opex_y1 = i['bess_opex_om_per_year'] + (bess_total_capex * i['bess_opex_insurance_pct'])
    st.sidebar.metric("Calculated BESS CAPEX (€)", f"{bess_total_capex:,.0f}")
    inputs_to_run['bess_total_capex'] = bess_total_capex
    inputs_to_run['bess_base_trading_income'] = bess_base_trading_income
    inputs_to_run['bess_supplier_cost_mwh_total'] = bess_supplier_cost_mwh_total
    inputs_to_run['bess_total_opex_y1'] = bess_total_opex_y1
else: # If BESS not active, zero out its financial impact
    inputs_to_run['bess_total_capex'] = 0
    inputs_to_run['bess_base_trading_income'] = 0
    inputs_to_run['bess_supplier_cost_mwh_total'] = 0
    inputs_to_run['bess_total_opex_y1'] = 0

# PV Calculations
if 'PV' in st.session_state.project_type:
    pv_total_kwp = (i['pv_power_per_panel_wp'] * i['pv_panel_count']) / 1000
    pv_base_capex = pv_total_kwp * 1000 * i['pv_capex_per_wp']
    pv_total_capex = pv_base_capex * (1 + i['pv_capex_civil_pct']) # Simplified
    pv_production_y1 = pv_total_kwp * i['pv_full_load_hours']
    pv_total_opex_y1 = pv_total_capex * i['pv_opex_insurance_pct']
    st.sidebar.metric("Total PV Peak Power (kWp)", f"{pv_total_kwp:,.0f}")
    st.sidebar.metric("Calculated PV CAPEX (€)", f"{pv_total_capex:,.0f}")
    inputs_to_run['pv_total_capex'] = pv_total_capex
    inputs_to_run['pv_production_y1'] = pv_production_y1
    inputs_to_run['pv_total_opex_y1'] = pv_total_opex_y1
else: # If PV not active, zero out its financial impact
    inputs_to_run['pv_total_capex'] = 0
    inputs_to_run['pv_production_y1'] = 0
    inputs_to_run['pv_total_opex_y1'] = 0

# --- RUN MODEL BUTTON ---
if st.sidebar.button('Run Model', type="primary"):
    results_df, metrics = run_financial_model(inputs_to_run, st.session_state.project_type)
    
    st.header('Financial Metrics')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Investment", f"€{metrics['Total Investment']:,.0f}")
    col2.metric("Project IRR", f"{metrics['Project IRR']:.2%}")
    col3.metric("Payback Period", f"{metrics['Payback Period (years)']} years")
    col4.metric("Final Cumulative Cash Flow", f"€{metrics['Final Cumulative Cash Flow']:,.0f}")
    
    st.header('Interactive Charts')
    fig1, fig2 = generate_interactive_charts(results_df, metrics['Total Investment'])
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1: st.plotly_chart(fig1, use_container_width=True)
    with col_chart2: st.plotly_chart(fig2, use_container_width=True)
    
    st.header('Annual Projections Table')
    display_df = results_df[['ebitda', 'depreciation', 'net_cash_flow', 'cumulative_cash_flow']].copy()
    st.dataframe(display_df.style.format("€{:,.0f}"), use_container_width=True)
else:
    st.info('Adjust inputs in the sidebar and click "Run Model" to see the results.')
