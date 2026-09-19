import tkinter as tk
from tkinter import ttk, messagebox
import math
import csv
import os
import sys
from datetime import datetime

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class PropulsionCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Propulsion Calculator")
        self.geometry("550x850")
        
        # Define styles
        style = ttk.Style(self)
        style.theme_use("clam")
        
        # Variables (with defaults)
        self.var_a = tk.DoubleVar(value=3.84)
        self.var_n = tk.DoubleVar(value=0.688)
        self.var_rho_p = tk.DoubleVar(value=1.865)
        self.var_c_star = tk.DoubleVar(value=912.0)
        self.var_P1 = tk.DoubleVar(value=4.0)
        self.var_k = tk.DoubleVar(value=1.131)
        self.var_P2 = tk.DoubleVar(value=0.101325)
        self.var_L = tk.StringVar() # Required, no default
        self.var_d = tk.StringVar() # Required, no default
        
        self.create_widgets()

    def create_widgets(self):
        # Add scrollbar support
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        main_frame = ttk.Frame(self.canvas, padding="20 20 20 20")
        self.canvas_window = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        def configure_scroll_region(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
        def configure_canvas_width(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)

        main_frame.bind("<Configure>", configure_scroll_region)
        self.canvas.bind("<Configure>", configure_canvas_width)
        
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        
        # Title
        title_label = ttk.Label(main_frame, text="Propulsion System Calculator", font=("TkDefaultFont", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Input Section
        input_frame = ttk.LabelFrame(main_frame, text="Inputs", padding="10 10 10 10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        inputs = [
            ("Burn Rate Coefficient (a) [mm/s]:", self.var_a),
            ("Pressure Exponent (n):", self.var_n),
            ("Propellant Density (\u03c1p) [g/cm\u00b3]:", self.var_rho_p),
            ("Characteristic Velocity (c*) [m/s]:", self.var_c_star),
            ("Chamber Pressure (P1) [MPa]:", self.var_P1),
            ("Ratio of Specific Heats (k):", self.var_k),
            ("Exit Pressure (P2) [MPa]:", self.var_P2),
            ("Core Length (L) [mm]:", self.var_L),
            ("Core Diameter (d) [mm]:", self.var_d)
        ]
        
        for idx, (label_text, var) in enumerate(inputs):
            ttk.Label(input_frame, text=label_text).grid(row=idx, column=0, sticky=tk.W, pady=4)
            ttk.Entry(input_frame, textvariable=var, width=15).grid(row=idx, column=1, sticky=tk.E, pady=4)
            
        input_frame.columnconfigure(0, weight=1)
        
        # Calculate Button
        calc_btn = ttk.Button(main_frame, text="Calculate", command=self.calculate)
        calc_btn.pack(pady=10)
        
        # Output Section
        output_frame = ttk.LabelFrame(main_frame, text="Results", padding="10 10 10 10")
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.result_vars = {
            "Kn": tk.StringVar(value="-"),
            "Cf": tk.StringVar(value="-"),
            "Area_throat": tk.StringVar(value="-"),
            "Thrust": tk.StringVar(value="-"),
            "Expansion_Ratio": tk.StringVar(value="-")
        }
        
        outputs = [
            ("Burn Area to Throat Area Ratio (Kn):", self.result_vars["Kn"]),
            ("Thrust Coefficient (Cf):", self.result_vars["Cf"]),
            ("Throat Area [mm\u00b2]:", self.result_vars["Area_throat"]),
            ("Thrust Produced (F) [N]:", self.result_vars["Thrust"]),
            ("Expansion Ratio (\u03b5):", self.result_vars["Expansion_Ratio"])
        ]
        
        for idx, (label_text, var) in enumerate(outputs):
            ttk.Label(output_frame, text=label_text, font=("TkDefaultFont", 10, "bold")).grid(row=idx, column=0, sticky=tk.W, pady=6)
            ttk.Label(output_frame, textvariable=var, font=("TkDefaultFont", 10)).grid(row=idx, column=1, sticky=tk.E, pady=6)
            
        output_frame.columnconfigure(0, weight=1)
        
        # New Formula Section
        formula_frame = ttk.LabelFrame(main_frame, text="Formulas Used", padding="10 10 10 10")
        formula_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        img_path = resource_path("formulas.png")
        if os.path.exists(img_path):
            self.formula_img = tk.PhotoImage(file=img_path)
            ttk.Label(formula_frame, image=self.formula_img).pack(pady=5)
        else:
            ttk.Label(formula_frame, text="Formulas image not found.", font=("TkDefaultFont", 9)).pack(pady=5)


        
    def calculate(self):
        try:
            # Retrieve inputs
            a = self.var_a.get()
            n = self.var_n.get()
            rho_p = self.var_rho_p.get()
            c_star = self.var_c_star.get()
            P1 = self.var_P1.get()
            k = self.var_k.get()
            P2 = self.var_P2.get()
            
            # Validate required inputs
            l_str = self.var_L.get().strip()
            d_str = self.var_d.get().strip()
            
            if not l_str or not d_str:
                messagebox.showerror("Input Error", "Core Length (L) and Core Diameter (d) are required fields.")
                return
                
            L = float(l_str)
            d = float(d_str)
            
            if P1 <= 0 or a <= 0 or rho_p <= 0 or c_star <= 0 or k <= 1 or P2 <= 0 or L <= 0 or d <= 0:
                messagebox.showerror("Input Error", "Values must be strictly positive (and k > 1).")
                return
                
            if P2 >= P1:
                messagebox.showerror("Input Error", "Exit pressure (P2) must be less than Chamber pressure (P1).")
                return

            # 1. Kn
            kn_val = (math.pow(P1, 1 - n) / (a * rho_p * c_star)) * 1e6
            
            # 2. Cf
            term1 = (2 * (k**2)) / (k - 1)
            term2 = math.pow(2 / (k + 1), (k + 1) / (k - 1))
            term3 = 1 - math.pow(P2 / P1, (k - 1) / k)
            cf_val = math.sqrt(term1 * term2 * term3)
            
            # 3. Area of throat
            area_throat_val = (math.pi * d * L) / kn_val
            
            # 4. Thrust Produced (F)
            thrust_val = cf_val * area_throat_val * P1
            
            # 5. Expansion Ratio (epsilon)
            er_term1 = math.pow((k + 1) / 2, 1 / (k - 1))
            er_term2 = math.pow(P2 / P1, 1 / k)
            er_term3 = math.sqrt( ((k + 1) / (k - 1)) * term3 )
            inv_epsilon = er_term1 * er_term2 * er_term3
            epsilon_val = 1 / inv_epsilon if inv_epsilon > 0 else float('inf')
            
            # Update GUI
            self.result_vars["Kn"].set(f"{kn_val:.2f}")
            self.result_vars["Cf"].set(f"{cf_val:.4f}")
            self.result_vars["Area_throat"].set(f"{area_throat_val:.2f} mm\u00b2")
            self.result_vars["Thrust"].set(f"{thrust_val:.2f} N")
            self.result_vars["Expansion_Ratio"].set(f"{epsilon_val:.2f}")
            
            # Save to CSV (Excel Sheet)
            self.save_to_csv(a, n, rho_p, c_star, P1, k, P2, L, d, kn_val, cf_val, area_throat_val, thrust_val, epsilon_val)
            

        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid numerical values.")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"An error occurred: {str(e)}")

    def save_to_csv(self, a, n, rho_p, c_star, P1, k, P2, L, d, Kn, Cf, Area_throat, Thrust, Expansion_Ratio):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(script_dir, "iteration_history.csv")
        file_exists = os.path.isfile(filename)
        
        try:
            with open(filename, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                if not file_exists:
                    # Write header
                    writer.writerow([
                        "Timestamp", "a (mm/s)", "n", "rho_p (g/cm\u00b3)", "c* (m/s)", "P1 (MPa)", "k", "P2 (MPa)", 
                        "L (mm)", "d (mm)", "Kn", "Cf", "Area_throat (mm\u00b2)", "Thrust (N)", "Expansion Ratio (\u03b5)"
                    ])
                    
                # Write data
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    a, n, rho_p, c_star, P1, k, P2, L, d,
                    round(Kn, 2), round(Cf, 4), round(Area_throat, 2), round(Thrust, 2), round(Expansion_Ratio, 2)
                ])
        except Exception as e:
            messagebox.showwarning("Save Error", f"Could not save iteration to Excel/CSV file: {str(e)}\nPlease make sure the file is not currently open in Excel.")

if __name__ == "__main__":
    app = PropulsionCalculator()
    app.mainloop()
