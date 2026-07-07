import os
import sys
import subprocess
import tempfile
import re
import csv
import time
import shutil
import glob
import traceback
import argparse
import numpy as np

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")

AOA_MIN = -5.0
AOA_MAX = 15.0
AOA_STEP = 1.0
MAX_LD_CAP = 100.0
MAX_CL_CAP = 2.5
MIN_CD_CAP = 0.003

def get_args():
    parser = argparse.ArgumentParser(description="Generate airfoil dataset using XFOIL")
    parser.add_argument("--zip", type=str, default=os.path.join(PROJECT_DIR, "Data", "Raw", "coord_seligFmt.zip"), help="Path to the ZIP file containing airfoil coordinates")
    parser.add_argument('--mach', type=float, default=0.0)
    parser.add_argument('--re', type=float, default=500000)
    parser.add_argument('--ar', type=float, default=10.0)
    parser.add_argument('--oswald', type=float, default=0.85)
    return parser.parse_args()

def get_next_csv_name(zip_name):
    base_dir = os.path.join(PROJECT_DIR, "Data", "CSVs")
    os.makedirs(base_dir, exist_ok=True)
    base_name = os.path.splitext(zip_name)[0]
    filename = os.path.join(base_dir, f"{base_name}.csv")
    if not os.path.exists(filename):
        return filename
    trial = 1
    while True:
        filename = os.path.join(base_dir, f"{base_name}({trial}).csv")
        if not os.path.exists(filename):
            return filename
        trial += 1

