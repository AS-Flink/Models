import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import os
import copy
from datetime import datetime
# from google.cloud import firestore
# from google.oauth2 import service_account
# import json


# --- IMPORTANT: Add this new import for the revenue tool ---
from revenue_logic import run_revenue_model

# --- Add these new helper functions to your main app script ---

def find_total_result_column(df):
    """Finds the correct total result column in the DataFrame."""
    possible_cols = [
        'total_result_imbalance_PAP',
        'total_result_imbalance_SAP',
        'total_result_day_ahead_trading',
        'total_result_self_consumption'
    ]
    for col in possible_cols:
        if col in df.columns:
            return col
    return None

def resample_data(df, resolution):
    """Resamples the DataFrame to the specified time resolution."""
    # Ensure the index is a DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        # Attempt to convert it if it's not
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            st.error("Could not process the DataFrame index as dates. Please ensure the 'datetime' column is correct.")
            return pd.DataFrame() # Return empty df on error

    resolution_map = {
        'Hourly': 'H',
        'Daily': 'D',
        'Monthly': 'M',
        'Yearly': 'Y'
    }
    
    if resolution == '15 Min (Original)':
        return df
        
    rule = resolution_map.get(resolution)
    if rule:
        # Use .sum() for aggregation; it works for both financial and energy data
        return df.resample(rule).sum()
    
    return df


# --- Page Configuration ---
# --- Page Configuration ---
st.set_page_config(
    layout="wide",
    page_title="Flink EMS",
    page_icon="https://i.postimg.cc/3Ncw69QP/SCHILD-LOGO-REGULAR-BLAUW150.webp" 
)
# --- DATA (Connections, Defaults for Financial Model) ---
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
    'interest_rate_junior': 0.08, 'term_senior': 10, 'term_junior': 10, 'wacc': 0.1,
    'eia_pct': 0.4,

    # Indexations
    'inflation': 0.02, 'idx_trading_income': -0.02, 'idx_supplier_costs': 0.0,
    'idx_om_bess': 0.0, 'idx_om_pv': 0.0, 'idx_grid_op': 0.005, 'idx_other_costs': 0.0,
    'idx_ppa_income': 0.0, 'idx_curtailment_income': 0.0,
    
    # Grid Connection
    'grid_one_time_bess': 0.0, 'grid_one_time_pv': 0.0, 'grid_one_time_general': 0.0,
    'grid_annual_fixed': 0.0, 'grid_annual_kw_max': 2000.0,
    'grid_annual_kw_contract': 800.0, 'grid_annual_kwh_offtake': 5000.0,

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
    'bess_opex_other_per_kwh_year': 1.0, 'bess_opex_retribution': 0.0,

    # PV
    'pv_power_per_panel_wp': 590, 'pv_panel_count': 3479, 'pv_full_load_hours': 817.8,
    'pv_annual_degradation': 0.005, 'pv_capex_per_wp': 0.2, 'pv_capex_civil_pct': 0.08,
    'pv_capex_security_pct': 0.02, 'pv_capex_permits_pct': 0.01,
    'pv_capex_mgmt_pct': 0.025, 'pv_capex_contingency_pct': 0.05,
    'pv_income_ppa_per_mwp': 0.0, 'pv_income_ppa_per_kwh': 0.0,
    'pv_income_curtailment_per_mwp': 0.0, 'pv_income_curtailment_per_kwh': 0.0,
    'pv_opex_insurance_pct': 0.01, 'pv_opex_property_tax_pct': 0.001,
    'pv_opex_overhead_pct': 0.005, 'pv_opex_other_pct': 0.005,
    'pv_opex_om_y1': 0.0, 'pv_opex_retribution': 0.0
}

# --- Session State & Project Persistence ---
if 'page' not in st.session_state:
    st.session_state.page = "Home"
    st.session_state.projects = {}
    st.session_state.current_project_name = None
    st.session_state.renaming_project = None
    st.session_state.deleting_project = None
    st.session_state.revenue_results = None # Add for new tool

PROJECTS_FILE = "flink_ems_projects.json"

def save_projects():
    with open(PROJECTS_FILE, 'w') as f:
        projects_for_save = copy.deepcopy(st.session_state.projects)
        for proj_name, proj_data in projects_for_save.items():
            if 'results' in proj_data and isinstance(proj_data['results'].get('df'), pd.DataFrame):
                projects_for_save[proj_name]['results']['df'] = proj_data['results']['df'].to_json()
        json.dump(projects_for_save, f, indent=4)

def load_projects():
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, 'r') as f:
                if os.path.getsize(PROJECTS_FILE) > 0:
                    loaded_projects = json.load(f)
                    for proj_name, proj_data in loaded_projects.items():
                        if 'results' in proj_data and isinstance(proj_data['results'].get('df'), str):
                            proj_data['results']['df'] = pd.read_json(proj_data['results']['df'])
                    st.session_state.projects = loaded_projects
                    st.sidebar.success("Projects loaded!")
                else: st.session_state.projects = {}
        except json.JSONDecodeError:
            st.sidebar.error("Could not load projects. Save file may be corrupt.")
            st.session_state.projects = {}
    else:
        st.sidebar.warning("No saved projects file found.")
# # Authenticate to Firestore with the credentials stored in st.secrets
# @st.cache_resource
# def get_firestore_client():
#     creds_dict = st.secrets["firestore"]
#     creds = service_account.Credentials.from_service_account_info(creds_dict)
#     db = firestore.Client(credentials=creds)
#     return db

# db = get_firestore_client()
# PROJECTS_COLLECTION = "projects" # Name of the collection in Firestore

# def save_projects():
#     """Saves all projects from session state to Firestore."""
#     projects_for_save = copy.deepcopy(st.session_state.projects)
#     for proj_name, proj_data in projects_for_save.items():
#         # Convert pandas DataFrame to JSON string before saving
#         if 'results' in proj_data and isinstance(proj_data['results'].get('df'), pd.DataFrame):
#             proj_data['results']['df'] = proj_data['results']['df'].to_json()
        
#         # In Firestore, each project is a "document" in the "projects" collection
#         doc_ref = db.collection(PROJECTS_COLLECTION).document(proj_name)
#         doc_ref.set(proj_data)
#     st.toast("Projects saved to the cloud!")

# def load_projects():
#     """Loads all projects from Firestore into session state."""
#     projects_from_db = {}
#     docs = db.collection(PROJECTS_COLLECTION).stream()
#     for doc in docs:
#         proj_data = doc.to_dict()
#         # Convert JSON string back to pandas DataFrame after loading
#         if 'results' in proj_data and isinstance(proj_data['results'].get('df'), str):
#             proj_data['results']['df'] = pd.read_json(proj_data['results']['df'])
#         projects_from_db[doc.id] = proj_data
    
#     st.session_state.projects = projects_from_db
#     if projects_from_db:
#         st.sidebar.success("Projects loaded from the cloud!")

# --- UI HELPER ---
def display_header(title):
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image("https://i.postimg.cc/RFgvn3Cp/LOGO-S-PRESENTATIE.webp", width=10000)
    with col2:
        st.title(title)
    st.markdown("---")

