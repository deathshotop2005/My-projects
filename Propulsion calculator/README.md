# Propulsion Calculator

## Overview
Propulsion Calculator is a Python-based graphical user interface (GUI) application designed to compute key performance parameters for a solid rocket motor propulsion system. Built with `tkinter`, it provides a simple interface to input physical and thermodynamic properties, instantly calculating critical outputs such as Thrust, Expansion Ratio, and Throat Area.

## Features
- **User-Friendly GUI**: Easy-to-use interface for entering propulsion system parameters.
- **Accurate Calculations**: Computes critical parameters including:
  - Burn Area to Throat Area Ratio (Kn)
  - Thrust Coefficient (Cf)
  - Throat Area
  - Thrust Produced (F)
  - Expansion Ratio (ε)
- **Calculation History Logging**: Automatically saves calculation iterations into an `iteration_history.csv` (Excel-compatible) file for future analysis.
- **Formula Reference**: Displays a built-in image of the formulas used for the calculations for quick verification.
- **Standalone Capability**: Includes necessary files to be built into a standalone executable using tools like PyInstaller.

## Requirements
- Python 3.x
- `tkinter` (Standard GUI library for Python, usually included by default)

## Getting Started

### Running the Application
1. Ensure Python 3 is installed on your system.
2. Clone or download this repository folder.
3. Open a terminal or command prompt in the `Propulsion Calculator` directory.
4. Run the application:
   ```bash
   python calculator.py
   ```

### Usage Instructions
1. Input your specific values for parameters like Chamber Pressure, Core Length, Core Diameter, etc.
2. Click the **Calculate** button.
3. The results will populate in the 'Results' section and will be appended to `iteration_history.csv`.

## Repository Structure
- `calculator.py`: Main application code.
- `formulas.png`: Visual reference of mathematical formulas used.
- `iteration_history.csv`: Auto-generated file storing previous calculation data.
- `calculator.spec`, `build/`, `dist/`: PyInstaller files for packaging the application.
