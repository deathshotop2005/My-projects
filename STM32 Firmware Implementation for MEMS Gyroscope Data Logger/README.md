# STM32 Firmware Implementation for MEMS Gyroscope Data Logger

## Overview
This project focuses on the development of a real-time orientation measurement, visualization, and data logging system. It uses the **MPU6050** Inertial Measurement Unit (IMU) interfaced with an **STM32F446RE** microcontroller.

The system computes:
- **Pitch and Roll angles:** From accelerometer data using trigonometric methods.
- **Yaw angle:** Estimated by integrating gyroscope measurements over time.

Orientation data is transmitted to a host computer through UART communication at a baud rate of 115200. A Python-based application on the host performs initial sensor calibration, applies offset correction, provides live graphical visualization of pitch, roll, and yaw angles, and logs time-stamped data to a CSV file.

## Features
- **Real-Time Orientation Measurement:** Computes and outputs pitch, roll, and yaw angles in real-time.
- **Continuous Data Processing:** Processes raw accelerometer and gyroscope outputs onboard using mathematical models for attitude estimation.
- **Serial Data Logging:** Transmits orientation data to a host system via UART for monitoring, visualization, and storage.
- **Dual-Path Data Processing:** Handles both true physical path (raw values) and corrected measurement path (offset calibration applied).
- **Python Visualization:** Live plots of orientation parameters using Matplotlib and real-time CSV data logging.

## Hardware Components
1. **STM32F446RE Microcontroller (Controller Unit):**
   - Central processing and control unit.
   - Initializes I2C, UART, GPIO, and system clock.
   - Computes orientation and transmits data over UART.
2. **MPU6050 MEMS IMU:**
   - Primary sensing element.
   - 3-axis accelerometer and 3-axis gyroscope.
   - Communicates with the STM32 via the I2C protocol.
3. **USB to UART Interface:**
   - ST-Link Virtual COM Port for PC communication.

## Software Architecture
### 1. Embedded Firmware (STM32 HAL-Based C Code)
- Configures MPU6050 registers (±2g accelerometer range, ±250°/s gyroscope range).
- Reads raw sensor data at fixed intervals (200 ms sampling).
- Computes Pitch and Roll from accelerometer data.
- Computes Yaw by integrating gyroscope angular velocity.
- Converts floating-point values to fixed-point for efficient serial transmission.
- Transmits formatted string via UART: `"Pitch:%d.%02d Roll:%d.%02d Yaw:%d.%02d\r\n"`.

### 2. Python Data Logger and Visualization
- **Calibration Phase:** Starts with a 6-second static calibration period to compute mean offset values for Pitch, Roll, and Yaw to compensate for sensor bias.
- **Real-Time Plot Display:** Uses a sliding window of the last 200 samples to display real-time live plots of Pitch, Roll, and Yaw with distinct color coding.
- **CSV Data Storage:** Logs time-stamped corrected orientation data into a CSV file for post-processing and offline analysis.

## Hardware Connections (I2C)
| MPU6050 Pin | STM32F446RE Pin | Description |
| :--- | :--- | :--- |
| **VCC** | 3.3V | Power Supply |
| **GND** | GND | Common Ground |
| **SCL** | PB8 | I2C Clock |
| **SDA** | PB9 | I2C Data |

## Performance Observations
- **Pitch and Roll:** Show good stability under static and low-dynamic conditions, responding accurately to slow tilting motions. Temporary deviations can occur during rapid movements or vibrations due to the accelerometer-only approach.
- **Yaw:** Tracks relative heading changes smoothly. However, since it relies on integrating gyroscope data without a magnetometer or sensor fusion, it expects unavoidable drift over time due to gyroscope bias.

## Future Improvements
To provide drift-free and high-accuracy 3-axis orientation estimation, the system could be enhanced by:
- Implementing sensor fusion algorithms such as Complementary or Kalman filtering.
- Including a magnetometer to correct yaw drift.
