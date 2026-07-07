"""
ga_active_learning.py
=====================
Genetic Algorithm with Active Learning Loop for Airfoil Optimization
Maximizes Peak L/D.

1. Generates population of airfoils (6 parameters).
2. Scores them instantly using XGBoost.
3. Takes the top performers, generates their physical coordinates.
4. Runs XFOIL on them to get the actual Peak L/D.
5. Feeds data back into the ML model (Active Learning).
6. Evolves the next generation.
"""

import os
import sys
import numpy as np
import pandas as pd
import pickle
import tempfile
import subprocess
import shutil
import warnings

warnings.filterwarnings('ignore')

# ML and Dataset paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(SCRIPT_DIR, "..", "Data", "master_dataset.csv")

def get_next_trial_filename(base_dir):
    trial_num = 1
    while True:
        filename = os.path.join(base_dir, f"trial_{trial_num}.csv")
        if not os.path.exists(filename):
            return filename
        trial_num += 1

OUTPUT_DATASET_PATH = get_next_trial_filename(SCRIPT_DIR)
print(f"Active learning data will be saved to: {os.path.basename(OUTPUT_DATASET_PATH)}")

MODEL_PATH = os.path.join(SCRIPT_DIR, "..", "Data", "surrogate_model.pkl")
XFOIL_EXE = os.path.join(SCRIPT_DIR, "..", "..", "xfoil.exe")
NEW_AIRFOILS_DIR = os.path.join(SCRIPT_DIR, "new generated airfoils")

# Create output directory
os.makedirs(NEW_AIRFOILS_DIR, exist_ok=True)

# GA Configuration
POP_SIZE = 100
GENERATIONS = 20
TOP_K_XFOIL = 3  # How many top airfoils to run in XFOIL per generation
MUTATION_RATE = 0.1

# Parameter Bounds
BOUNDS = {
    'thickness': (0.05, 0.25),
    'thickness_loc': (0.20, 0.45),
    'camber': (0.00, 0.10),
    'camber_loc': (0.20, 0.60),
    'le_radius': (0.005, 0.050),
    'te_angle': (2.0, 20.0)
}
FEATURES = list(BOUNDS.keys())

# ============================================================
# AIRFOIL COORDINATE GENERATOR (PARSEC-like Polynomial)
# ============================================================
def generate_airfoil_coordinates(params, num_points=100):
    """
    Generate physical airfoil X, Y coordinates from the 6 parameters.
    Returns array of points [X, Y] starting from TE along upper surface to LE, 
    then back to TE along lower surface (XFOIL standard).
    """
    t, t_loc, c, c_loc, r_le, te_angle = params
    
    # Thickness distribution: yt = a0*sqrt(x) + a1*x + a2*x^2 + a3*x^3 + a4*x^4
    a0 = np.sqrt(2 * r_le)
    
    # Set up linear system for thickness coefficients
    A_t = np.array([
        [t_loc, t_loc**2, t_loc**3, t_loc**4],
        [1, 2*t_loc, 3*t_loc**2, 4*t_loc**3],
        [1, 1, 1, 1],
        [1, 2, 3, 4]
    ])
    B_t = np.array([
        t/2.0 - a0*np.sqrt(t_loc),
        -a0 / (2.0 * np.sqrt(t_loc)),
        -a0,  # yt(1) = 0
        -np.tan(np.deg2rad(te_angle)/2.0) - a0/2.0
    ])
    
    try:
        a1, a2, a3, a4 = np.linalg.solve(A_t, B_t)
    except np.linalg.LinAlgError:
        # Fallback if matrix is singular
        a1, a2, a3, a4 = 0, 0, 0, 0
        
    def yt(x):
        return a0*np.sqrt(x) + a1*x + a2*x**2 + a3*x**3 + a4*x**4
        
    # Camber distribution: yc = c1*x + c2*x^2 + c3*x^3
    if c <= 0.0001:
        c1, c2, c3 = 0, 0, 0
    else:
        A_c = np.array([
            [1, 1, 1],
            [c_loc, c_loc**2, c_loc**3],
            [1, 2*c_loc, 3*c_loc**2]
        ])
        B_c = np.array([0, c, 0])
        try:
            c1, c2, c3 = np.linalg.solve(A_c, B_c)
        except np.linalg.LinAlgError:
            c1, c2, c3 = 0, 0, 0
            
    def yc(x):
        return c1*x + c2*x**2 + c3*x**3
        
    def dyc_dx(x):
        return c1 + 2*c2*x + 3*c3*x**2
        
    # Generate points (cosine spacing for better LE/TE resolution)
    beta = np.linspace(0, np.pi, num_points)
    x = 0.5 * (1.0 - np.cos(beta))
    
    # Calculate camber and thickness
    y_c = yc(x)
    dy_c = dyc_dx(x)
    theta = np.arctan(dy_c)
    
    y_t = yt(x)
    y_t = np.clip(y_t, 0, None)  # Prevent negative thickness
    
    # Upper and lower surfaces
    xu = x - y_t * np.sin(theta)
    yu = y_c + y_t * np.cos(theta)
    xl = x + y_t * np.sin(theta)
    yl = y_c - y_t * np.cos(theta)
    
    # Combine (TE -> upper -> LE -> lower -> TE)
    X_upper, Y_upper = xu[::-1], yu[::-1]
    X_lower, Y_lower = xl[1:], yl[1:]
    
    X = np.concatenate([X_upper, X_lower])
    Y = np.concatenate([Y_upper, Y_lower])
    
    return np.column_stack((X, Y))

