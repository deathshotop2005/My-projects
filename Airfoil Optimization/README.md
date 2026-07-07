# Honeywell AeroForge: Airfoil Optimization and Analysis

This repository contains tools and scripts for the automated screening, machine learning-driven surrogate modeling, and active learning-based optimization of airfoils, utilizing XFOIL for aerodynamic evaluations. This project was developed as part of the RVCE AeroForge Design-A-Thon.

## Overview

The project provides an end-to-end pipeline to:
1. **Screen Airfoils**: Automatically run XFOIL on large datasets of airfoil coordinates to compute aerodynamic polars (Lift, Drag, L/D ratios).
2. **Surrogate Modeling**: Train machine learning models on XFOIL data to rapidly predict aerodynamic performance without expensive computational simulations.
3. **Optimization**: Use Genetic Algorithms (GA) combined with active learning to generate and optimize new airfoil shapes (using CST parameterization) that maximize desired aerodynamic properties (e.g., maximum L/D).
4. **Web Interface**: A web application (`app.py`) to easily interact with the underlying optimization pipeline and visualize results.

## Directory Structure

- **`Streamlined process/`**: The core workspace for the project.
  - **`Scripts/`**: Contains all Python scripts for ML training, GA optimization, CST generation, and XFOIL interfacing.
  - **`Data/`**: Stores coordinate files (`.dat`), generated datasets (`.csv`), ANSYS simulation data, and trained ML surrogate models (`.pkl`).
  - **`Results/`**: Contains output plots (`.png`), optimized airfoil geometries, and text-based analysis reports.
  - **`Docs/`**: Project documentation, problem statements, and presentation slides.
  - **`app.py`, `templates/`, `static/`**: The web application frontend and backend.
- **`xfoil.exe`, `pplot.exe`, `pxplot.exe`**: Executables for XFOIL required by the automated scripts for aerodynamic analysis.

## Prerequisites

- **Python 3.8+**
- **Required Libraries**: `numpy`, `pandas`, `matplotlib`, `scikit-learn`, `flask` (for the web app).
- **Operating System**: Windows (due to `.exe` XFOIL binaries). 

*Note: Ensure that the Python scripts have sufficient permissions to execute `xfoil.exe` as a subprocess.*

## Usage

### 1. Running the Web Application
To start the interactive interface, navigate to the `Streamlined process` folder and run the Flask application:
```bash
cd "Streamlined process"
python app.py
```

### 2. Running Individual Scripts
You can also run individual steps of the pipeline from the `Scripts` directory:
- **Optimization**: `python "Streamlined process/Scripts/ga_active_learning.py"`
- **Screening**: `python "Streamlined process/Scripts/screen_airfoils.py"`
- **Visualization**: `python "Streamlined process/Scripts/visualize_results.py"`

## Notes

- **XFOIL Subprocesses**: The Python scripts are configured to dynamically generate temporary XFOIL input files, run the `xfoil.exe` binary located in the root directory, and parse the resulting polar dumps. 
