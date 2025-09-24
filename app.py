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
from revenue_logic import run_revenue_model
import streamlit as st
import base64
import os
from battery_shaving_core import BatteryShavingAnalyzer # Add this

@st.cache_data
def get_image_as_base64(path):
    """Encodes an image to base64 for embedding in HTML."""
    if not os.path.exists(path):
        st.error(f"Icon file not found at: {path}")
        return None
    with open(path, "rb") as f:
        data = f.read()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"

def create_horizontal_diagram_with_icons(situation_name, icons_b64):
    """
    Generates the correct horizontal diagram using PNG icons and corrected connections
    for any of the 7 situations, with all labels in English.
    """
    # Defines BOTH the start and end arrowheads for the lines
    arrow_defs = """
        <defs>
            <marker id="arrow-end-yellow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 8 4 L 0 8 z" fill="#FDB813" />
            </marker>
            <marker id="arrow-start-yellow" viewBox="0 0 8 8" refX="1" refY="4" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 8 0 L 0 4 L 8 8 z" fill="#FDB813" />
            </marker>
        </defs>
    """

    # Helper function to create a component with an icon and a label
    def create_node(x, y, label, icon_b64, w=100, h=80):
        # Using the gray boxes from your code
        return f'''
            <g transform="translate({x}, {y})">
                <rect x="0" y="0" width="{w}" height="{h}" rx="8" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1"/>
                <image href="{icon_b64}" x="{w*0.25}" y="5" width="{w*0.5}" height="{h*0.5}"/>
                <text x="{w/2}" y="{h*0.8}" text-anchor="middle" font-weight="bold" font-size="12px" fill="#333">{label}</text>
            </g>
        '''
    
    # Define consistent positions with English keys
    POS = {
        'grid': (20, 185), 'main_meter': (180, 185),
        'pv': (680, 20), 'load': (680, 185), 'battery': (680, 350),
        'meter_pv': (520, 20), 'meter_battery': (520, 350),
        'pap_main': (350, 185),
        'sap1': (350, 80), 'pap_center_sit6': (350, 185), 'sap2': (350, 290)
    }

    # Defines the styles that use the markers from arrow_defs
    arrow = 'stroke="#FDB813" stroke-width="3" fill="none" marker-end="url(#arrow-end-yellow)"'
    arrow_two_way = 'stroke="#FDB813" stroke-width="3" fill="none" marker-start="url(#arrow-start-yellow)" marker-end="url(#arrow-end-yellow)"'
    direct_use_arrow = 'stroke="#FDB813" stroke-width="3" stroke-dasharray="6, 6" fill="none" marker-end="url(#arrow-end-yellow)"'

    nodes_to_draw = []
    lines_to_draw = []

    # Base components (Grid and Main Meter) now correctly use the two-way arrow
    nodes_to_draw.extend([
        create_node(POS['grid'][0], POS['grid'][1], 'Grid', icons_b64['grid']),
        create_node(POS['main_meter'][0], POS['main_meter'][1], 'Main Meter', icons_b64['meter'])
    ])
    lines_to_draw.append(f'<line x1="{POS["grid"][0]+100}" y1="{POS["grid"][1]+40}" x2="{POS["main_meter"][0]}" y2="{POS["main_meter"][1]+40}" {arrow_two_way} />')

    # --- Configure Diagram Based on Selected Situation ---
    # NOTE: Most situations use a height of 450px, but Sit 6 needs more vertical space.
    svg_height = 450
    if "Situation 6" in situation_name:
        svg_height = 500 # Increase canvas height for this specific case

    # All situations except #6 are the same as before
    if "Situation 1" in situation_name:
        nodes_to_draw.extend([
            create_node(POS['pap_main'][0], POS['pap_main'][1], 'PAP', icons_b64['alloc']),
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['load'][0], POS['load'][1], 'Load', icons_b64['load']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter'])
        ])
        lines_to_draw.extend([
            f'<line x1="{POS["main_meter"][0]+100}" y1="{POS["main_meter"][1]+40}" x2="{POS["pap_main"][0]}" y2="{POS["pap_main"][1]+40}" {arrow_two_way} />',
            f'<line x1="{POS["pap_main"][0]+100}" y1="{POS["pap_main"][1]+40}" x2="{POS["load"][0]}" y2="{POS["load"][1]+40}" {arrow} />',
            f'<path d="M {POS["meter_pv"][0]+45} {POS["meter_pv"][1]+80} L {POS["meter_pv"][0]+45} 145 L 400 145 L {POS["pap_main"][0]+50} {POS["pap_main"][1]}" {arrow} />',
            f'<line x1="{POS["pv"][0]}" y1="{POS["pv"][1]+40}" x2="{POS["meter_pv"][0]+100}" y2="{POS["meter_pv"][1]+40}" {arrow} />',
            
            # CORRECTED: Replaced curve with a simple, angled dashed path to the top of the Load box
            f'<path d="M {POS["meter_pv"][0]+55} {POS["meter_pv"][1]+80} L {POS["meter_pv"][0]+55} 145 L {POS["load"][0]+50} 145 L {POS["load"][0]+50} {POS["load"][1]}" {direct_use_arrow} />'
        ])

    elif "Situation 2" in situation_name:
        # --- Node Placement (Rearranged for perfect symmetry) ---
        nodes_to_draw.extend([
            # Top row (PV System)
            create_node(350, 80, 'SAP', icons_b64['alloc']),
            create_node(POS['meter_pv'][0], 80, 'PV Meter', icons_b64['meter']),
            create_node(POS['pv'][0], 80, 'PV', icons_b64['pv']),
            
            # Bottom row (Load System) - Symmetrically placed
            create_node(350, 290, 'PAP', icons_b64['alloc']), 
            create_node(POS['load'][0], 290, 'Load', icons_b64['load'])
        ])
        # --- Connections redrawn for the new layout ---
        lines_to_draw.extend([
            # 1. Main Meter -> SAP (Angled path to the top row)
            f'<path d="M 350 120 L 315 120 L 315 200 L {POS["main_meter"][0]+100} 200" {arrow} />',          
            
            # 2. CORRECTED: Main Meter -> PAP (New zig-zag path to the bottom row)
            f'<path d="M {POS["main_meter"][0]+100} 250 L 315 250 L 315 330 L 350 330" {arrow} />',
            
            # 3. SAP -> PV Meter (Straight line on the top row)
            f'<line x2="450" y1="120" x1="{POS["meter_pv"][0]}" y2="120" {arrow} />',
            
            # 4. PAP -> Load (Straight line on the bottom row)
            f'<line x1="450" y1="330" x2="{POS["load"][0]}" y2="330" {arrow} />',

            # 5. PV -> PV Meter (Straight line on the top row)
            f'<line x1="{POS["pv"][0]}" y1="120" x2="{POS["meter_pv"][0]+100}" y2="120" {arrow} />'
        ])

    elif "Situation 3" in situation_name:
        nodes_to_draw.extend([
            create_node(350, 185, 'PAP', icons_b64['alloc']),
            create_node(350, 350, 'SAP', icons_b64['alloc']),
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['load'][0], POS['load'][1], 'Load', icons_b64['load']),
            create_node(POS['battery'][0], POS['battery'][1], 'Battery', icons_b64['batt']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter']),
            create_node(POS['meter_battery'][0], POS['meter_battery'][1], 'Battery Meter', icons_b64['meter'])
        ])
        lines_to_draw.extend([
            # 1. PV -> PV Meter
            f'<line x1="{POS["pv"][0]}" y1="{POS["pv"][1]+40}" x2="{POS["meter_pv"][0]+100}" y2="{POS["meter_pv"][1]+40}" {arrow} />',
            
            # 2. PV Meter -> PAP
            f'<path d="M {POS["meter_pv"][0]+45} {POS["meter_pv"][1]+80} L 565 145 L {POS["pap_main"][0]+50} 145 L {POS["pap_main"][0]+50} {POS["load"][1]}" {arrow} />',
            
            # 3. Main Meter -> PAP (The outgoing arrow)
            f'<line x1="{POS["main_meter"][0]+100}" y1="{POS["main_meter"][1]+40}" x2="350" y2="225" {arrow} />',

            # 4. CORRECTED: PAP -> Main Meter (The incoming arrow, typo fixed)
            f'<line x1="350" y1="200" x2="{POS["main_meter"][0]+100}" y2="200" {arrow} />',
            
            # 5. PAP -> Load
            f'<line x1="450" y1="225" x2="{POS["load"][0]}" y2="{POS["load"][1]+40}" {arrow} />',

            # 6. Main Meter <-> SAP (Two-way zig-zag path)
            f'<path d="M {POS["main_meter"][0]+100} 250 L 315 250 L 315 390 L 350 390" {arrow_two_way} />',
            
            # 7. SAP <-> Battery Meter
            f'<line x1="450" y1="390" x2="{POS["meter_battery"][0]}" y2="{POS["meter_battery"][1]+40}" {arrow_two_way} />',
            
            # 8. Battery <-> Battery Meter
            f'<line x1="{POS["meter_battery"][0]+100}" y1="{POS["meter_battery"][1]+40}" x2="{POS["battery"][0]}" y2="{POS["battery"][1]+40}" {arrow_two_way} />',
            
            # 9. CORRECTED: Dashed line is now a clean zig-zag from PV Meter to Load
            f'<path d="M {POS["meter_pv"][0]+55} {POS["meter_pv"][1]+80} L 575 145 L {POS["load"][0]+50} 145 L {POS["load"][0]+50} {POS["load"][1]}" {direct_use_arrow} />'
        ])


    
    elif "Situation 4" in situation_name:
        nodes_to_draw.extend([
            create_node(POS['pap_main'][0], POS['pap_main'][1], 'PAP', icons_b64['alloc']),
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['load'][0], POS['load'][1], 'Load', icons_b64['load']),
            create_node(POS['battery'][0], POS['battery'][1], 'Battery', icons_b64['batt']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter']),
            create_node(POS['meter_battery'][0], POS['meter_battery'][1], 'Battery Meter', icons_b64['meter'])
        ])
        lines_to_draw.extend([
            # Connection from Main Meter to PAP
            f'<line x1="{POS["main_meter"][0]+100}" y1="{POS["main_meter"][1]+40}" x2="{POS["pap_main"][0]}" y2="{POS["pap_main"][1]+40}" {arrow} />',

            # 1. Line from PV Meter to PAP (reversed as previously requested)
            f'<path d="M {POS["meter_pv"][0]} 60 L 480 60 L 480 {POS["pap_main"][1]+20} L {POS["pap_main"][0]+100} {POS["pap_main"][1]+20}" {arrow} />',
            
            # 2. Line from PAP to Load (unchanged)
            f'<line x1="{POS["pap_main"][0]+100}" y1="{POS["pap_main"][1]+40}" x2="{POS["load"][0]}" y2="{POS["load"][1]+40}" {arrow} />',

            # 3. Line from PAP to Battery Meter (unchanged)
            f'<path d="M {POS["pap_main"][0]+100} {POS["pap_main"][1]+60} L 480 {POS["pap_main"][1]+60} L 480 390 L {POS["meter_battery"][0]} 390" {arrow} />',

            # Local connections from meters to assets
            f'<line x1="{POS["pv"][0]}" y1="{POS["pv"][1]+40}" x2="{POS["meter_pv"][0]+100}" y2="{POS["meter_pv"][1]+40}" {arrow} />',
            f'<line x1="{POS["meter_battery"][0]+100}" y1="{POS["meter_battery"][1]+40}" x2="{POS["battery"][0]}" y2="{POS["battery"][1]+40}" {arrow_two_way} />',

            # --- CORRECTED DASHED LINES ---
            # 1. Dashed line from PV Meter to Load (angled, not curved)
            f'<path d="M {POS["meter_pv"][0]+50} {POS["meter_pv"][1]+80} L {POS["meter_pv"][0]+50} 200 L {POS["load"][0]} 200" {direct_use_arrow} />',
            
            # 2. Dashed line from Battery Meter to Load (angled, not curved)
            f'<path d="M {POS["meter_battery"][0]+50} {POS["meter_battery"][1]} L {POS["meter_battery"][0]+50} 250 L {POS["load"][0]} 250" {direct_use_arrow} />',
            
            # 3. Dashed line from PV Meter to Battery Meter (angled, not curved)
            f'<path d="M {POS["meter_pv"][0]} {POS["meter_pv"][1]+20} L {POS["meter_pv"][0]-50} {POS["meter_pv"][1]+20} L {POS["meter_pv"][0]-50} {POS["meter_battery"][1]+60} L {POS["meter_battery"][0]} {POS["meter_battery"][1]+60}" {direct_use_arrow} />'
        ])

    elif "Situation 5" in situation_name:
        # --- Node Placement (As per the three-row layout) ---
        nodes_to_draw.extend([
            # Top Row
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter']),
            
            # Middle Row
            create_node(350, 185, 'SAP', icons_b64['alloc']),
            create_node(POS['meter_battery'][0], 185, 'Battery Meter', icons_b64['meter']),
            create_node(POS['battery'][0], 185, 'Battery', icons_b64['batt']),

            # Bottom Row
            create_node(350, 350, 'PAP', icons_b64['alloc']),
            create_node(POS['load'][0], 350, 'Load', icons_b64['load'])
        ])
        # --- Connections rebuilt to your final specification ---
        lines_to_draw.extend([
            # 1. PV -> PV Meter
            f'<line x1="{POS["pv"][0]}" y1="{POS["pv"][1]+40}" x2="{POS["meter_pv"][0]+100}" y2="{POS["meter_pv"][1]+40}" {arrow} />',
            
            # 2. CORRECTED: PV Meter -> SAP
            f'<line x1="{POS["meter_pv"][0]}" y1="{POS["meter_pv"][1]+40}" x2="450" y2="200" {arrow} />',
            
            # 3. Main Meter <-> SAP (Two-way connection)
            f'<line x2="{POS["main_meter"][0]+100}" y1="200" x1="350" y2="200" {arrow} />',
            f'<line x2="350" y1="225" x1="{POS["main_meter"][0]+100}" y2="225" {arrow} />',
            
            # 4. SAP -> Battery Meter
            f'<line x1="450" y1="225" x2="{POS["meter_battery"][0]}" y2="225" {arrow_two_way} />',

            # 5. Battery Meter <-> Battery (Two-way)
            f'<line x1="{POS["meter_battery"][0]+100}" y1="230" x2="{POS["battery"][0]}" y2="230" {arrow_two_way} />',

            # 6. CORRECTED: Main Meter -> PAP (Direct connection)
            f'<path d="M {POS["main_meter"][0]+100} 250 L 315 250 L 315 390 L 350 390" {arrow} />',

            # 7. PAP -> Load
            f'<line x1="450" y1="390" x2="{POS["load"][0]}" y2="390" {arrow} />',
            
            # 8. Dashed line for direct use from PV to Battery
            f'<path d="M {POS["pv"][0]} {POS["pv"][1]+60} C 640 120, 640 200, {POS["battery"][0]} {POS["battery"][1]-145}" {direct_use_arrow} />'
        ])

    elif "Situation 6" in situation_name:
        nodes_to_draw.extend([
            create_node(POS['sap1'][0], POS['sap1'][1], 'SAP1', icons_b64['alloc']),
            create_node(POS['pap_center_sit6'][0], POS['pap_center_sit6'][1], 'PAP', icons_b64['alloc']),
            create_node(POS['sap2'][0], POS['sap2'][1], 'SAP2', icons_b64['alloc']),
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['load'][0], POS['load'][1], 'Load', icons_b64['load']),
            create_node(POS['battery'][0], POS['battery'][1], 'Battery', icons_b64['batt']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter']),
            create_node(POS['meter_battery'][0], POS['meter_battery'][1], 'Battery Meter', icons_b64['meter'])
        ])
        # --- Connections rebuilt with three separate lines from Main Meter ---
        lines_to_draw.extend([
            # 1. NEW: Direct line from Main Meter (top-right) to SAP1
            f'<path d="M {POS["main_meter"][0]+100} {POS["main_meter"][1]+20} L 315 {POS["main_meter"][1]+20} L 315 {POS["sap1"][1]+40} L {POS["sap1"][0]} {POS["sap1"][1]+40}" {arrow} />',

            # 2. NEW: Direct line from Main Meter (center-right) to PAP
            f'<line x1="{POS["main_meter"][0]+100}" y1="{POS["main_meter"][1]+40}" x2="{POS["pap_center_sit6"][0]}" y2="{POS["pap_center_sit6"][1]+40}" {arrow} />',

            # 3. NEW: Direct line from Main Meter (bottom-right) to SAP2
            f'<path d="M {POS["main_meter"][0]+100} {POS["main_meter"][1]+60} L 315 {POS["main_meter"][1]+60} L 315 {POS["sap2"][1]+40} L {POS["sap2"][0]} {POS["sap2"][1]+40}" {arrow} />',
            
            # Connections from allocation points to assets (with your previous corrections)
            f'<line x1="{POS["meter_pv"][0]}" y1="{POS["meter_pv"][1]+40}" x2="{POS["sap1"][0]+100}" y2="{POS["sap1"][1]+40}" {arrow} />',
            f'<line x1="{POS["pap_center_sit6"][0]+100}" y1="{POS["pap_center_sit6"][1]+40}" x2="{POS["load"][0]}" y2="{POS["load"][1]+40}" {arrow} />',
            f'<line x1="{POS["sap2"][0]+100}" y1="{POS["sap2"][1]+40}" x2="{POS["meter_battery"][0]}" y2="{POS["meter_battery"][1]+40}" {arrow_two_way} />',
            
            # Connections from meters to assets (with your previous corrections)
            f'<line x1="{POS["pv"][0]}" y1="{POS["pv"][1]+40}" x2="{POS["meter_pv"][0]+100}" y2="{POS["meter_pv"][1]+40}" {arrow} />',
            f'<line x1="{POS["meter_battery"][0]+100}" y1="{POS["meter_battery"][1]+40}" x2="{POS["battery"][0]}" y2="{POS["battery"][1]+40}" {arrow_two_way} />'
        ])


    elif "Situation 7" in situation_name:
        nodes_to_draw.extend([
            create_node(POS['pap_main'][0], POS['pap_main'][1], 'PAP', icons_b64['alloc']),
            create_node(POS['pv'][0], POS['pv'][1], 'PV', icons_b64['pv']),
            create_node(POS['battery'][0], POS['battery'][1], 'Battery', icons_b64['batt']),
            create_node(POS['meter_pv'][0], POS['meter_pv'][1], 'PV Meter', icons_b64['meter']),
            create_node(POS['meter_battery'][0], POS['meter_battery'][1], 'Battery Meter', icons_b64['meter'])
        ])
        lines_to_draw.extend([
            # Connection from Main Meter to PAP
            f'<line x1="{POS["main_meter"][0]+100}" y1="{POS["main_meter"][1]+40}" x2="{POS["pap_main"][0]}" y2="{POS["pap_main"][1]+40}" {arrow} />',

            # CORRECTED: Arrow now points FROM PV Meter TO PAP
            f'<path d="M {POS["meter_pv"][0]} 60 L 480 60 L 480 {POS["pap_main"][1]+20} L {POS["pap_main"][0]+100} {POS["pap_main"][1]+20}" {arrow} />', # Reversed start/end

            # Direct line from PAP (bottom-right) to Battery Meter (UNCHANGED)
            f'<path d="M {POS["pap_main"][0]+100} {POS["pap_main"][1]+60} L 480 {POS["pap_main"][1]+60} L 480 390 L {POS["meter_battery"][0]} 390" {arrow} />',
            
            # Local connections from meters to assets (UNCHANGED)
            f'<line x2="{POS["meter_pv"][0]+100}" y1="{POS["meter_pv"][1]+40}" x1="{POS["pv"][0]}" y2="{POS["pv"][1]+40}" {arrow} />',
            f'<line x1="{POS["meter_battery"][0]+100}" y1="{POS["meter_battery"][1]+40}" x2="{POS["battery"][0]}" y2="{POS["battery"][1]+40}" {arrow} />',
            
            # CORRECTED: Dashed line from PV Meter to Battery Meter with angled path
            f'<path d="M {POS["meter_pv"][0]} {POS["meter_pv"][1]+20} L {POS["meter_pv"][0]-50} {POS["meter_pv"][1]+20} L {POS["meter_pv"][0]-50} {POS["battery"][1]+60} L {POS["meter_battery"][0]} {POS["battery"][1]+60}" {direct_use_arrow} />'
        ])

    # --- Assemble the Final HTML/SVG ---
    svg_content = "".join(nodes_to_draw) + "".join(lines_to_draw)
    html_code = f'''
        <div style="width: 100%; max-width: 850px; height: {svg_height}px; font-family: sans-serif; margin: auto; border: 1px solid #ddd; border-radius: 8px;">
            <svg viewBox="0 0 850 {svg_height}" style="width: 100%; height: 100%;">
                {arrow_defs}
                {svg_content}
            </svg>
        </div>
    '''
    return html_code

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