def write_clean_dat(src_path, dst_path):
    """Strip header / bad lines so XFOIL gets numeric x y pairs only."""
    coords = []
    with open(src_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            try:
                x, y = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            if x > 1.5 or x < -0.1:
                continue
            coords.append((x, y))
    if len(coords) < 10:
        return False
    with open(dst_path, "w") as f:
        f.write("AIRFOIL\n")
        for x, y in coords:
            f.write(f"  {x:.6f}  {y:.6f}\n")
    return True

def extract_geom_info(xfoil_output):
    """Extract thickness and camber from XFOIL stdout."""
    thick_match = re.search(r"Max thickness\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    camb_match  = re.search(r"Max camber\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    
    thick = float(thick_match.group(1)) if thick_match else None
    thick_loc = float(thick_match.group(2)) if thick_match else None
    camb = float(camb_match.group(1)) if camb_match else None
    camb_loc = float(camb_match.group(2)) if camb_match else None
    
    return thick, thick_loc, camb, camb_loc

def run_xfoil(dat_path, name, args):
    """Run XFOIL and return the best point meeting the constraints."""
    clean_fd, clean_path = tempfile.mkstemp(suffix=".dat", prefix="xfoil_airfoil_", dir=SCRIPT_DIR)
    os.close(clean_fd)
    clean_basename = os.path.basename(clean_path)

    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", prefix="xfoil_polar_", dir=SCRIPT_DIR)
    os.close(polar_fd)
    os.remove(polar_path)
    polar_basename = os.path.basename(polar_path)
    
    best_result = None
    
    try:
        if not write_clean_dat(dat_path, clean_path):
            return None

        commands = f"""PLOP
G

LOAD {clean_basename}
PANE

OPER
ALFA 0.0
VISC {args.re}
MACH {args.mach}
ITER 100
PACC
{polar_basename}

ASEQ 0 15 1
PACC

QUIT
"""
        proc = subprocess.run(
            [XFOIL_EXE],
            input=commands,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=SCRIPT_DIR
        )
        
        thick, thick_loc, camb, camb_loc = extract_geom_info(proc.stdout)
        
        if thick is None or thick < 0.10:
            return None
            
        best_ld_3d = -float('inf')
        best_ld_2d_global = -float('inf')
        best_alpha_3d = None
        best_cl_3d = None
        best_cd_3d = None
        best_alpha_2d = None
        
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
                            
                            if cl >= MAX_CL_CAP or cd_2d < MIN_CD_CAP:
                                continue
                                
                            ld_2d = cl / cd_2d if cd_2d != 0 else 0
                            
                            # Track absolute peak 2D L/D
                            if ld_2d > best_ld_2d_global:
                                best_ld_2d_global = ld_2d
                                best_alpha_2d = alpha
                            
                            # Calculate 3D Induced Drag
                            cd_i = (cl ** 2) / (np.pi * args.oswald * args.ar)
                            cd_3d = cd_2d + cd_i
                            ld_3d = cl / cd_3d if cd_3d != 0 else 0
                            
                            if ld_3d > MAX_LD_CAP:
                                continue
                                
                            if ld_3d > best_ld_3d:
                                best_ld_3d = ld_3d
                                best_alpha_3d = alpha
                                best_cl_3d = cl
                                best_cd_3d = cd_3d
                        except (ValueError, IndexError):
                            continue
        
        if best_ld_3d != -float('inf'):
            best_result = {
                "Airfoil_Name": name,
                "Camber": camb if camb is not None else "",
                "Camber_Location": camb_loc if camb_loc is not None else "",
                "Thickness": thick if thick is not None else "",
                "Thickness_Location": thick_loc if thick_loc is not None else "",
                "Reynolds_Number": args.re,
                "Cl": best_cl_3d,
                "Cd": best_cd_3d,
                "peak_LD_2d": best_ld_2d_global,
                "aoa_2d": best_alpha_2d,
                "peak_LD_3d": best_ld_3d,
                "aoa_3d": best_alpha_3d
            }
        return best_result
    except Exception:
        return None
    finally:
        if os.path.exists(clean_path):
            try:
                os.remove(clean_path)
            except Exception:
                pass
        if os.path.exists(polar_path):
            try:
                os.remove(polar_path)
            except Exception:
                pass

def main():
    args = get_args()
    
    print("\n" + "="*60)
    print("XFOIL DATASET GENERATION")
    print(f"ZIP Path: {args.zip}")
    print(f"Mach: {args.mach} | Reynolds: {args.re}")
    print("="*60)
    
    import time
    timestamp = int(time.time())
    zip_basename = os.path.splitext(os.path.basename(args.zip))[0]
    extract_dir = os.path.join(PROJECT_DIR, "Data", "Raw", f"{zip_basename}_{timestamp}")
    
    if not os.path.exists(args.zip):
        print(f"[ERROR] Zip file not found: {args.zip}")
        return

    print(f"Extracting ZIP file into new directory: {extract_dir}")
    try:
        import zipfile
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(args.zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("Extraction complete.")
    except Exception as e:
        print(f"[ERROR] Failed to extract zip: {e}")
        return

    csv_out_path = get_next_csv_name(zip_basename)
    
    airfoil_files = []
    for root, dirs, files in os.walk(extract_dir):
        for f in files:
            if f.endswith(".dat"):
                airfoil_files.append(os.path.join(root, f))
                
    total = len(airfoil_files)
    if total == 0:
        print(f"[ERROR] No .dat files found inside the extracted directory.")
        return
        
    print(f"Found {total} airfoil files. Starting evaluation for MAX L/D <= {MAX_LD_CAP}...\n")

    fields = [
        "Airfoil_Name", "Camber", "Camber_Location", 
        "Thickness", "Thickness_Location", "Reynolds_Number", 
        "Cl", "Cd", "peak_LD_2d", "aoa_2d", "peak_LD_3d", "aoa_3d"
    ]
    
    results = []
    success_count = 0
    t0 = time.time()
    
    for i, path in enumerate(airfoil_files, 1):
        name = os.path.splitext(os.path.basename(path))[0]
        
        result = run_xfoil(path, name, args)
        if result is not None:
            results.append(result)
            success_count += 1
            
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0
        eta = (total - i) / rate if rate > 0 else 0
        
        bar_len = 30
        filled = int(bar_len * i // total)
        bar = "#" * filled + "-" * (bar_len - filled)
        pct = int(100 * i / total)
        print(f"[PROGRESS] [{bar}] {pct}% ({i}/{total}) | Valid: {success_count} | ETA: {int(eta)}s")

    print("\n\nSorting data by 3D L/D descending...")
    results.sort(key=lambda r: r["peak_LD_3d"], reverse=True)

    with open(csv_out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done! Saved sorted data to {csv_out_path}")

if __name__ == "__main__":
    main()
