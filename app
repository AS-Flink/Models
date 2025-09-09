

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import io

# --- Page Configuration ---
st.set_page_config(layout="wide")

# --- COMPLETE Hardcoded default values ---
# This dictionary contains the initial state for ALL parameters.
HARDCODED_DEFAULTS = {
    # General
    'project_term': 10, 'inflation': 0.02, 'wacc': 0.10,
    'depr_period_battery': 10, 'depr_period_pv': 15,
    'grid_cost_extra_inflation': 0.005,
    # Tax
    'tax_threshold': 200000, 'tax_rate_1': 0.19, 'tax_rate_2': 0.258,
    # Battery Technical
    'battery_power_kw': 2000, 'battery_capacity_kwh': 4000, 'battery_degradation': 0.04,
    # Battery Unit Costs / Revenue
    'bess_price_per_kwh': 116.3, 'base_trading_income_per_mw_year': 243254,
    'control_party_cost_fraction': 0.1,
    # PV Technical
    'pv_power_per_panel_wp': 590, 'pv_panel_count': 3479,
    'pv_full_load_hours': 817.8, 'pv_degradation': 0.005,
    # PV Unit Costs
    'pv_price_per_wp': 0.2,
    # Detailed OPEX - Battery
    'opex_battery_om': 4652.0, 'opex_battery_asset_mgmt': 8000.0,
    'opex_battery_insurance': 4652.0, 'opex_battery_property_tax': 465.2,
    'opex_battery_overhead': 4000.0, 'opex_battery_other': 4000.0,
    # Detailed OPEX - PV
    'opex_pv_insurance': 4105.22, 'opex_pv_property_tax': 410.52,
    'opex_pv_overhead': 2052.61, 'opex_pv_other': 2052.61,
    # Detailed Grid Costs
    'grid_kw_max': 2283.6, 'grid_kwh_offtake': 5454.77
}

# --- Session State Initialization ---
# This robust block prevents all initialization errors.
if 'inputs' not in st.session_state:
    st.session_state.inputs = HARDCODED_DEFAULTS.copy()
    st.session_state.source = "default values"