# --- CORE CALCULATION & CHARTING FUNCTIONS (Financial Model) ---
def calculate_all_kpis(i, tech_type):
    kpis = {}
    if tech_type == 'bess':
        kpis['Capacity Factor'] = i['bess_capacity_kwh'] / i['bess_power_kw'] if i['bess_power_kw'] > 0 else 0
        kpis['SoC Available'] = i['bess_max_soc'] - i['bess_min_soc']
        kpis['Usable Capacity'] = i['bess_capacity_kwh'] * kpis['SoC Available']
        kpis['C-Rate'] = i['bess_power_kw'] / kpis['Usable Capacity'] if kpis['Usable Capacity'] > 0 else 0
        kpis['Round Trip Efficiency (RTE)'] = i['bess_charging_eff'] * i['bess_discharging_eff']
        kpis['Purchase Costs'] = i['bess_capacity_kwh'] * i['bess_capex_per_kwh']
        kpis['IT & Security Costs'] = i['bess_capacity_kwh'] * (i['bess_capex_it_per_kwh'] + i['bess_capex_security_per_kwh'])
        base_capex = kpis['Purchase Costs'] + kpis['IT & Security Costs']
        kpis['Civil Works'] = base_capex * i['bess_capex_civil_pct']
        capex_subtotal = base_capex + kpis['Civil Works']
        kpis['Permits & Fees'] = capex_subtotal * i['bess_capex_permits_pct']
        kpis['Project Management'] = capex_subtotal * i['bess_capex_mgmt_pct']
        kpis['Contingency'] = capex_subtotal * i['bess_capex_contingency_pct']
        kpis['total_capex'] = capex_subtotal + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
        kpis['trading_income_y1'] = (i['bess_power_kw'] / 1000) * i['bess_income_trading_per_mw_year']
        kpis['control_party_costs_y1'] = kpis['trading_income_y1'] * i['bess_income_ctrl_party_pct']
        offtake_y1 = i['bess_cycles_per_year'] * kpis['Usable Capacity'] / i['bess_charging_eff']
        kpis['supplier_costs_y1'] = (offtake_y1 / 1000) * i['bess_income_supplier_cost_per_mwh']
        kpis['om_y1'] = i['bess_opex_om_per_year']
        kpis['retribution_y1'] = i['bess_opex_retribution']
        kpis['asset_mgmt_y1'] = (i['bess_power_kw'] / 1000) * i['bess_opex_asset_mgmt_per_mw_year']
        kpis['insurance_y1'] = kpis['total_capex'] * i['bess_opex_insurance_pct']
        kpis['property_tax_y1'] = kpis['total_capex'] * i['bess_opex_property_tax_pct']
        kpis['overhead_y1'] = i['bess_capacity_kwh'] * i['bess_opex_overhead_per_kwh_year']
        kpis['other_y1'] = i['bess_capacity_kwh'] * i['bess_opex_other_per_kwh_year']
    elif tech_type == 'pv':
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
        kpis['total_capex'] = capex_subtotal + kpis['Security'] + kpis['Permits & Fees'] + kpis['Project Management'] + kpis['Contingency']
        kpis['ppa_income_y1'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_ppa_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_ppa_per_kwh'])
        kpis['curtailment_income_y1'] = (kpis['Total Peak Power'] * 1000 * i['pv_income_curtailment_per_mwp']) + (kpis['Production (Year 1)'] * i['pv_income_curtailment_per_kwh'])
        kpis['om_y1'] = i['pv_opex_om_y1']
        kpis['retribution_y1'] = i['pv_opex_retribution']
        kpis['insurance_y1'] = kpis['total_capex'] * i['pv_opex_insurance_pct']
        kpis['property_tax_y1'] = kpis['total_capex'] * i['pv_opex_property_tax_pct']
        kpis['overhead_y1'] = kpis['total_capex'] * i['pv_opex_overhead_pct']
        kpis['other_y1'] = kpis['total_capex'] * i['pv_opex_other_pct']
    return kpis

def run_financial_model(i, project_type):
    years_op = np.arange(1, int(i['project_term']) + 1)
    df = pd.DataFrame(index=years_op); df.index.name = 'Year'
    is_bess, is_pv = 'BESS' in project_type, 'PV' in project_type
    years_vector = df.index - 1
    df['idx_inflation'] = (1 + i['inflation']) ** years_vector
    df['idx_trading_income'] = (1 + i['inflation'] + i['idx_trading_income']) ** years_vector
    df['idx_supplier_costs'] = (1 + i['inflation'] + i['idx_supplier_costs']) ** years_vector
    df['idx_om_bess'] = (1 + i['inflation'] + i['idx_om_bess']) ** years_vector
    df['idx_om_pv'] = (1 + i['inflation'] + i['idx_om_pv']) ** years_vector
    df['idx_grid_op'] = (1 + i['inflation'] + i['idx_grid_op']) ** years_vector
    df['idx_other_costs'] = (1 + i['inflation'] + i['idx_other_costs']) ** years_vector
    df['idx_ppa_income'] = (1 + i['inflation'] + i['idx_ppa_income']) ** years_vector
    df['idx_curtailment_income'] = (1 + i['inflation'] + i['idx_curtailment_income']) ** years_vector
    df['idx_degradation_bess'] = (1 - i['bess_annual_degradation']) ** df.index
    df['idx_degradation_pv'] = (1 - i['pv_annual_degradation']) ** df.index
    bess_base = calculate_all_kpis(i, 'bess') if is_bess else {}
    bess_capex = bess_base.get('total_capex', 0)
    bess_active_mask = (df.index <= i['project_term']) & (df.index <= i['lifespan_battery_tech'])
    if is_bess:
        df['bess_trading_income'] = bess_base['trading_income_y1'] * df['idx_trading_income'] * df['idx_degradation_bess']
        df['bess_control_party_costs'] = -df['bess_trading_income'] * i['bess_income_ctrl_party_pct']
        df['bess_supplier_costs'] = -bess_base['supplier_costs_y1'] * df['idx_supplier_costs'] * df['idx_degradation_bess']
        df['bess_om'] = -bess_base['om_y1'] * df['idx_om_bess']
        df['bess_retribution'] = -bess_base['retribution_y1'] * df['idx_other_costs']
        df['bess_asset_mgmt'] = -bess_base['asset_mgmt_y1'] * df['idx_other_costs']
        df['bess_insurance'] = -bess_base['insurance_y1'] * df['idx_other_costs']
        df['bess_property_tax'] = -bess_base['property_tax_y1'] * df['idx_other_costs']
        df['bess_overhead'] = -bess_base['overhead_y1'] * df['idx_other_costs']
        df['bess_other'] = -bess_base['other_y1'] * df['idx_other_costs']
        bess_cols = [c for c in df.columns if 'bess_' in c and 'idx_' not in c]
        for col in bess_cols: df[col] *= bess_active_mask
        df['ebitda_bess'] = df[bess_cols].sum(axis=1)
    else: df['ebitda_bess'] = 0
    pv_base = calculate_all_kpis(i, 'pv') if is_pv else {}
    pv_capex = pv_base.get('total_capex', 0)
    pv_active_mask = (df.index <= i['project_term']) & (df.index <= i['lifespan_pv_tech'])
    if is_pv:
        df['pv_ppa_income'] = pv_base['ppa_income_y1'] * df['idx_ppa_income'] * df['idx_degradation_pv']
        df['pv_curtailment_income'] = pv_base['curtailment_income_y1'] * df['idx_curtailment_income'] * df['idx_degradation_pv']
        df['pv_om'] = -pv_base['om_y1'] * df['idx_om_pv']
        df['pv_retribution'] = -pv_base['retribution_y1'] * df['idx_other_costs']
        df['pv_insurance'] = -pv_base['insurance_y1'] * df['idx_other_costs']
        df['pv_property_tax'] = -pv_base['property_tax_y1'] * df['idx_other_costs']
        df['pv_overhead'] = -pv_base['overhead_y1'] * df['idx_other_costs']
        df['pv_other'] = -pv_base['other_y1'] * df['idx_other_costs']
        pv_cols = [c for c in df.columns if 'pv_' in c and 'idx_' not in c]
        for col in pv_cols: df[col] *= pv_active_mask
        df['ebitda_pv'] = df[pv_cols].sum(axis=1)
    else: df['ebitda_pv'] = 0
    grid_capex = i['grid_one_time_bess'] + i['grid_one_time_pv'] + i['grid_one_time_general']
    df['grid_annual_fixed'] = -i['grid_annual_fixed'] * df['idx_grid_op']
    df['grid_annual_kw_max'] = -i['grid_annual_kw_max'] * df['idx_grid_op']
    df['grid_annual_kw_contract'] = -i['grid_annual_kw_contract'] * df['idx_grid_op']
    df['grid_annual_kwh_offtake'] = -i['grid_annual_kwh_offtake'] * df['idx_grid_op']
    df['ebitda_grid'] = df[['grid_annual_fixed', 'grid_annual_kw_max', 'grid_annual_kw_contract', 'grid_annual_kwh_offtake']].sum(axis=1)
    df['total_ebitda'] = df['ebitda_bess'] + df['ebitda_pv'] + df['ebitda_grid']
    total_investment = bess_capex + pv_capex + grid_capex
    df['depreciation_bess'] = -bess_capex / i['depr_period_battery'] if i['depr_period_battery'] > 0 else 0
    df.loc[df.index > i['depr_period_battery'], 'depreciation_bess'] = 0
    df['depreciation_pv'] = -pv_capex / i['depr_period_pv'] if i['depr_period_pv'] > 0 else 0
    df.loc[df.index > i['depr_period_pv'], 'depreciation_pv'] = 0
    df['result_before_eia'] = df['total_ebitda'] + df['depreciation_bess'] + df['depreciation_pv']
    eia_allowance = total_investment * i['eia_pct']
    df['eia_applied'] = 0
    if len(df) > 0 and df.loc[1, 'result_before_eia'] > 0:
        df.loc[1, 'eia_applied'] = min(eia_allowance, df.loc[1, 'result_before_eia'])
    df['result_before_tax'] = df['result_before_eia'] - df['eia_applied']
    df['corporate_tax'] = -df['result_before_tax'].apply(lambda x: 200000 * 0.19 + (x - 200000) * 0.258 if x > 200000 else x * 0.19 if x > 0 else 0)
    df['profit_after_tax'] = df['result_before_tax'] + df['corporate_tax']
    df['net_cash_flow'] = df['total_ebitda'] + df['corporate_tax']
    ncf_y0 = -total_investment
    df['cumulative_cash_flow'] = df['net_cash_flow'].cumsum() + ncf_y0
    df['cumulative_ebitda'] = df['total_ebitda'].cumsum() + ncf_y0
    cash_flows_for_irr = [ncf_y0] + df['net_cash_flow'].tolist()
    metrics = {}
    metrics['total_investment'] = total_investment
    metrics['cumulative_cash_flow_end'] = df['cumulative_cash_flow'].iloc[-1] if not df.empty else ncf_y0
    metrics['cumulative_ebitda_end'] = df['cumulative_ebitda'].iloc[-1] if not df.empty else ncf_y0
    metrics['npv'] = npf.npv(i['wacc'], cash_flows_for_irr[1:]) + ncf_y0
    metrics['equity_irr'] = npf.irr(cash_flows_for_irr)
    project_ebitda_flows = [ncf_y0] + df['total_ebitda'].tolist()
    metrics['project_irr'] = npf.irr(project_ebitda_flows)
    try:
        payback_year_val = df[df['cumulative_cash_flow'] >= 0].index[0]
        cash_flow_prev_year = df.loc[payback_year_val - 1, 'cumulative_cash_flow'] if payback_year_val > 1 else ncf_y0
        metrics['payback_period'] = (payback_year_val - 1) + abs(cash_flow_prev_year / df.loc[payback_year_val, 'net_cash_flow'])
    except (IndexError, KeyError, ZeroDivisionError):
        metrics['payback_period'] = "Not reached"
    return {"df": df, "metrics": metrics, "bess_kpis": bess_base, "pv_kpis": pv_base}

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
                elif unit == "kWp" or unit == "kWh": formatted_value = f"{value:,.0f} {unit}"
                else: formatted_value = f"{value:,.2f}"
                data.append({'Metric': key.replace('_', ' ').title(), 'Value': formatted_value})
    return pd.DataFrame(data).set_index('Metric')

def generate_summary_chart(df, y_bar, y_line, title):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.index, y=df[y_bar], name=y_bar.replace('_', ' ').title(), marker_color='#1f77b4'))
    fig.add_trace(go.Scatter(x=df.index, y=df[y_line], name=y_line.replace('_', ' ').title(), mode='lines+markers', line=dict(color='#2ca02c', width=3)))
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=18)), # Smaller title
        yaxis_tickprefix="€",
        yaxis_tickformat="~s",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12)), # Smaller legend
        font=dict(size=11) # Smaller axis labels/ticks
    )
    return fig

