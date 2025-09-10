import tkinter as tk
from tkinter import filedialog, messagebox
import datetime
import csv
from imbalance_algorithm_SAP import run_battery_trading as run_battery_trading_SAP
from self_consumption_PV_PAP import run_battery_trading as run_battery_trading_PAP
from day_ahead_trading_PAP import run_battery_trading as run_battery_trading_day_ahead
import pandas as pd
import os
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import xlwings as xw
import threading
import queue

VERSION = "5.8"
# Current version

class ParamWindow:
    def __init__(self, master):
        self.master = master
        master.title(f"Batterijmodel v{VERSION}")
        
        # Aangepast vensterformaat voor meerdere runs (breder voor Nederlandse tekst en eenheden)
        master.geometry("550x650")  # Breedte x Hoogte
        master.resizable(True, True)  # Venster resizable maken voor flexibiliteit
        
        # Padding toevoegen voor betere layout
        master.configure(padx=10, pady=10)
        
        # Default waarden voor een nieuwe run
        self.default_values = {
            "POWER_MW": 1.0,
            "CAPACITY_MWH": 2.0,
            "MIN_SOC": 0.05,
            "MAX_SOC": 0.95,
            "EFF_CH": 0.95,
            "EFF_DIS": 0.95,
            "MAX_CYCLES": 600,
            "INIT_SOC": 0.5,
            "SUPPLY_COSTS": 20.0,
            "TRANSPORT_COSTS": 15.0,
            "E_PROGRAM": 100.0,
        }
        self.labels = {
            "POWER_MW": "Vermogen batterij",
            "CAPACITY_MWH": "Capaciteit batterij",
            "MIN_SOC": "Minimum SoC",
            "MAX_SOC": "Maximum SoC",
            "EFF_CH": "Efficiëntie opladen",
            "EFF_DIS": "Efficiëntie ontladen",
            "MAX_CYCLES": "Max cycli per jaar",
            "INIT_SOC": "Initiële SoC",
            "SUPPLY_COSTS": "Kosten energieleverancier",
            "TRANSPORT_COSTS": "Transportkosten afname",
            "E_PROGRAM": "E-programma",
        }
        self.units = {
            "POWER_MW": "MW",
            "CAPACITY_MWH": "MWh",
            "MIN_SOC": "fractie",
            "MAX_SOC": "fractie",
            "EFF_CH": "fractie",
            "EFF_DIS": "fractie",
            "MAX_CYCLES": "cycli/jaar",
            "INIT_SOC": "fractie",
            "SUPPLY_COSTS": "€/MWh",
            "TRANSPORT_COSTS": "€/MWh",
            "E_PROGRAM": "% van werkelijke afname/invoeding",
        }

        # List to keep track of all model runs
        self.model_runs = []
        
        # Add first run
        self.add_model_run()
        
        self.create_widgets()
        self.result = None
        self.progress_messages = []

    def add_model_run(self):
        """Voeg een nieuwe model run toe aan de lijst"""
        run_data = {
            "entries": {},
            "input_file": tk.StringVar(),
            "battery_config": tk.StringVar(value="Day-ahead trading, minimaliseer energiekosten"),
            "frame": None  # Will be filled later with the tkinter frame
        }
        self.model_runs.append(run_data)
        return len(self.model_runs) - 1  # Return index of new run

    def remove_model_run(self, run_index):
        """Verwijder een model run"""
        if len(self.model_runs) <= 1:
            return  # Keep at least 1 run
        
        # Remove the frame
        if self.model_runs[run_index]["frame"]:
            self.model_runs[run_index]["frame"].destroy()
        
        # Remove from list
        del self.model_runs[run_index]
        
        # Rebuild the interface
        self.refresh_interface()

    def save_current_values(self):
        """Sla de huidige waarden van alle runs op voordat de interface wordt ververst"""
        for i, run_data in enumerate(self.model_runs):
            if "entries" in run_data and run_data["entries"]:
                # Save current values in a temporary dictionary
                if "saved_values" not in run_data:
                    run_data["saved_values"] = {}
                
                for key, entry_widget in run_data["entries"].items():
                    try:
                        # Try to get the current value from the entry widget
                        run_data["saved_values"][key] = entry_widget.get()
                    except:
                        # If the widget does not exist, use default value
                        run_data["saved_values"][key] = str(self.default_values[key])

    def save_scroll_position(self):
        """Sla de huidige scroll positie op"""
        try:
            if hasattr(self, 'canvas') and self.canvas:
                # Get the current scroll position (between 0.0 and 1.0)
                # yview() geeft een tuple terug (top, bottom) waarin top de positie is
                scroll_top, scroll_bottom = self.canvas.yview()
                self.saved_scroll_position = scroll_top
        except:
            # If an error occurs, save no scroll position (start at the top)
            self.saved_scroll_position = 0.0

    def restore_scroll_position(self):
        """Herstel de opgeslagen scroll positie"""
        try:
            if hasattr(self, 'canvas') and self.canvas and hasattr(self, 'saved_scroll_position'):
                # Small delay to wait until the interface is fully built
                self.master.after(50, lambda: self.canvas.yview_moveto(self.saved_scroll_position))
        except:
            # If an error occurs, scroll to the top
            pass

    def restore_saved_values(self):
        """Herstel de opgeslagen waarden na het opnieuw bouwen van de interface"""
        for i, run_data in enumerate(self.model_runs):
            if "saved_values" in run_data and "entries" in run_data:
                for key, saved_value in run_data["saved_values"].items():
                    if key in run_data["entries"]:
                        try:
                            # Clear current content and set the saved value
                            run_data["entries"][key].delete(0, tk.END)
                            run_data["entries"][key].insert(0, saved_value)
                        except:
                            # If an error occurs, use default value
                            run_data["entries"][key].delete(0, tk.END)
                            run_data["entries"][key].insert(0, str(self.default_values[key]))

    def refresh_interface(self):
        """Herbouw de volledige interface en behoud de huidige waarden en scroll positie"""
        # Save all current values and scroll position
        self.save_current_values()
        self.save_scroll_position()
        
        # Clear all existing widgets
        for widget in self.master.winfo_children():
            widget.destroy()
        
        # Create interface again
        self.create_widgets()
        
        # Restore the saved values and scroll position
        self.restore_saved_values()
        self.restore_scroll_position()

    def create_widgets(self):

        
        # Scrollable frame for the model runs
        self.canvas = tk.Canvas(self.master)
        scrollbar = tk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mouse wheel scrolling functionality
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel events
        self.canvas.bind('<Enter>', _bind_to_mousewheel)
        self.canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # Grid the scrollable components
        self.canvas.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(0,10))
        scrollbar.grid(row=1, column=3, sticky="ns", pady=(0,10))
        
        # Configure grid weights
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Add all model runs to the scrollable frame
        for i, run_data in enumerate(self.model_runs):
            self.create_run_frame(i)
        
        # Add Model Run knop
        add_button = tk.Button(self.master, text="+ Add Model Run", command=self.add_new_run,
                              font=("Arial", 10, "bold"), bg="#2196F3", fg="white", width=20)
        add_button.grid(row=2, column=0, columnspan=3, pady=(10,5))
        
        # Run All Models knop
        run_button = tk.Button(self.master, text="Uitvoeren", command=self.submit, 
                              font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", width=25, height=2)
        run_button.grid(row=3, column=0, columnspan=3, pady=(5,10))
        
        # Progress text
        self.progress_text = tk.Text(self.master, height=8, width=70, fg="blue", wrap=tk.WORD, state=tk.DISABLED)
        self.progress_text.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10,0))

    def create_run_frame(self, run_index):
        """Create a frame for a specific model run"""
        run_data = self.model_runs[run_index]
        
        # Main frame for this run
        main_frame = tk.LabelFrame(self.scrollable_frame, text=f"Model Run {run_index + 1}", 
                                  font=("Arial", 10, "bold"), padx=10, pady=10)
        main_frame.grid(row=run_index, column=0, sticky="ew", padx=5, pady=5)
        
        # Configure weights
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        
        run_data["frame"] = main_frame
        
        row = 0
        
        # Batterijconfiguratie keuzemenu
        tk.Label(main_frame, text="Batterijconfiguratie:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="e", padx=(0,10), pady=(0,5))
        opties = [
            "Onbalanshandel, alleen batterij op SAP",
            "Onbalanshandel, alles op onbalansprijzen",
            "Verhogen eigen verbruik PV, alles op day-ahead",
            "Day-ahead trading, minimaliseer energiekosten"
        ]
        option_menu = tk.OptionMenu(main_frame, run_data["battery_config"], *opties)
        option_menu.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0,5))
        
        # Bind de configuratie wijziging om e-programma veld te tonen/verbergen
        run_data["battery_config"].trace('w', lambda *args, idx=run_index: self._update_conditional_fields(idx))
        row += 1
        
        # Input file selector
        tk.Label(main_frame, text="Invoerbestand:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="e", padx=(0,10), pady=(0,5))
        entry_file = tk.Entry(main_frame, textvariable=run_data["input_file"], width=35)
        entry_file.grid(row=row, column=1, sticky="ew", pady=(0,5))
        browse_button = tk.Button(main_frame, text="Bladeren", command=lambda idx=run_index: self.browse_file(idx), width=8)
        browse_button.grid(row=row, column=2, padx=(5,0), pady=(0,5))
        row += 1
        
        # Parameter fields
        for key, val in self.default_values.items():
            # E-programma veld alleen tonen voor "Onbalanshandel, alles op onbalansprijzen"
            if key == "E_PROGRAM":
                # Maak het E-programma veld alleen voor de juiste configuratie
                self._create_conditional_param_field(main_frame, run_data, key, val, row, run_index)
                row += 1
            else:
                # Normale parameter velden
                label = self.labels.get(key, key)
                unit = self.units.get(key, "")
                tk.Label(main_frame, text=label, anchor="e", width=20).grid(row=row, column=0, sticky="e", padx=(0,10), pady=1)
                entry = tk.Entry(main_frame, width=35, justify='right')  # Zelfde breedte als invoerbestand veld
                entry.insert(0, f"{val} ")  # Spatie toegevoegd voor marge
                entry.grid(row=row, column=1, sticky="ew", pady=1)
                tk.Label(main_frame, text=unit, anchor="w").grid(row=row, column=2, sticky="w", padx=(5,0), pady=1)
                run_data["entries"][key] = entry
                row += 1
        
        # Remove button (alleen als er meer dan 1 run is)
        if len(self.model_runs) > 1:
            remove_button = tk.Button(main_frame, text="Verwijder Run", command=lambda idx=run_index: self.remove_model_run(idx),
                                     bg="#f44336", fg="white", width=12)
            remove_button.grid(row=row, column=1, sticky="w", pady=(10,0))

    def add_new_run(self):
        """Voeg een nieuwe model run toe en refresh de interface"""
        self.add_model_run()
        self.refresh_interface()
    
    def _create_conditional_param_field(self, main_frame, run_data, key, val, row, run_index):
        """Maak een conditioneel parameter veld dat alleen getoond wordt voor specifieke configuraties"""
        label = self.labels.get(key, key)
        unit = self.units.get(key, "")
        
        # Maak de widgets maar verberg ze mogelijk
        label_widget = tk.Label(main_frame, text=label, anchor="e", width=20)
        entry = tk.Entry(main_frame, width=35, justify='right')
        entry.insert(0, f"{val} ")
        unit_widget = tk.Label(main_frame, text=unit, anchor="w")
        
        # Bewaar widgets voor later gebruik
        run_data["conditional_widgets"] = run_data.get("conditional_widgets", {})
        run_data["conditional_widgets"][key] = {
            "label": label_widget,
            "entry": entry,
            "unit": unit_widget,
            "row": row
        }
        
        # Sla entry op in entries dict
        run_data["entries"][key] = entry
        
        # Bepaal of veld zichtbaar moet zijn
        self._update_e_program_visibility(run_index)
    
    def _update_conditional_fields(self, run_index):
        """Update de zichtbaarheid van conditionale velden gebaseerd op batterijconfiguratie"""
        self._update_e_program_visibility(run_index)
    
    def _update_e_program_visibility(self, run_index):
        """Update de zichtbaarheid van het E-programma veld"""
        if run_index >= len(self.model_runs):
            return
            
        run_data = self.model_runs[run_index]
        config = run_data["battery_config"].get()
        
        # Bepaal of E-programma veld zichtbaar moet zijn
        show_e_program = (config == "Onbalanshandel, alles op onbalansprijzen")
        
        # Update zichtbaarheid
        if "conditional_widgets" in run_data and "E_PROGRAM" in run_data["conditional_widgets"]:
            widgets = run_data["conditional_widgets"]["E_PROGRAM"]
            
            if show_e_program:
                # Toon de widgets
                widgets["label"].grid(row=widgets["row"], column=0, sticky="e", padx=(0,10), pady=1)
                widgets["entry"].grid(row=widgets["row"], column=1, sticky="ew", pady=1)
                widgets["unit"].grid(row=widgets["row"], column=2, sticky="w", padx=(5,0), pady=1)
            else:
                # Verberg de widgets
                widgets["label"].grid_remove()
                widgets["entry"].grid_remove()
                widgets["unit"].grid_remove()

    def browse_file(self, run_index=None):
        """Browse voor een bestand voor een specifieke run"""
        filename = filedialog.askopenfilename(filetypes=[("Data files", "*.csv;*.xlsx"), ("CSV files", "*.csv"), ("Excel files", "*.xlsx")])
        if filename:
            if run_index is not None:
                self.model_runs[run_index]["input_file"].set(filename)

    def add_progress_message(self, message):
        """Voeg een bericht toe aan de voortgangsweergave (thread-safe)"""
        def _add_message():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            full_message = f"[{timestamp}] {message}\n"
            self.progress_messages.append(full_message)
            
            # Update de tekst widget
            self.progress_text.config(state=tk.NORMAL)
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, "".join(self.progress_messages))
            self.progress_text.config(state=tk.DISABLED)
            
            # Scroll naar beneden
            self.progress_text.see(tk.END)
            
            # Force GUI update
            self.master.update_idletasks()
        
        # Controleer of we in de main thread zijn
        if threading.current_thread() == threading.main_thread():
            _add_message()
        else:
            # Schedule update in main thread
            self.master.after(0, _add_message)

    def submit(self):
        """Voer alle model runs uit in een separate thread"""
        try:
            # Valideer alle runs
            all_params = []
            for i, run_data in enumerate(self.model_runs):
                try:
                    params = {k: float(run_data["entries"][k].get().strip()) for k in self.default_values.keys()}
                    other_params = {
                        "TIME_STEP_H": 0.25,
                        "DATA_PATH": run_data["input_file"].get(),
                        "BATTERY_CONFIG": run_data["battery_config"].get()
                    }
                    params.update(other_params)
                    if not params["DATA_PATH"]:
                        messagebox.showerror("Fout", f"Model Run {i+1}: Selecteer een invoerbestand.")
                        return
                    all_params.append(params)
                except Exception as e:
                    messagebox.showerror("Error", f"Model Run {i+1}: Ongeldige input - {e}")
                    return
            
            # Disable de Uitvoeren knop om dubbele clicks te voorkomen
            for widget in self.master.winfo_children():
                if isinstance(widget, tk.Button) and widget['text'] == 'Uitvoeren':
                    widget.config(state='disabled', text='Bezig...')
                    break
            
            # Start optimalisatie in separate thread
            self.add_progress_message("Start optimalisatie...")
            thread = threading.Thread(target=self.run_models_thread, args=(all_params,))
            thread.daemon = True  # Thread stopt als main programma stopt
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Algemene fout: {e}")
    
    def run_models_thread(self, all_params):
        """Voer model runs uit in background thread"""
        try:
            total_runs = len(all_params)
            self.add_progress_message(f"Start van {total_runs} model run(s)")
            
            results = []
            successful_runs = 0
            failed_runs = 0
            fallback_runs = 0
            
            for i, params in enumerate(all_params):
                run_number = i + 1
                try:
                    result_message, output_path, optimization_method = run_single_model(params, self, run_number, total_runs)
                    if output_path:  # Succesvolle run
                        if optimization_method == 'Fallback heuristiek (Pyomo gefaald)':
                            results.append(f"⚠️ Run {run_number}: {output_path} (Fallback gebruikt)")
                            fallback_runs += 1
                        else:
                            results.append(f"✓ Run {run_number}: {output_path}")
                        successful_runs += 1
                    else:  # Gefaalde run
                        # Gebruik de specifieke foutmelding die door run_single_model wordt teruggegeven
                        results.append(f"✗ Run {run_number}: {result_message.split(': ', 1)[-1] if ': ' in result_message else result_message}")
                        failed_runs += 1
                except Exception as e:
                    error_msg = f"✗ Run {run_number}: FOUT - {str(e)}"
                    results.append(error_msg)
                    self.add_progress_message(error_msg)
                    failed_runs += 1
            
            # Toon eindresultaat
            final_message = f"Alle model runs voltooid!\n\n"
            final_message += f"Succesvol: {successful_runs}\n"
            if fallback_runs > 0:
                final_message += f"Fallback gebruikt: {fallback_runs}\n"
            final_message += f"Gefaald: {failed_runs}\n\n"
            final_message += "Resultaten:\n" + "\n".join(results)
            
            self.add_progress_message(final_message)
            
            # Re-enable de Uitvoeren knop
            self.master.after(0, self.re_enable_button)
            
            # Toon eindresultaat pop-up met optie om programma te sluiten
            self.master.after(0, lambda: self.show_completion_dialog(final_message, successful_runs, failed_runs))
            
        except Exception as e:
            self.add_progress_message(f"FOUT in thread: {str(e)}")
            self.master.after(0, self.re_enable_button)
    
    def re_enable_button(self):
        """Re-enable de Uitvoeren knop"""
        for widget in self.master.winfo_children():
            if isinstance(widget, tk.Button) and widget['text'] == 'Bezig...':
                widget.config(state='normal', text='Uitvoeren')
                break
    
    def show_completion_dialog(self, final_message, successful_runs, failed_runs):
        """Toon voltooiings dialog met optie om programma te sluiten"""
        try:
            if successful_runs > 0 and failed_runs == 0:
                # Alle runs succesvol
                title = "Alle Model Runs Voltooid!"
                icon = "info"
                message = f"✓ Alle {successful_runs} model run(s) zijn succesvol voltooid!\n\nWilt u het programma sluiten?"
            elif successful_runs > 0 and failed_runs > 0:
                # Gemengde resultaten
                title = "Model Runs Voltooid"
                icon = "warning"
                message = f"Model runs voltooid met gemengde resultaten:\n\n✓ Succesvol: {successful_runs}\n✗ Gefaald: {failed_runs}\n\nWilt u het programma sluiten?"
            else:
                # Alle runs gefaald
                title = "Model Runs Voltooid"
                icon = "error"
                message = f"✗ Alle {failed_runs} model run(s) zijn gefaald.\n\nWilt u het programma sluiten?"
            
            # Toon dialog met Ja/Nee knoppen
            result = messagebox.askyesno(title, message, icon=icon)
            
            if result:  # Gebruiker klikte op "Ja"
                self.master.destroy()
                
        except Exception as e:
            # Fallback: toon gewoon een informatieve dialog zonder sluiten
            messagebox.showinfo("Model Runs Voltooid", final_message)


