import numpy as np
import matplotlib.pyplot as plt
import os

filename = 'OPTIMIZED_AIRFOIL_TRIAL_1.dat'

try:
    # Read coordinates, skipping the first line (name)
    coords = np.loadtxt(filename, skiprows=1)
    
    x = coords[:, 0]
    y = coords[:, 1]
    
    plt.figure(figsize=(12, 4))
    plt.plot(x, y, color='royalblue', linewidth=2, label='Optimized Airfoil (Trial 1)')
    plt.fill_between(x, y, color='cornflowerblue', alpha=0.4)
    
    plt.title('Optimized Airfoil Geometry - Peak L/D = 173.05', fontsize=14, fontweight='bold')
    plt.xlabel('x/c', fontsize=12)
    plt.ylabel('y/c', fontsize=12)
    plt.axis('equal')  # Ensure the aspect ratio is 1:1 so the airfoil doesn't look distorted
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    
    import os; out_file = os.path.join('..', 'Results', 'OPTIMIZED_AIRFOIL_TRIAL_1.png')
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    print(f"Successfully saved plot to {out_file}")
    
except Exception as e:
    print(f"Error: {e}")
