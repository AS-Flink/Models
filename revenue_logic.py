# revenue_logic.py (Improved Version)

import pandas as pd
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import datetime
import io
import traceback

# --- MODIFIED IMPORT BLOCK ---
# This new structure provides clearer error messages if a file is missing.
IMPORTS_OK = False
IMPORT_ERROR_MESSAGE = ""
try:
    from imbalance_algorithm_SAP import run_battery_trading as run_battery_trading_SAP
    from self_consumption_PV_PAP import run_battery_trading as run_battery_trading_PAP
    from day_ahead_trading_PAP import run_battery_trading as run_battery_trading_day_ahead
    from imbalance_everything_PAP import run_battery_trading as run_battery_trading_everything_PAP
    IMPORTS_OK = True
except ImportError as e:
    IMPORT_ERROR_MESSAGE = f"Critical Error: Could not import an algorithm file. Please ensure all four trading algorithm scripts (`day_ahead_trading_PAP.py`, `imbalance_algorithm_SAP.py`, etc.) are in the correct directory. Details: {e}"
# --- END MODIFIED BLOCK ---


def run_revenue_model(params, input_df, progress_callback):
    """
    This is the adapted version of your 'run_single_model' function.
    """
    # --- ADD THIS CHECK AT THE TOP ---
    if not IMPORTS_OK:
        return {
            "summary": None,
            "output_file_bytes": None,
            "warnings": [],
            "error": IMPORT_ERROR_MESSAGE
        }
    # --- END CHECK ---

    now = datetime.datetime.now()
    warnings = []
    
    class Cfg: pass
    config = Cfg()
    for k, v in params.items():
        setattr(config, k, v)
    
    config.input_data = input_df

    progress_callback("Starting model run...")

    try:
        if params["BATTERY_CONFIG"] == "Onbalanshandel, alleen batterij op SAP":
            df, summary = run_battery_trading_SAP(config, progress_callback=progress_callback)
        elif params["BATTERY_CONFIG"] == "Onbalanshandel, alles op onbalansprijzen":
            df, summary = run_battery_trading_everything_PAP(config, progress_callback=progress_callback)
        elif params["BATTERY_CONFIG"] == "Day-ahead trading, minimaliseer energiekosten":
            df, summary = run_battery_trading_day_ahead(config, progress_callback=progress_callback)
        else:
            df, summary = run_battery_trading_PAP(config, progress_callback=progress_callback)
        
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("Model run failed to return a valid DataFrame.")

        progress_callback("Model run complete. Generating Excel output...")
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Import uit Python"

        for r in dataframe_to_rows(df, index=True, header=True):
            ws.append(r)
        
        summary_text = (
            f"Python run {now.strftime('%d-%m-%Y %Hu%M')} | "
            f"{params['POWER_MW']} MW / {params['CAPACITY_MWH']} MWh | "
            f"Cycles: {summary.get('total_cycles', 0):.1f}"
        )
        ws['C6'] = summary_text

        output_buffer = io.BytesIO()
        wb.save(output_buffer)
        output_buffer.seek(0)
        
        if 'warning_message' in summary and summary['warning_message']:
            warnings.append(summary['warning_message'])
        if 'infeasible_days' in summary and len(summary.get('infeasible_days', [])) > 0:
            warnings.append(f"Model was infeasible for {len(summary['infeasible_days'])} days.")

        progress_callback("Output file generated successfully!")
        
        return {
            "summary": summary,
            "output_file_bytes": output_buffer.getvalue(),
            "warnings": warnings,
            "error": None
        }

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ERROR in revenue_logic: {tb}")
        return {
            "summary": None,
            "output_file_bytes": None,
            "warnings": [],
            "error": f"An error occurred during the model run: {str(e)}"
        }
