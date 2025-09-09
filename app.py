%%writefile app.py

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(layout="wide")

# --- COMPLETE Hardcoded default values ---
HARDCODED_DEFAULTS = {
    'project_term': 10, 'depr_period_battery': 10, 'depr_period_pv': 15,
    'lifespan_battery': 10, 'lifespan_pv': 25, 'inflation': 0.02,
    'tax_threshold': 200000, 'tax_rate_1': 0.19, 'tax_rate_2': 0.258,
    'debt_senior_pct': 0.0, 'debt_junior_pct': 0.0, 'irr_equity_req': 0.1,
    'interest_rate_senior': 0.06, 'interest_rate_junior': 0.08,
    'grid_connection_old': 'Liander t/m 2.000 kVA', 'grid_connection_new': 'Liander t/m 2.000 kVA',
    'kw_max_old': 195, 'kw_contract_old': 250, 'kw_max_new': 250, 'kw_contract_new': 250,

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

# --- Data Loading and KPI Functions ---
@st.cache_data
def load_connection_data():
    try:
        return pd.read_csv('connections.csv')
    except FileNotFoundError:
        return None

def calculate_bess_kpis(i):
    kpis = {}
    kpis['Capacity Factor'] = i['bess_capacity_kwh'] / i['bess_power_kw'] if i['bess_power_kw'] > 0 else 0
    kpis['SoC Available'] = i['bess_max_soc'] - i['bess_min_soc']
    kpis['Usable Capacity'] = i['bess_capacity_kwh'] * kpis['SoC Available']
    kpis['C-Rate'] = i['bess_power_kw'] / kpis['Usable Capacity'] if kpis['Usable Capacity'] > 0 else 0
    kpis['Round Trip Efficiency (RTE)'] = i['bess_charging_eff'] * i['bess_discharging_eff']
    kpis['Offtake from Grid (Year 1)'] = i['bess_cycles_per_year'] * kpis['Usable Capacity'] / i['bess_charging_eff']
    kpis['Purchase Costs'] = i['bess_capacity_kwh'] * i['bess_capex_per_kwh']
    kpis['IT & Security Costs'] = i['bess_capacity_kwh'] * (i['bess_capex_it_per_kwh'] + i['bess_capex_security_per_kwh'])
    base_capex = kpis['Purchase Costs'] + kpis['IT & Security Costs']
    kpis['Civil Works'] = base_capex * i['bess_capex_civil_pct']
    capex_subtotal = base_capex + kpis['Civil Works']
    kpis['Permits & Fees'] = capex_subtotal * i['bess_capex_permits_pct']
    kpis['Project Management'] = capex_subtotal * i['bess_capex_mgmt_pct']
    kpis['Contingency'] = capex_subtotal * i['bess_capex_contingency_pct']
    kpis['bess_total_capex'] = capex_subtotal + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
    kpis['bess_base_trading_income'] = (i['bess_power_kw'] / 1000) * i['bess_income_trading_per_mw_year']
    kpis['Control Party Costs'] = kpis['bess_base_trading_income'] * i['bess_income_ctrl_party_pct']
    kpis['Energy Supplier Costs'] = (kpis['Offtake from Grid (Year 1)'] / 1000) * i['bess_income_supplier_cost_per_mwh']
    kpis['Asset Management'] = (i['bess_power_kw'] / 1000) * i['bess_opex_asset_mgmt_per_mw_year']
    kpis['Insurance'] = kpis['bess_total_capex'] * i['bess_opex_insurance_pct']
    kpis['Property Tax'] = kpis['bess_total_capex'] * i['bess_opex_property_tax_pct']
    kpis['Overhead'] = i['bess_capacity_kwh'] * i['bess_opex_overhead_per_kwh_year']
    kpis['Other OPEX'] = i['bess_capacity_kwh'] * i['bess_opex_other_per_kwh_year']
    kpis['bess_total_opex_y1'] = i['bess_opex_om_per_year'] + kpis['Asset Management'] + kpis['Insurance'] + kpis['Property Tax'] + kpis['Overhead'] + kpis['Other OPEX']
    return kpis

def calculate_pv_kpis(i):
    kpis = {}
    kpis['Total Peak Power'] = (i['pv_power_per_panel_wp'] * i['pv_panel_count']) / 1000
    kpis['Production (Year 1)'] = kpis['Total Peak Power'] * i['pv_full_load_hours']
    kpis['Purchase Costs'] = kpis['Total Peak Power'] * 1000 * i['pv_capex_per_wp']
    capex_subtotal = kpis['Purchase Costs']
    kpis['Civil Works'] = capex_subtotal * i['pv_capex_civil_pct']
    capex_subtotal += kpis['Civil Works']
    kpis['Security'] = capex_subtotal * i['pv_capex_security_pct']
    kpis['Permits & Fees'] = capex_subtotal * i['pv_capex_permits_pct']
    kpis['Project Management'] = capex_subtotal * i['pv_capex_mgmt_pct']
    kpis['Contingency'] = capex_subtotal * i['pv_capex_contingency_pct']
    kpis['pv_total_capex'] = capex_subtotal + kpis['Security'] + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
    kpis['PPA Income'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_ppa_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_ppa_per_kwh'])
    kpis['Curtailment Income'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_curtailment_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_curtailment_per_kwh'])
    kpis['Insurance'] = kpis['pv_total_capex'] * i['pv_opex_insurance_pct']
    kpis['Property Tax'] = kpis['pv_total_capex'] * i['pv_opex_property_tax_pct']
    kpis['Overhead'] = kpis['pv_total_capex'] * i['pv_opex_overhead_pct']
    kpis['Other OPEX'] = kpis['pv_total_capex'] * i['pv_opex_other_pct']
    kpis['pv_total_opex_y1'] = kpis['Insurance'] + kpis['Property Tax'] + kpis['Overhead'] + kpis['Other OPEX']
    return kpis

def run_financial_model(inputs, project_type):
    years = np.arange(1, int(inputs['project_term']) + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'
    is_bess = 'BESS' in project_type; is_pv = 'PV' in project_type
    df['inflation_factor'] = (1 + inputs['inflation']) ** (df.index - 1)
    df['bess_degradation_factor'] = (1 + inputs['bess_annual_degradation']) ** (df.index - 1) if is_bess else 1
    df['pv_degradation_factor'] = (1 - inputs['pv_annual_degradation']) ** (df.index - 1) if is_pv else 1
    df['bess_trading_income'] = (inputs.get('bess_base_trading_income', 0) * df['bess_degradation_factor']) if is_bess else 0
    df['bess_control_party_costs'] = -df['bess_trading_income'] * inputs.get('bess_income_ctrl_party_pct', 0)
    df['bess_supplier_costs'] = -inputs.get('Energy Supplier Costs', 0) * df['bess_degradation_factor'] * df['inflation_factor']
    df['pv_ppa_income'] = (inputs.get('PPA Income',0) * df['pv_degradation_factor'] * df['inflation_factor']) if is_pv else 0
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
    fig1 = px.bar(df_results, x=df_results.index, y='net_cash_flow', title="Annual Net Cash Flow")
    fig1.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    cumulative_data = pd.DataFrame({'Year': np.arange(0, len(df_results) + 1), 'Cumulative Cash Flow': np.concatenate([[-total_capex], df_results['cumulative_cash_flow'].values])})
    fig2 = px.line(cumulative_data, x='Year', y='Cumulative Cash Flow', title="Cumulative Cash Flow", markers=True)
    fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even")
    fig2.update_layout(title_x=0.5, yaxis_tickprefix="€", yaxis_tickformat="~s")
    return fig1, fig2

def generate_cost_breakdown_charts(kpis, prefix):
    capex_data = {k: v for k, v in kpis.items() if ('Costs' in k or 'Works' in k or 'Security' in k or 'Permits' in k or 'Management' in k or 'Contingency' in k) and v > 0}
    df_capex = pd.DataFrame(list(capex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
    fig_capex = px.pie(df_capex, values='Cost', names='Component', title=f'{prefix.upper()} CAPEX Breakdown', hole=.3)
    opex_data = {k: v for k, v in kpis.items() if k in ['Insurance', 'Property Tax', 'Overhead', 'Other OPEX', 'Asset Management']}
    df_opex = pd.DataFrame(list(opex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
    fig_opex = px.pie(df_opex, values='Cost', names='Component', title=f'{prefix.upper()} OPEX (Year 1) Breakdown', hole=.3)
    return fig_capex, fig_opex

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
st.title('Flink EMS: BESS & PV Financial Model ☀️🔋')

connection_data = load_connection_data()
i = st.session_state.inputs

st.sidebar.title("Configuration")
st.session_state.project_type = st.sidebar.selectbox("Select Project Type", ["BESS & PV", "BESS-only", "PV-only"])

uploaded_file = st.sidebar.file_uploader("Upload CSV to Override All Inputs", type=['csv'])
if uploaded_file:
    st.sidebar.success(f"CSV '{uploaded_file.name}' logic would be here.")

if 'BESS' in st.session_state.project_type:
    st.sidebar.header("🔋 BESS Inputs")
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

if 'PV' in st.session_state.project_type:
    st.sidebar.header("☀️ PV Inputs")
    with st.sidebar.expander("Technical Inputs (PV)"):
        # Full PV input widgets...
        pass
    with st.sidebar.expander("CAPEX Assumptions (PV)"):
        # Full PV CAPEX widgets...
        pass
    with st.sidebar.expander("Income Assumptions (PV)"):
        # Full PV Income widgets...
        pass
    with st.sidebar.expander("OPEX Assumptions (PV)"):
        # Full PV OPEX widgets...
        pass

with st.sidebar.expander("General & Financial", expanded=True):
    st.subheader("Time / Duration")
    i['project_term'] = st.slider("Project Term", 5, 30, i['project_term'], key='g_term')
    if 'BESS' in st.session_state.project_type: i['depr_period_battery'] = st.slider("Depreciation BESS", 5, 20, i['depr_period_battery'], key='g_depr_b')
    if 'BESS' in st.session_state.project_type: i['lifespan_battery'] = st.slider("Lifespan BESS", 5, 25, i['lifespan_battery'], key='g_life_b')
    if 'PV' in st.session_state.project_type: i['depr_period_pv'] = st.slider("Depreciation PV", 10, 30, i['depr_period_pv'], key='g_depr_pv')
    if 'PV' in st.session_state.project_type: i['lifespan_pv'] = st.slider("Lifespan PV", 10, 30, i['lifespan_pv'], key='g_life_pv')

    st.subheader("Financing")
    i['debt_senior_pct'] = st.slider("Debt (senior) (%)", 0.0, 100.0, i['debt_senior_pct'] * 100, key='fin_ds') / 100
    i['debt_junior_pct'] = st.slider("Debt (junior) (%)", 0.0, 100.0, i['debt_junior_pct'] * 100, key='fin_dj') / 100
    equity = 1 - i['debt_senior_pct'] - i['debt_junior_pct']
    st.metric("Equity", f"{equity:.1%}")
    i['irr_equity_req'] = st.slider("IRR requirement (equity) (%)", 5.0, 20.0, i['irr_equity_req'] * 100, key='fin_irr') / 100
    i['interest_rate_senior'] = st.slider("Interest rate (senior) (%)", 2.0, 12.0, i['interest_rate_senior'] * 100, key='fin_int_s') / 100
    i['interest_rate_junior'] = st.slider("Interest rate (junior) (%)", 4.0, 15.0, i['interest_rate_junior'] * 100, key='fin_int_j') / 100
    wacc = (equity * i['irr_equity_req']) + (i['debt_senior_pct'] * i['interest_rate_senior']) + (i['debt_junior_pct'] * i['interest_rate_junior'])
    st.metric("WACC", f"{wacc:.2%}")

    st.subheader("Inflation & Tax")
    i['inflation'] = st.slider('Inflation (%)', 0.0, 10.0, i['inflation'] * 100, key='g_inf') / 100
    st.subheader("Corporate Tax Threshold")
    st.markdown("| Threshold | Tariff |\n|---|---|\n| Up to €200,000 | 19.0% |\n| Above €200,000 | 25.8% |")

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
        st.header('Interactive Charts')
        fig1, fig2 = generate_interactive_charts(results_df, metrics['Total Investment'])
        st.plotly_chart(fig2, use_container_width=True)
        st.plotly_chart(fig1, use_container_width=True)
        st.header('Annual Projections Table')
        display_df = results_df[['ebitda', 'depreciation', 'net_cash_flow', 'cumulative_cash_flow']].copy()
        st.dataframe(display_df.style.format("€{:,.0f}"), use_container_width=True)

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
            # Full PV KPI display logic would be here
            pass
else:
    st.info('Adjust inputs and click "Run Model".')
