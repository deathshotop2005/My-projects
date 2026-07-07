import os
import subprocess
import tempfile
import re
import numpy as np

SCRIPT_DIR = r"C:\Users\ompat\OneDrive\Desktop\Honeywell\Streamlined process\Scripts"
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
DAT_DIR = r"C:\Users\ompat\OneDrive\Desktop\Honeywell\coord_seligFmt"

RE = 500000  # Updated to match the CSV's Reynolds number
MACH = 0.0
AR = 10.0
OSWALD = 0.85

def write_clean_dat(src_path, dst_path):
    coords = []
    with open(src_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2: continue
            try: x, y = float(parts[0]), float(parts[1])
            except ValueError: continue
            if x > 1.5 or x < -0.1: continue
            coords.append((x, y))
    if len(coords) < 10: return False
    with open(dst_path, "w") as f:
        f.write("AIRFOIL\n")
        for x, y in coords:
            f.write(f"  {x:.6f}  {y:.6f}\n")
    return True

def extract_geom_info(xfoil_output):
    thick_match = re.search(r"Max thickness\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    camb_match  = re.search(r"Max camber\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    
    thick = float(thick_match.group(1)) if thick_match else None
    thick_loc = float(thick_match.group(2)) if thick_match else None
    camb = float(camb_match.group(1)) if camb_match else None
    camb_loc = float(camb_match.group(2)) if camb_match else None
    return thick, thick_loc, camb, camb_loc

def run_airfoil(name):
    dat_path = os.path.join(DAT_DIR, f"{name}.dat")
    clean_fd, clean_path = tempfile.mkstemp(suffix=".dat", prefix="xfoil_airfoil_", dir=SCRIPT_DIR)
    os.close(clean_fd)
    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", prefix="xfoil_polar_", dir=SCRIPT_DIR)
    os.close(polar_fd)
    os.remove(polar_path)
    
    try:
        if not write_clean_dat(dat_path, clean_path):
            return None
        
        commands = f"""PLOP
G

LOAD {os.path.basename(clean_path)}
PANE

OPER
ALFA 0.0
VISC {RE}
MACH {MACH}
ITER 100
PACC
{os.path.basename(polar_path)}

ASEQ 0 15 1
PACC

QUIT
"""
        proc = subprocess.run([XFOIL_EXE], input=commands, capture_output=True, text=True, timeout=30, cwd=SCRIPT_DIR)
        thick, thick_loc, camb, camb_loc = extract_geom_info(proc.stdout)
        
        best_ld_2d = -float('inf')
        best_result_2d = None
        
        if os.path.exists(polar_path):
            with open(polar_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("-") or line.startswith("alpha") or "CD" in line or "CL" in line:
                        continue
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            alpha = float(parts[0])
                            cl = float(parts[1])
                            cd_2d = float(parts[2])
                            
                            ld_2d = cl / cd_2d if cd_2d != 0 else 0
                            
                            if ld_2d > best_ld_2d:
                                best_ld_2d = ld_2d
                                best_result_2d = {
                                    "Airfoil_Name": name,
                                    "Peak L/D (2D)": ld_2d,
                                    "Alpha (AoA 2D)": alpha,
                                }
                        except Exception:
                            pass
        return best_result_2d
    finally:
        if os.path.exists(clean_path): os.remove(clean_path)
        if os.path.exists(polar_path): os.remove(polar_path)

for af in ["goe238", "ag19"]:
    res = run_airfoil(af)
    print(f"Results for {af} at Re={RE}:")
    if res:
        for k, v in res.items():
            print(f"  {k}: {v}")
    else:
        print("  Simulation failed or no valid data.")
    print("-" * 40)
