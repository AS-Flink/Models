
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
    'bess_power_kw': 2000, 'bess_capacity_kwh': 4000, 'bess_min_soc': 0.05,
    'bess_max_soc': 0.95, 'bess_charging_eff': 0.92, 'bess_discharging_eff': 0.92,
    'bess_annual_degradation': 0.04, 'bess_cycles_per_year': 600,
    'bess_capex_per_kwh': 116.3, 'bess_capex_civil_pct': 0.06, 'bess_capex_it_per_kwh': 1.5,
    'bess_capex_security_per_kwh': 5.0, 'bess_capex_permits_pct': 0.015,
    'bess_capex_mgmt_pct': 0.025, 'bess_capex_contingency_pct': 0.05,
    'bess_income_trading_per_mw_year': 243254, 'bess_income_ctrl_party_pct': 0.1,
    'bess_income_supplier_cost_per_mwh': 2.0, 'bess_opex_om_per_year': 4652.0,
    'bess_opex_asset_mgmt_per_mw_year': 4000.0, 'bess_opex_insurance_pct': 0.01,
    'bess_opex_property_tax_pct': 0.001, 'bess_opex_overhead_per_kwh_year': 1.0,
    'bess_opex_other_per_kwh_year': 1.0,

    # --- PV Parameters ---
    'pv_power_per_panel_wp': 590, 'pv_panel_count': 3479, 'pv_full_load_hours': 817.8,
    'pv_annual_degradation': 0.005, 'pv_capex_per_wp': 0.2, 'pv_capex_civil_pct': 0.08,
    'pv_capex_security_pct': 0.02, 'pv_capex_permits_pct': 0.01,
    'pv_capex_mgmt_pct': 0.025, 'pv_capex_contingency_pct': 0.05,
    'pv_income_ppa_per_mwp': 0.0, 'pv_income_ppa_per_kwh': 0.0,
    'pv_income_curtailment_per_mwp': 0.0, 'pv_income_curtailment_per_kwh': 0.0,
    'pv_opex_insurance_pct': 0.01, 'pv_opex_property_tax_pct': 0.001,
    'pv_opex_overhead_pct': 0.005, 'pv_opex_other_pct': 0.005
}

# --- Session State Initialization ---
if 'inputs' not in st.session_state:
    st.session_state.inputs = HARDCODED_DEFAULTS.copy()
    st.session_state.project_type = "BESS & PV"

# --- KPI Calculation Functions ---
def calculate_bess_kpis(i):
    kpis = {}
    # Technical KPIs
    kpis['Capacity Factor'] = i['bess_capacity_kwh'] / i['bess_power_kw'] if i['bess_power_kw'] > 0 else 0
    kpis['SoC Available'] = i['bess_max_soc'] - i['bess_min_soc']
    kpis['Usable Capacity'] = i['bess_capacity_kwh'] * kpis['SoC Available']
    kpis['C-Rate'] = i['bess_power_kw'] / kpis['Usable Capacity'] if kpis['Usable Capacity'] > 0 else 0
    kpis['Round Trip Efficiency (RTE)'] = i['bess_charging_eff'] * i['bess_discharging_eff']
    kpis['Offtake from Grid (Year 1)'] = i['bess_cycles_per_year'] * kpis['Usable Capacity'] / i['bess_charging_eff']
    # CAPEX KPIs
    kpis['Purchase Costs'] = i['bess_capacity_kwh'] * i['bess_capex_per_kwh']
    kpis['IT & Security Costs'] = i['bess_capacity_kwh'] * (i['bess_capex_it_per_kwh'] + i['bess_capex_security_per_kwh'])
    base_capex = kpis['Purchase Costs'] + kpis['IT & Security Costs']
    kpis['Civil Works'] = base_capex * i['bess_capex_civil_pct']
    capex_subtotal = base_capex + kpis['Civil Works']
    kpis['Permits & Fees'] = capex_subtotal * i['bess_capex_permits_pct']
    kpis['Project Management'] = capex_subtotal * i['bess_capex_mgmt_pct']
    kpis['Contingency'] = capex_subtotal * i['bess_capex_contingency_pct']
    kpis['bess_total_capex'] = capex_subtotal + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
    # Income KPIs
    kpis['bess_base_trading_income'] = (i['bess_power_kw'] / 1000) * i['bess_income_trading_per_mw_year']
    kpis['Control Party Costs'] = kpis['bess_base_trading_income'] * i['bess_income_ctrl_party_pct']
    kpis['Energy Supplier Costs'] = (kpis['Offtake from Grid (Year 1)'] / 1000) * i['bess_income_supplier_cost_per_mwh']
    # OPEX KPIs
    kpis['Asset Management'] = (i['bess_power_kw'] / 1000) * i['bess_opex_asset_mgmt_per_mw_year']
    kpis['Insurance'] = kpis['bess_total_capex'] * i['bess_opex_insurance_pct']
    kpis['Property Tax'] = kpis['bess_total_capex'] * i['bess_opex_property_tax_pct']
    kpis['Overhead'] = i['bess_capacity_kwh'] * i['bess_opex_overhead_per_kwh_year']
    kpis['Other OPEX'] = i['bess_capacity_kwh'] * i['bess_opex_other_per_kwh_year']
    kpis['bess_total_opex_y1'] = i['bess_opex_om_per_year'] + kpis['Asset Management'] + kpis['Insurance'] + kpis['Property Tax'] + kpis['Overhead'] + kpis['Other OPEX']
    return kpis

