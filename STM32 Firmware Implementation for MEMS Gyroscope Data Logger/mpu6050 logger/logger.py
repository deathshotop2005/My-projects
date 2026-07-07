import serial
import serial.tools.list_ports
import time
import csv
import re
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# --- CONFIGURATION ---
BAUD_RATE = 115200
LOG_FILE = "mpu6050_log.csv"

# Regex to parse your STM32 output format "P: 0.00 R: 0.00 Y: 0.00"
pattern = re.compile(r"P:\s*(-?[\d.]+)\s*R:\s*(-?[\d.]+)\s*Y:\s*(-?[\d.]+)")

def find_stm32_port():
    """Automatically finds the STLink Virtual COM port."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "STMicroelectronics" in port.description or "STLink" in port.description:
            return port.device
    return None

def get_data(ser):
    """Reads and parses one line of sensor data."""
    try:
        line = ser.readline().decode('utf-8').strip()
        match = pattern.search(line)
        if match:
            return [float(x) for x in match.groups()]
    except:
        pass
    return None

def calibrate_system(ser):
    """Calibrates for 6 seconds and sets the zero-reference plane."""
    while True:
        print("\n[STEP 1] Calibrating... Keep the sensor still on the reference plane for 6 seconds.")
        offsets = [0.0, 0.0, 0.0]
        count = 0
        start = time.time()
        
        while time.time() - start < 6:
            val = get_data(ser)
            if val:
                offsets = [offsets[i] + val[i] for i in range(3)]
                count += 1
        
        if count > 0:
            avg_offsets = [x / count for x in offsets]
            print(f"Detected Orientation: P:{avg_offsets[0]:.2f} R:{avg_offsets[1]:.2f} Y:{avg_offsets[2]:.2f}")
            choice = input("Is this the reference plane? (yes/no): ").lower().strip()
            if choice == 'yes':
                return avg_offsets
        print("Recalibrating...")

def main():
    port = find_stm32_port()
    if not port:
        print("Error: Could not find STLink Virtual COM Port. Check USB connection.")
        return

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        print(f"Connected to {port}")
    except serial.SerialException as e:
        print(f"Error: Could not open port {port}. Is the Serial Monitor open elsewhere?")
        return

    # 1. Calibration phase
    offsets = calibrate_system(ser)
    
    # 2. Plotting preference
    show_plot = input("Do you want to see a live plot? (yes/no): ").lower().strip() == 'yes'

    # 3. Logging Setup
    csv_f = open(LOG_FILE, 'w', newline='')
    writer = csv.writer(csv_f)
    writer.writerow(["Time(s)", "Pitch", "Roll", "Yaw"])

    # Live Data containers
    t_data, p_data, r_data, y_data = [], [], [], []
    start_t = time.time()

    print("\n--- Logging Started. Press Ctrl+C to Exit ---")

    def update(frame):
        val = get_data(ser)
        if val:
            now = time.time() - start_t
            # Apply reference plane zeroing
            p, r, y = [val[i] - offsets[i] for i in range(3)]
            
            writer.writerow([round(now, 2), round(p, 2), round(r, 2), round(y, 2)])
            print(f"T: {now:5.2f}s | P: {p:7.2f} | R: {r:7.2f} | Y: {y:7.2f}")

            if show_plot:
                t_data.append(now); p_data.append(p); r_data.append(r); y_data.append(y)
                if len(t_data) > 100: # Limit plot to 100 points
                    t_data.pop(0); p_data.pop(0); r_data.pop(0); y_data.pop(0)
                ax.clear()
                ax.plot(t_data, p_data, label='Pitch'); ax.plot(t_data, r_data, label='Roll'); ax.plot(t_data, y_data, label='Yaw')
                ax.legend(loc='upper right'); ax.set_ylabel("Degrees"); ax.set_xlabel("Time (s)")

    if show_plot:
        fig, ax = plt.subplots()
        ani = FuncAnimation(fig, update, interval=20, cache_frame_data=False)
        plt.show()
    else:
        try:
            while True:
                update(None)
        except KeyboardInterrupt:
            print("\nExiting...")

    csv_f.close()
    ser.close()

if __name__ == "__main__":
    main()