# --- Core Calculation and Charting Functions ---
def run_financial_model(inputs: dict):
    """
    Takes a dictionary of inputs and returns a results DataFrame and key metrics.
    """
    years = np.arange(1, inputs['project_term'] + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'
    df['inflation_factor'] = (1 + inputs['inflation']) ** (df.index - 1)
    df['grid_inflation_factor'] = (1 + inputs['inflation'] + inputs['grid_cost_extra_inflation']) ** (df.index - 1)
    df['battery_degradation_factor'] = (1 - inputs['battery_degradation']) ** (df.index - 1)
    df['trading_income'] = inputs['base_trading_income'] * df['battery_degradation_factor']
    df['control_party_costs'] = -df['trading_income'] * inputs['control_party_cost_fraction']
    df['total_opex'] = -inputs['base_opex_sum'] * df['inflation_factor']
    df['grid_costs'] = -inputs['base_grid_costs'] * df['grid_inflation_factor']
    revenue_cols = ['trading_income', 'control_party_costs', 'total_opex', 'grid_costs']
    df['ebitda'] = df[revenue_cols].sum(axis=1)
    annual_depr_battery = inputs['battery_capex'] / inputs['depr_period_battery']
    annual_depr_pv = inputs['pv_capex'] / inputs['depr_period_pv']
    df['depreciation'] = annual_depr_battery + annual_depr_pv
    df.loc[df.index > inputs['depr_period_battery'], 'depreciation'] -= annual_depr_battery
    df.loc[df.index > inputs['depr_period_pv'], 'depreciation'] -= annual_depr_pv
    df['profit_before_tax'] = df['ebitda'] - df['depreciation']
    df['corporate_tax'] = np.where(
        df['profit_before_tax'] <= inputs['tax_threshold'],
        df['profit_before_tax'] * inputs['tax_rate_1'],
        (inputs['tax_threshold'] * inputs['tax_rate_1']) + ((df['profit_before_tax'] - inputs['tax_threshold']) * inputs['tax_rate_2'])
    )
    df.loc[df['profit_before_tax'] < 0, 'corporate_tax'] = 0
    df['corporate_tax'] = -df['corporate_tax']
    df['net_cash_flow'] = df['ebitda'] + df['corporate_tax']
    total_capex = inputs['battery_capex'] + inputs['pv_capex']
    cash_flows = [-total_capex] + df['net_cash_flow'].tolist()
    irr = npf.irr(cash_flows)
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
    """
    Takes results and returns two interactive Plotly chart objects.
    """
    # Chart 1: Annual Net Cash Flow
    fig1 = px.bar(
        df_results, x=df_results.index, y='net_cash_flow',
        title="Annual Net Cash Flow", labels={'net_cash_flow': 'Net Cash Flow (€)', 'Year': 'Project Year'}
    )
    fig1.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")

    # Chart 2: Cumulative Cash Flow
    cumulative_data = pd.DataFrame({
        'Year': np.arange(0, len(df_results) + 1),
        'Cumulative Cash Flow': np.concatenate([[-total_capex], df_results['cumulative_cash_flow'].values])
    })
    fig2 = px.line(
        cumulative_data, x='Year', y='Cumulative Cash Flow',
        title="Cumulative Cash Flow", markers=True
    )
    fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    fig2.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")

    return fig1, fig2

# --- Main Application UI and Logic ---
st.title('Interactive Financial Model ☀️🔋')
st.sidebar.header('Project Inputs')

# --- CSV Uploader ---
uploaded_file = st.sidebar.file_uploader("Upload CSV to Override All Inputs", type=['csv'])

if uploaded_file is not None:
    try:
        df_inputs = pd.read_csv(uploaded_file)
        def get_value(item_name, default_val):
            try: return df_inputs[df_inputs['Item'] == item_name]['Value'].iloc[0]
            except: return default_val
        
        csv_inputs = {}
        # This comprehensive block parses all expected values from the CSV
        for key, default_value in HARDCODED_DEFAULTS.items():
            # A simple mapping for CSV 'Item' names to our dictionary keys
            # This can be made more robust, but works for the known format
            item_name = key.replace('_', ' ').replace('per', '/').title()
            # Special cases for names that differ significantly
            if key == 'bess_price_per_kwh': item_name = 'BESS'
            if key == 'pv_price_per_wp': item_name = 'Price per Wp'
            
            value = get_value(item_name, default_value)
            if isinstance(default_value, (int, float)):
                csv_inputs[key] = pd.to_numeric(value)
            else:
                csv_inputs[key] = value

        st.session_state.inputs = csv_inputs
        st.session_state.source = f"'{uploaded_file.name}'"
        st.sidebar.success(f"Loaded values from {uploaded_file.name}")
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")

st.sidebar.info(f"Currently using: **{st.session_state.source}**")

# --- COMPLETE SET OF WIDGETS ---
st.sidebar.subheader("Battery - Technical Specs")
st.session_state.inputs['battery_power_kw'] = st.sidebar.number_input("Power (kW)", value=st.session_state.inputs['battery_power_kw'])
st.session_state.inputs['battery_capacity_kwh'] = st.sidebar.number_input("Storage Capacity (kWh)", value=st.session_state.inputs['battery_capacity_kwh'])
st.session_state.inputs['battery_degradation'] = st.sidebar.slider("Annual Degradation (%)", 0.0, 10.0, st.session_state.inputs['battery_degradation'] * 100) / 100

st.sidebar.subheader("PV-System - Technical Specs")
st.session_state.inputs['pv_power_per_panel_wp'] = st.sidebar.number_input("Power per Panel (Wp)", value=st.session_state.inputs['pv_power_per_panel_wp'])
st.session_state.inputs['pv_panel_count'] = st.sidebar.number_input("Number of Panels", value=st.session_state.inputs['pv_panel_count'])
st.session_state.inputs['pv_full_load_hours'] = st.sidebar.number_input("Full Load Hours (kWh/kWp)", value=st.session_state.inputs['pv_full_load_hours'])

st.sidebar.subheader("Unit Costs & Main Revenue")
st.session_state.inputs['bess_price_per_kwh'] = st.sidebar.number_input("BESS Price (€/kWh)", value=st.session_state.inputs['bess_price_per_kwh'])
st.session_state.inputs['pv_price_per_wp'] = st.sidebar.number_input("PV Price (€/Wp)", value=st.session_state.inputs['pv_price_per_wp'])
st.session_state.inputs['base_trading_income_per_mw_year'] = st.sidebar.number_input("Trading Income (€/MW/year)", value=st.session_state.inputs['base_trading_income_per_mw_year'])

with st.sidebar.expander("Financial, Tax & OPEX Assumptions"):
    st.subheader('General Financial')
    st.session_state.inputs['project_term'] = st.slider('Project Term (years)', 5, 25, st.session_state.inputs['project_term'])
    st.session_state.inputs['inflation'] = st.slider('Annual Inflation Rate (%)', 0.0, 10.0, st.session_state.inputs['inflation'] * 100) / 100
    st.session_state.inputs['wacc'] = st.slider('WACC (%)', 5.0, 15.0, st.session_state.inputs['wacc'] * 100) / 100
    st.session_state.inputs['depr_period_battery'] = st.slider('Battery Depreciation Period', 5, 20, st.session_state.inputs['depr_period_battery'])
    st.session_state.inputs['depr_period_pv'] = st.slider('PV Depreciation Period', 10, 25, st.session_state.inputs['depr_period_pv'])
    
    st.subheader('Tax')
    st.session_state.inputs['tax_threshold'] = st.number_input('Tax Threshold (€)', value=st.session_state.inputs['tax_threshold'])
    st.session_state.inputs['tax_rate_1'] = st.slider('Tax Rate 1 (%)', 10.0, 30.0, st.session_state.inputs['tax_rate_1'] * 100) / 100
    st.session_state.inputs['tax_rate_2'] = st.slider('Tax Rate 2 (%)', 10.0, 30.0, st.session_state.inputs['tax_rate_2'] * 100) / 100
    
    st.subheader('Detailed OPEX & Grid Costs (€/year)')
    st.session_state.inputs['opex_battery_om'] = st.number_input("Battery O&M", value=st.session_state.inputs['opex_battery_om'])
    st.session_state.inputs['opex_battery_asset_mgmt'] = st.number_input("Battery Asset Mngmt", value=st.session_state.inputs['opex_battery_asset_mgmt'])
    st.session_state.inputs['opex_pv_insurance'] = st.number_input("PV Insurance", value=st.session_state.inputs['opex_pv_insurance'])
    st.session_state.inputs['grid_kw_max'] = st.number_input("Grid kW Max Cost", value=st.session_state.inputs['grid_kw_max'])

# --- LIVE CALCULATIONS ---
st.sidebar.subheader("Live Calculated Values")
i = st.session_state.inputs
total_pv_peak_power_kw = (i['pv_power_per_panel_wp'] * i['pv_panel_count']) / 1000
pv_capex = total_pv_peak_power_kw * 1000 * i['pv_price_per_wp']
battery_capex = i['battery_capacity_kwh'] * i['bess_price_per_kwh']
base_trading_income = (i['battery_power_kw'] / 1000) * i['base_trading_income_per_mw_year']
st.sidebar.metric("Total PV Peak Power (kWp)", f"{total_pv_peak_power_kw:,.0f}")
st.sidebar.metric("Calculated PV CAPEX (€)", f"{pv_capex:,.0f}")
st.sidebar.metric("Calculated Battery CAPEX (€)", f"{battery_capex:,.0f}")

# --- RUN MODEL BUTTON ---
if st.sidebar.button('Run Model'):
    inputs_to_run = i.copy()
    inputs_to_run['pv_capex'] = pv_capex
    inputs_to_run['battery_capex'] = battery_capex
    inputs_to_run['base_trading_income'] = base_trading_income
    
    opex_keys = [k for k in i if k.startswith('opex_')]
    grid_keys = [k for k in i if k.startswith('grid_')]
    inputs_to_run['base_opex_sum'] = sum(i[k] for k in opex_keys)
    inputs_to_run['base_grid_costs'] = sum(i[k] for k in grid_keys)

    results_df, metrics = run_financial_model(inputs_to_run)
    
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
    display_df = results_df[['ebitda', 'depreciation', 'profit_before_tax', 'net_cash_flow', 'cumulative_cash_flow']].copy()
    st.dataframe(display_df.style.format("€{:,.0f}"))
else:
    st.info('Adjust inputs or upload a CSV, then click "Run Model".')
