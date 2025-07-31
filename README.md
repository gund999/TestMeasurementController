GPIB Instrument Control GUI (Tkinter)
This project provides a graphical user interface (GUI) built with Python's Tkinter library for controlling various laboratory instruments via serial (COM) port communication. It allows users to select instruments, send specific commands, and visualize real-time measurement data.

Current Features
The application currently offers a robust set of functionalities designed for efficient instrument interaction and data monitoring:

1. Instrument Control
Instrument Selection: Easily choose from a predefined list of supported instruments.

Dynamic Subcommands: The available subcommands and their associated parameters automatically update based on the instrument currently selected, streamlining command generation.

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

HOME Command (H0): Resets the multimeter to default settings.

Measure DC Voltage (H1)

Measure AC Volts (H2)

Measure 2-Wire Ohms (H3)

Measure 4-Wire Ohms (H4)

Measure DC Current (H5)

Measure AC Current (H6)

Measure Extended Ohms (H7)

Clear Display (D1): Clears the multimeter's display.

Write to Display (wrt 723 D2{text}): Sends custom text to the multimeter's display.

Read IDN: Reads the instrument's identification string.

2. Serial Communication
COM Port Management:

Automatically detects and lists all available COM ports on your system.

Allows seamless selection of a COM port and configuration of the baud rate.

Provides clear Connect and Disconnect functionality with a visual status indicator (red/green light).

Command Sending:

Effortlessly send commands generated via the instrument controls.

Utilize a dedicated input bar to send arbitrary, custom serial commands.

Real-time Logging:

A "Debug Log" provides detailed application events and records all sent commands.

A "Receive Log" displays incoming data from the serial port.

Both logs feature intelligent auto-scrolling that automatically pauses when you manually scroll up, allowing uninterrupted review of historical data.

3. Data Visualization (Plotting)
Real-time Plotting: Integrates the powerful Matplotlib library to display live measurement data over time.

Supported Plotting Modes: Automatically plots data received for key measurements from the HP 3478A Multimeter, including:

"Measure DC Voltage"

"Measure AC Volts"

"Measure DC Current"

"Measure AC Current"

Dynamic Labels: The Y-axis label and plot title dynamically update to reflect the specific type of measurement being visualized.

Dynamic Axis Scaling: Plot axes automatically adjust to accommodate incoming data ranges, ensuring optimal visibility.

Clear Plot: A convenient button to instantly clear all plotted data and reset the graph for a new session.

4. User Interface (GUI)
Intuitive Layout: The application features a well-organized and user-friendly interface with distinct sections for instrument controls, serial communication, and data logs/plots.

Responsive Design: The GUI layout seamlessly adapts to window resizing, maintaining usability across different screen dimensions.

Placeholder Text: All input fields include helpful grey placeholder text that vanishes upon focus and reappears if the field is left empty, guiding user input.

Configuration Management (Simulated): "Save Config" and "Load Config" buttons are present, currently offering simulated functionality for future implementation.

To Be Added Features (Future Enhancements)
Actual Configuration Saving/Loading: Implement robust functionality to save and load instrument configurations and application settings to persistent files (e.g., JSON, YAML).

Data Export: Add options to easily export received raw data and generated plot data to common formats like CSV, enabling further analysis.

Advanced Plotting Features:

Support for plotting data from multiple measurement channels simultaneously on the same graph.

Customizable plot aesthetics, including colors, line styles, and markers.

Enhanced interactive tools for zooming, panning, and detailed data inspection beyond the default Matplotlib toolbar.

Ability to save plots as high-resolution image files.

Input Validation: Implement more robust validation for all user inputs, ensuring data integrity and preventing common errors (e.g., ensuring numeric values where expected).

Automated Measurement Sequences: Develop a powerful feature to define, save, and execute automated sequences of commands and measurements, ideal for repetitive testing.

Error Handling Improvements: Enhance error reporting with more specific details and provide clearer user guidance for serial communication issues and invalid instrument responses.

GPIB Integration: Explore and integrate actual GPIB communication capabilities alongside the existing serial interface, if a physical GPIB hardware is available.

Unit Conversion/Display: Automatically handle and display appropriate units for measurements based on the selected instrument and subcommand, improving data readability.

User Preferences: Allow users to save and load GUI preferences such as window size, log display settings, and default COM port settings.

Additional Instrument Support: Continuously expand the instrument_data dictionary to include a wider range of common laboratory instruments and their commands.