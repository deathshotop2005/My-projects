"""Compare AH 79-100 B L/D at Re=100k vs 500k (online ref: 65.85 @ 8.25 deg, Re=100k)."""
import os
import numpy as np
from baseclasses import AeroProblem
from cmplxfoil import CMPLXFOIL

os.chdir(os.path.dirname(os.path.abspath(__file__)))
DAT = "coord_seligFmt/ah79100b.dat"
OPTS = {"writeSolution": False, "printRealConvergence": False, "nCrit": 9.0}
MACH = 0.1
T = 288.15


def sweep(re, aoa_list):
    solver = CMPLXFOIL(DAT, options=OPTS)
    rows = []
    best = (-1, None, None, None)
    for aoa in aoa_list:
        ap = AeroProblem(
            name="ap", alpha=float(aoa), mach=MACH,
            reynolds=re, reynoldsLength=1.0, T=T,
            areaRef=1.0, chordRef=1.0, evalFuncs=["cl", "cd"],
        )
        solver(ap)
        f = {}
        solver.evalFunctions(ap, f)
        cl, cd = float(f["ap_cl"]), float(f["ap_cd"])
        ld = cl / cd if cd > 0 else float("nan")
        rows.append((aoa, cl, cd, ld))
        if ld > best[0]:
            best = (ld, aoa, cl, cd)
    return rows, best


print("AH 79-100 B — CMPLXFOIL (nCrit=9, Mach=0.1, chord=1 m)\n")

aoa_fine = np.arange(0.0, 12.0 + 0.25 / 2, 0.25)

for re in [100_000, 500_000]:
    rows, (ld_max, aoa_best, cl_b, cd_b) = sweep(re, aoa_fine)
    print(f"Re = {re:,}")
    print(f"  Best in sweep:  L/D = {ld_max:.2f}  @ alpha = {aoa_best:.2f} deg  (CL={cl_b:.4f}, CD={cd_b:.6f})")
  # point check near online reference
    for target in [8.0, 8.25, 8.5]:
        r = [x for x in rows if abs(x[0] - target) < 0.01]
        if r:
            a, cl, cd, ld = r[0]
            print(f"  @ alpha = {a:.2f} deg:  L/D = {ld:.2f}  (CL={cl:.4f}, CD={cd:.6f})")
    print()

print("Online reference (user):  L/D = 65.85 @ alpha = 8.25 deg, Re = 100,000")
print("Your screening_results:   L/D = 192.80 @ alpha = 5.0 deg,  Re = 500,000")
