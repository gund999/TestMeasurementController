# USB-GPIB Instrument Controller

![Fully Built Robot](Images/GPIB_IC_GUI.png)

This project provides a graphical user interface (GUI) built with Python's Tkinter library for controlling various laboratory instruments, including those that use GPIB communication via a Prologix USB-to-GPIB adapter connected over a serial (COM) port. It allows users to select a variety of instruments, send specific commands, and log measurement data. 

## Current Features

The application offers a robust set of functionalities designed for efficient instrument interaction and data monitoring:

### 1. Instrument Control

* **Instrument Selection:** Easily choose from a predefined list of supported instruments.

* **Subcommands:** The available subcommands and their associated parameters update based on the selected instrument.

* **Supported Instruments and Commands:**

  #### HP 3478A Multimeter (In Progress)

  * **HOME Command** (`H0`): Resets the multimeter to default settings.

  * **Measure DC Voltage** (`H1`)

  * **Measure AC Volts** (`H2`)

  * **Measure 2-Wire Ohms** (`H3`)

  * **Measure 4-Wire Ohms** (`H4`)

  * **Measure DC Current** (`H5`)

  * **Measure AC Current** (`H6`)

  * **Measure Extended Ohms** (`H7`)

  * **Clear Display** (`D1`): Clears the multimeter's display.

  * **Write to Display** (`wrt 723 D2{text}`): Sends custom text to the multimeter's display.

  * **Read IDN (WIP)**: Reads the instrument's identification string.
  
  #### Power Supply (WIP)

  * **Set Voltage**

  * **Set Current Limit**

  * **Output ON/OFF**

  * **Measure Output**

  #### Chroma DC Load (WIP)

  * **Set Current**

  * **Set Voltage**

  * **Load ON/OFF**

  * **Measure Input**

### 2. Serial Communication

* **COM Port Management:**

  * Detects and lists all available COM ports on your system.

  * Displays COM port availability and offers customizable configuration of the baud rate.

  * Includes a visual status indicator (red/green light).

* **Command Sending:**

  * Effortlessly send commands generated via the instrument controls.

  * Utilize a dedicated input bar to send arbitrary, custom serial commands.

* **Real-time Logging:**

  * A "Debug Log" captures detailed application events and sent commands in real-time. It also provides an interface for testing ASCII input via the COM port.

  * A "Receive Log" displays incoming data from the serial port as an output.

  * Both logs feature intelligent **auto-scrolling** that automatically pauses when you manually scroll up, allowing uninterrupted review of historical data while handling new packets.

### 3. Data Visualization (Plotting)

* **Real-time Plotting (WIP):** Integrates the Matplotlib library to display live measurement data over time.

* **Supported Plotting Modes (In Progress):** Automatically plots data received for key measurements from the **HP 3478A Multimeter**, including:

  * "Measure DC Voltage"

  * "Measure AC Volts"

  * "Measure DC Current"

  * "Measure AC Current"

* **Dynamic Labels (In Progress):** The Y-axis label and plot title dynamically update to reflect the specific type of measurement being visualized.

* **Dynamic Axis Scaling (In Progress):** Plot axes automatically adjust to accommodate incoming data ranges, ensuring optimal visibility.

* **Clear Plot (In Progress):** A convenient button to instantly clear all plotted data and reset the graph for a new session.

### 4. User Interface (GUI)

* **Intuitive Layout:** The application features a well-organized and user-friendly interface with distinct sections for instrument controls, serial communication, and data logs/plots.

* **Configuration Management (WIP):** "Save Config" and "Load Config" buttons are present, currently offering simulated functionality for future implementation.

## Features To Be Added

* **Multiple Instrument Functionality:** Support simultaneous data logging from multiple instruments, including both district models and multiple units of the same model.

* **Actual Configuration Saving/Loading:** Implement robust functionality to save and load instrument configurations and application settings to persistent files (e.g., JSON, YAML).

* **Data Export:** Add options to easily export received raw data and generated plot data to common formats like CSV, for further analysis.

* **Advanced Plotting Features:**

  * Support for plotting data from multiple measurement channels simultaneously on the same graph.

  * Customizable plots, including colors, line styles, and markers for data from several instruments.

  * Enhanced interactive tools for zooming, panning, and detailed data inspection beyond the default Matplotlib toolbar.


* **Input Validation:** Implement more robust validation for all user inputs, ensuring data integrity and preventing common errors (e.g., ensuring numeric values where expected).

* **Automated Measurement Sequences:** Develop a powerful feature to define, save, and execute automated sequences of commands and measurements, ideal for repetitive testing.

* **Error Handling Improvements:** Expand error reporting with more specific details and more robustness to the addition of other instruments and subcommands.

* **GPIB Integration:** Explore and integrate actual GPIB communication capabilities alongside the existing serial interface, if a physical GPIB hardware is available.

* **User Preferences (WIP):** Allow users to save and load application preferences such as data logging settings, display settings, and default COM port settings.