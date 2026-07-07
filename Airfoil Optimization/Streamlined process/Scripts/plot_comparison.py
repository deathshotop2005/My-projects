import numpy as np
import matplotlib.pyplot as plt

file1 = 'FINAL_OPTIMIZED_gen10_rank2.dat'
file2 = 'OPTIMIZED_AIRFOIL_TRIAL_1.dat'

try:
    coords1 = np.loadtxt(file1, skiprows=1)
    coords2 = np.loadtxt(file2, skiprows=1)
    
    plt.figure(figsize=(12, 5))
    
    plt.plot(coords1[:, 0], coords1[:, 1], color='indianred', linewidth=2, label='Previous Trial (Peak L/D = 161.06)')
    plt.plot(coords2[:, 0], coords2[:, 1], color='royalblue', linewidth=2, linestyle='--', label='New Trial 1 (Peak L/D = 173.05)')
    
    plt.fill_between(coords1[:, 0], coords1[:, 1], color='indianred', alpha=0.15)
    plt.fill_between(coords2[:, 0], coords2[:, 1], color='royalblue', alpha=0.2)
    
    plt.title('Comparison of Optimized Airfoils', fontsize=14, fontweight='bold')
    plt.xlabel('x/c', fontsize=12)
    plt.ylabel('y/c', fontsize=12)
    plt.axis('equal')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(fontsize=12)
    plt.tight_layout()
    
    import os; out_file = os.path.join('..', 'Results', 'COMPARISON_PLOT.png')
    plt.savefig(out_file, dpi=300, bbox_inches='tight')
    print(f"Successfully saved plot to {out_file}")
    
except Exception as e:
    print(f"Error: {e}")