# Add this dictionary to your script
ASSET_ICONS = {
    "Solar PV": "☀️",
    "Battery": "🔋",
    "Load": "💡",
    "Grid": "⚡️" # The grid is always implicitly included
}

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

# --- UI HELPER ---
# def display_header(title):
    # col1, col2 = st.columns([1, 4])
    # with col1:
    #     st.image("https://i.postimg.cc/RFgvn3Cp/LOGO-S-PRESENTATIE.webp", width=10000)
    # with col2:
    #     st.title(title)
    # st.markdown("---")
def display_header(title):
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


################# BATTERY SIZING CODE

def show_battery_sizing_page():
    """
    Displays the UI for the Battery Peak Shaving Sizing Tool.
    """
    display_header("Battery Sizing Tool for Peak Shaving 🔋")
    st.info("This tool calculates the battery **power (kW)** and **capacity (kWh)** needed to keep your grid exchange within defined import and export limits.")

    # --- 1. User Inputs in Sidebar ---
    with st.sidebar:
        st.header("⚙️ Sizing Configuration")
        uploaded_file = st.file_uploader(
            "Upload Your Data (CSV)",
            type="csv",
            help="CSV must have 'Datetime', 'load', and 'pv_production' columns."
        )
        import_limit = st.number_input("Grid Import Limit (kW)", min_value=0, value=350, step=10)
        export_limit = st.number_input("Grid Export Limit (kW)", max_value=0, value=-250, step=10)
        run_button = st.button("🚀 Run Sizing Analysis", type="primary")

    # --- 2. Analysis and Results Display ---
    if run_button:
        if uploaded_file is not None:
            try:
                # Load and prepare data
                input_df = pd.read_csv(uploaded_file)
                input_df["Datetime"] = pd.to_datetime(input_df["Datetime"], dayfirst=True)
                input_df.set_index("Datetime", inplace=True)

                # Instantiate and run analyzer
                analyzer = BatteryShavingAnalyzer(import_limit_kw=import_limit, export_limit_kw=export_limit)
                capacity, power, results_df = analyzer.run_analysis(input_df)

                # Store results in session state to persist them
                st.session_state['sizing_results'] = {
                    "capacity": capacity,
                    "power": power,
                    "df": results_df,
                    "import_limit": import_limit,
                    "export_limit": export_limit
                }
                st.rerun() # Rerun to display results outside the 'if run_button' block
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.error("Please ensure your CSV has the columns 'Datetime', 'load', and 'pv_production' with correctly formatted data.")
        else:
            st.warning("Please upload a file to run the analysis.")

    # --- 3. Display Results if they exist in session state ---
    if 'sizing_results' in st.session_state:
        results = st.session_state['sizing_results']
        st.subheader("💡 Recommended Battery Size")
        
        col1, col2 = st.columns(2)
        col1.metric("Required Power (Charge/Discharge)", f"{results['power']:,.2f} kW")
        col2.metric("Required Energy Capacity", f"{results['capacity']:,.2f} kWh")

        st.markdown("---")
        st.subheader("📊 Analysis Charts")

        df = results['df']
        
        # Plot 1: Net Load vs Limits
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df.index, y=df['net_load'], mode='lines', name='Net Load', line=dict(color='royalblue', width=1)))
        fig1.add_hline(y=results['import_limit'], line_dash="dash", line_color="red", annotation_text=f"Import Limit ({results['import_limit']} kW)")
        fig1.add_hline(y=results['export_limit'], line_dash="dash", line_color="green", annotation_text=f"Export Limit ({results['export_limit']} kW)")
        fig1.update_layout(title="Net Load vs. Grid Limits", xaxis_title="Time", yaxis_title="Power (kW)")
        st.plotly_chart(fig1, use_container_width=True)

        # Plot 2: Battery Power (Charge/Discharge)
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df.index, y=df['battery_power'].clip(lower=0), mode='lines', name='Charging Power (to Battery)', fill='tozeroy', line=dict(color='green')))
        fig2.add_trace(go.Scatter(x=df.index, y=df['battery_power'].clip(upper=0), mode='lines', name='Discharging Power (from Battery)', fill='tozeroy', line=dict(color='red')))
        fig2.update_layout(title="Required Battery Power to Shave Peaks", xaxis_title="Time", yaxis_title="Power (kW)")
        st.plotly_chart(fig2, use_container_width=True)
        
        # Plot 3: Battery State of Charge
        fig3 = px.line(df, x=df.index, y='soc_kwh', title="Calculated Battery State of Charge (Relative)", labels={"soc_kwh": "Energy (kWh)", "index": "Time"})
        st.plotly_chart(fig3, use_container_width=True)

    else:
        st.info("Upload a file and configure the limits in the sidebar to get started.")

    # --- Navigation ---
    if st.button("⬅️ Back to Home"):
        if 'sizing_results' in st.session_state:
            del st.session_state['sizing_results'] # Clean up state
        st.session_state.page = "Home"
        st.rerun()


