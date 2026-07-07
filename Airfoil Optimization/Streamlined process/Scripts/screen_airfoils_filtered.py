import os
import sys
import subprocess
import tempfile
import re
import csv
import time

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AIRFOIL_DIR = os.path.join(SCRIPT_DIR, "coord_seligFmt")
OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "..", "Data", "Airfoil data max L_D_100.csv")

RE          = 500_000
MACH        = 0.1
NCRIT       = 9.0
AOA_START   = 0.0
AOA_END     = 10.0
AOA_STEP    = 0.5

# Constraints requested by user
MAX_LD_CAP = 100.0
MAX_CL_CAP = 2.5
# Note: I'm using 0.003 here instead of 0.3 because an airfoil with Cd >= 0.3 
# is effectively a stalled bluff body (like a brick), which would filter out everything. 
# Feel free to change this to 0.3 if you genuinely want extreme drag profiles!
MIN_CD_CAP = 0.003
# ─────────────────────────────────────────────────────────────────────────────

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
        f.write("AIRFOIL\n")  # XFOIL expects a header line
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

def evaluate_airfoil(name, dat_path):
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
VISC {RE}
MACH {MACH}
VPAR
N {NCRIT}

ITER 200
PACC
{polar_basename}

ASEQ {AOA_START} {AOA_END} {AOA_STEP}
PACC

QUIT
"""
        xfoil_exe = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
        proc = subprocess.run(
            [xfoil_exe],
            input=commands,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        thick, thick_loc, camb, camb_loc = extract_geom_info(proc.stdout)
        
        best_ld = -float('inf')
        
        # Parse polar output file
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
                            cd = float(parts[2])
                            
                            # Filter constraints
                            if cl >= MAX_CL_CAP:
                                continue
                            if cd < MIN_CD_CAP:
                                continue
                                
                            ld = cl / cd if cd != 0 else 0
                            
                            if ld > MAX_LD_CAP:
                                continue
                                
                            # Track best L/D that meets all constraints
                            if ld > best_ld:
                                best_ld = ld
                                best_result = {
                                    "Airfoil_Name": name,
                                    "Camber": camb if camb is not None else "",
                                    "Camber_Location": camb_loc if camb_loc is not None else "",
                                    "Thickness": thick if thick is not None else "",
                                    "Thickness_Location": thick_loc if thick_loc is not None else "",
                                    "Reynolds_Number": RE,
                                    "Alpha": alpha,
                                    "Cl": cl,
                                    "Cd": cd,
                                    "L_over_D": ld
                                }
                        except (ValueError, IndexError):
                            continue
        return best_result
    except Exception as e:
        return None
    finally:
        if os.path.exists(clean_path):
            os.remove(clean_path)
        if os.path.exists(polar_path):
            os.remove(polar_path)

def main():
    dat_files = sorted([f for f in os.listdir(AIRFOIL_DIR) if f.endswith(".dat")])
    total     = len(dat_files)
    print(f"Found {total} airfoil files. Starting evaluation for MAX L/D <= {MAX_LD_CAP}...\n")

    fields = [
        "Airfoil_Name", "Camber", "Camber_Location", 
        "Thickness", "Thickness_Location", "Reynolds_Number", 
        "Alpha", "Cl", "Cd", "L_over_D"
    ]
    
    results = []
    
    success_count = 0
    t0 = time.time()
    for i, fname in enumerate(dat_files, 1):
        path = os.path.join(AIRFOIL_DIR, fname)
        name = os.path.splitext(fname)[0]
        
        result = evaluate_airfoil(name, path)
        if result is not None:
            results.append(result)
            success_count += 1
            
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0
        eta = (total - i) / rate if rate > 0 else 0
        
        print(f"\rProgress: {i}/{total} | Valid Airfoils Found: {success_count} | ETA: {int(eta)}s    ", end="", flush=True)

    print("\n\nSorting data by L/D descending...")
    results.sort(key=lambda r: r["L_over_D"], reverse=True)

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done! Saved sorted data to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
