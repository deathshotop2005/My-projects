import os
import pandas as pd
import matplotlib.pyplot as plt
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "..", "Data", "master_dataset.csv")
NEW_AIRFOILS_DIR = os.path.join(SCRIPT_DIR, "new generated airfoils")

CONVERGENCE_PLOT = os.path.join(SCRIPT_DIR, "..", "Results", "convergence.png")
BEST_AIRFOIL_PLOT = os.path.join(SCRIPT_DIR, "..", "Results", "best_airfoil.png")
SUMMARY_OUT = os.path.join(SCRIPT_DIR, "..", "Results", "optimization_summary.txt")

def main():
    if not os.path.exists(DATASET_PATH):
        print("Dataset not found!")
        return

    df = pd.read_csv(DATASET_PATH)

    # 1. Extract newly generated airfoils (start with 'gen')
    df_gen = df[df['airfoil'].astype(str).str.startswith('gen')].copy()
    if df_gen.empty:
        print("No generated airfoils found in the dataset yet.")
        return

    # Extract generation number
    def get_gen(name):
        match = re.search(r'gen(\d+)_', name)
        return int(match.group(1)) if match else 0

    df_gen['generation'] = df_gen['airfoil'].apply(get_gen)

    # Calculate max L/D per generation
    gen_stats = df_gen.groupby('generation')['peak_LD'].max().reset_index()

    # 2. Plot Convergence Graph
    plt.figure(figsize=(10, 6))
    plt.plot(gen_stats['generation'], gen_stats['peak_LD'], marker='o', linestyle='-', color='b', linewidth=2)
    plt.title('Genetic Algorithm Convergence (Peak L/D over Generations)', fontsize=14, fontweight='bold')
    plt.xlabel('Generation', fontsize=12)
    plt.ylabel('Maximum Peak L/D', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(CONVERGENCE_PLOT, dpi=300)
    print(f"Convergence plot saved to: {CONVERGENCE_PLOT}")
    plt.close()

    # 3. Find the Absolute Best Airfoil
    best_row = df_gen.loc[df_gen['peak_LD'].idxmax()]
    best_filename = best_row['airfoil']
    best_ld = best_row['peak_LD']

    print(f"\n--- WINNING AIRFOIL ---")
    print(f"File: {best_filename}")
    print(f"Peak L/D: {best_ld:.2f}")

    # Plot the Best Airfoil
    dat_path = os.path.join(NEW_AIRFOILS_DIR, best_filename)
    if os.path.exists(dat_path):
        x, y = [], []
        with open(dat_path, 'r') as f:
            for line in f.readlines()[1:]: # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        x.append(float(parts[0]))
                        y.append(float(parts[1]))
                    except ValueError:
                        pass

        plt.figure(figsize=(12, 4))
        plt.plot(x, y, color='k', linewidth=2)
        plt.fill_between(x, y, color='skyblue', alpha=0.4)
        plt.title(f'Optimized Airfoil Shape: {best_filename} (Peak L/D: {best_ld:.2f})', fontsize=14, fontweight='bold')
        plt.xlabel('x/c')
        plt.ylabel('y/c')
        plt.axis('equal')
        plt.grid(True, linestyle='--', alpha=0.3)
        plt.tight_layout()
        plt.savefig(BEST_AIRFOIL_PLOT, dpi=300)
        print(f"Best airfoil plot saved to: {BEST_AIRFOIL_PLOT}")
        plt.close()
        
        # Also copy it to the main folder for easy access
        export_path = os.path.join(SCRIPT_DIR, f"FINAL_OPTIMIZED_{best_filename}")
        shutil.copy(dat_path, export_path)
        print(f"Coordinates exported to: {export_path}")

    # 4. Save Summary Report
    with open(SUMMARY_OUT, 'w') as f:
        f.write("==================================================\n")
        f.write("GA OPTIMIZATION SUMMARY\n")
        f.write("==================================================\n\n")
        f.write(f"Total Generations Run: {gen_stats['generation'].max()}\n")
        f.write(f"Total Airfoils Simulated in XFOIL: {len(df_gen)}\n\n")
        f.write("--- WINNING AIRFOIL ---\n")
        f.write(f"File Name: {best_filename}\n")
        f.write(f"Peak L/D : {best_ld:.2f}\n\n")
        f.write("Optimized Geometry Parameters:\n")
        f.write(f"  Thickness    : {best_row['thickness']:.4f}\n")
        f.write(f"  Thickness Loc: {best_row['thickness_loc']:.4f}\n")
        f.write(f"  Camber       : {best_row['camber']:.4f}\n")
        f.write(f"  Camber Loc   : {best_row['camber_loc']:.4f}\n")
        f.write(f"  LE Radius    : {best_row['le_radius']:.4f}\n")
        f.write(f"  TE Angle     : {best_row['te_angle']:.4f}\n")
        
    print(f"\nSummary saved to: {SUMMARY_OUT}")

if __name__ == "__main__":
    main()
