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
OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "..", "Data", "all_airfoils_polar_data.csv")

RE          = 500_000
MACH        = 0.1
NCRIT       = 9.0
AOA_START   = 0.0
AOA_END     = 10.0
AOA_STEP    = 0.5
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
    # Example format in stdout:
    # Max thickness =     0.100376  at x =   0.309
    # Max camber    =     0.063809  at x =   0.500
    thick_match = re.search(r"Max thickness\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    camb_match  = re.search(r"Max camber\s*=\s*([0-9.-]+)\s*at x\s*=\s*([0-9.-]+)", xfoil_output)
    
    thick = float(thick_match.group(1)) if thick_match else None
    thick_loc = float(thick_match.group(2)) if thick_match else None
    camb = float(camb_match.group(1)) if camb_match else None
    camb_loc = float(camb_match.group(2)) if camb_match else None
    
    return thick, thick_loc, camb, camb_loc

def evaluate_airfoil(name, dat_path, csv_writer):
    """Run XFOIL and append results to CSV."""
    clean_fd, clean_path = tempfile.mkstemp(suffix=".dat", prefix="xfoil_airfoil_", dir=SCRIPT_DIR)
    os.close(clean_fd)
    clean_basename = os.path.basename(clean_path)

    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", prefix="xfoil_polar_", dir=SCRIPT_DIR)
    os.close(polar_fd)
    os.remove(polar_path)
    polar_basename = os.path.basename(polar_path)
    
    try:
        if not write_clean_dat(dat_path, clean_path):
            return False

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
        
        # Parse polar output file
        points_converged = 0
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
                            
                            ld = cl / cd if cd != 0 else 0
                            
                            csv_writer.writerow({
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
                            })
                            points_converged += 1
                        except (ValueError, IndexError):
                            continue
        return points_converged > 0
    except Exception as e:
        return False
    finally:
        if os.path.exists(clean_path):
            os.remove(clean_path)
        if os.path.exists(polar_path):
            os.remove(polar_path)

def main():
    dat_files = sorted([f for f in os.listdir(AIRFOIL_DIR) if f.endswith(".dat")])
    total     = len(dat_files)
    print(f"Found {total} airfoil files. Starting evaluation...\n")

    fields = [
        "Airfoil_Name", "Camber", "Camber_Location", 
        "Thickness", "Thickness_Location", "Reynolds_Number", 
        "Alpha", "Cl", "Cd", "L_over_D"
    ]
    
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        
        success_count = 0
        t0 = time.time()
        for i, fname in enumerate(dat_files, 1):
            path = os.path.join(AIRFOIL_DIR, fname)
            name = os.path.splitext(fname)[0]
            
            success = evaluate_airfoil(name, path, writer)
            if success:
                success_count += 1
                
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            
            print(f"\rProgress: {i}/{total} | Success: {success_count} | ETA: {int(eta)}s    ", end="", flush=True)

    print(f"\n\nDone! Saved all data to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()