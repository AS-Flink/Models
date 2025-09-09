import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import io
import json
import os
import copy # Import the copy library

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Flink EMS")

# --- DATA (Connections, Defaults) ---

@st.cache_data
def get_connection_data():
    csv_data = """name,transport_category,kw_max_offtake,kw_contract_offtake
"Liander t/m 2.000 kVA","Enexis MS-D (t/m 1.500 kW)",195,250
"Stedin > 2.000 kVA","Liander HS-A (t/m 10.000 kW)",1500,2000
"Enexis Kleinverbruik","Stedin MS-C",50,80
"Custom","Custom",0,0
"""
    return pd.read_csv(io.StringIO(csv_data))

connections_df = get_connection_data()

HARDCODED_DEFAULTS = {
    # General & Financial
    'project_term': 10, 'lifespan_battery_tech': 10, 'lifespan_pv_tech': 25,
    'depr_period_battery': 10, 'depr_period_pv': 15, 'debt_senior_pct': 0.0,
    'debt_junior_pct': 0.0, 'irr_equity_req': 0.10, 'interest_rate_senior': 0.06,
    'interest_rate_junior': 0.08, 'term_senior': 10, 'term_junior': 10,
    'inflation': 0.02, 'idx_trading_income': -0.02, 'idx_supplier_costs': 0.0,
    'idx_om_bess': 0.0, 'idx_om_pv': 0.0, 'idx_other_costs': 0.0,
    'idx_ppa_income': 0.0, 'idx_curtailment_income': 0.0, 'connection_old': "Liander t/m 2.000 kVA",
    'connection_new': "Liander t/m 2.000 kVA", 'wacc': 0.1,
    # BESS
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
    # PV
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
if 'page' not in st.session_state:
    st.session_state.page = "Home"
    st.session_state.projects = {}
    st.session_state.current_project_name = None

# --- Project Persistence Functions ---
PROJECTS_FILE = "flink_ems_projects.json"

def save_projects():
    """Saves the current projects dictionary to a JSON file."""
    with open(PROJECTS_FILE, 'w') as f:
        # ** THE FIX IS HERE: Use deepcopy to avoid changing the live session state **
        projects_for_save = copy.deepcopy(st.session_state.projects)
        
        for proj_name, proj_data in projects_for_save.items():
            if 'results' in proj_data and isinstance(proj_data['results'].get('df'), pd.DataFrame):
                proj_data['results']['df'] = proj_data['results']['df'].to_json()
        json.dump(projects_for_save, f)

def load_projects():
    """Loads projects from a JSON file into the session state."""
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            loaded_projects = json.load(f)
            for proj_name, proj_data in loaded_projects.items():
                if 'results' in proj_data and isinstance(proj_data['results'].get('df'), str):
                    proj_data['results']['df'] = pd.read_json(proj_data['results']['df'])
            st.session_state.projects = loaded_projects
        st.sidebar.success("Projects loaded!")
    else:
        st.sidebar.warning("No saved projects file found.")

# --- UI HELPER ---
def display_header(title):
    """Creates a consistent header with logo and title for each page."""
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("https://i.postimg.cc/RFgvn3Cp/LOGO-S-PRESENTATIE.webp", width=140)
    with col2:
        st.title(title)
    st.markdown("---")

# --- CORE CALCULATION & CHARTING FUNCTIONS (UNCHANGED) ---
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
    kpis['bess_om_y1'] = i['bess_opex_om_per_year']
    kpis['bess_other_opex_y1'] = kpis['Asset Management'] + kpis['Insurance'] + kpis['Property Tax'] + kpis['Overhead'] + kpis['Other OPEX']
    kpis['bess_total_opex_y1'] = kpis['bess_om_y1'] + kpis['bess_other_opex_y1']
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
    kpis['pv_total_opex_y1'] = (kpis['pv_total_capex'] * (i['pv_opex_insurance_pct'] + i['pv_opex_property_tax_pct'] + i['pv_opex_overhead_pct'] + i['pv_opex_other_pct']))
    return kpis

def run_financial_model(inputs, project_type):
    years = np.arange(1, int(inputs['project_term']) + 1)
    df = pd.DataFrame(index=years); df.index.name = 'Year'
    is_bess_active = 'BESS' in project_type; is_pv_active = 'PV' in project_type
    df['bess_degradation_factor'] = (1 - inputs['bess_annual_degradation']) ** (df.index - 1) if is_bess_active else 1
    df['pv_degradation_factor'] = (1 - inputs['pv_annual_degradation']) ** (df.index - 1) if is_pv_active else 1
    trading_income_growth = (1 + inputs['inflation'] + inputs['idx_trading_income']) ** (df.index - 1)
    supplier_costs_growth = (1 + inputs['inflation'] + inputs['idx_supplier_costs']) ** (df.index - 1)
    bess_om_growth = (1 + inputs['inflation'] + inputs['idx_om_bess']) ** (df.index - 1)
    other_costs_growth = (1 + inputs['inflation'] + inputs['idx_other_costs']) ** (df.index - 1)
    ppa_income_growth = (1 + inputs['inflation'] + inputs['idx_ppa_income']) ** (df.index - 1)
    if is_bess_active:
        df['bess_trading_income'] = inputs.get('bess_base_trading_income', 0) * df['bess_degradation_factor'] * trading_income_growth
        df['bess_control_party_costs'] = -df['bess_trading_income'] * inputs.get('bess_income_ctrl_party_pct', 0)
        df['bess_supplier_costs'] = -inputs.get('Energy Supplier Costs', 0) * df['bess_degradation_factor'] * supplier_costs_growth
        bess_om_y1 = inputs.get('bess_om_y1', 0); bess_other_opex_y1 = inputs.get('bess_other_opex_y1', 0)
        df['bess_opex'] = -(bess_om_y1 * bess_om_growth + bess_other_opex_y1 * other_costs_growth)
    else: df['bess_trading_income'] = df['bess_control_party_costs'] = df['bess_supplier_costs'] = df['bess_opex'] = 0
    if is_pv_active:
        df['pv_ppa_income'] = inputs.get('PPA Income', 0) * df['pv_degradation_factor'] * ppa_income_growth
        df['pv_curtailment_income'] = inputs.get('Curtailment Income', 0) * df['pv_degradation_factor']
        df['pv_opex'] = -inputs.get('pv_total_opex_y1', 0) * other_costs_growth
    else: df['pv_ppa_income'] = df['pv_curtailment_income'] = df['pv_opex'] = 0
    income_cols = ['bess_trading_income', 'bess_control_party_costs', 'bess_supplier_costs', 'bess_opex', 'pv_ppa_income', 'pv_curtailment_income', 'pv_opex']
    df['ebitda'] = df[income_cols].sum(axis=1)
    annual_depr_battery = (inputs.get('bess_total_capex', 0) / inputs['depr_period_battery']) if is_bess_active and inputs['depr_period_battery'] > 0 else 0
    annual_depr_pv = (inputs.get('pv_total_capex', 0) / inputs['depr_period_pv']) if is_pv_active and inputs['depr_period_pv'] > 0 else 0
    df['depreciation'] = 0
    if is_bess_active: df.loc[df.index <= inputs['depr_period_battery'], 'depreciation'] += annual_depr_battery
    if is_pv_active: df.loc[df.index <= inputs['depr_period_pv'], 'depreciation'] += annual_depr_pv
    df['profit_before_tax'] = df['ebitda'] - df['depreciation']
    tax_threshold, tax_rate_1, tax_rate_2 = 200000, 0.19, 0.258
    df['corporate_tax'] = np.where(df['profit_before_tax'] <= tax_threshold, df['profit_before_tax'] * tax_rate_1, (tax_threshold * tax_rate_1) + ((df['profit_before_tax'] - tax_threshold) * tax_rate_2))
    df.loc[df['profit_before_tax'] < 0, 'corporate_tax'] = 0
    df['corporate_tax'] = -df['corporate_tax']
    df['net_cash_flow'] = df['ebitda'] + df['corporate_tax']
    total_capex = inputs.get('bess_total_capex', 0) + inputs.get('pv_total_capex', 0)
    cash_flows = [-total_capex] + df['net_cash_flow'].tolist()
    irr = npf.irr(cash_flows) if total_capex > 0 else 0
    npv = npf.npv(inputs['wacc'], cash_flows)
    df['cumulative_cash_flow'] = df['net_cash_flow'].cumsum() - total_capex
    try:
        payback_year = df[df['cumulative_cash_flow'] >= 0].index[0]
        cash_flow_last_negative_year = df.loc[payback_year - 1, 'cumulative_cash_flow'] + total_capex
        payback_period = (payback_year - 1) + (-cash_flow_last_negative_year / df.loc[payback_year, 'net_cash_flow'])
    except IndexError: payback_period = "Not reached"
    metrics = {"Total Investment": total_capex, "Project IRR": irr, "Project NPV": npv, "Payback Period (years)": payback_period if isinstance(payback_period, str) else f"{payback_period:.2f}", "Final Cumulative Cash Flow": df['cumulative_cash_flow'].iloc[-1]}
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
    capex_data = {k: v for k, v in kpis.items() if ('Costs' in k or 'Works' in k or 'Security' in k or 'Permits' in k or 'Management' in k or 'Contingency' in k) and isinstance(v, (int, float)) and v > 0}
    df_capex = pd.DataFrame(list(capex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
    fig_capex = px.pie(df_capex, values='Cost', names='Component', title=f'{prefix.upper()} CAPEX Breakdown', hole=.3)
    if prefix == 'bess': opex_data = {'O&M': kpis.get('bess_om_y1', 0), **{k: v for k, v in kpis.items() if k in ['Asset Management', 'Insurance', 'Property Tax', 'Overhead', 'Other OPEX']}}
    else: opex_data = {k: v for k, v in kpis.items() if k in ['Insurance', 'Property Tax', 'Overhead', 'Other OPEX']}
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

# --- PAGE DISPLAY FUNCTIONS ---
def show_home_page():
    display_header("Flink Nederland EMS ☀️🔋")
    st.subheader('Welcome to the Energy Modeling Suite')
    st.write("Please select a tool to begin.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🛠️ Sizing Tools")
        if st.button("Battery Size Finder"): st.info("This feature is coming soon!")
    with col2:
        st.markdown("#### 💰 Revenue Analysis")
        if st.button("Battery Revenue Analysis"): st.info("This feature is coming soon!")
    with col3:
        st.markdown("#### 📈 Financial Modeling")
        if st.button("Business Case Simulation", type="primary"):
            st.session_state.page = "Project_Selection"
            st.rerun()

def show_project_selection_page():
    display_header("Project Management 🗂️")
    st.subheader("Create a New Project")
    new_project_name = st.text_input("Enter new project name:", key="new_project_name_input")
    if st.button("Create and Start Project"):
        if not new_project_name: st.warning("Project name cannot be empty.")
        elif new_project_name in st.session_state.projects: st.error("A project with this name already exists.")
        else:
            st.session_state.projects[new_project_name] = {'inputs': HARDCODED_DEFAULTS.copy(), 'type': "BESS & PV"}
            st.session_state.current_project_name = new_project_name
            st.session_state.page = "Model"
            st.rerun()
    st.markdown("---")
    st.subheader("Load an Existing Project")
    if not st.session_state.projects: st.info("No projects found. Create one above to get started, or load projects from the sidebar.")
    else:
        project_to_load = st.selectbox("Select a project:", options=list(st.session_state.projects.keys()))
        if st.button("Load Project"):
            st.session_state.current_project_name = project_to_load
            st.session_state.page = "Model"
            st.rerun()

def show_model_page():
    project_name = st.session_state.current_project_name
    if not project_name or project_name not in st.session_state.projects:
        st.error("Error: No project loaded."); st.session_state.page = "Project_Selection"; st.rerun()
        return
    
    project_data = st.session_state.projects[project_name]
    i = project_data['inputs']
    
    display_header(f"Business Case: {project_name}")

    # Navigation buttons on the main page
    nav_cols = st.columns([1, 1, 5])
    with nav_cols[0]:
        if st.button("⬅️ Back to Projects"):
            st.session_state.page = "Project_Selection"
            st.rerun()
    with nav_cols[1]:
        if st.button("💾 Save Project"):
            save_projects()
            st.toast(f"Project '{project_name}' saved successfully!")

    # --- Sidebar for Inputs ---
    with st.sidebar:
        st.title("Configuration")
        project_data['type'] = st.selectbox("Select Project Type", ["BESS & PV", "BESS-only", "PV-only"], index=["BESS & PV", "BESS-only", "PV-only"].index(project_data['type']), key=f"{project_name}_type")
        uploaded_file = st.file_uploader("Upload CSV to Override Inputs", type=['csv'], key=f"{project_name}_upload")
        if uploaded_file: st.sidebar.success("CSV Uploaded (Parsing logic to be implemented)")
        
        st.header("General & Financial")
        with st.expander("Time/Duration", expanded=True):
            i['project_term'] = st.slider('Project Term (years)', 5, 30, i['project_term'], key=f"{project_name}_g_term")
            if 'BESS' in project_data['type']:
                i['depr_period_battery'] = st.slider('Depreciation Period Battery (financial)', 5, 20, i['depr_period_battery'], key=f"{project_name}_g_depr_b")
                i['lifespan_battery_tech'] = st.slider('Lifespan Battery (technical)', 5, 20, i['lifespan_battery_tech'], key=f"{project_name}_g_life_b")
            if 'PV' in project_data['type']:
                i['depr_period_pv'] = st.slider('Depreciation Period PV (financial)', 10, 30, i['depr_period_pv'], key=f"{project_name}_g_depr_pv")
                i['lifespan_pv_tech'] = st.slider('Lifespan PV (technical)', 10, 40, i['lifespan_pv_tech'], key=f"{project_name}_g_life_pv")
        with st.expander("Grid Connection"):
            st.markdown("<h6>Old Situation</h6>", unsafe_allow_html=True)
            i['connection_old'] = st.selectbox("Connection", options=connections_df['name'], index=connections_df['name'].tolist().index(i['connection_old']), key=f"{project_name}_conn_old")
            old_conn_details = connections_df[connections_df['name'] == i['connection_old']].iloc[0]
            st.text(f"Transport: {old_conn_details['transport_category']}"); st.metric("kW Max (offtake)", f"{old_conn_details['kw_max_offtake']} kW"); st.metric("kW Contract (offtake)", f"{old_conn_details['kw_contract_offtake']} kW")
            st.markdown("<h6>New Situation</h6>", unsafe_allow_html=True)
            i['connection_new'] = st.selectbox("Connection", options=connections_df['name'], index=connections_df['name'].tolist().index(i['connection_new']), key=f"{project_name}_conn_new")
            new_conn_details = connections_df[connections_df['name'] == i['connection_new']].iloc[0]
            st.text(f"Transport: {new_conn_details['transport_category']}"); st.metric("kW Max (offtake)", f"{new_conn_details['kw_max_offtake']} kW"); st.metric("kW Contract (offtake)", f"{new_conn_details['kw_contract_offtake']} kW")
        with st.expander("Financing", expanded=True):
            i['debt_senior_pct'] = st.slider('Debt (senior) (%)', 0.0, 100.0, i['debt_senior_pct'] * 100, key=f"{project_name}_fin_ds") / 100
            i['debt_junior_pct'] = st.slider('Debt (junior) (%)', 0.0, 100.0, i['debt_junior_pct'] * 100, key=f"{project_name}_fin_dj") / 100
            equity_pct = 1.0 - i['debt_senior_pct'] - i['debt_junior_pct']
            if equity_pct < 0: st.error("Total debt cannot exceed 100%"); equity_pct = 0
            st.metric(label="Equity", value=f"{equity_pct:.1%}")
            i['irr_equity_req'] = st.slider('IRR requirement (equity) (%)', 0.0, 25.0, i['irr_equity_req'] * 100, key=f"{project_name}_fin_irr") / 100
            i['interest_rate_senior'] = st.slider('Interest rate debt (senior) (%)', 0.0, 15.0, i['interest_rate_senior'] * 100, key=f"{project_name}_fin_irs") / 100
            i['interest_rate_junior'] = st.slider('Interest rate debt (junior) (%)', 0.0, 15.0, i['interest_rate_junior'] * 100, key=f"{project_name}_fin_irj") / 100
            wacc = (equity_pct * i['irr_equity_req']) + (i['debt_senior_pct'] * i['interest_rate_senior']) + (i['debt_junior_pct'] * i['interest_rate_junior'])
            i['wacc'] = wacc
            st.metric(label="Weighted Average Cost of Capital (WACC)", value=f"{wacc:.2%}")
        with st.expander("Inflation & Indexations"):
            i['inflation'] = st.slider('General Inflation (%)', 0.0, 10.0, i['inflation'] * 100, key=f"{project_name}_g_inf") / 100
            st.markdown("###### Indexations relative to inflation:")
            i['idx_trading_income'] = st.slider('Trading income (battery) (%)', -5.0, 5.0, i['idx_trading_income'] * 100, key=f"{project_name}_idx_ti") / 100
            i['idx_supplier_costs'] = st.slider('Energy supplier costs (battery) (%)', -5.0, 5.0, i['idx_supplier_costs'] * 100, key=f"{project_name}_idx_sc") / 100
            i['idx_om_bess'] = st.slider('O&M (battery) (%)', -5.0, 5.0, i['idx_om_bess'] * 100, key=f"{project_name}_idx_omb") / 100
            i['idx_other_costs'] = st.slider('Other annual costs (battery and PV) (%)', -5.0, 5.0, i['idx_other_costs'] * 100, key=f"{project_name}_idx_oc") / 100
            i['idx_ppa_income'] = st.slider('Income PPA (PV) (%)', -5.0, 5.0, i['idx_ppa_income'] * 100, key=f"{project_name}_idx_ppa") / 100
        with st.expander("Corporate Tax"):
            st.markdown("• **VPB threshold**: € 200,000\n\n• **Tariff ≤ €200,000**: 19.0%\n\n• **Tariff > €200,000**: 25.8%"); st.info("These tax rates are fixed.")
        if 'BESS' in project_data['type']:
            st.header("🔋 BESS")
            with st.expander("Technical Inputs (BESS)"):
                i['bess_power_kw'] = st.number_input("Power (kW)", value=i['bess_power_kw'], key=f"{project_name}_bess_p_kw")
                i['bess_capacity_kwh'] = st.number_input("Capacity (kWh)", value=i['bess_capacity_kwh'], key=f"{project_name}_bess_c_kwh")
                i['bess_min_soc'], i['bess_max_soc'] = st.slider("Operating SoC Range", 0.0, 1.0, (i['bess_min_soc'], i['bess_max_soc']), key=f"{project_name}_bess_soc")
                i['bess_charging_eff'] = st.slider("Charging Efficiency", 0.80, 1.00, i['bess_charging_eff'], step=0.01, key=f"{project_name}_bess_chg_eff")
                i['bess_discharging_eff'] = st.slider("Discharging Efficiency", 0.80, 1.00, i['bess_discharging_eff'], step=0.01, key=f"{project_name}_bess_dis_eff")
                i['bess_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 10.0, i['bess_annual_degradation'] * 100, key=f"{project_name}_bess_deg") / 100
                i['bess_cycles_per_year'] = st.number_input("Cycles per Year", value=i['bess_cycles_per_year'], key=f"{project_name}_bess_cycles")
            with st.expander("CAPEX Assumptions (BESS)"):
                i['bess_capex_per_kwh'] = st.number_input("BESS Price (€/kWh)", value=i['bess_capex_per_kwh'], key=f"{project_name}_bess_capex_price")
                i['bess_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['bess_capex_civil_pct'] * 100, key=f"{project_name}_bess_capex_civil") / 100
                i['bess_capex_it_per_kwh'] = st.number_input("IT/Control (€/kWh)", value=i['bess_capex_it_per_kwh'], key=f"{project_name}_bess_capex_it")
                i['bess_capex_security_per_kwh'] = st.number_input("Security (€/kWh)", value=i['bess_capex_security_per_kwh'], key=f"{project_name}_bess_capex_sec")
                i['bess_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['bess_capex_permits_pct'] * 100, key=f"{project_name}_bess_capex_perm") / 100
                i['bess_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['bess_capex_mgmt_pct'] * 100, key=f"{project_name}_bess_capex_mgmt") / 100
                i['bess_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['bess_capex_contingency_pct'] * 100, key=f"{project_name}_bess_capex_cont") / 100
            with st.expander("Income Assumptions (BESS)"):
                i['bess_income_trading_per_mw_year'] = st.number_input("Trading Income (€/MW/year)", value=i['bess_income_trading_per_mw_year'], key=f"{project_name}_bess_inc_trad")
                i['bess_income_ctrl_party_pct'] = st.slider("Control Party Costs (% of Income)", 0.0, 25.0, i['bess_income_ctrl_party_pct'] * 100, key=f"{project_name}_bess_inc_ctrl") / 100
                i['bess_income_supplier_cost_per_mwh'] = st.number_input("Energy Supplier Costs (€/MWh)", value=i['bess_income_supplier_cost_per_mwh'], key=f"{project_name}_bess_inc_supp")
            with st.expander("OPEX Assumptions (BESS)"):
                i['bess_opex_om_per_year'] = st.number_input("O&M (€/year)", value=i['bess_opex_om_per_year'], key=f"{project_name}_bess_opex_om")
                i['bess_opex_asset_mgmt_per_mw_year'] = st.number_input("Asset Management (€/MW/year)", value=i['bess_opex_asset_mgmt_per_mw_year'], key=f"{project_name}_bess_opex_am")
                i['bess_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['bess_opex_insurance_pct'] * 100, key=f"{project_name}_bess_opex_ins") / 100
                i['bess_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['bess_opex_property_tax_pct'] * 100, format="%.3f", key=f"{project_name}_bess_opex_tax") / 100
                i['bess_opex_overhead_per_kwh_year'] = st.number_input("Overhead (€/kWh/year)", value=i['bess_opex_overhead_per_kwh_year'], key=f"{project_name}_bess_opex_over")
                i['bess_opex_other_per_kwh_year'] = st.number_input("Other (€/kWh/year)", value=i['bess_opex_other_per_kwh_year'], key=f"{project_name}_bess_opex_oth")
        if 'PV' in project_data['type']:
            st.header("☀️ Solar PV")
            with st.expander("Technical Inputs (PV)"):
                i['pv_panel_count'] = st.number_input("Number of Panels", value=i['pv_panel_count'], key=f"{project_name}_pv_panel_c")
                i['pv_power_per_panel_wp'] = st.number_input("Power per Panel (Wp)", value=i['pv_power_per_panel_wp'], key=f"{project_name}_pv_ppp_wp")
                i['pv_full_load_hours'] = st.number_input("Full Load Hours (kWh/kWp)", value=i['pv_full_load_hours'], key=f"{project_name}_pv_flh")
                i['pv_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 2.0, i['pv_annual_degradation'] * 100, format="%.2f", key=f"{project_name}_pv_deg") / 100
            with st.expander("CAPEX Assumptions (PV)"):
                i['pv_capex_per_wp'] = st.number_input("PV Price (€/Wp)", value=i['pv_capex_per_wp'], format="%.3f", key=f"{project_name}_pv_capex_price")
                i['pv_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['pv_capex_civil_pct'] * 100, key=f"{project_name}_pv_capex_civil") / 100
                i['pv_capex_security_pct'] = st.slider("Security (%)", 0.0, 10.0, i['pv_capex_security_pct'] * 100, key=f"{project_name}_pv_capex_sec") / 100
                i['pv_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['pv_capex_permits_pct'] * 100, key=f"{project_name}_pv_capex_perm") / 100
                i['pv_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['pv_capex_mgmt_pct'] * 100, key=f"{project_name}_pv_capex_mgmt") / 100
                i['pv_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['pv_capex_contingency_pct'] * 100, key=f"{project_name}_pv_capex_cont") / 100
            with st.expander("Income Assumptions (PV)"):
                i['pv_income_ppa_per_mwp'] = st.number_input("Income PPA (€/MWp)", value=i['pv_income_ppa_per_mwp'], key=f"{project_name}_pv_inc_ppa_mwp")
                i['pv_income_ppa_per_kwh'] = st.number_input("Income PPA (€/kWh)", value=i['pv_income_ppa_per_kwh'], format="%.4f", key=f"{project_name}_pv_inc_ppa_kwh")
                i['pv_income_curtailment_per_mwp'] = st.number_input("Income Curtailment (€/MWp)", value=i['pv_income_curtailment_per_mwp'], key=f"{project_name}_pv_inc_curt_mwp")
                i['pv_income_curtailment_per_kwh'] = st.number_input("Income Curtailment (€/kWh)", value=i['pv_income_curtailment_per_kwh'], format="%.4f", key=f"{project_name}_pv_inc_curt_kwh")
            with st.expander("OPEX Assumptions (PV)"):
                i['pv_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['pv_opex_insurance_pct'] * 100, key=f"{project_name}_pv_opex_ins") / 100
                i['pv_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['pv_opex_property_tax_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_tax") / 100
                i['pv_opex_overhead_pct'] = st.slider("Overhead (% of CAPEX)", 0.0, 2.0, i['pv_opex_overhead_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_over") / 100
                i['pv_opex_other_pct'] = st.slider("Other (% of CAPEX)", 0.0, 2.0, i['pv_opex_other_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_oth") / 100
        
        if st.button('Run Model', type="primary", key=f"{project_name}_run"):
            if equity_pct < 0: st.error("Cannot run model: Total debt exceeds 100%.")
            else:
                inputs_to_run = i.copy()
                bess_kpis, pv_kpis = {}, {}
                if 'BESS' in project_data['type']: bess_kpis = calculate_bess_kpis(i); inputs_to_run.update(bess_kpis)
                if 'PV' in project_data['type']: pv_kpis = calculate_pv_kpis(i); inputs_to_run.update(pv_kpis)
                results_df, metrics = run_financial_model(inputs_to_run, project_data['type'])
                project_data['results'] = {'df': results_df, 'metrics': metrics, 'bess_kpis': bess_kpis, 'pv_kpis': pv_kpis}
                st.rerun()

    # --- Main content area to display results ---
    if 'results' in project_data:
        metrics = project_data['results']['metrics']; results_df = project_data['results']['df']
        bess_kpis = project_data['results']['bess_kpis']; pv_kpis = project_data['results']['pv_kpis']
        st.header('Financial Metrics')
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Investment", f"€{metrics['Total Investment']:,.0f}")
        col2.metric("Project IRR", f"{metrics['Project IRR']:.2%}")
        col3.metric("Project NPV", f"€{metrics['Project NPV']:,.0f}", help=f"Calculated with WACC of {i['wacc']:.2%}")
        col4.metric("Payback Period", f"{metrics['Payback Period (years)']} years")
        col5.metric("Final Cumulative Cash Flow", f"€{metrics['Final Cumulative Cash Flow']:,.0f}")
        tab_charts, tab_bess, tab_pv = st.tabs(["📊 Financial Summary", "🔋 BESS KPIs", "☀️ PV KPIs"])
        with tab_charts:
            st.plotly_chart(generate_interactive_charts(results_df, metrics['Total Investment'])[1], use_container_width=True)
            st.plotly_chart(generate_interactive_charts(results_df, metrics['Total Investment'])[0], use_container_width=True)
            st.dataframe(results_df[['ebitda', 'depreciation', 'net_cash_flow', 'cumulative_cash_flow']].style.format("€{:,.0f}"), use_container_width=True)
        with tab_bess:
            st.header("🔋 BESS - Key Performance Indicators")
            if 'BESS' in project_data['type']:
                bess_kpi_map = {"Technical": {'Capacity Factor': 'h', 'SoC Available': '%', 'Usable Capacity': 'kWh', 'C-Rate': '', 'Round Trip Efficiency (RTE)': '%', 'Offtake from Grid (Year 1)': 'kWh'}, "CAPEX": {'Purchase Costs': '€', 'IT & Security Costs': '€', 'Civil Works': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€'}, "Income (Year 1)": {'bess_base_trading_income': '€', 'Control Party Costs': '€', 'Energy Supplier Costs': '€'}, "OPEX (Year 1)": {'O&M': '€', 'Asset Management': '€', 'Insurance': '€', 'Property Tax': '€', 'Overhead': '€', 'Other OPEX': '€'}}
                capex_chart, opex_chart = generate_cost_breakdown_charts(bess_kpis, 'bess'); col1, col2 = st.columns(2)
                with col1: st.plotly_chart(capex_chart, use_container_width=True)
                with col2: st.plotly_chart(opex_chart, use_container_width=True)
                for section, keys in bess_kpi_map.items(): st.subheader(section); st.dataframe(create_kpi_dataframe(bess_kpis, {section: keys}), use_container_width=True)
            else: st.info("BESS not included in this project type.")
        with tab_pv:
            st.header("☀️ PV - Key Performance Indicators")
            if 'PV' in project_data['type']:
                pv_kpi_map = {"Technical": {'Total Peak Power': 'kWp', 'Production (Year 1)': 'kWh'}, "CAPEX": {'Purchase Costs': '€', 'Civil Works': '€', 'Security': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€'}, "Income (Year 1)": {'PPA Income': '€', 'Curtailment Income': '€'}, "OPEX (Year 1)": {'Insurance': '€', 'Property Tax': '€', 'Overhead': '€', 'Other OPEX': '€'}}
                capex_chart, opex_chart = generate_cost_breakdown_charts(pv_kpis, 'pv'); col1, col2 = st.columns(2)
                with col1: st.plotly_chart(capex_chart, use_container_width=True)
                with col2: st.plotly_chart(opex_chart, use_container_width=True)
                for section, keys in pv_kpi_map.items(): st.subheader(section); st.dataframe(create_kpi_dataframe(pv_kpis, {section: keys}), use_container_width=True)
            else: st.info("PV not included in this project type.")
    else:
        st.info('Adjust inputs in the sidebar and click "Run Model" to see the financial forecast.')

# --- MAIN ROUTER ---
# Sidebar elements that are always visible
with st.sidebar:
    st.markdown("---")
    st.header("Navigation")
    if st.button("🏠 Back to Home"):
        st.session_state.page = "Home"
        st.rerun()

    st.markdown("---")
    st.header("Data Management")
    if st.button("📂 Load Projects from File"):
        load_projects()
        st.rerun()

# Automatically load projects when the app starts, if they haven't been loaded yet.
if 'projects' not in st.session_state or not st.session_state.projects:
    if os.path.exists(PROJECTS_FILE):
        load_projects()

if st.session_state.page == "Home":
    show_home_page()
elif st.session_state.page == "Project_Selection":
    show_project_selection_page()
elif st.session_state.page == "Model":
    show_model_page()