# --- PAGE DISPLAY FUNCTIONS ---
def show_home_page():
    display_header("Flink Energy Management System (EMS) Simulation ")
    st.subheader('Tools')
    st.write("Please select a tool to begin.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🛠️ Sizing Tools")
        if st.button("Battery Size Finder"): st.info("This feature is coming soon!")
    with col2:
        st.markdown("#### 💰 Revenue Analysis")
        if st.button("Battery Revenue Analysis",type="primary"):
            st.session_state.page = "Revenue_Analysis"
            st.rerun()
    with col3:
        st.markdown("#### 📈 Financial Modeling")
        if st.button("Business Case Simulation", type="primary"):
            st.session_state.page = "Project_Selection"; st.rerun()

def show_project_selection_page():
    display_header("Project Management 🗂️")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Create a New Project")
        with st.form("new_project_form"):
            new_project_name = st.text_input("New project name:")
            submitted = st.form_submit_button("Create Project")
            if submitted:
                if not new_project_name: st.warning("Project name cannot be empty.")
                elif new_project_name in st.session_state.projects: st.error("A project with this name already exists.")
                else:
                    st.session_state.projects[new_project_name] = {'inputs': HARDCODED_DEFAULTS.copy(),'type': "BESS & PV",'last_saved': datetime.now().isoformat()}
                    save_projects(); st.success(f"Project '{new_project_name}' created!"); st.rerun()
    with col2:
        st.subheader("Manage Existing Projects")
        if not st.session_state.projects: st.info("No projects found. Create one or load from file.")
        else:
            for project_name, project_data in st.session_state.projects.items():
                with st.container(border=True):
                    p_col1, p_col2 = st.columns([3, 1])
                    with p_col1:
                        st.markdown(f"**{project_name}**")
                        if 'last_saved' in project_data:
                            saved_time = datetime.fromisoformat(project_data['last_saved']).strftime("%Y-%m-%d %H:%M")
                            st.caption(f"Last saved: {saved_time}")
                    with p_col2:
                        if st.button("Load", key=f"load_{project_name}", use_container_width=True):
                            st.session_state.current_project_name = project_name; st.session_state.page = "Model"; st.rerun()
                    if st.session_state.renaming_project == project_name:
                        with st.form(f"rename_form_{project_name}"):
                            new_name = st.text_input("New name", value=project_name)
                            rename_col1, rename_col2 = st.columns(2)
                            if rename_col1.form_submit_button("Save", use_container_width=True):
                                if new_name and new_name not in st.session_state.projects:
                                    st.session_state.projects[new_name] = st.session_state.projects.pop(project_name)
                                    st.session_state.renaming_project = None; save_projects(); st.rerun()
                                else: st.error("New name is invalid or already exists.")
                            if rename_col2.form_submit_button("Cancel", use_container_width=True):
                                st.session_state.renaming_project = None; st.rerun()
                    elif st.session_state.deleting_project == project_name:
                        st.warning(f"Are you sure you want to delete **{project_name}**?")
                        del_col1, del_col2 = st.columns(2)
                        if del_col1.button("Yes, permanently delete", type="primary", key=f"del_confirm_{project_name}", use_container_width=True):
                            del st.session_state.projects[project_name]
                            st.session_state.deleting_project = None; save_projects(); st.rerun()
                        if del_col2.button("Cancel", key=f"del_cancel_{project_name}", use_container_width=True):
                            st.session_state.deleting_project = None; st.rerun()
                    else:
                        action_cols = st.columns(3)
                        if action_cols[0].button("✏️ Rename", key=f"rename_{project_name}", use_container_width=True): st.session_state.renaming_project = project_name; st.rerun()
                        if action_cols[1].button("Duplicate", key=f"clone_{project_name}", use_container_width=True):
                            new_name = f"{project_name} (copy)"; i = 1
                            while new_name in st.session_state.projects: i += 1; new_name = f"{project_name} (copy {i})"
                            st.session_state.projects[new_name] = copy.deepcopy(project_data)
                            st.session_state.projects[new_name]['last_saved'] = datetime.now().isoformat()
                            save_projects(); st.rerun()
                        if action_cols[2].button("🗑️ Delete", key=f"delete_{project_name}", use_container_width=True): st.session_state.deleting_project = project_name; st.rerun()


