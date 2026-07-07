"""
cst_optimization.py
===================
Surrogate-Based Optimization for 10-Parameter CST Airfoils.
Uses XGBoost to predict L/D instantly and searches the space using
Differential Evolution. Evaluates the top 5 predictions per loop in XFOIL.
Finally, polishes the best shape using L-BFGS-B.
"""

import os
import sys
import numpy as np
import tempfile
import subprocess
import json
import warnings
import argparse
import matplotlib.pyplot as plt
from scipy.optimize import differential_evolution, minimize
from math import comb
from xgboost import XGBRegressor

warnings.filterwarnings('ignore')

# ── CONFIGURATION ────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
NEW_AIRFOILS_DIR = os.path.join(PROJECT_DIR, "Output", "Airfoils")
os.makedirs(NEW_AIRFOILS_DIR, exist_ok=True)

parser = argparse.ArgumentParser()
parser.add_argument('--mach', type=float, default=0.0)
parser.add_argument('--re', type=float, default=1000000)
parser.add_argument('--ar', type=float, default=10.0)
parser.add_argument('--oswald', type=float, default=0.85)
args = parser.parse_args()

GLOBAL_EVAL_COUNT = 0
GLOBAL_BEST_TRUE_LD = 0.0

# Parameter Bounds
# Upper weights strictly positive, Lower weights strictly negative
BOUNDS = [
    (0.05, 0.40), (0.05, 0.40), (0.05, 0.40), (0.05, 0.40), (0.05, 0.40), # Upper w0-w4
    (-0.40, -0.05), (-0.40, -0.05), (-0.40, -0.05), (-0.40, -0.05), (-0.40, -0.05) # Lower w0-w4
]