def save_airfoil_dat(coords, filename, name="GENERATED_AIRFOIL"):
    """Save coordinates to XFOIL compatible .dat file."""
    with open(filename, 'w') as f:
        f.write(f"{name}\n")
        for x, y in coords:
            f.write(f"{x:.6f} {y:.6f}\n")


# ============================================================
# XFOIL EVALUATION
# ============================================================
def evaluate_xfoil(dat_path, re_val=1e6, mach_val=0.0):
    """Run XFOIL and return Peak L/D."""
    if not os.path.exists(XFOIL_EXE):
        print("  [ERROR] xfoil.exe not found. Cannot run active learning loop.")
        return 0.0
        
    polar_fd, polar_path = tempfile.mkstemp(suffix=".txt", dir=NEW_AIRFOILS_DIR)
    os.close(polar_fd)
    os.remove(polar_path)  # Delete the empty file so XFOIL doesn't prompt to overwrite it
    
    dat_basename = os.path.basename(dat_path)
    polar_basename = os.path.basename(polar_path)
    
    # XFOIL commands
    commands = f"""LOAD {dat_basename}
PANE
PLOP
G

OPER
ALFA 0.0
VISC {re_val}
MACH {mach_val}
ITER 100
PACC
{polar_basename}

ASEQ 0 10 1
PACC

QUIT
"""
    
    try:
        proc = subprocess.run(
            [XFOIL_EXE],
            input=commands,
            text=True,
            capture_output=True,
            timeout=20,
            cwd=NEW_AIRFOILS_DIR
        )
    except subprocess.TimeoutExpired:
        return 0.0
        
    # Read polar to find Peak L/D
    peak_ld = 0.0
    if os.path.exists(polar_path):
        try:
            with open(polar_path, 'r') as f:
                lines = f.readlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 7 and "alpha" not in line.lower() and "---" not in line:
                    try:
                        cl = float(parts[1])
                        cd = float(parts[2])
                        if cd > 0:
                            ld = cl / cd
                            if ld > peak_ld:
                                peak_ld = ld
                    except ValueError:
                        pass
        except Exception:
            pass
        os.remove(polar_path)
        
    if peak_ld == 0.0:
        print("\n[DEBUG] XFOIL Output for failed run:")
        print(proc.stdout)
        print("[DEBUG] End of XFOIL Output\n")
        
    return peak_ld

# ============================================================
# GENETIC ALGORITHM HELPERS
# ============================================================
def init_population(size):
    pop = []
    for _ in range(size):
        ind = []
        for param in FEATURES:
            low, high = BOUNDS[param]
            ind.append(np.random.uniform(low, high))
        pop.append(ind)
    return np.array(pop)

def crossover(parent1, parent2):
    """Blend crossover."""
    alpha = 0.3
    child1, child2 = [], []
    for p1, p2, feat in zip(parent1, parent2, FEATURES):
        low, high = BOUNDS[feat]
        c1 = p1 + alpha * (p2 - p1)
        c2 = p2 - alpha * (p2 - p1)
        child1.append(np.clip(c1, low, high))
        child2.append(np.clip(c2, low, high))
    return np.array(child1), np.array(child2)

def mutate(ind):
    """Random Gaussian mutation."""
    mutated = []
    for val, feat in zip(ind, FEATURES):
        low, high = BOUNDS[feat]
        if np.random.rand() < MUTATION_RATE:
            val += np.random.normal(0, (high-low)*0.1)
        mutated.append(np.clip(val, low, high))
    return np.array(mutated)

