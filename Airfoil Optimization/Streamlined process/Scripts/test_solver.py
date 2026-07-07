import os
import numpy as np
from baseclasses import AeroProblem
from cmplxfoil import CMPLXFOIL

# NACA 2412 coordinates — NO header line
dat_content = """1.0000  0.0013
0.9500  0.0114
0.9000  0.0208
0.8000  0.0375
0.7000  0.0518
0.6000  0.0636
0.5000  0.0724
0.4000  0.0780
0.3000  0.0788
0.2500  0.0767
0.2000  0.0726
0.1500  0.0661
0.1000  0.0563
0.0750  0.0496
0.0500  0.0413
0.0250  0.0299
0.0125  0.0215
0.0000  0.0000
0.0125 -0.0165
0.0250 -0.0216
0.0500 -0.0280
0.0750 -0.0322
0.1000 -0.0360
0.1500 -0.0412
0.2000 -0.0446
0.2500 -0.0466
0.3000 -0.0473
0.4000 -0.0464
0.5000 -0.0436
0.6000 -0.0393
0.7000 -0.0334
0.8000 -0.0263
0.9000 -0.0176
0.9500 -0.0124
1.0000 -0.0013
"""

dat_path = "/mnt/c/Users/ompat/OneDrive/Desktop/Honeywell/naca2412.dat"
with open(dat_path, "w") as f:
    f.write(dat_content)

print("Testing CMPLXFOIL on NACA 2412...")

CFDSolver = CMPLXFOIL(dat_path, options={
    "writeSolution": False,
    "printRealConvergence": False,
    "nCrit": 9.0,
})

ap = AeroProblem(
    name="test",
    alpha=5.0,
    mach=0.1,
    reynolds=500000,
    reynoldsLength=1.0,
    T=288.15,
    areaRef=1.0,
    chordRef=1.0,
    evalFuncs=["cl", "cd"],
)

CFDSolver(ap)

funcs = {}
CFDSolver.evalFunctions(ap, funcs)

cl = funcs["test_cl"]
cd = funcs["test_cd"]
print(f"CL  = {cl:.4f}")
print(f"CD  = {cd:.6f}")
print(f"L/D = {cl/cd:.2f}")
print("Solver working correctly!")