# ── CST AIRFOIL GENERATION ───────────────────────────────────────────────────
def cst_airfoil(weights_u, weights_l, dz_te=0.0, num_points=200):
    n_u = len(weights_u) - 1
    n_l = len(weights_l) - 1
    
    beta = np.linspace(0, np.pi, num_points // 2)
    x = 0.5 * (1.0 - np.cos(beta))
    
    C = np.sqrt(x) * (1 - x)
    
    S_u = np.zeros_like(x)
    for i in range(n_u + 1):
        K = comb(n_u, i)
        S_u += weights_u[i] * K * (x**i) * ((1 - x)**(n_u - i))
        
    S_l = np.zeros_like(x)
    for i in range(n_l + 1):
        K = comb(n_l, i)
        S_l += weights_l[i] * K * (x**i) * ((1 - x)**(n_l - i))
        
    y_u = C * S_u + x * dz_te
    y_l = C * S_l - x * dz_te
    
    X_upper, Y_upper = x[::-1], y_u[::-1]
    X_lower, Y_lower = x[1:], y_l[1:]
    
    X = np.concatenate([X_upper, X_lower])
    Y = np.concatenate([Y_upper, Y_lower])
    
    return np.column_stack((X, Y))

def get_thickness_and_loc(coords):
    x = coords[:, 0]
    y = coords[:, 1]
    
    le_idx = np.argmin(x)
    x_upper = x[:le_idx+1][::-1]
    y_upper = y[:le_idx+1][::-1]
    x_lower = x[le_idx:]
    y_lower = y[le_idx:]
    
    x_common = np.linspace(0.01, 0.99, 100)
    y_u_interp = np.interp(x_common, x_upper, y_upper)
    y_l_interp = np.interp(x_common, x_lower, y_lower)
    
    thicknesses = y_u_interp - y_l_interp
    max_idx = np.argmax(thicknesses)
    return thicknesses[max_idx], x_common[max_idx]

def is_geometrically_valid(x):
    """Check thickness constraints and intersection."""
    weights_u = x[:5]
    weights_l = x[5:]
    
    coords = cst_airfoil(weights_u, weights_l)
    thick, thick_loc = get_thickness_and_loc(coords)
    
    if thick < 0.10:
        return False
    if thick_loc < 0.20 or thick_loc > 0.50:
        return False
        
    return True

def save_airfoil_dat(coords, filename, name="CST_AIRFOIL"):
    with open(filename, 'w') as f:
        f.write(f"{name}\n")
        for x, y in coords:
            f.write(f"{x:.6f} {y:.6f}\n")

# ── XFOIL EVALUATION ─────────────────────────────────────────────────────────
def evaluate_xfoil(dat_path):
    empty_res = {'peak_ld_3d': 0.0, 'peak_aoa_3d': 0.0, 'cl_at_peak': 0.0, 'cd_at_peak': 0.0,
                 'peak_ld_2d': 0.0, 'peak_aoa_2d': 0.0, 'polar': {'alpha': [], 'cl': [], 'cd': []}}
    if not os.path.exists(XFOIL_EXE):
        return empty_res       
        
    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", dir=NEW_AIRFOILS_DIR)
    os.close(polar_fd)
    os.remove(polar_path)
    
    dat_basename = os.path.basename(dat_path)
    polar_basename = os.path.basename(polar_path)
    
    commands = f"""PLOP
G

LOAD {dat_basename}
PANE

OPER
ALFA 0.0
VISC {args.re}
MACH {args.mach}
ITER 100
PACC
{polar_basename}

ASEQ 0 10 1
PACC

QUIT
"""
    try:
        proc = subprocess.run([XFOIL_EXE], input=commands, text=True, capture_output=True, timeout=15, cwd=NEW_AIRFOILS_DIR)
    except subprocess.TimeoutExpired:
        return empty_res
        
    peak_ld_3d = 0.0
    peak_aoa_3d = 0.0
    cl_at_peak = 0.0
    cd_at_peak = 0.0
    peak_ld_2d = 0.0
    peak_aoa_2d = 0.0
    polar_data = {'alpha': [], 'cl': [], 'cd': []}
    
    if os.path.exists(polar_path):
        try:
            with open(polar_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 7 and "alpha" not in line.lower() and "---" not in line:
                        try:
                            alpha = float(parts[0])
                            cl = float(parts[1])
                            cd_2d = float(parts[2])
                            
                            # CRITICAL CONSTRAINT: Discard mathematically impossible Cd
                            if cd_2d < 0.003:
                                continue
                                
                            ld_2d = cl / cd_2d
                            if ld_2d > peak_ld_2d:
                                peak_ld_2d = ld_2d
                                peak_aoa_2d = alpha
                            
                            cd_i = (cl ** 2) / (np.pi * args.oswald * args.ar)
                            cd_3d = cd_2d + cd_i
                            ld_3d = cl / cd_3d if cd_3d != 0 else 0
                            
                            if ld_3d > peak_ld_3d:
                                peak_ld_3d = ld_3d
                                peak_aoa_3d = alpha
                                cl_at_peak = cl
                                cd_at_peak = cd_3d
                                
                            polar_data['alpha'].append(alpha)
                            polar_data['cl'].append(cl)
                            polar_data['cd'].append(cd_3d)
                        except ValueError:
                            pass
        except Exception:
            pass
        finally:
            try:
                os.remove(polar_path)
            except Exception:
                pass
                
    if peak_ld_3d == 0.0:
        return empty_res
        
    return {
        'peak_ld_3d': peak_ld_3d,
        'peak_aoa_3d': peak_aoa_3d,
        'cl_at_peak': cl_at_peak,
        'cd_at_peak': cd_at_peak,
        'peak_ld_2d': peak_ld_2d,
        'peak_aoa_2d': peak_aoa_2d,
        'polar': polar_data
    }

def true_objective(x):
    global GLOBAL_EVAL_COUNT, GLOBAL_BEST_TRUE_LD
    GLOBAL_EVAL_COUNT += 1
    
    if not is_geometrically_valid(x):
        return 0.0
        
    coords = cst_airfoil(x[:5], x[5:])
    dat_path = os.path.join(NEW_AIRFOILS_DIR, f"temp_{GLOBAL_EVAL_COUNT}.dat")
    save_airfoil_dat(coords, dat_path)
    
    res = evaluate_xfoil(dat_path)
    if os.path.exists(dat_path):
        try: os.remove(dat_path)
        except: pass
        
    ld = res['peak_ld_3d']
    if ld > GLOBAL_BEST_TRUE_LD:
        GLOBAL_BEST_TRUE_LD = ld
        print(f"  [XFOIL] New True Best: L/D = {ld:.2f} (Eval {GLOBAL_EVAL_COUNT})")
        
    return ld

# ── ACTIVE LEARNING LOOP ─────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("TRADITIONAL DIFFERENTIAL EVOLUTION CST OPTIMIZATION")
    print("=" * 60)
    
    # We use a penalty-based objective for the DE so it can handle constraints gracefully
    def de_objective(x):
        if not is_geometrically_valid(x):
            return 100.0  # High penalty for invalid geometry
        ld = true_objective(x)
        if ld <= 0:
            return 100.0
        return -ld
        
    print("Starting Differential Evolution search (Evaluating purely in XFOIL)...")
    print("This will take a few minutes as it thoroughly explores the design space.")
    
    res_de = differential_evolution(
        de_objective, 
        BOUNDS, 
        maxiter=15, 
        popsize=2,  # 2 * 10 parameters = 20 individuals per generation (~300 evaluations)
        mutation=(0.5, 1.0),
        recombination=0.7,
        disp=True
    )
    
    best_x = res_de.x
    print(f"\nDE Search Complete. Best found L/D: {-res_de.fun:.2f}")
    
    # 3. FINAL POLISHING
    print("\nTraditional Polishing on the Best Found Shape...")
    
    def polishing_objective(x):
        if not is_geometrically_valid(x):
            return 100.0
        ld = true_objective(x)
        if ld <= 0:
            return 100.0
        return -ld
        
    res_polish = minimize(
        polishing_objective, 
        best_x, 
        method='L-BFGS-B', 
        bounds=BOUNDS,
        options={'maxiter': 10, 'disp': True}
    )
    
    final_x = res_polish.x
    
    print("\n" + "=" * 60)
    print("OPTIMIZATION COMPLETE")
    print("=" * 60)
    
    # Generate final stats & plots
    coords = cst_airfoil(final_x[:5], final_x[5:])
    final_dat_path = os.path.join(NEW_AIRFOILS_DIR, "final_optimal.dat")
    save_airfoil_dat(coords, final_dat_path, name="final_optimal_cst")
    
    res_opt = evaluate_xfoil(final_dat_path)
    final_thick, final_thick_loc = get_thickness_and_loc(coords)
    
    # Generate Plots
    print("Generating plots for the optimal CST airfoil geometry...")
    x = coords[:, 0]
    y = coords[:, 1]
    
    plt.figure(figsize=(10, 4))
    plt.plot(x, y, color='crimson', linewidth=2, label='Optimized CST Airfoil')
    plt.fill_between(x, y, color='lightcoral', alpha=0.4)
    plt.title(f'Final Optimized CST Airfoil Geometry', fontsize=14, fontweight='bold')
    plt.xlabel('x/c', fontsize=12)
    plt.ylabel('y/c', fontsize=12)
    plt.axis('equal')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "optimized_airfoil.png"), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Cl vs AoA
    plt.figure(figsize=(6, 5))
    if res_opt['polar']['alpha']:
        plt.plot(res_opt['polar']['alpha'], res_opt['polar']['cl'], 'b-', label='Optimized')
    plt.title('Cl vs AoA', fontweight='bold')
    plt.xlabel('Angle of Attack (°)')
    plt.ylabel('Lift Coefficient (Cl)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "cl_vs_aoa.png"), dpi=300, bbox_inches='tight')
    plt.close()

    # Cd vs AoA
    plt.figure(figsize=(6, 5))
    if res_opt['polar']['alpha']:
        plt.plot(res_opt['polar']['alpha'], res_opt['polar']['cd'], 'r-', label='Optimized')
    plt.title('Cd vs AoA', fontweight='bold')
    plt.xlabel('Angle of Attack (°)')
    plt.ylabel('Drag Coefficient (Cd)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(os.path.join(PROJECT_DIR, "Output", "Images", "cd_vs_aoa.png"), dpi=300, bbox_inches='tight')
    plt.close()
    
    metrics = {
        "thickness": float(final_thick),
        "thickness_loc": float(final_thick_loc),
        "camber": 0.0,
        "camber_loc": 0.0,
        "le_radius": 0.0,
        "te_angle": 0.0,
        "peak_ld_2d": float(res_opt['peak_ld_2d']),
        "aoa_2d": float(res_opt['peak_aoa_2d']),
        "peak_ld": float(res_opt['peak_ld_3d']),
        "peak_aoa": float(res_opt['peak_aoa_3d']),
        "ld_5deg": 0.0,
        "ld_5deg_2d": 0.0,
        "cl_5deg": 0.0,
        "cd_5deg_3d": 0.0,
        "avg_ld": 0.0,
        "cl_at_peak": float(res_opt['cl_at_peak']),
        "cd_at_peak": float(res_opt['cd_at_peak']),
        "cst_weights_upper": [float(w) for w in final_x[:5]],
        "cst_weights_lower": [float(w) for w in final_x[5:]]
    }
    
    print("\n" + "=" * 40)
    print("FINAL OPTIMIZED PHYSICAL PARAMETERS")
    print("=" * 40)
    print(f"  Maximum Thickness   : {metrics['thickness']*100:.2f}% (at {metrics['thickness_loc']*100:.2f}% chord)")
    print("-" * 40)
    print(f"  Peak 3D L/D         : {metrics['peak_ld']:.2f} (at {metrics['peak_aoa']:.1f}°)")
    print(f"  Peak 2D L/D         : {metrics['peak_ld_2d']:.2f} (at {metrics['aoa_2d']:.1f}°)")
    print(f"  Cl at Peak L/D      : {metrics['cl_at_peak']:.4f}")
    print(f"  Cd at Peak L/D (3D) : {metrics['cd_at_peak']:.5f}")
    print("=" * 40 + "\n")
    
    metrics_path = os.path.join(NEW_AIRFOILS_DIR, "metrics.json")
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=4)
        
    print(f"Metrics saved to: {metrics_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