# ============================================================
# MAIN OPTIMIZATION LOOP
# ============================================================
def main():
    print("=" * 60)
    print("GA + ACTIVE LEARNING OPTIMIZATION (Maximizing Peak L/D)")
    print("=" * 60)

    # 1. Load ML Model
    if not os.path.exists(MODEL_PATH):
        print(f"Error: {MODEL_PATH} not found. Train the ML model first.")
        sys.exit(1)
        
    with open(MODEL_PATH, 'rb') as f:
        pkg = pickle.load(f)
    xgb_model = pkg['model']
    
    # 2. Load Dataset (to append active learning results)
    if os.path.exists(DATASET_PATH):
        df_master = pd.read_csv(DATASET_PATH)
    else:
        df_master = pd.DataFrame(columns=['airfoil'] + FEATURES + ['peak_LD'])

    # 3. Initialize GA
    population = init_population(POP_SIZE)

    prev_best_ld = None
    patience_counter = 0
    PATIENCE_LIMIT = 5  # Wait for 5 generations of <1% improvement before stopping

    for gen in range(GENERATIONS):
        print(f"\n--- Generation {gen+1}/{GENERATIONS} ---")
        
        # Predict fitness using ML Model instantly
        fitness_scores = xgb_model.predict(population)
        
        # Sort population by fitness (descending)
        sorted_indices = np.argsort(fitness_scores)[::-1]
        population = population[sorted_indices]
        fitness_scores = fitness_scores[sorted_indices]
        
        current_best_ld = fitness_scores[0]
        
        print(f"  Best Predicted Peak L/D: {current_best_ld:.2f}")
        print(f"  Avg  Predicted Peak L/D: {np.mean(fitness_scores):.2f}")

        # Check for convergence (< 1% improvement)
        if prev_best_ld is not None:
            improvement = (current_best_ld - prev_best_ld) / prev_best_ld
            if improvement <= 0.01:
                patience_counter += 1
                print(f"  Convergence Check: Improvement ({improvement*100:.2f}%) <= 1%. (Patience: {patience_counter}/{PATIENCE_LIMIT})")
                if patience_counter >= PATIENCE_LIMIT:
                    print("\n  [!] Early stopping triggered: GA has converged.")
                    break
            else:
                patience_counter = 0  # Reset patience if we get a >1% jump
        
        prev_best_ld = current_best_ld
        
        # ========================================
        # ACTIVE LEARNING (XFOIL LOOP)
        # ========================================
        print(f"  Running XFOIL on Top {TOP_K_XFOIL} generated airfoils...")
        new_xfoil_data = []
        
        for i in range(TOP_K_XFOIL):
            best_params = population[i]
            airfoil_name = f"gen{gen+1}_rank{i+1}"
            dat_filename = os.path.join(NEW_AIRFOILS_DIR, f"{airfoil_name}.dat")
            
            # Generate physical coordinates
            coords = generate_airfoil_coordinates(best_params)
            save_airfoil_dat(coords, dat_filename, name=airfoil_name)
            
            # Evaluate in XFOIL
            actual_ld = evaluate_xfoil(dat_filename)
            print(f"    {airfoil_name} -> Predicted: {fitness_scores[i]:.2f} | Actual XFOIL: {actual_ld:.2f}")
            
            if actual_ld > 0:
                # Add to dataset
                row = {
                    'airfoil': f"{airfoil_name}.dat",
                    'thickness': best_params[0],
                    'thickness_loc': best_params[1],
                    'camber': best_params[2],
                    'camber_loc': best_params[3],
                    'le_radius': best_params[4],
                    'te_angle': best_params[5],
                    'peak_LD': actual_ld
                }
                new_xfoil_data.append(row)
                
        # Retrain ML Model with new truth
        if new_xfoil_data:
            print("  Updating ML Model with new XFOIL data (Active Learning)...")
            df_new = pd.DataFrame(new_xfoil_data)
            # Ensure df_master has same columns
            for col in df_new.columns:
                if col not in df_master.columns:
                    df_master[col] = np.nan
                    
            df_master = pd.concat([df_master, df_new], ignore_index=True)
            df_master.to_csv(OUTPUT_DATASET_PATH, index=False)
            
            # Prepare fresh training data
            df_clean = df_master.dropna(subset=FEATURES + ['peak_LD'])
            X_train = df_clean[FEATURES].values
            y_train = df_clean['peak_LD'].values
            
            # Retrain model
            xgb_model.fit(X_train, y_train)
            
            # Save updated model
            pkg['model'] = xgb_model
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump(pkg, f)
            print(f"  Model retrained on {len(X_train)} samples and saved.")

        # ========================================
        # GA REPRODUCTION
        # ========================================
        next_population = []
        # Elitism: keep top 10%
        elites = int(POP_SIZE * 0.1)
        next_population.extend(population[:elites])
        
        while len(next_population) < POP_SIZE:
            # Tournament selection
            idx1, idx2 = np.random.choice(POP_SIZE, 2, replace=False)
            p1 = population[idx1] if fitness_scores[idx1] > fitness_scores[idx2] else population[idx2]
            
            idx1, idx2 = np.random.choice(POP_SIZE, 2, replace=False)
            p2 = population[idx1] if fitness_scores[idx1] > fitness_scores[idx2] else population[idx2]
            
            c1, c2 = crossover(p1, p2)
            next_population.append(mutate(c1))
            if len(next_population) < POP_SIZE:
                next_population.append(mutate(c2))
                
        population = np.array(next_population)
        
    print("\n=" * 60)
    print("OPTIMIZATION COMPLETE")
    print(f"Best airfoils saved in: {NEW_AIRFOILS_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