################# BATTERY SIZING CODE

# --- PAGE DISPLAY FUNCTIONS ---
def show_home_page():
    display_header("Flink Energy Management System (EMS) Simulation ")
    st.subheader('Tools')
    st.write("Please select a tool to begin.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🛠️ Sizing Tools")
        # Change this line:
        if st.button("Battery Size Finder", type="primary"): 
            st.session_state.page = "Battery_Sizing"
            st.rerun()

    with col2:
        st.markdown("#### 💰 Revenue Analysis")
        if st.button("Battery Revenue Analysis",type="primary"):
            st.session_state.page = "Revenue_Analysis"
            st.rerun()
    with col3:
        st.markdown("#### 📈 Financial Modeling")
        if st.button("Business Case Simulation", type="primary"):
            st.session_state.page = "Project_Selection"; st.rerun()
            
    st.markdown("---") 
    st.image("https://i.postimg.cc/2ykmvjVb/Energy-blog-anim.gif", use_container_width=False)



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


# This is the complete and correct version of your page function.
def show_revenue_analysis_page():
    display_header("Energy System Simulation ⚡")
    st.write("Select a system configuration from the sidebar, upload your data, and run the simulation.")

    # --- Configuration Sidebar ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # --- 1. Master Situation Selector ---
        st.subheader("1. Select System Configuration")
        
        situation_options = [
            "Situation 1: PV + Consumption on PAP",
            "Situation 2: PV on SAP, Consumption on PAP",
            "Situation 3: PV+Consumption on PAP, Battery on SAP",
            "Situation 4: Everything on PAP (Imbalance)",
            "Situation 5: Consumption on PAP, Battery+PV on SAP",
            "Situation 6: Consumption on PAP, Battery on SAP1, PV on SAP2",
            "Situation 7: PV + Battery on PAP"
        ]
        
        # Store the user's choice in session_state
        st.session_state['selected_situation'] = st.selectbox(
            "Choose the system topology:",
            options=situation_options
        )
        st.markdown("---")

        # --- 2. Upload Data File ---
        st.subheader("2. Upload Data File")
        uploaded_file = st.file_uploader("Upload Input Data (CSV or Excel)", type=['csv', 'xlsx'])
        st.markdown("---")

        # --- 3. Optimization Strategy & Parameters ---
        st.subheader("3. Optimization Strategy")
        strategy_choice = st.selectbox(
            "Select a strategy:", 
            ("Prioritize Self-Consumption", "Optimize on Day-Ahead Market", "Simple Battery Trading (Imbalance)")
        )

        # Conditionally show battery parameters only if "Battery" is in the selected situation name
        if "Battery" in st.session_state.get('selected_situation', ''):
            st.subheader("Battery Parameters")
            power_mw = st.number_input("Power (MW)", value=1.0, min_value=0.1, step=0.1, key="power_mw")
            capacity_mwh = st.number_input("Capacity (MWh)", value=2.0, min_value=0.1, step=0.1, key="capacity_mwh")
            min_soc = st.slider("Minimum SoC", 0.0, 1.0, 0.05, key="min_soc")
            max_soc = st.slider("Maximum SoC", 0.0, 1.0, 0.95, key="max_soc")
            eff_ch = st.slider("Charging Efficiency", 0.80, 1.00, 0.95, step=0.01, key="eff_ch")
            eff_dis = st.slider("Discharging Efficiency", 0.80, 1.00, 0.95, step=0.01, key="eff_dis")
            max_cycles = st.number_input("Max Cycles per Year", value=600, min_value=1, key="max_cycles")
        else:
            # If no battery in the situation, set placeholder values so the app doesn't crash
            power_mw, capacity_mwh, min_soc, max_soc, eff_ch, eff_dis, max_cycles = 0, 0, 0, 1, 1, 1, 0

        st.subheader("Cost Parameters")
        supply_costs = st.number_input("Supplier Costs (€/MWh)", value=20.0, key="supply_costs")
        transport_costs = st.number_input("Transport Costs (€/MWh)", value=15.0, key="transport_costs")

    # --- Main Page Content ---
    st.subheader("Selected Configuration")
    
    # Get the situation name from the session state
    situation = st.session_state.get('selected_situation')
    
    if situation:
        # This dictionary is required again for the new function
        icons_b64 = {
            'grid': get_image_as_base64('Assets/power-line.png'),
            'meter': get_image_as_base64('Assets/energy-meter.png'), 
            'alloc': get_image_as_base64('Assets/energy-meter.png'), # You might need to create/rename this icon for PAP/SAP
            'pv': get_image_as_base64('Assets/energy-meter.png'),
            'batt': get_image_as_base64('Assets/energy-storage.png'),
            'load': get_image_as_base64('Assets/energy-consumption.png')
        }
    
        # 1. Call the new function with both required arguments
        html_diagram = create_horizontal_diagram_with_icons(situation, icons_b64)
        
        # 2. Render the diagram using the components.html function
        # Note: Adjusted height to match the new diagram's size
        st.components.v1.html(html_diagram, height=470)
    else:
        st.warning("Please select a situation from the sidebar first.")
    
    st.markdown("---")
    
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
                    "STRATEGY_CHOICE": strategy_choice, "TIME_STEP_H": 0.25,
                    # --- ADD THIS NEW LINE ---
                    "SELECTED_ASSETS": selected_assets
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
    st.image("https://i.postimg.cc/RFgvn3Cp/LOGO-S-PRESENTATIE.webp", width=1500) 
    
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
# ADD THIS NEW ELIF BLOCK:
elif st.session_state.page == "Battery_Sizing":
    show_battery_sizing_page()
