"""
Max Cl/Cd for AH 79-100 B (ah79100b) via standard XFOIL (subprocess).
AoA sweep: 0° to 10° in 0.5° steps with physical realism filtering.
Calls the XFOIL binary directly — supports Mach=0 (incompressible).
"""
import os
import sys
import subprocess
import tempfile
import re

import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AIRFOIL_DAT = os.path.join(SCRIPT_DIR, "coord_seligFmt", "ah79100b.dat")

RE = 500_000
MACH = 0.1
NCRIT = 9.0
AOA_START = 0.0
AOA_END = 10.0
AOA_STEP = 0.5

# physical realism bounds
MIN_CD = 0.001       # below this is numerical noise
MAX_CD = 0.1         # above this is too draggy
MIN_CL = 0.1         # must produce meaningful lift
MAX_CL = 2.5         # physically impossible above this
MAX_LD = 200.0       # realistic upper bound at Re=500k
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
            coords.append((x, y))
    if len(coords) < 10:
        raise ValueError(f"Too few coordinates in {src_path}")
    with open(dst_path, "w") as f:
        f.write("AH79100B\n")  # XFOIL expects a header line
        for x, y in coords:
            f.write(f"  {x:.6f}  {y:.6f}\n")
    return len(coords)


def run_xfoil_polar(dat_path, re_val, mach_val, ncrit_val, aoa_start, aoa_end, aoa_step):
    """
    Run XFOIL via subprocess to generate a polar.
    Returns list of (alpha, cl, cd, cm) tuples.
    """
    # Create a temp file path for the polar output in SCRIPT_DIR
    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", prefix="xfoil_polar_", dir=SCRIPT_DIR)
    os.close(polar_fd)
    os.remove(polar_path)
    polar_basename = os.path.basename(polar_path)

    try:
        # Build the XFOIL command sequence
        commands = f"""LOAD {dat_path}
PANE
PLOP
G

OPER
ALFA 0.0
VISC {re_val}
MACH {mach_val}
VPAR
N {ncrit_val}

ITER 200
PACC
{polar_basename}

ASEQ {aoa_start} {aoa_end} {aoa_step}
PACC

QUIT
"""
        # Run XFOIL
        xfoil_exe = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
        proc = subprocess.run(
            [xfoil_exe],
            input=commands,
            capture_output=True,
            text=True,
            timeout=120,
        )
        run_xfoil_polar.last_output = proc.stdout + "\n" + proc.stderr

        # Parse polar output file
        results = []
        if os.path.exists(polar_path):
            with open(polar_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("-") or line.startswith("alpha"):
                        continue
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            alpha = float(parts[0])
                            cl = float(parts[1])
                            cd = float(parts[2])
                            cm = float(parts[4]) if len(parts) > 4 else 0.0
                            results.append((alpha, cl, cd, cm))
                        except (ValueError, IndexError):
                            continue
        return results

    finally:
        if os.path.exists(polar_path):
            os.remove(polar_path)


def main():
    if not os.path.isfile(AIRFOIL_DAT):
        print(f"Airfoil file not found: {AIRFOIL_DAT}", file=sys.stderr)
        sys.exit(1)

    # Write clean dat file in SCRIPT_DIR
    clean_fd, clean_path = tempfile.mkstemp(suffix=".dat", prefix="xfoil_airfoil_", dir=SCRIPT_DIR)
    os.close(clean_fd)
    clean_basename = os.path.basename(clean_path)

    try:
        n_pts = write_clean_dat(AIRFOIL_DAT, clean_path)

        print("=" * 60)
        print("AH 79-100 B — Cl/Cd sweep (XFOIL, physical realism filter)")
        print("=" * 60)
        print(f"  Geometry : {AIRFOIL_DAT} ({n_pts} points)")
        print(f"  Re       : {RE:,}   Mach : {MACH}   nCrit : {NCRIT}")
        print(f"  AoA      : {AOA_START}° to {AOA_END}° step {AOA_STEP}°")
        print(f"  Bounds   : CD [{MIN_CD}, {MAX_CD}]  CL [{MIN_CL}, {MAX_CL}]  L/D max {MAX_LD}")
        print()

        # Run XFOIL
        print("Running XFOIL...", end=" ", flush=True)
        polar_data = run_xfoil_polar(
            clean_basename, RE, MACH, NCRIT, AOA_START, AOA_END, AOA_STEP
        )
        print(f"done. ({len(polar_data)} points converged)")
        print()

        if not polar_data:
            print("XFOIL returned no converged points. Subprocess output:", file=sys.stderr)
            print(run_xfoil_polar.last_output, file=sys.stderr)
            sys.exit(1)

        # Build the expected AoA list for tracking
        aoa_list = np.arange(AOA_START, AOA_END + AOA_STEP / 2, AOA_STEP)
        converged_alphas = {round(a, 1) for a, _, _, _ in polar_data}

        best_ld = -np.inf
        best = None
        rows = []

        print(f"{'α [deg]':>8}  {'CL':>10}  {'CD':>12}  {'Cl/Cd':>10}  {'Status':>12}")
        print("-" * 60)

        for aoa in aoa_list:
            aoa_r = round(float(aoa), 1)

            if aoa_r not in converged_alphas:
                print(f"{aoa_r:8.1f}  {'—':>10}  {'—':>12}  {'—':>10}  {'NO CONVERGE':>12}")
                continue

            # Find the matching result
            match = None
            for a, cl, cd, cm in polar_data:
                if abs(round(a, 1) - aoa_r) < 0.01:
                    match = (cl, cd, cm)
                    break

            if match is None:
                print(f"{aoa_r:8.1f}  {'—':>10}  {'—':>12}  {'—':>10}  {'NO CONVERGE':>12}")
                continue

            cl, cd, cm = match

            # Check for NaN or negative drag
            if cd <= 0 or np.isnan(cl) or np.isnan(cd):
                print(f"{aoa_r:8.1f}  {'—':>10}  {'—':>12}  {'—':>10}  {'NO CONVERGE':>12}")
                continue

            ld = cl / cd

            # Physical realism filtering
            if cd < MIN_CD or cd > MAX_CD:
                print(f"{aoa_r:8.1f}  {cl:10.4f}  {cd:12.6f}  {ld:10.2f}  {'CD OUT':>12}")
                continue
            if cl < MIN_CL or cl > MAX_CL:
                print(f"{aoa_r:8.1f}  {cl:10.4f}  {cd:12.6f}  {ld:10.2f}  {'CL OUT':>12}")
                continue
            if ld > MAX_LD:
                print(f"{aoa_r:8.1f}  {cl:10.4f}  {cd:12.6f}  {ld:10.2f}  {'L/D OUT':>12}")
                continue

            rows.append((aoa_r, cl, cd, ld))
            print(f"{aoa_r:8.1f}  {cl:10.4f}  {cd:12.6f}  {ld:10.2f}  {'OK':>12}")

            if ld > best_ld:
                best_ld = ld
                best = (aoa_r, cl, cd, ld)

        print("-" * 60)
        print(f"\nValid data points: {len(rows)} / {len(aoa_list)}")

        if best is None:
            print("No valid Cl/Cd points passed the realism filter.")
            sys.exit(1)

        aoa, cl, cd, ld = best
        print(f"\n{'=' * 60}")
        print(f"  MAX Cl/Cd = {ld:.2f}  at α = {aoa:.1f}°")
        print(f"  CL = {cl:.4f}   CD = {cd:.6f}")
        print(f"{'=' * 60}")

    finally:
        if os.path.exists(clean_path):
            os.remove(clean_path)


if __name__ == "__main__":
    main()