# --- NEW PAGE FUNCTION for REVENUE ANALYSIS ---
# def show_revenue_analysis_page():
#     display_header("Battery Revenue Analysis 🔋")
#     st.write("Upload a data file and configure the battery parameters to run a revenue simulation.")

#     with st.sidebar:
#         st.header("⚙️ Configuration")

#         # 1. File Uploader
#         uploaded_file = st.file_uploader("Upload Input Data (CSV or Excel)", type=['csv', 'xlsx'])

#         # 2. Battery Configuration Selector
#         # battery_config_options = [
#         #     "Day-ahead trading, minimaliseer energiekosten",
#         #     "Onbalanshandel, alleen batterij op SAP",
#         #     "Onbalanshandel, alles op onbalansprijzen",
#         #     "Verhogen eigen verbruik PV, alles op day-ahead",
#         # ]
#         # battery_config = st.selectbox("Battery Strategy", battery_config_options)


#         # --- Add this NEW section in its place ---
#         st.subheader("Optimization Strategy")
        
#         # Step 1: User chooses the primary goal
#         goal_choice = st.radio(
#             "What is your primary financial goal?",
#             ("Minimize My Energy Bill", "Generate Revenue Through Market Trading"),
#             horizontal=True,
#             label_visibility="collapsed"
#         )
        
#         # Step 2: Based on the goal, show relevant strategies
#         if goal_choice == "Minimize My Energy Bill":
#             st.write("_Use assets to reduce overall energy costs by smartly using solar power and avoiding high grid prices._")
#             strategy_choice = st.selectbox(
#                 "Select a cost-minimization strategy:",
#                 (
#                     "Prioritize Self-Consumption", # -> self_consumption_PV_PAP.py
#                     "Optimize on Day-Ahead Market"   # -> day_ahead_trading_PAP.py
#                 )
#             )
#         else: # Generate Revenue
#             st.write("_Actively use assets to trade on energy markets and generate direct profit._")
#             strategy_choice = st.selectbox(
#                 "Select a revenue-generation strategy:",
#                 (
#                     "Simple Battery Trading (Imbalance)",     # -> imbalance_algorithm_SAP.py
#                     "Advanced Whole-System Trading (Imbalance)" # -> imbalance_everything_PAP.py
#                 )
#     )


#         # 3. Parameter Inputs
#         st.subheader("Battery Parameters")
#         power_mw = st.number_input("Vermogen batterij (MW)", value=1.0, min_value=0.1, step=0.1)
#         capacity_mwh = st.number_input("Capaciteit batterij (MWh)", value=2.0, min_value=0.1, step=0.1)
#         min_soc = st.slider("Minimum SoC", 0.0, 1.0, 0.05)
#         max_soc = st.slider("Maximum SoC", 0.0, 1.0, 0.95)
#         eff_ch = st.slider("Efficiëntie opladen", 0.8, 1.0, 0.95)
#         eff_dis = st.slider("Efficiëntie ontladen", 0.8, 1.0, 0.95)

#         st.subheader("Cost & Other Parameters")
#         max_cycles = st.number_input("Max cycli per jaar", value=600, min_value=1)
#         supply_costs = st.number_input("Kosten energieleverancier (€/MWh)", value=20.0)
#         transport_costs = st.number_input("Transportkosten afname (€/MWh)", value=15.0)

#     # Main page layout
#     col1, col2 = st.columns([2, 3])

#     with col1:
#         st.subheader("Run Simulation")
#         if st.button("🚀 Run Analysis", type="primary"):
#             if uploaded_file is None:
#                 st.error("Please upload an input file.")
#             else:
#                 with st.spinner("Reading data and running model... Please wait."):
#                     try:
#                         if uploaded_file.name.endswith('.csv'):
#                             # For CSV files
#                             input_df = pd.read_csv(uploaded_file, header=0)
#                         else:
#                             # For Excel files, using the CORRECT sheet name now
#                             input_df = pd.read_excel(
#                                 uploaded_file,
#                                 sheet_name='Export naar Python', # <-- CORRECTED NAME
#                                 header=0
#                             )
#                     except Exception as e:
#                         st.error(f"Error reading file: {e}. Ensure it contains a sheet named 'Export naar Python'.")
#                         st.stop()


#                     params = {
#                         "POWER_MW": power_mw, "CAPACITY_MWH": capacity_mwh,
#                         "MIN_SOC": min_soc, "MAX_SOC": max_soc,
#                         "EFF_CH": eff_ch, "EFF_DIS": eff_dis,
#                         "MAX_CYCLES": max_cycles, "INIT_SOC": 0.5,
#                         "SUPPLY_COSTS": supply_costs, "TRANSPORT_COSTS": transport_costs,
#                         "STRATEGY_CHOICE": strategy_choice, "TIME_STEP_H": 0.25,
#                     }
#                     params.pop("BATTERY_CONFIG", None) 

#                     status_placeholder = st.empty()
#                     def progress_callback(msg):
#                         status_placeholder.info(f"⏳ {msg}")
                    
#                     results = run_revenue_model(params, input_df, progress_callback)
#                     st.session_state.revenue_results = results
#                     status_placeholder.empty()
#                 st.rerun()

#     # with col2:
#     #     st.subheader("Results")
#     #     results = st.session_state.revenue_results
#     #     if results:
#     #         if results["error"]:
#     #             st.error(results["error"])
#     #         else:
#     #             st.success("Analysis complete!")
                
#     #             summary = results["summary"]
#     #             # --- ADD THIS LINE ---
#     #             st.info(f"**Analysis Method Used:** {summary.get('optimization_method', 'Not specified')}")

#     #             st.metric("Total Cycles", f"{summary.get('total_cycles', 0):.1f}")
#     #             # Add more metrics from your summary dictionary here if needed
                
#     #             for warning in results["warnings"]:
#     #                 st.warning(warning)
                
#     #             st.download_button(
#     #                 label="📥 Download Results (Excel)",
#     #                 data=results["output_file_bytes"],
#     #                 file_name=f"Revenue_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
#     #                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#     #             )
#     #     else:
#     #         st.info("Configure parameters and click 'Run Analysis' to see results.")

#     with col2:
#         st.subheader("Results")
#         results = st.session_state.revenue_results
#         if not results:
#             st.info("Configure parameters and click 'Run Analysis' to see results.")
#         elif results["error"]:
#             st.error(results["error"])
#         else:
#             st.success("Analysis complete!")
#             summary = results["summary"]
#             df_original = results["df"] # The original, high-resolution data
    
#             # --- Display Summary Metrics & Download Button ---
#             st.info(f"**Analysis Method Used:** {summary.get('optimization_method', 'Not specified')}")
            
#             summary_cols = st.columns(3)
    
#             # --- CORRECTED LOGIC ---
#             # 1. Find the name of the final result column in the DataFrame
#             total_result_col = find_total_result_column(df_original)
            
#             # 2. Calculate the net result by summing that column
#             net_result = 0 # Default to 0
#             if total_result_col:
#                 net_result = df_original[total_result_col].sum()
#             # --- END OF CORRECTION ---
    
#             summary_cols[0].metric("Net Result / Revenue", f"€ {net_result:,.0f}")
#             summary_cols[1].metric("Total Cycles", f"{summary.get('total_cycles', 0):.1f}")
#             summary_cols[2].metric("Infeasible Days", f"{len(summary.get('infeasible_days', []))}")
                