def calculate_pv_kpis(i):
    kpis = {}
    # Technical KPIs
    kpis['Total Peak Power'] = (i['pv_power_per_panel_wp'] * i['pv_panel_count']) / 1000
    kpis['Production (Year 1)'] = kpis['Total Peak Power'] * i['pv_full_load_hours']
    # CAPEX KPIs
    kpis['Purchase Costs'] = kpis['Total Peak Power'] * 1000 * i['pv_capex_per_wp']
    capex_subtotal = kpis['Purchase Costs']
    kpis['Civil Works'] = capex_subtotal * i['pv_capex_civil_pct']
    capex_subtotal += kpis['Civil Works']
    kpis['Security'] = capex_subtotal * i['pv_capex_security_pct']
    kpis['Permits & Fees'] = capex_subtotal * i['pv_capex_permits_pct']
    kpis['Project Management'] = capex_subtotal * i['pv_capex_mgmt_pct']
    kpis['Contingency'] = capex_subtotal * i['pv_capex_contingency_pct']
    kpis['pv_total_capex'] = capex_subtotal + kpis['Security'] + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
    # Income KPIs
    kpis['PPA Income'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_ppa_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_ppa_per_kwh'])
    kpis['Curtailment Income'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_curtailment_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_curtailment_per_kwh'])
    # OPEX KPIs
    kpis['Insurance'] = kpis['pv_total_capex'] * i['pv_opex_insurance_pct']
    kpis['Property Tax'] = kpis['pv_total_capex'] * i['pv_opex_property_tax_pct']
    kpis['Overhead'] = kpis['pv_total_capex'] * i['pv_opex_overhead_pct']
    kpis['Other OPEX'] = kpis['pv_total_capex'] * i['pv_opex_other_pct']
    kpis['pv_total_opex_y1'] = kpis['Insurance'] + kpis['Property Tax'] + kpis['Overhead'] + kpis['Other OPEX']
    return kpis

# --- Core Financial & Charting Functions ---
def run_financial_model(inputs, project_type):
    years = np.arange(1, int(inputs['project_term']) + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'
    is_bess_active = 'BESS' in project_type; is_pv_active = 'PV' in project_type
    df['inflation_factor'] = (1 + inputs['inflation']) ** (df.index - 1)
    df['bess_degradation_factor'] = (1 + inputs['bess_annual_degradation']) ** (df.index - 1) if is_bess_active else 1
    df['pv_degradation_factor'] = (1 - inputs['pv_annual_degradation']) ** (df.index - 1) if is_pv_active else 1
    df['bess_trading_income'] = (inputs.get('bess_base_trading_income', 0) * df['bess_degradation_factor']) if is_bess_active else 0
    df['bess_control_party_costs'] = -df['bess_trading_income'] * inputs.get('bess_income_ctrl_party_pct', 0)
    df['bess_supplier_costs'] = -inputs.get('Energy Supplier Costs', 0) * df['bess_degradation_factor'] * df['inflation_factor']
    df['pv_ppa_income'] = (inputs.get('PPA Income',0) * df['pv_degradation_factor'] * df['inflation_factor']) if is_pv_active else 0
    df['bess_opex'] = -inputs.get('bess_total_opex_y1', 0) * df['inflation_factor'] if is_bess_active else 0
    df['pv_opex'] = -inputs.get('pv_total_opex_y1', 0) * df['inflation_factor'] if is_pv_active else 0
    income_cols = ['bess_trading_income', 'bess_control_party_costs', 'bess_supplier_costs', 'pv_ppa_income', 'bess_opex', 'pv_opex']
    df['ebitda'] = df[income_cols].sum(axis=1)
    annual_depr_battery = (inputs.get('bess_total_capex', 0) / inputs['depr_period_battery']) if is_bess_active else 0
    annual_depr_pv = (inputs.get('pv_total_capex', 0) / inputs['depr_period_pv']) if is_pv_active else 0
    df['depreciation'] = 0
    if is_bess_active: df.loc[df.index <= inputs['depr_period_battery'], 'depreciation'] += annual_depr_battery
    if is_pv_active: df.loc[df.index <= inputs['depr_period_pv'], 'depreciation'] += annual_depr_pv
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
    fig1 = px.bar(df_results, x=df_results.index, y='net_cash_flow', title="Annual Net Cash Flow")
    fig1.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    cumulative_data = pd.DataFrame({'Year': np.arange(0, len(df_results) + 1), 'Cumulative Cash Flow': np.concatenate([[-total_capex], df_results['cumulative_cash_flow'].values])})
    fig2 = px.line(cumulative_data, x='Year', y='Cumulative Cash Flow', title="Cumulative Cash Flow", markers=True)
    fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    fig2.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    return fig1, fig2

def generate_cost_breakdown_charts(kpis, prefix):
    capex_data = {k: v for k, v in kpis.items() if 'Costs' in k or 'Works' in k or 'Security' in k or 'Permits' in k or 'Management' in k or 'Contingency' in k and v > 0}
    df_capex = pd.DataFrame(list(capex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
    fig_capex = px.pie(df_capex, values='Cost', names='Component', title=f'{prefix.upper()} CAPEX Breakdown', hole=.3)
    
    opex_data = {k: v for k, v in kpis.items() if k in ['Insurance', 'Property Tax', 'Overhead', 'Other OPEX', 'Asset Management']}
    df_opex = pd.DataFrame(list(opex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
    fig_opex = px.pie(df_opex, values='Cost', names='Component', title=f'{prefix.upper()} OPEX (Year 1) Breakdown', hole=.3)
    return fig_capex, fig_opex

# --- NEW: Corrected KPI DataFrame Function ---
def create_kpi_dataframe(kpis, kpi_map):
    data = []
    for section, keys in kpi_map.items():
        data.append({'Metric': f'--- {section} ---', 'Value': ''})
        for key, unit in keys.items():
            if key in kpis:
                value = kpis[key]
                if unit == "€": formatted_value = f"€ {value:,.0f}"
                elif unit == "%": formatted_value = f"{value:.2%}"
                elif unit == "h": formatted_value = f"{value:.2f} h"
                elif unit == "kWh" or unit == "kWp": formatted_value = f"{value:,.0f} {unit}"
                else: formatted_value = f"{value:,.2f}"
                data.append({'Metric': key, 'Value': formatted_value})
    return pd.DataFrame(data).set_index('Metric')

# --- Main Application UI and Logic ---
st.title('Flink Nederland EMS ☀️🔋')
st.sidebar.title("Configuration")
st.session_state.project_type = st.sidebar.selectbox("Select Project Type", ["BESS & PV", "BESS-only", "PV-only"])
i = st.session_state.inputs
uploaded_file = st.sidebar.file_uploader("Upload CSV to Override Inputs", type=['csv'])
if uploaded_file:
    st.sidebar.success("CSV Uploaded (Full parsing logic would be implemented here)")

# --- BESS INPUTS ---
if 'BESS' in st.session_state.project_type:
    st.sidebar.header("🔋 Battery Energy Storage System")
    with st.sidebar.expander("Technical Inputs (BESS)", expanded=False):
        i['bess_power_kw'] = st.number_input("Power (kW)", value=i['bess_power_kw'], help="Maximum charge/discharge power.", key='bess_p_kw')
        i['bess_capacity_kwh'] = st.number_input("Capacity (kWh)", value=i['bess_capacity_kwh'], help="Total nominal energy capacity.", key='bess_c_kwh')
        i['bess_min_soc'], i['bess_max_soc'] = st.slider("Operating SoC Range", 0.0, 1.0, (i['bess_min_soc'], i['bess_max_soc']), help="Min and Max State of Charge.", key='bess_soc')
        i['bess_charging_eff'] = st.slider("Charging Efficiency", 0.80, 1.00, i['bess_charging_eff'], step=0.01, key='bess_chg_eff')
        i['bess_discharging_eff'] = st.slider("Discharging Efficiency", 0.80, 1.00, i['bess_discharging_eff'], step=0.01, key='bess_dis_eff')
        i['bess_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 10.0, i['bess_annual_degradation'] * 100, key='bess_deg') / 100
        i['bess_cycles_per_year'] = st.number_input("Cycles per Year", value=i['bess_cycles_per_year'], key='bess_cycles')
    with st.sidebar.expander("CAPEX Assumptions (BESS)"):
        i['bess_capex_per_kwh'] = st.number_input("BESS Price (€/kWh)", value=i['bess_capex_per_kwh'], key='bess_capex_price')
        i['bess_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['bess_capex_civil_pct'] * 100, key='bess_capex_civil') / 100
        i['bess_capex_it_per_kwh'] = st.number_input("IT/Control (€/kWh)", value=i['bess_capex_it_per_kwh'], key='bess_capex_it')
        i['bess_capex_security_per_kwh'] = st.number_input("Security (€/kWh)", value=i['bess_capex_security_per_kwh'], key='bess_capex_sec')
        i['bess_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['bess_capex_permits_pct'] * 100, key='bess_capex_perm') / 100
        i['bess_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['bess_capex_mgmt_pct'] * 100, key='bess_capex_mgmt') / 100
        i['bess_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['bess_capex_contingency_pct'] * 100, key='bess_capex_cont') / 100
    with st.sidebar.expander("Income Assumptions (BESS)"):
        i['bess_income_trading_per_mw_year'] = st.number_input("Trading Income (€/MW/year)", value=i['bess_income_trading_per_mw_year'], key='bess_inc_trad')
        i['bess_income_ctrl_party_pct'] = st.slider("Control Party Costs (% of Income)", 0.0, 25.0, i['bess_income_ctrl_party_pct'] * 100, key='bess_inc_ctrl') / 100
        i['bess_income_supplier_cost_per_mwh'] = st.number_input("Energy Supplier Costs (€/MWh)", value=i['bess_income_supplier_cost_per_mwh'], key='bess_inc_supp')
    with st.sidebar.expander("OPEX Assumptions (BESS)"):
        i['bess_opex_om_per_year'] = st.number_input("O&M (€/year)", value=i['bess_opex_om_per_year'], key='bess_opex_om')
        i['bess_opex_asset_mgmt_per_mw_year'] = st.number_input("Asset Management (€/MW/year)", value=i['bess_opex_asset_mgmt_per_mw_year'], key='bess_opex_am')
        i['bess_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['bess_opex_insurance_pct'] * 100, key='bess_opex_ins') / 100
        i['bess_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['bess_opex_property_tax_pct'] * 100, format="%.3f", key='bess_opex_tax') / 100
        i['bess_opex_overhead_per_kwh_year'] = st.number_input("Overhead (€/kWh/year)", value=i['bess_opex_overhead_per_kwh_year'], key='bess_opex_over')
        i['bess_opex_other_per_kwh_year'] = st.number_input("Other (€/kWh/year)", value=i['bess_opex_other_per_kwh_year'], key='bess_opex_oth')

# --- PV INPUTS ---
if 'PV' in st.session_state.project_type:
    st.sidebar.header("☀️ Solar PV System")
    help_ppa = "Enter a value in the \"PPA Revenue / MWp\" field to calculate the \"PPA Revenue in Year 1\" based on expected revenue per MWp. Enter a value in the \"PPA Revenue / kWh\" field to calculate the \"PPA Revenue in Year 1\" based on expected revenue per kWh. One of the two fields must be empty."
    help_curtailment = "Enter a value in the \"Curtailment Income / MWp\" field to calculate the \"Curtailment Income in Year 1\" based on expected income per MWp. Enter a value in the \"Curtailment Income / kWh\" field to calculate the \"Curtailment Income in Year 1\" based on expected income per kWh. One of the two fields must be empty."
    with st.sidebar.expander("Technical Inputs (PV)", expanded=False):
        i['pv_panel_count'] = st.number_input("Number of Panels", value=i['pv_panel_count'], key='pv_panel_c')
        i['pv_power_per_panel_wp'] = st.number_input("Power per Panel (Wp)", value=i['pv_power_per_panel_wp'], key='pv_ppp_wp')
        i['pv_full_load_hours'] = st.number_input("Full Load Hours (kWh/kWp)", value=i['pv_full_load_hours'], key='pv_flh')
        i['pv_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 2.0, i['pv_annual_degradation'] * 100, format="%.2f", key='pv_deg') / 100
    with st.sidebar.expander("CAPEX Assumptions (PV)"):
        i['pv_capex_per_wp'] = st.number_input("PV Price (€/Wp)", value=i['pv_capex_per_wp'], format="%.3f", key='pv_capex_price')
        i['pv_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['pv_capex_civil_pct'] * 100, key='pv_capex_civil') / 100
        i['pv_capex_security_pct'] = st.slider("Security (%)", 0.0, 10.0, i['pv_capex_security_pct'] * 100, key='pv_capex_sec') / 100
        i['pv_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['pv_capex_permits_pct'] * 100, key='pv_capex_perm') / 100
        i['pv_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['pv_capex_mgmt_pct'] * 100, key='pv_capex_mgmt') / 100
        i['pv_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['pv_capex_contingency_pct'] * 100, key='pv_capex_cont') / 100
    with st.sidebar.expander("Income Assumptions (PV)"):
        i['pv_income_ppa_per_mwp'] = st.number_input("Income PPA (€/MWp)", value=i['pv_income_ppa_per_mwp'], help=help_ppa, key='pv_inc_ppa_mwp')
        i['pv_income_ppa_per_kwh'] = st.number_input("Income PPA (€/kWh)", value=i['pv_income_ppa_per_kwh'], help=help_ppa, format="%.4f", key='pv_inc_ppa_kwh')
        i['pv_income_curtailment_per_mwp'] = st.number_input("Income Curtailment (€/MWp)", value=i['pv_income_curtailment_per_mwp'], help=help_curtailment, key='pv_inc_curt_mwp')
        i['pv_income_curtailment_per_kwh'] = st.number_input("Income Curtailment (€/kWh)", value=i['pv_income_curtailment_per_kwh'], help=help_curtailment, format="%.4f", key='pv_inc_curt_kwh')
    with st.sidebar.expander("OPEX Assumptions (PV)"):
        i['pv_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['pv_opex_insurance_pct'] * 100, key='pv_opex_ins') / 100
        i['pv_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['pv_opex_property_tax_pct'] * 100, format="%.3f", key='pv_opex_tax') / 100
        i['pv_opex_overhead_pct'] = st.slider("Overhead (% of CAPEX)", 0.0, 2.0, i['pv_opex_overhead_pct'] * 100, format="%.3f", key='pv_opex_over') / 100
        i['pv_opex_other_pct'] = st.slider("Other (% of CAPEX)", 0.0, 2.0, i['pv_opex_other_pct'] * 100, format="%.3f", key='pv_opex_oth') / 100

# --- General Financial Inputs ---
st.sidebar.header("General & Financial")
with st.sidebar.expander("Project Term, Depreciation & Finance"):
    i['project_term'] = st.slider('Project Term (years)', 5, 30, i['project_term'], key='g_term')
    if 'BESS' in st.session_state.project_type: i['depr_period_battery'] = st.slider('BESS Depreciation Period', 5, 20, i['depr_period_battery'], key='g_depr_b')
    if 'PV' in st.session_state.project_type: i['depr_period_pv'] = st.slider('PV Depreciation Period', 10, 30, i['depr_period_pv'], key='g_depr_pv')
    i['wacc'] = st.slider('WACC (%)', 5.0, 15.0, i['wacc'] * 100, key='g_wacc') / 100
with st.sidebar.expander("Inflation & Tax"):
    i['inflation'] = st.slider('Annual Inflation Rate (%)', 0.0, 10.0, i['inflation'] * 100, key='g_inf') / 100
    i['tax_threshold'] = st.number_input('Tax Threshold (€)', value=i['tax_threshold'], key='t_thresh')
    i['tax_rate_1'] = st.slider('Tax Rate 1 (%)', 10.0, 30.0, i['tax_rate_1'] * 100, key='t_r1') / 100
    i['tax_rate_2'] = st.slider('Tax Rate 2 (%)', 10.0, 30.0, i['tax_rate_2'] * 100, key='t_r2') / 100

# --- RUN MODEL BUTTON ---
if st.sidebar.button('Run Model', type="primary"):
    inputs_to_run = i.copy()
    bess_kpis, pv_kpis = {}, {}
    if 'BESS' in st.session_state.project_type: bess_kpis = calculate_bess_kpis(i); inputs_to_run.update(bess_kpis)
    if 'PV' in st.session_state.project_type: pv_kpis = calculate_pv_kpis(i); inputs_to_run.update(pv_kpis)
    
    results_df, metrics = run_financial_model(inputs_to_run, st.session_state.project_type)
    
    st.header('Financial Metrics')
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Investment", f"€{metrics['Total Investment']:,.0f}")
    col2.metric("Project IRR", f"{metrics['Project IRR']:.2%}")
    col3.metric("Payback Period", f"{metrics['Payback Period (years)']} years")
    col4.metric("Final Cumulative Cash Flow", f"€{metrics['Final Cumulative Cash Flow']:,.0f}")

    tab_charts, tab_bess, tab_pv = st.tabs(["📊 Financial Summary", "🔋 BESS KPIs", "☀️ PV KPIs"])
    with tab_charts:
        st.plotly_chart(generate_interactive_charts(results_df, metrics['Total Investment'])[1], use_container_width=True)
        st.plotly_chart(generate_interactive_charts(results_df, metrics['Total Investment'])[0], use_container_width=True)
        st.dataframe(results_df[['ebitda', 'depreciation', 'net_cash_flow', 'cumulative_cash_flow']].style.format("€{:,.0f}"), use_container_width=True)
    with tab_bess:
        st.header("🔋 BESS - Key Performance Indicators")
        if 'BESS' in st.session_state.project_type:
            bess_kpi_map = {
                "Technical": {'Capacity Factor': 'h', 'SoC Available': '%', 'Usable Capacity': 'kWh', 'C-Rate': '', 'Round Trip Efficiency (RTE)': '%', 'Offtake from Grid (Year 1)': 'kWh'},
                "CAPEX": {'Purchase Costs': '€', 'IT & Security Costs': '€', 'Civil Works': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€'},
                "Income (Year 1)": {'bess_base_trading_income': '€', 'Control Party Costs': '€', 'Energy Supplier Costs': '€'},
                "OPEX (Year 1)": {'Asset Management': '€', 'Insurance': '€', 'Property Tax': '€', 'Overhead': '€', 'Other OPEX': '€'}
            }
            capex_chart, opex_chart = generate_cost_breakdown_charts(bess_kpis, 'bess')
            col1, col2 = st.columns(2)
            with col1: st.plotly_chart(capex_chart, use_container_width=True)
            with col2: st.plotly_chart(opex_chart, use_container_width=True)
            for section, keys in bess_kpi_map.items():
                st.subheader(section)
                st.dataframe(create_kpi_dataframe(bess_kpis, {section: keys}), use_container_width=True)
        else: st.info("BESS not included in this project type.")
    with tab_pv:
        st.header("☀️ PV - Key Performance Indicators")
        if 'PV' in st.session_state.project_type:
            pv_kpi_map = {
                "Technical": {'Total Peak Power': 'kWp', 'Production (Year 1)': 'kWh'},
                "CAPEX": {'Purchase Costs': '€', 'Civil Works': '€', 'Security': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€'},
                "Income (Year 1)": {'PPA Income': '€', 'Curtailment Income': '€'},
                "OPEX (Year 1)": {'Insurance': '€', 'Property Tax': '€', 'Overhead': '€', 'Other OPEX': '€'}
            }
            capex_chart, opex_chart = generate_cost_breakdown_charts(pv_kpis, 'pv')
            col1, col2 = st.columns(2)
            with col1: st.plotly_chart(capex_chart, use_container_width=True)
            with col2: st.plotly_chart(opex_chart, use_container_width=True)
            for section, keys in pv_kpi_map.items():
                st.subheader(section)
                st.dataframe(create_kpi_dataframe(pv_kpis, {section: keys}), use_container_width=True)
        else: st.info("PV not included in this project type.")
else:
    st.info('Adjust inputs, optionally load a CSV, and click "Run Model".')