def extract_project_name(input_filename):
    """Extracteer de projectnaam uit de inputbestandsnaam"""
    # Verwijder de extensie
    base_name = os.path.splitext(os.path.basename(input_filename))[0]
    
    # Zoek naar patroon: "Model Profielanalyse" + versie + optionele projectnaam
    import re
    
    # Patroon: "Model Profielanalyse" gevolgd door versie (v + nummer + punt + nummer) gevolgd door optionele naam
    pattern = r"Model Profielanalyse\s+v\d+\.\d+(?:\s+(.+))?"
    match = re.match(pattern, base_name, re.IGNORECASE)
    
    if match and match.group(1):
        # Er is een projectnaam gevonden na de versie
        return match.group(1).strip()
    else:
        # Geen specifieke projectnaam gevonden, gebruik hele bestandsnaam zonder extensie
        return base_name

def run_single_model(params, app, run_number, total_runs):
    """Voer een enkele model run uit"""
    now = datetime.datetime.now()
    vermogen = str(params["POWER_MW"]).replace('.', ',')
    capaciteit = str(params["CAPACITY_MWH"]).replace('.', ',')

    # Dummy config-achtig object
    class Cfg: pass
    config = Cfg()
    for k, v in params.items():
        setattr(config, k, v)
    
    # Progress callback
    def progress_callback(msg):
        app.add_progress_message(f"Run {run_number}/{total_runs}: {msg}")
    
    # Run model
    app.add_progress_message(f"Start van Model Run {run_number}/{total_runs} ({params['BATTERY_CONFIG']})")
    
    try:
        if params["BATTERY_CONFIG"] == "Onbalanshandel, alleen batterij op SAP":
            df, summary = run_battery_trading_SAP(config, progress_callback=progress_callback)
        elif params["BATTERY_CONFIG"] == "Onbalanshandel, alles op onbalansprijzen":
            from imbalance_everything_PAP import run_battery_trading as run_battery_trading_everything_PAP
            df, summary = run_battery_trading_everything_PAP(config, progress_callback=progress_callback)
        elif params["BATTERY_CONFIG"] == "Day-ahead trading, minimaliseer energiekosten":
            df, summary = run_battery_trading_day_ahead(config, progress_callback=progress_callback)
        else:
            df, summary = run_battery_trading_PAP(config, progress_callback=progress_callback)
        
        # Controleer of df geldig is
        if df is None:
            raise ValueError("Model run heeft geen DataFrame geretourneerd - mogelijk is de optimalisatie gefaald")
        
        # Debug informatie
        app.add_progress_message(f"Run {run_number}/{total_runs}: DataFrame ontvangen met {len(df)} rijen en kolommen: {list(df.columns)}")
        
        # Nieuwe bestandsnaam volgens gewenste structuur
        data_path = str(params["DATA_PATH"])
        input_dir = os.path.dirname(data_path)
        
        # Extracteer projectnaam uit inputbestand
        project_name = extract_project_name(data_path)
        
        # Datum en tijd formattering
        datum = now.strftime("%d-%m-%y")  # 15-08-25
        tijd = now.strftime("%Hu%M")      # 10u42
        
        # Batterijspecificaties
        vermogen_str = f"{vermogen} MW"
        capaciteit_str = f"{capaciteit} MWh"
        
        # Bouw nieuwe bestandsnaam
        if total_runs > 1:
            # Meerdere runs: "Py Run1 Twente Standaardverbruik 15-08-25 10u40 - 0,5 MW - 2,5 MWh"
            filename = f"Py Run{run_number} {project_name} {datum} {tijd} - {vermogen_str} - {capaciteit_str}.xlsx"
        else:
            # Enkele run: "Py Twente Standaardverbruik 15-08-25 10u40 - 0,5 MW - 2,5 MWh"
            filename = f"Py {project_name} {datum} {tijd} - {vermogen_str} - {capaciteit_str}.xlsx"
        
        new_path = os.path.join(input_dir, filename)
        # Voortgangsupdate voor het opslaan
        app.add_progress_message(f"Run {run_number}/{total_runs}: Opslaan van het nieuwe bestand. Dit kan een minuutje duren")
        # Open met xlwings en schrijf resultaten
        app_xl = xw.App(visible=False)
        wb = app_xl.books.open(params["DATA_PATH"])
        if 'Import uit Python' not in [s.name for s in wb.sheets]:
            wb.close()
            app_xl.quit()
            raise ValueError("Tabblad 'Import uit Python' niet gevonden in het geselecteerde bestand.")
        ws = wb.sheets['Import uit Python']
        # Alleen de gewenste kolommen exporteren
        if params["BATTERY_CONFIG"] == "Onbalanshandel, alleen batterij op SAP":
            gewenste_kolommen = [
                'regulation_state',
                'price_surplus',
                'price_shortage',
                'price_day_ahead',
                'space_for_charging_kWh',
                'space_for_discharging_kWh',
                'energy_charged_kWh',
                'energy_discharged_kWh',
                'SoC_kWh',
                'SoC_pct',
                'grid_exchange_kWh',
                'e_program_kWh',
                'day_ahead_result',
                'imbalance_result',
                'energy_tax',
                'supplier_costs',
                'transport_costs',
                'total_result_imbalance_SAP'
            ]
        elif params["BATTERY_CONFIG"] == "Onbalanshandel, alles op onbalansprijzen":
            gewenste_kolommen = [
                'regulation_state',
                'price_surplus',
                'price_shortage',
                'price_day_ahead',
                'space_for_charging_kWh',
                'space_for_discharging_kWh',
                'energy_charged_kWh',
                'energy_discharged_kWh',
                'SoC_kWh',
                'SoC_pct',
                'grid_exchange_kWh',
                'e_program_kWh',
                'day_ahead_result',
                'imbalance_result',
                'energy_tax',
                'supplier_costs',
                'transport_costs',
                'total_result_imbalance_PAP'
            ]
        elif params["BATTERY_CONFIG"] == "Day-ahead trading, minimaliseer energiekosten":
            gewenste_kolommen = [
                'production_PV',
                'load',
                'grid_exchange_kWh',
                'price_day_ahead',
                'space_for_charging_kWh',
                'space_for_discharging_kWh',
                'energy_charged_kWh',
                'energy_discharged_kWh',
                'SoC_kWh',
                'SoC_pct',
                'dummy1',
                'dummy2',
                'day_ahead_result',
                'dummy3',
                'energy_tax',
                'supplier_costs',
                'transport_costs',
                'total_result_day_ahead_trading'
            ]
        else:  # Voor self_consumption_PV_PAP
            gewenste_kolommen = [
                'production_PV',
                'load',
                'grid_exchange_kWh',
                'price_day_ahead',
                'space_for_charging_kWh',
                'space_for_discharging_kWh',
                'energy_charged_kWh',
                'energy_discharged_kWh',
                'SoC_kWh',
                'SoC_pct',
                'dummy1',
                'dummy2',
                'day_ahead_result',
                'dummy3',
                'energy_tax',
                'supplier_costs',
                'transport_costs',
                'total_result_self_consumption'
            ]
        # Zet de indexnaam als 'Datetime' indien nodig
        df.index.name = 'Datetime'
        
        # Controleer of df.columns geldig is
        if df.columns is None:
            raise ValueError("DataFrame heeft geen geldige kolommen - mogelijk is de optimalisatie gefaald")
        
        # Voeg dummy kolommen toe waar nodig
        if params["BATTERY_CONFIG"] != "Day-ahead trading, minimaliseer energiekosten":
            # Voor andere algoritmes: voeg dummy kolommen toe met nulwaarden
            if 'dummy1' not in df.columns:
                df['dummy1'] = 0
            if 'dummy2' not in df.columns:
                df['dummy2'] = 0
            # Voor SAP algoritme wordt supplier_costs berekend, voor andere krijgen ze dummy3
            if params["BATTERY_CONFIG"] != "Onbalanshandel, alleen batterij op SAP" and 'dummy3' not in df.columns:
                df['dummy3'] = 0
        
        # Selecteer alleen de gewenste kolommen (indien aanwezig)
        kolommen_aanwezig = [k for k in gewenste_kolommen if k in df.columns]
        
        # Controleer of er kolommen gevonden zijn
        if not kolommen_aanwezig:
            raise ValueError(f"Geen van de verwachte kolommen gevonden in de output. Verwacht: {gewenste_kolommen}, Aanwezig: {list(df.columns)}")
        
        df_export = df[kolommen_aanwezig].copy()
        # Kolomnamen schrijven: B7 = indexnaam ('Datetime'), C7 = eerste kolom van df, etc.
        start_row = 7
        start_col = 2
        ws.range((start_row, start_col)).value = df_export.index.name or 'Datetime'
        ws.range((start_row, start_col+1)).options(transpose=False).value = list(df_export.columns)
        # Data schrijven
        data = [[row.Index] + list(row[1:]) for row in df_export.itertuples(index=True)]
        ws.range((start_row+1, start_col)).value = data
        # Samengevoegde cel C6:M6 vullen met samenvattende tekst
        merge_range = ws.range('C6:M6')
        merge_range.merge()
        # Formatteren volgens voorbeeld: 'Python run 07-07-2025 10u56      0.2 MW      0.4 MWh     562.2 cycli per jaar.'
        datum_str = now.strftime('%d-%m-%Y %Hu%M')
        optimization_method = summary.get('optimization_method', 'Pyomo optimalisatie')
        summary_text = (
            f"Python run {datum_str}      {params['POWER_MW']} MW      {params['CAPACITY_MWH']} MWh     "
            f"{round(summary['total_cycles'], 1)} cycli per jaar.      "
            f"Algoritme: {params['BATTERY_CONFIG']}      "
            f"Optimalisatie: {optimization_method}"
        )
        merge_range.value = summary_text
        # Belangrijkste inputwaarden exporteren naar W2-W9
        ws.range('W2').value = params['POWER_MW']
        ws.range('W3').value = params['CAPACITY_MWH']
        ws.range('W4').value = params['MIN_SOC']
        ws.range('W5').value = params['MAX_SOC']
        ws.range('W6').value = params['EFF_CH']
        ws.range('W7').value = params['EFF_DIS']
        ws.range('W8').value = params['SUPPLY_COSTS']
        ws.range('W9').value = params['TRANSPORT_COSTS']
        # Opslaan als nieuw bestand
        wb.save(new_path)
        
        # Robuuste afsluiting van Excel om COM/OLE fouten te voorkomen
        try:
            wb.close()
        except Exception as close_error:
            print(f"Waarschuwing bij sluiten workbook: {close_error}")
        
        try:
            app_xl.quit()
        except Exception as quit_error:
            print(f"Waarschuwing bij afsluiten Excel: {quit_error}")
        
        # Forceer cleanup van Excel processen indien nodig
        import time
        time.sleep(0.5)  # Korte pauze om Excel tijd te geven om af te sluiten

        
        # Toon waarschuwing voor netwerkoverschrijdingen als die er zijn
        if (params["BATTERY_CONFIG"] == "Verhogen eigen verbruik PV, alles op day-ahead" and 
            'warning_message' in summary and 
            summary['warning_message'] is not None and 
            "WAARSCHUWING" in summary['warning_message']):
            messagebox.showwarning("Netwerkoverschrijdingen Gedetecteerd", summary['warning_message'])
        
        # Toon waarschuwing voor infeasible dagen als die er zijn
        if 'infeasible_days' in summary and len(summary['infeasible_days']) > 0:
            infeasible_count = len(summary['infeasible_days'])
            infeasible_list = "\n".join([f"• {dag['datum']}: {dag['reden']}" for dag in summary['infeasible_days']])
            warning_message = (f"WAARSCHUWING: Het model kon niet worden opgelost voor {infeasible_count} dag(en):\n\n"
                             f"{infeasible_list}\n\n"
                             f"Voor deze dagen werd de batterij SoC gereset en bleef de batterij inactief.\n"
                             f"Overweeg om het batterijvermogen te verhogen of de data te controleren.")
            messagebox.showwarning("Infeasible Dagen Gedetecteerd", warning_message)
        
        success_message = f"Model Run {run_number}/{total_runs} voltooid!\nResultaten opgeslagen in:\n{new_path}"
        
        # Controleer of fallback heuristiek werd gebruikt
        if summary.get('optimization_method') == 'Fallback heuristiek (Pyomo gefaald)':
            success_message += f"\n\n⚠️  BELANGRIJK: Fallback heuristiek gebruikt"
            success_message += f"\nDe Pyomo optimalisatie is gefaald, daarom werd een vereenvoudigde heuristiek gebruikt."
            success_message += f"\nDe resultaten zijn minder optimaal dan bij succesvolle Pyomo optimalisatie."
        
        if 'infeasible_days' in summary and len(summary['infeasible_days']) > 0:
            success_message += f"\n\nLet op: {len(summary['infeasible_days'])} dag(en) overgeslagen vanwege onoplosbare situaties."
        
        app.add_progress_message(f"Run {run_number}/{total_runs} succesvol voltooid!")
        
        # Return extra info over optimization method
        optimization_method = summary.get('optimization_method', 'Pyomo optimalisatie')
        return success_message, new_path, optimization_method
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        
        # Log de volledige traceback voor debugging
        app.add_progress_message(f"Run {run_number}/{total_runs} VOLLEDIGE FOUT:")
        app.add_progress_message(f"Traceback:\n{tb}")
        
        # Suggestie voor de gebruiker
        if 'argument of type \'NoneType\' is not iterable' in str(e):
            msg = ("NoneType iteratie fout - mogelijk is een DataFrame kolom None.\n"
                   "Dit gebeurt meestal tijdens het opslaan van resultaten.\n"
                   f"Volledige fout: {str(e)}")
        elif 'PermissionError' in str(e) or 'Permission denied' in str(e):
            msg = ("BESTAND NOG OPEN: Het invoerbestand kan niet worden gelezen omdat het nog open staat in Excel.\n"
                   "Sluit het Excel-bestand en probeer opnieuw.\n"
                   f"Bestand: {params.get('DATA_PATH', 'onbekend')}")
        elif 'No such file or directory' in str(e):
            msg = "Het geselecteerde bestand kon niet worden gevonden. Controleer het bestandspad."
        elif 'Excel' in str(e) or 'read_excel' in str(e):
            msg = "Het Excel-bestand kon niet worden gelezen. Controleer of het bestand geldig is (.xlsx) en niet open staat in een ander programma."
        elif 'CSV' in str(e) or 'read_csv' in str(e):
            msg = "Het CSV-bestand kon niet worden gelezen. Controleer of het bestand geldig is (.csv) en niet open staat in een ander programma."
        elif 'KeyError' in str(e):
            msg = f"Een vereiste kolom ontbreekt in het invoerbestand: {e}. Controleer de kolomnamen."
        elif 'de netoverschrijding niet corrigeren' in str(e):
            msg = ("De batterij kon op een bepaald moment de overschrijding van het gecontracteerde vermogen niet corrigeren.\n"
                   "Dit betekent dat de batterij op dat tijdstip niet genoeg vol of leeg was, of het benodigde vermogen te groot was.\n"
                   f"\nFoutmelding:\n{e}")
        elif 'OLE error' in str(e) or 'COM error' in str(e) or 'pywintypes.com_error' in str(e):
            msg = ("Er is een Excel-gerelateerde fout opgetreden. Dit kan gebeuren als:\n"
                   "• Excel nog bezig is met het opslaan van het bestand\n"
                   "• Het bestand wordt gebruikt door een ander programma\n"
                   "• Er zijn te veel Excel processen actief\n\n"
                   "Probeer het opnieuw of sluit alle Excel vensters en probeer opnieuw.\n"
                   f"\nFoutmelding:\n{e}")
        else:
            msg = f"Onbekende fout: {str(e)}"
        
        error_message = f"Run {run_number}/{total_runs} gefaald: {msg}"
        app.add_progress_message(error_message)
        return error_message, None, None


def main():
    """Hoofdfunctie die de GUI start"""
    root = tk.Tk()
    app = ParamWindow(root)
    
    # Direct sluiten zonder bevestiging
    def on_closing():
        """Handler voor het sluiten van het venster"""
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