#             for warning in results["warnings"]:
#                 st.warning(warning)
    
#             st.download_button(
#                 label="📥 Download Full Results (Excel)",
#                 data=results["output_file_bytes"],
#                 file_name=f"Revenue_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
#                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )
#             st.markdown("---")
    
    
#             # --- Interactive Plotting Section ---
#             st.subheader("📊 Interactive Charts")
    
#             # 1. UI: Create the resolution selector
#             resolution = st.selectbox(
#                 "Select Chart Time Resolution",
#                 ('15 Min (Original)', 'Hourly', 'Daily', 'Monthly', 'Yearly')
#             )
    
#             # 2. DATA: Resample data based on user's choice
#             df_resampled = resample_data(df_original.copy(), resolution)
    
#             # 3. PLOTS: Create tabs and display the charts
#             tab1, tab2, tab3 = st.tabs(["💰 Financial Results", "⚡ Energy Profiles", "🔋 Battery SoC"])
    
#             with tab1:
#                 # Find the correct financial column to plot
#                 total_result_col = find_total_result_column(df_resampled)
#                 if total_result_col:
#                     fig_finance = px.line(
#                         df_resampled, 
#                         x=df_resampled.index, 
#                         y=total_result_col,
#                         title=f"Financial Result ({resolution})",
#                         labels={"x": "Date", "y": "Amount (€)"}
#                     )
#                     st.plotly_chart(fig_finance, use_container_width=True)
#                 else:
#                     st.warning("Could not find a 'total_result' column to plot.")
    
#             with tab2:
#                 st.markdown("#### Production & Consumption")
#                 # Use the resampled data for these plots
#                 fig_pv = px.line(
#                     df_resampled, 
#                     x=df_resampled.index, 
#                     y='production_PV',
#                     title=f"PV Production ({resolution})",
#                     labels={"x": "Date", "y": "Energy (kWh)"}
#                 )
#                 st.plotly_chart(fig_pv, use_container_width=True)
    
#                 fig_load = px.line(
#                     df_resampled, 
#                     x=df_resampled.index, 
#                     y='load',
#                     title=f"Load ({resolution})",
#                     labels={"x": "Date", "y": "Energy (kWh)"}
#                 )
#                 st.plotly_chart(fig_load, use_container_width=True)
    
#             with tab3:
#                 st.markdown("#### Battery State of Charge (SoC)")
#                 st.info("This chart is always shown in the original 15-minute resolution.")
#                 # IMPORTANT: Use the ORIGINAL DataFrame for this plot
#                 fig_soc = px.line(
#                     df_original, 
#                     x=df_original.index, 
#                     y='SoC_kWh',
#                     title="Battery SoC (15 Min Resolution)",
#                     labels={"x": "Date", "y": "State of Charge (kWh)"}
#                 )
#             st.plotly_chart(fig_soc, use_container_width=True)

    
    # if st.button("⬅️ Back to Home"):
    #     st.session_state.page = "Home"
    #     st.session_state.revenue_results = None # Clear results on exit
    #     st.rerun()

