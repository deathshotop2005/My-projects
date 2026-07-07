import os
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import glob

# Parameters for 3D Correction
ASPECT_RATIO = 10.0  # Typical for a small aircraft / UAV wing
OSWALD_E = 0.85      # Oswald efficiency factor (0.7 to 0.95 is typical)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
AIRFOILS_DIR = os.path.join(PROJECT_DIR, "Output", "Airfoils")
IMAGES_DIR = os.path.join(PROJECT_DIR, "Output", "Images")

def run_xfoil(airfoil_path, re_val=1000000, mach_val=0.0):
    airfoil_name = os.path.basename(airfoil_path)
    polar_path = "temp_polar.txt"
    polar_abs = os.path.join(AIRFOILS_DIR, polar_path)
    if os.path.exists(polar_abs):
        os.remove(polar_abs)
        
    commands = f"""
LOAD {airfoil_name}
PANE
OPER
ALFA 0.0
VISC {re_val}
MACH {mach_val}
ITER 100
PACC
{polar_path}

ASEQ 0 10 1
PACC

QUIT
"""
    try:
        subprocess.run(
            [XFOIL_EXE],
            input=commands,
            text=True,
            capture_output=True,
            timeout=15,
            cwd=AIRFOILS_DIR
        )
    except subprocess.TimeoutExpired:
        print("XFOIL timed out!")
        return None, None, None

    alphas, cls, cds = [], [], []
    if os.path.exists(polar_abs):
        with open(polar_abs, 'r') as f:
            lines = f.readlines()
        for line in lines:
            parts = line.split()
            if len(parts) >= 7 and "alpha" not in line.lower() and "---" not in line:
                try:
                    a = float(parts[0])
                    c = float(parts[1])
                    d = float(parts[2])
                    alphas.append(a)
                    cls.append(c)
                    cds.append(d)
                except ValueError:
                    pass
        os.remove(polar_abs)
    return np.array(alphas), np.array(cls), np.array(cds)

def main():
    print("=" * 60)
    print("2D vs 3D INDUCED DRAG COMPARISON")
    print("=" * 60)
    print(f"Aspect Ratio (AR)      : {ASPECT_RATIO}")
    print(f"Oswald Efficiency (e)  : {OSWALD_E}")
    print("-" * 60)
    
    # Pick an airfoil
    test_airfoil = os.path.join(AIRFOILS_DIR, "final_optimal_new.dat")
    if not os.path.exists(test_airfoil):
        print(f"Error: Could not find {test_airfoil}. Please run GA first.")
        return
    print(f"Testing Airfoil: {os.path.basename(test_airfoil)}")
    
    alphas, cls, cds_2d = run_xfoil(test_airfoil)
    
    if alphas is None or len(alphas) == 0:
        print("Failed to get polar data from XFOIL.")
        return
        
    # Calculate 3D Induced Drag
    # Cd_total = Cd_profile (2D) + Cd_induced
    # Cd_induced = Cl^2 / (pi * e * AR)
    cds_induced = (cls**2) / (np.pi * OSWALD_E * ASPECT_RATIO)
    cds_3d = cds_2d + cds_induced
    
    # Calculate L/D
    ld_2d = cls / cds_2d
    ld_3d = cls / cds_3d
    
    peak_ld_2d = np.max(ld_2d)
    peak_aoa_2d = alphas[np.argmax(ld_2d)]
    
    peak_ld_3d = np.max(ld_3d)
    peak_aoa_3d = alphas[np.argmax(ld_3d)]
    
    print("\nRESULTS:")
    print(f"  2D Peak L/D (Infinite Wing) : {peak_ld_2d:.2f} at {peak_aoa_2d}° AoA")
    print(f"  3D Peak L/D (Real Wing)     : {peak_ld_3d:.2f} at {peak_aoa_3d}° AoA")
    print(f"  -> The L/D ratio dropped by {((peak_ld_2d - peak_ld_3d)/peak_ld_2d)*100:.1f}% due to induced drag!")
    
    print("\nRAW POLAR DATA TRACE:")
    for a, cl, cd, ld in zip(alphas, cls, cds_2d, ld_2d):
        print(f"  Alpha: {a:4.1f} | Cl: {cl:6.4f} | Cd: {cd:6.4f} | L/D: {ld:6.2f}")
    
    # Plotting
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Polar Plot (Cd vs Cl)
    ax1.plot(cds_2d, cls, 'o-', color='royalblue', label='2D (Profile Drag Only)')
    ax1.plot(cds_3d, cls, 's-', color='crimson', label='3D (Profile + Induced Drag)')
    ax1.set_xlabel('Drag Coefficient (Cd)')
    ax1.set_ylabel('Lift Coefficient (Cl)')
    ax1.set_title('Drag Polar')
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend()
    
    # L/D Plot
    ax2.plot(alphas, ld_2d, 'o-', color='royalblue', label='2D L/D')
    ax2.plot(alphas, ld_3d, 's-', color='crimson', label='3D L/D')
    ax2.set_xlabel('Angle of Attack (Alpha)')
    ax2.set_ylabel('Lift-to-Drag Ratio (L/D)')
    ax2.set_title('L/D vs Angle of Attack')
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.legend()
    
    plt.tight_layout()
    plot_path = os.path.join(IMAGES_DIR, "drag_comparison.png")
    plt.savefig(plot_path, dpi=300)
    print(f"\nSaved comparison plot to: {plot_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
