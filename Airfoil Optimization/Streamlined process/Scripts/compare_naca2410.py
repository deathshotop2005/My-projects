import os
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import sys

# Add Scripts to path so we can import evaluate_xfoil
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ga_active_learning import evaluate_xfoil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")

def generate_naca2410():
    naca_dat_path = os.path.join(PROJECT_DIR, "Output", "Airfoils", "naca2410.dat")
    if os.path.exists(naca_dat_path):
        os.remove(naca_dat_path)
    
    cmd = f"""NACA 2410
SAVE ../Output/Airfoils/naca2410.dat
Y
QUIT
"""
    subprocess.run([XFOIL_EXE], input=cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    return naca_dat_path

def load_coords(dat_path):
    coords = []
    with open(dat_path, 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
    return np.array(coords)

def main():
    print("Generating NACA 2410 coordinates via XFOIL...")
    naca_dat_path = generate_naca2410()
    
    final_dat_path = os.path.join(PROJECT_DIR, "Output", "Airfoils", "final_optimal.dat")
    
    if not os.path.exists(final_dat_path):
        print(f"Error: Could not find optimized airfoil at {final_dat_path}")
        return
        
    print("Evaluating NACA 2410...")
    res_naca = evaluate_xfoil(naca_dat_path, re_val=500000, mach_val=0.1, ar_val=10.0)
    
    print("Evaluating Optimized Airfoil...")
    res_opt = evaluate_xfoil(final_dat_path, re_val=500000, mach_val=0.1, ar_val=10.0)
    
    print("Plotting...")
    
    # 1. Plot Geometry
    coords_naca = load_coords(naca_dat_path)
    coords_opt = load_coords(final_dat_path)
    
    plt.figure(figsize=(10, 4))
    if len(coords_naca) > 0:
        plt.plot(coords_naca[:, 0], coords_naca[:, 1], 'k--', linewidth=1.5, label='Baseline')
    if len(coords_opt) > 0:
        plt.plot(coords_opt[:, 0], coords_opt[:, 1], color='royalblue', linewidth=2, label='Optimized Airfoil')
        plt.fill_between(coords_opt[:, 0], coords_opt[:, 1], color='cornflowerblue', alpha=0.4)
    
    plt.title('Airfoil Geometry: Optimized vs Baseline', fontsize=14, fontweight='bold')
    plt.xlabel('x/c', fontsize=12)
    plt.ylabel('y/c', fontsize=12)
    plt.axis('equal')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "geom_naca2410_vs_opt.png"), dpi=300)
    plt.close()
    
    # 2. Plot Cl vs Alpha
    plt.figure(figsize=(8, 6))
    if res_naca is not None and res_naca['polar']['alpha']:
        plt.plot(res_naca['polar']['alpha'], res_naca['polar']['cl'], 'k--', linewidth=2, label='Baseline')
    
    if res_opt is not None and res_opt['polar']['alpha']:
        plt.plot(res_opt['polar']['alpha'], res_opt['polar']['cl'], 'b-', linewidth=2, label='Optimized Airfoil')
        
    plt.title('Lift Coefficient (Cl) vs Angle of Attack: Optimized vs Baseline', fontsize=14, fontweight='bold')
    plt.xlabel('Angle of Attack (°)', fontsize=12)
    plt.ylabel('Lift Coefficient (Cl)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "cl_naca2410_vs_opt.png"), dpi=300)
    plt.close()
    
    # 3. Plot Total Cd vs Alpha
    plt.figure(figsize=(8, 6))
    if res_naca is not None and res_naca['polar']['alpha']:
        plt.plot(res_naca['polar']['alpha'], res_naca['polar']['cd'], 'k--', linewidth=2, label='Baseline')
    
    if res_opt is not None and res_opt['polar']['alpha']:
        plt.plot(res_opt['polar']['alpha'], res_opt['polar']['cd'], 'r-', linewidth=2, label='Optimized Airfoil')
        
    plt.title('Total Drag Coefficient (Cd) vs Angle of Attack: Optimized vs Baseline', fontsize=14, fontweight='bold')
    plt.xlabel('Angle of Attack (°)', fontsize=12)
    plt.ylabel('Total Drag Coefficient (Cd)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "cd_naca2410_vs_opt.png"), dpi=300)
    plt.close()
    
    print(f"Plots saved to {os.path.join(PROJECT_DIR, 'Output', 'Images')}")

if __name__ == "__main__":
    main()