def show_revenue_analysis_page():
    display_header("Battery Revenue Analysis 🔋")
    st.write("Upload a data file and configure the battery parameters to run a revenue simulation.")

    # --- Configuration Sidebar ---
    # The entire configuration now lives neatly in the sidebar.
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        uploaded_file = st.file_uploader("Upload Input Data (CSV or Excel)", type=['csv', 'xlsx'])
        
        st.subheader("Optimization Strategy")
        goal_choice = st.radio(
            "What is your primary financial goal?",
            ("Minimize My Energy Bill", "Generate Revenue Through Market Trading"),
            horizontal=True,
            label_visibility="collapsed"
        )
        
        if goal_choice == "Minimize My Energy Bill":
            st.write("_Use assets to reduce overall energy costs by smartly using solar power and avoiding high grid prices._")
            strategy_choice = st.selectbox(
                "Select a cost-minimization strategy:",
                ("Prioritize Self-Consumption", "Optimize on Day-Ahead Market")
            )
        else: # Generate Revenue
            st.write("_Actively use assets to trade on energy markets and generate direct profit._")
            strategy_choice = st.selectbox(
                "Select a revenue-generation strategy:",
                ("Simple Battery Trading (Imbalance)", "Advanced Whole-System Trading (Imbalance)")
            )

        st.subheader("Battery Parameters")
        power_mw = st.number_input("Vermogen batterij (MW)", value=1.0, min_value=0.1, step=0.1)
        capacity_mwh = st.number_input("Capaciteit batterij (MWh)", value=2.0, min_value=0.1, step=0.1)
        min_soc = st.slider("Minimum SoC", 0.0, 1.0, 0.05)
        max_soc = st.slider("Maximum SoC", 0.0, 1.0, 0.95)
        eff_ch = st.slider("Efficiëntie opladen", 0.8, 1.0, 0.95)
        eff_dis = st.slider("Efficiëntie ontladen", 0.8, 1.0, 0.95)

        st.subheader("Cost & Other Parameters")
        max_cycles = st.number_input("Max cycli per jaar", value=600, min_value=1)
        supply_costs = st.number_input("Kosten energieleverancier (€/MWh)", value=20.0)
        transport_costs = st.number_input("Transportkosten afname (€/MWh)", value=15.0)

    # --- PART 1: SIMULATION CONTROLS (Top of the main page) ---
    st.subheader("Run Simulation")
    if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
        if uploaded_file is None:
            st.error("Please upload an input file.")
        else:
            with st.spinner("Reading data and running model... Please wait."):
                try:
                    if uploaded_file.name.endswith('.csv'):
                        input_df = pd.read_csv(uploaded_file, header=0)
                    else:
                        input_df = pd.read_excel(uploaded_file, sheet_name='Export naar Python', header=0)
                except Exception as e:
                    st.error(f"Error reading file: {e}. Ensure the sheet is named 'Export naar Python'.")
                    st.stop()
                
                params = {
                    "POWER_MW": power_mw, "CAPACITY_MWH": capacity_mwh,
                    "MIN_SOC": min_soc, "MAX_SOC": max_soc, "EFF_CH": eff_ch,
                    "EFF_DIS": eff_dis, "MAX_CYCLES": max_cycles, "INIT_SOC": 0.5,
                    "SUPPLY_COSTS": supply_costs, "TRANSPORT_COSTS": transport_costs,
                    "STRATEGY_CHOICE": strategy_choice, "TIME_STEP_H": 0.25
                }
                
                status_placeholder = st.empty()
                def progress_callback(msg):
                    status_placeholder.info(f"⏳ {msg}")
                
                results = run_revenue_model(params, input_df, progress_callback)
                st.session_state.revenue_results = results
                status_placeholder.empty()
            st.rerun()

    # --- PART 2: RESULTS DISPLAY (Below the run button, full width) ---
    st.markdown("---")
    results = st.session_state.revenue_results
    
    if not results:
        st.info("Configure your simulation in the sidebar and click 'Run Analysis' to see the results.")
    elif results["error"]:
        st.error(results["error"])
    else:
        summary = results["summary"]
        df_original = results.get("df")

        # --- A. Summary Section ---
        st.subheader("📈 Results Summary")
        st.info(f"**Analysis Method Used:** {summary.get('optimization_method', 'Not specified')}")
        
        summary_cols = st.columns(3)
        total_result_col = find_total_result_column(df_original)
        net_result = df_original[total_result_col].sum() if total_result_col else 0
        
        summary_cols[0].metric("Net Result / Revenue", f"€ {net_result:,.0f}")
        summary_cols[1].metric("Total Cycles", f"{summary.get('total_cycles', 0):.1f}")
        summary_cols[2].metric("Infeasible Days", f"{len(summary.get('infeasible_days', []))}")
        
        for warning in results["warnings"]:
            st.warning(warning)

        st.download_button(
            label="📥 Download Full Results (Excel)",
            data=results["output_file_bytes"],
            file_name=f"Revenue_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.markdown("<br>", unsafe_allow_html=True) # Add some space

        # --- B. Interactive Plotting Section ---
        if df_original is not None and not df_original.empty:
            st.subheader("📊 Interactive Charts")
            resolution = st.selectbox(
                "Select Chart Time Resolution",
                ('15 Min (Original)', 'Hourly', 'Daily', 'Monthly', 'Yearly')
            )
            df_resampled = resample_data(df_original.copy(), resolution)
            
            tab1, tab2, tab3 = st.tabs(["💰 Financial Results", "⚡ Energy Profiles", "🔋 Battery SoC"])
            with tab1:
                if total_result_col:
                    fig_finance = px.line(df_resampled, x=df_resampled.index, y=total_result_col, title=f"Financial Result ({resolution})", labels={"x": "Date", "y": "Amount (€)"})
                    st.plotly_chart(fig_finance, use_container_width=True)
                else:
                    st.warning("Could not find a 'total_result' column to plot.")
            with tab2:
                st.markdown("#### Production & Consumption")
                fig_pv = px.line(df_resampled, x=df_resampled.index, y='production_PV', title=f"PV Production ({resolution})", labels={"x": "Date", "y": "Energy (kWh)"})
                st.plotly_chart(fig_pv, use_container_width=True)
                fig_load = px.line(df_resampled, x=df_resampled.index, y='load', title=f"Load ({resolution})", labels={"x": "Date", "y": "Energy (kWh)"})
                st.plotly_chart(fig_load, use_container_width=True)
            with tab3:
                st.markdown("#### Battery State of Charge (SoC)")
                st.info("This chart is always shown in the original 15-minute resolution.")
                fig_soc = px.line(df_original, x=df_original.index, y='SoC_kWh', title="Battery SoC (15 Min Resolution)", labels={"x": "Date", "y": "State of Charge (kWh)"})
                st.plotly_chart(fig_soc, use_container_width=True)
        else:
             st.warning("The model ran, but no data was returned for plotting.")

    # --- Navigation ---
    if st.button("⬅️ Back to Home"):
        st.session_state.page = "Home"
        st.session_state.revenue_results = None
        st.rerun()



def show_model_page():
    # --- ADD THIS CODE AT THE TOP OF THE FUNCTION ---
    # Define custom CSS for smaller metric fonts
    st.markdown("""
    <style>
    .metric-label {
        font-size: 14px;
        color: #555555;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 600;
        line-height: 1.2;
    }
    </style>
    """, unsafe_allow_html=True)

    # Helper function to display the custom metric
    def custom_metric(label, value):
        st.markdown(f'<p class="metric-label">{label}</p><p class="metric-value">{value}</p>', unsafe_allow_html=True)
    # --- END OF ADDED CODE ---
    project_name = st.session_state.current_project_name
    if not project_name or project_name not in st.session_state.projects:
        st.error("Error: No project loaded."); st.session_state.page = "Project_Selection"; st.rerun()
        return
    
    project_data = st.session_state.projects[project_name]
    i = project_data['inputs']
    
    display_header(f"Business Case: {project_name}")

    nav_cols = st.columns([1, 1, 5])
    if nav_cols[0].button("⬅️ Back to Projects"): st.session_state.page = "Project_Selection"; st.rerun()
    if nav_cols[1].button("💾 Save Project"):
        project_data['last_saved'] = datetime.now().isoformat(); save_projects(); st.toast(f"Project '{project_name}' saved!")

    # --- Sidebar for Inputs ---
    with st.sidebar:
        st.title("Configuration")
        project_data['type'] = st.selectbox("Select Project Type",["BESS & PV", "BESS-only", "PV-only"],index=["BESS & PV", "BESS-only", "PV-only"].index(project_data['type']),key=f"{project_name}_type")
        st.header("General & Financial")
        with st.expander("Time/Duration & EIA", expanded=True):
            i['project_term'] = st.slider('Project Term (years)', 5, 40, i['project_term'], key=f"{project_name}_g_term")
            i['eia_pct'] = st.slider('Energy Investment Allowance (%)', 0.0, 100.0, i['eia_pct'] * 100, key=f"{project_name}_eia") / 100
            if 'BESS' in project_data['type']:
                i['lifespan_battery_tech'] = st.slider('BESS Lifespan (technical)', 5, 20, i['lifespan_battery_tech'], key=f"{project_name}_g_life_b")
                i['depr_period_battery'] = st.slider('BESS Depreciation Period', 5, 20, i['depr_period_battery'], key=f"{project_name}_g_depr_b")
            if 'PV' in project_data['type']:
                i['lifespan_pv_tech'] = st.slider('PV Lifespan (technical)', 10, 40, i['lifespan_pv_tech'], key=f"{project_name}_g_life_pv")
                i['depr_period_pv'] = st.slider('PV Depreciation Period', 10, 40, i['depr_period_pv'], key=f"{project_name}_g_depr_pv")
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
        with st.expander("Indexations"):
            i['inflation'] = st.slider('General Inflation (%)', 0.0, 10.0, i['inflation'] * 100, key=f"{project_name}_g_inf") / 100
            st.markdown("###### Indexations relative to inflation:")
            i['idx_trading_income'] = st.slider('Trading Income Index (%)', -5.0, 5.0, i['idx_trading_income'] * 100, key=f"{project_name}_idx_ti") / 100
            i['idx_ppa_income'] = st.slider('PPA Income Index (%)', -5.0, 5.0, i['idx_ppa_income'] * 100, key=f"{project_name}_idx_ppa") / 100
            i['idx_supplier_costs'] = st.slider('Supplier Costs Index (%)', -5.0, 5.0, i['idx_supplier_costs'] * 100, key=f"{project_name}_idx_sc") / 100
            i['idx_grid_op'] = st.slider('Grid Operator Index (%)', -5.0, 5.0, i['idx_grid_op'] * 100, key=f"{project_name}_idx_go") / 100
            i['idx_om_bess'] = st.slider('BESS O&M Index (%)', -5.0, 5.0, i['idx_om_bess'] * 100, key=f"{project_name}_idx_omb") / 100
            i['idx_om_pv'] = st.slider('PV O&M Index (%)', -5.0, 5.0, i['idx_om_pv'] * 100, key=f"{project_name}_idx_ompv") / 100
            i['idx_other_costs'] = st.slider('Other Annual Costs Index (%)', -5.0, 5.0, i['idx_other_costs'] * 100, key=f"{project_name}_idx_oc") / 100
        st.header("Grid Connection")
        with st.expander("One-Time Costs"):
            i['grid_one_time_bess'] = st.number_input('One-time BESS Costs (€)', value=i['grid_one_time_bess'], key=f"{project_name}_grid_ot_bess")
            i['grid_one_time_pv'] = st.number_input('One-time PV Costs (€)', value=i['grid_one_time_pv'], key=f"{project_name}_grid_ot_pv")
            i['grid_one_time_general'] = st.number_input('One-time General Costs (€)', value=i['grid_one_time_general'], key=f"{project_name}_grid_ot_gen")
        with st.expander("Annual Costs (Year 1)"):
            i['grid_annual_fixed'] = st.number_input('Annual Fixed Charge (€/year)', value=i['grid_annual_fixed'], key=f"{project_name}_grid_ann_fixed")
            i['grid_annual_kw_max'] = st.number_input('Annual cost kW max (€/year)', value=i['grid_annual_kw_max'], key=f"{project_name}_grid_ann_kwmax")
            i['grid_annual_kw_contract'] = st.number_input('Annual cost kW contract (€/year)', value=i['grid_annual_kw_contract'], key=f"{project_name}_grid_ann_kwcont")
            i['grid_annual_kwh_offtake'] = st.number_input('Annual cost kWh offtake (€/year)', value=i['grid_annual_kwh_offtake'], key=f"{project_name}_grid_ann_kwh")
        if 'BESS' in project_data['type']:
            st.header("🔋 BESS")
            with st.expander("Technical"):
                i['bess_power_kw'] = st.number_input("Power (kW)", value=i['bess_power_kw'], key=f"{project_name}_bess_p_kw")
                i['bess_capacity_kwh'] = st.number_input("Capacity (kWh)", value=i['bess_capacity_kwh'], key=f"{project_name}_bess_c_kwh")
                i['bess_min_soc'], i['bess_max_soc'] = st.slider("Operating SoC Range", 0.0, 1.0, (i['bess_min_soc'], i['bess_max_soc']), key=f"{project_name}_bess_soc")
                i['bess_charging_eff'] = st.slider("Charging Efficiency", 0.80, 1.00, i['bess_charging_eff'], step=0.01, key=f"{project_name}_bess_chg_eff")
                i['bess_discharging_eff'] = st.slider("Discharging Efficiency", 0.80, 1.00, i['bess_discharging_eff'], step=0.01, key=f"{project_name}_bess_dis_eff")
                i['bess_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 10.0, i['bess_annual_degradation'] * 100, key=f"{project_name}_bess_deg") / 100
                i['bess_cycles_per_year'] = st.number_input("Cycles per Year", value=i['bess_cycles_per_year'], key=f"{project_name}_bess_cycles")
            with st.expander("CAPEX Assumptions"):
                i['bess_capex_per_kwh'] = st.number_input("BESS Price (€/kWh)", value=i['bess_capex_per_kwh'], key=f"{project_name}_bess_capex_price")
                i['bess_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['bess_capex_civil_pct'] * 100, key=f"{project_name}_bess_capex_civil") / 100
                i['bess_capex_it_per_kwh'] = st.number_input("IT/Control (€/kWh)", value=i['bess_capex_it_per_kwh'], key=f"{project_name}_bess_capex_it")
                i['bess_capex_security_per_kwh'] = st.number_input("Security (€/kWh)", value=i['bess_capex_security_per_kwh'], key=f"{project_name}_bess_capex_sec")
                i['bess_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['bess_capex_permits_pct'] * 100, key=f"{project_name}_bess_capex_perm") / 100
                i['bess_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['bess_capex_mgmt_pct'] * 100, key=f"{project_name}_bess_capex_mgmt") / 100
                i['bess_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['bess_capex_contingency_pct'] * 100, key=f"{project_name}_bess_capex_cont") / 100
            with st.expander("Income Assumptions"):
                i['bess_income_trading_per_mw_year'] = st.number_input("Trading Income (€/MW/year)", value=i['bess_income_trading_per_mw_year'], key=f"{project_name}_bess_inc_trad")
                i['bess_income_ctrl_party_pct'] = st.slider("Control Party Costs (% of Income)", 0.0, 25.0, i['bess_income_ctrl_party_pct'] * 100, key=f"{project_name}_bess_inc_ctrl") / 100
                i['bess_income_supplier_cost_per_mwh'] = st.number_input("Energy Supplier Costs (€/MWh)", value=i['bess_income_supplier_cost_per_mwh'], key=f"{project_name}_bess_inc_supp")
            with st.expander("OPEX Assumptions (Year 1)"):
                i['bess_opex_om_per_year'] = st.number_input("O&M (€/year)", value=i['bess_opex_om_per_year'], key=f"{project_name}_bess_opex_om")
                i['bess_opex_retribution'] = st.number_input("Retribution (€/year)", value=i['bess_opex_retribution'], key=f"{project_name}_bess_opex_ret")
                i['bess_opex_asset_mgmt_per_mw_year'] = st.number_input("Asset Management (€/MW/year)", value=i['bess_opex_asset_mgmt_per_mw_year'], key=f"{project_name}_bess_opex_am")
                i['bess_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['bess_opex_insurance_pct'] * 100, key=f"{project_name}_bess_opex_ins") / 100
                i['bess_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['bess_opex_property_tax_pct'] * 100, format="%.3f", key=f"{project_name}_bess_opex_tax") / 100
                i['bess_opex_overhead_per_kwh_year'] = st.number_input("Overhead (€/kWh/year)", value=i['bess_opex_overhead_per_kwh_year'], key=f"{project_name}_bess_opex_over")
                i['bess_opex_other_per_kwh_year'] = st.number_input("Other (€/kWh/year)", value=i['bess_opex_other_per_kwh_year'], key=f"{project_name}_bess_opex_oth")
        if 'PV' in project_data['type']:
            st.header("☀️ Solar PV")
            with st.expander("Technical"):
                i['pv_panel_count'] = st.number_input("Number of Panels", value=i['pv_panel_count'], key=f"{project_name}_pv_panel_c")
                i['pv_power_per_panel_wp'] = st.number_input("Power per Panel (Wp)", value=i['pv_power_per_panel_wp'], key=f"{project_name}_pv_ppp_wp")
                i['pv_full_load_hours'] = st.number_input("Full Load Hours (kWh/kWp)", value=i['pv_full_load_hours'], key=f"{project_name}_pv_flh")
                i['pv_annual_degradation'] = st.slider("Annual Degradation (%)", 0.0, 2.0, i['pv_annual_degradation'] * 100, format="%.2f", key=f"{project_name}_pv_deg") / 100
            with st.expander("CAPEX Assumptions"):
                i['pv_capex_per_wp'] = st.number_input("PV Price (€/Wp)", value=i['pv_capex_per_wp'], format="%.3f", key=f"{project_name}_pv_capex_price")
                i['pv_capex_civil_pct'] = st.slider("Civil/Installation (%)", 0.0, 20.0, i['pv_capex_civil_pct'] * 100, key=f"{project_name}_pv_capex_civil") / 100
                i['pv_capex_security_pct'] = st.slider("Security (%)", 0.0, 10.0, i['pv_capex_security_pct'] * 100, key=f"{project_name}_pv_capex_sec") / 100
                i['pv_capex_permits_pct'] = st.slider("Permits & Fees (%)", 0.0, 10.0, i['pv_capex_permits_pct'] * 100, key=f"{project_name}_pv_capex_perm") / 100
                i['pv_capex_mgmt_pct'] = st.slider("Project Management (%)", 0.0, 10.0, i['pv_capex_mgmt_pct'] * 100, key=f"{project_name}_pv_capex_mgmt") / 100
                i['pv_capex_contingency_pct'] = st.slider("Contingency (%)", 0.0, 15.0, i['pv_capex_contingency_pct'] * 100, key=f"{project_name}_pv_capex_cont") / 100
            with st.expander("Income Assumptions"):
                i['pv_income_ppa_per_mwp'] = st.number_input("Income PPA (€/MWp)", value=i['pv_income_ppa_per_mwp'], key=f"{project_name}_pv_inc_ppa_mwp")
                i['pv_income_ppa_per_kwh'] = st.number_input("Income PPA (€/kWh)", value=i['pv_income_ppa_per_kwh'], format="%.4f", key=f"{project_name}_pv_inc_ppa_kwh")
                i['pv_income_curtailment_per_mwp'] = st.number_input("Income Curtailment (€/MWp)", value=i['pv_income_curtailment_per_mwp'], key=f"{project_name}_pv_inc_curt_mwp")
                i['pv_income_curtailment_per_kwh'] = st.number_input("Income Curtailment (€/kWh)", value=i['pv_income_curtailment_per_kwh'], format="%.4f", key=f"{project_name}_pv_inc_curt_kwh")
            with st.expander("OPEX Assumptions (Year 1)"):
                i['pv_opex_om_y1'] = st.number_input("O&M (€/year)", value=i['pv_opex_om_y1'], key=f"{project_name}_pv_opex_om")
                i['pv_opex_retribution'] = st.number_input("Retribution (€/year)", value=i['pv_opex_retribution'], key=f"{project_name}_pv_opex_ret")
                i['pv_opex_insurance_pct'] = st.slider("Insurance (% of CAPEX)", 0.0, 5.0, i['pv_opex_insurance_pct'] * 100, key=f"{project_name}_pv_opex_ins") / 100
                i['pv_opex_property_tax_pct'] = st.slider("Property Tax (% of CAPEX)", 0.0, 2.0, i['pv_opex_property_tax_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_tax") / 100
                i['pv_opex_overhead_pct'] = st.slider("Overhead (% of CAPEX)", 0.0, 2.0, i['pv_opex_overhead_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_over") / 100
                i['pv_opex_other_pct'] = st.slider("Other (% of CAPEX)", 0.0, 2.0, i['pv_opex_other_pct'] * 100, format="%.3f", key=f"{project_name}_pv_opex_oth") / 100

        if st.button('Run Model', type="primary", key=f"{project_name}_run"):
            project_data['last_saved'] = datetime.now().isoformat()
            project_data['results'] = run_financial_model(i, project_data['type'])
            save_projects()
            st.rerun()

    # --- Results Display ---
    if 'results' in project_data:
        results_dict = project_data['results']
        results_df = results_dict['df']
        metrics = results_dict['metrics']
        bess_kpis = results_dict['bess_kpis']
        pv_kpis = results_dict['pv_kpis']
        tab1, tab2, tab3 = st.tabs(["📊 Financial Summary", "🔋 BESS Details", "☀️ PV Details"])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                with st.container(border=True):
                    st.subheader("Project Result")
                    payback_val_proj = metrics['payback_period']
                    custom_metric("Investment", f"€{metrics['total_investment']:,.0f}")
                    custom_metric("Cumulative EBITDA end of term", f"€{metrics['cumulative_ebitda_end']:,.0f}")
                    custom_metric("Project IRR (10 years)", f"{metrics['project_irr']:.1%}")
                    custom_metric("Payback period (simple)", f"{payback_val_proj:.1f} jaar" if isinstance(payback_val_proj, (int,float)) else "N/A")
                    fig_proj = generate_summary_chart(results_df, 'total_ebitda', 'cumulative_ebitda', 'Project Result (based on EBITDA)')
                    st.plotly_chart(fig_proj, use_container_width=True)

            with col2:
                with st.container(border=True):
                    st.subheader("Return on Equity")
                    payback_val_eq = metrics['payback_period']
                    custom_metric("Investment", f"€{metrics['total_investment']:,.0f}")
                    custom_metric("Cumulative cash flow end of term", f"€{metrics['cumulative_cash_flow_end']:,.0f}")
                    custom_metric("Return on equity (10 years)", f"{metrics['equity_irr']:.1%}")
                    custom_metric("Payback period", f"{payback_val_eq:.1f} jaar" if isinstance(payback_val_eq, (int,float)) else "N/A")
                    fig_eq = generate_summary_chart(results_df, 'net_cash_flow', 'cumulative_cash_flow', 'Cash Flow Equity')
                    st.plotly_chart(fig_eq, use_container_width=True)


        with tab2:
            if 'BESS' in project_data['type']:
                st.header("🔋 BESS Details")
                bess_kpi_map = { "Technical": {'Capacity Factor': 'h', 'SoC Available': '%', 'Usable Capacity': 'kWh', 'C-Rate': '', 'Round Trip Efficiency (RTE)': '%'}, "CAPEX": {'Purchase Costs': '€', 'IT & Security Costs': '€', 'Civil Works': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€', 'total_capex': '€'}, "OPEX (Year 1)": {'om_y1':'€', 'retribution_y1':'€', 'asset_mgmt_y1':'€', 'insurance_y1':'€', 'property_tax_y1':'€', 'overhead_y1':'€', 'other_y1':'€'} }
                pie_col1, pie_col2 = st.columns(2)
                with pie_col1:
                    capex_data = {k: v for k, v in bess_kpis.items() if k in ['Purchase Costs', 'IT & Security Costs', 'Civil Works', 'Permits & Fees', 'Project Management', 'Contingency']}
                    if any(v > 0 for v in capex_data.values()):
                        df_capex = pd.DataFrame(list(capex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
                        fig_capex = px.pie(df_capex, values='Cost', names='Component', title='BESS CAPEX Breakdown', hole=.3)
                        st.plotly_chart(fig_capex, use_container_width=True)
                with pie_col2:
                    opex_data = {k.replace('_y1','').replace('_',' ').title(): v for k, v in bess_kpis.items() if '_y1' in k}
                    if any(v > 0 for v in opex_data.values()):
                        df_opex = pd.DataFrame(list(opex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
                        fig_opex = px.pie(df_opex, values='Cost', names='Component', title='BESS OPEX (Year 1) Breakdown', hole=.3)
                        st.plotly_chart(fig_opex, use_container_width=True)
                for section, keys in bess_kpi_map.items():
                    st.subheader(section)
                    st.dataframe(create_kpi_dataframe(bess_kpis, {section: keys}), use_container_width=True)
            else: st.info("BESS not included in this project type.")

        with tab3:
            if 'PV' in project_data['type']:
                st.header("☀️ PV Details")
                pv_kpi_map = { "Technical": {'Total Peak Power': 'kWp', 'Production (Year 1)': 'kWh'}, "CAPEX": {'Purchase Costs': '€', 'Civil Works': '€', 'Security': '€', 'Permits & Fees': '€', 'Project Management': '€', 'Contingency': '€', 'total_capex': '€'}, "OPEX (Year 1)": {'om_y1':'€', 'retribution_y1':'€', 'insurance_y1':'€', 'property_tax_y1':'€', 'overhead_y1':'€', 'other_y1':'€'} }
                pie_col1, pie_col2 = st.columns(2)
                with pie_col1:
                    capex_data = {k: v for k, v in pv_kpis.items() if k in ['Purchase Costs', 'Civil Works', 'Security', 'Permits & Fees', 'Project Management', 'Contingency']}
                    if any(v > 0 for v in capex_data.values()):
                        df_capex = pd.DataFrame(list(capex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
                        fig_capex = px.pie(df_capex, values='Cost', names='Component', title='PV CAPEX Breakdown', hole=.3)
                        st.plotly_chart(fig_capex, use_container_width=True)
                with pie_col2:
                    opex_data = {k.replace('_y1','').replace('_',' ').title(): v for k, v in pv_kpis.items() if '_y1' in k}
                    if any(v > 0 for v in opex_data.values()):
                        df_opex = pd.DataFrame(list(opex_data.items()), columns=['Component', 'Cost']).sort_values('Cost', ascending=False)
                        fig_opex = px.pie(df_opex, values='Cost', names='Component', title='PV OPEX (Year 1) Breakdown', hole=.3)
                        st.plotly_chart(fig_opex, use_container_width=True)
                for section, keys in pv_kpi_map.items():
                    st.subheader(section)
                    st.dataframe(create_kpi_dataframe(pv_kpis, {section: keys}), use_container_width=True)
            else: st.info("PV not included in this project type.")
    else:
        st.info('Adjust inputs in the sidebar and click "Run Model" to see the financial forecast.')


# --- MAIN ROUTER ---
with st.sidebar:
    st.markdown("---"); st.header("Navigation")
    if st.button("🏠 Back to Home"): 
        st.session_state.page = "Home"
        st.session_state.renaming_project = None
        st.session_state.deleting_project = None
        st.session_state.revenue_results = None
        st.rerun()
    st.markdown("---"); st.header("Data Management")
    if st.button("📂 Load Projects from File"): load_projects(); st.rerun()

if 'projects' not in st.session_state or not st.session_state.projects:
    if os.path.exists(PROJECTS_FILE):
        load_projects()

if st.session_state.page == "Home":
    show_home_page()
elif st.session_state.page == "Project_Selection":
    show_project_selection_page()
elif st.session_state.page == "Model":
    show_model_page()
elif st.session_state.page == "Revenue_Analysis":
    show_revenue_analysis_page()
