GPIB Instrument Control GUI (Tkinter)
This project provides a graphical user interface (GUI) built with Python's Tkinter library for controlling various laboratory instruments via serial (COM) port communication. It allows users to select instruments, send specific commands, and visualize real-time measurement data.

Current Features
The application currently offers the following functionalities:

1. Instrument Control
Instrument Selection: Choose from a predefined list of instruments.

Dynamic Subcommands: Subcommands and their associated parameters dynamically update based on the selected instrument.

Supported Instruments and Commands:

Power Supply:

Set Voltage

Set Current Limit

Output ON/OFF

Measure Output

Chroma DC Load:

Set Current

Set Voltage

Load ON/OFF

Measure Input

HP 3478A Multimeter:

HOME Command (H0)

Measure DC Voltage (H1)

Measure AC Volts (H2)

Measure 2-Wire Ohms (H3)

Measure 4-Wire Ohms (H4)

Measure DC Current (H5)

Measure AC Current (H6)

Measure Extended Ohms (H7)

Clear Display (D1)

Write to Display (wrt 723 D2{text})

Read IDN

2. Serial Communication
COM Port Management:

Automatically lists available COM ports.

Allows selection of a COM port and setting of baud rate.

Connect and disconnect functionality with visual status indicator.

Command Sending:

Send commands generated from instrument controls.

Send arbitrary serial commands via a dedicated input bar.

Real-time Logging:

Separate "Debug Log" for application events and sent commands.

"Receive Log" for displaying data received from the serial port.

Both logs feature auto-scrolling that can be paused by manual scrolling.

3. Data Visualization (Plotting)
Real-time Plotting: Integrates Matplotlib to display real-time measurements over time.

Supported Plotting Modes: Automatically plots data for "Measure DC Voltage", "Measure AC Volts", "Measure DC Current", and "Measure AC Current" commands from the HP 3478A Multimeter.

Dynamic Labels: The Y-axis label and plot title update to reflect the type of measurement being plotted.

Dynamic Axis Scaling: Plot axes automatically adjust to fit the incoming data.

Clear Plot: A dedicated button to clear all plotted data and reset the graph.

4. User Interface (GUI)
Intuitive Layout: Organized interface with distinct sections for instrument controls, serial communication, and logs.

Responsive Design: The layout adapts to window resizing.

Placeholder Text: Input fields feature grey placeholder text that disappears on focus and reappears if the field is left empty.

Configuration Management (Simulated): "Save Config" and "Load Config" buttons are present, currently providing simulated functionality.

To Be Added Features (Future Enhancements)
Actual Configuration Saving/Loading: Implement functionality to save and load instrument configurations and settings to a file (e.g., JSON, YAML).

Data Export: Add options to export received data and plotted data to common formats like CSV.

Advanced Plotting Features:

Support for multiple measurement channels on the same plot.

Customizable plot aesthetics (colors, line styles).

Zoom, pan, and interactive data inspection tools beyond the default Matplotlib toolbar.

Ability to save plots as images.

Input Validation: Implement more robust validation for parameter inputs (e.g., ensuring numeric values where expected).

Automated Measurement Sequences: Develop a feature to define and run automated sequences of commands and measurements.

Error Handling Improvements: More specific error handling and user feedback for serial communication issues and invalid instrument responses.

GPIB Integration: If a physical GPIB interface is available, integrate actual GPIB communication capabilities alongside serial.

Unit Conversion/Display: Automatically handle and display units for measurements based on the instrument and subcommand.

User Preferences: Allow users to save GUI preferences like window size, log display settings, etc.

Additional Instrument Support: Expand the instrument_data to include more common lab instruments.