import tkinter as tk
from tkinter import ttk, filedialog
from tkinter import font as tkFont
from tkinter import messagebox
import datetime
import time # For simulating delays
import serial # Import the pyserial library
import serial.tools.list_ports # To list available COM ports
import threading # For running serial read in a separate thread
import json # For saving and loading configuration
import csv # To save data to a CSV file

# Import matplotlib for plotting
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# Helper function to add placeholder text to ttk.Entry widgets
def add_placeholder_to_entry(entry, placeholder_text):
    """
    Adds placeholder text functionality to a ttk.Entry widget.
    The placeholder disappears on focus and reappears if the field is left empty.
    """
    # Set initial text and style
    entry.delete(0, tk.END) # Clear existing text
    entry.insert(0, placeholder_text)
    entry.config(style='Placeholder.TEntry') # Apply placeholder style

    def on_focus_in(event):
        """Removes the placeholder text when the entry widget is clicked."""
        if entry.get() == placeholder_text and entry.cget('style') == 'Placeholder.TEntry':
            entry.delete(0, tk.END)
            entry.config(style='TEntry') # Switch to default style for active text

    def on_focus_out(event):
        """Adds the placeholder text back if the entry is left empty."""
        if not entry.get():
            entry.insert(0, placeholder_text)
            entry.config(style='Placeholder.TEntry') # Switch back to placeholder style

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

# Helper function to add placeholder text to tk.Text widgets
def add_placeholder_to_text(text_widget, placeholder_text):
    """
    Adds placeholder text functionality to a tk.Text widget.
    The placeholder is grayed out and disappears on focus or key press.
    """
    text_widget.tag_configure("placeholder", foreground="grey")
    # Store the placeholder text directly on the widget for easy access
    text_widget._placeholder_text = placeholder_text
    text_widget._has_placeholder = False # Internal state to track if placeholder is active

    def show_placeholder_internal():
        """Displays the placeholder text if the widget is empty."""
        if not text_widget.get("1.0", tk.END).strip() and not text_widget._has_placeholder:
            text_widget.delete("1.0", tk.END) # Clear to ensure no stray characters
            text_widget.insert("1.0", text_widget._placeholder_text, "placeholder")
            text_widget.config(fg="grey")
            text_widget._has_placeholder = True

    def hide_placeholder_internal(event=None): # event=None for manual calls
        """Hides the placeholder text."""
        if text_widget._has_placeholder:
            text_widget.delete("1.0", tk.END)
            text_widget.tag_remove("placeholder", "1.0", tk.END)
            text_widget.config(fg="black")
            text_widget._has_placeholder = False

    def check_placeholder_internal(event):
        """Checks on focus out if the placeholder should be shown again."""
        if not text_widget.get("1.0", tk.END).strip():
            show_placeholder_internal()
        else:
            text_widget.config(fg="black") # Ensure it stays black if text is there

    # Bindings
    text_widget.bind("<FocusIn>", hide_placeholder_internal)
    text_widget.bind("<FocusOut>", check_placeholder_internal)
    # Crucial: Bind to <Key> to remove placeholder immediately on first type
    text_widget.bind("<Key>", hide_placeholder_internal)

    # Initial display of placeholder
    show_placeholder_internal()

    # Return the internal show/hide functions for external control
    return show_placeholder_internal, hide_placeholder_internal


class GPIBApp:
    """
    Main application class for the GPIB Instrument Control GUI.
    Handles all UI elements and communication logic.
    """
    def __init__(self, master):
        self.master = master
        master.title("GPIB Instrument Control")
        master.geometry("1000x700") # Set a default window size
        master.resizable(True, True) # Allow window resizing

        # Configure a custom font for better aesthetics
        self.default_font = tkFont.Font(family="Helvetica", size=10)
        self.master.option_add("*Font", self.default_font)

        # Style for ttk widgets (Combobox, Frame, etc.)
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0')
        self.style.configure('TButton', font=self.default_font, padding=5)
        self.style.configure('TCombobox', font=self.default_font, padding=5)

        # Define a style for placeholder text in Entry widgets
        self.style.configure('Placeholder.TEntry', foreground='grey')
        self.style.configure('TEntry', foreground='black') # Default for active text

        # Serial port instance and thread control
        self.serial_port = None
        self.serial_read_thread = None
        self.stop_thread = threading.Event() # Event to signal the thread to stop
        self._read_buffer = b'' # Buffer for handling partial serial messages

        # Autoscroll flags for log windows
        self.debug_autoscroll_enabled = True
        self.receive_autoscroll_enabled = True

        # Set up a protocol handler for when the window is closed
        self.master.protocol("WM_DELETE_WINDOW", self._on_closing)

        # --- Instrument and Subcommand Data ---
        # Defines available instruments, their subcommands, and associated parameter labels/command prefixes
        self.instrument_data = {
            "Power Supply": {
                "subcommands": {
                    "Set Voltage": {"command": "VSET", "params": ["Voltage (V)", "Channel"]},
                    "Set Current Limit": {"command": "CSET", "params": ["Current (A)", "Channel"]},
                    "Output ON/OFF": {"command": "OUT", "params": ["State (ON/OFF)"]},
                    "Measure Output": {"command": "MEAS", "params": []}
                },
                "command_prefix": "PS:"
            },
            "Chroma DC Load": {
                "subcommands": {
                    "Set Current": {"command": "CSET", "params": ["Current (A)", "Mode (CC/CR/CP)"]},
                    "Set Voltage": {"command": "VSET", "params": ["Voltage (V)"]},
                    "Load ON/OFF": {"command": "LOAD", "params": ["State (ON/OFF)"]},
                    "Measure Input": {"command": "MEAS", "params": []}
                },
                "command_prefix": "LOAD:"
            },
            "HP 3478A Multimeter": {
                "subcommands": {
                    # Preset Commands
                    "Preset: H0 - Home Command": {"command": "H0", "params": []},
                    "Preset: H1 - Measure DC Volts": {"command": "H1", "params": []},
                    "Preset: H2 - Measure AC Volts": {"command": "H2", "params": []},
                    "Preset: H3 - Measure 2-Wire Ohms": {"command": "H3", "params": []},
                    "Preset: H4 - Measure 4-Wire Ohms": {"command": "H4", "params": []},
                    "Preset: H5 - Measure DC Current": {"command": "H5", "params": []},
                    "Preset: H6 - Measure AC Current": {"command": "H6", "params": []},
                    "Preset: H7 - Measure Extended Ohms": {"command": "H7", "params": []},
                    
                    # Measurement Function Commands
                    "Measurement Function: F1 - DC Volts Function": {"command": "F1", "params": []},
                    "Measurement Function: F2 - AC Volts Function": {"command": "F2", "params": []},
                    "Measurement Function: F3 - 2-Wire Ohms Function": {"command": "F3", "params": []},
                    "Measurement Function: F4 - 4-Wire Ohms Function": {"command": "F4", "params": []},
                    "Measurement Function: F5 - DC Current Function": {"command": "F5", "params": []},
                    "Measurement Function: F6 - AC Current Function": {"command": "F6", "params": []},
                    "Measurement Function: F7 - Extended Ohms Function": {"command": "F7", "params": []},

                    # Range Commands
                    "Range: R-1 - 30mV DC Range": {"command": "R-1", "params": []},
                    "Range: R-2 - 300mV/300mA Range": {"command": "R-2", "params": []},
                    "Range: R0 - 3V AC or DC/3A AC or DC Range": {"command": "R0", "params": []},
                    "Range: R1 - 30V AC or DC/30 ohm Range": {"command": "R1", "params": []},
                    "Range: R2 - 300V DC or AC/300 ohm Range": {"command": "R2", "params": []},
                    "Range: R3 - 3K ohm Range": {"command": "R3", "params": []},
                    "Range: R4 - 30K ohm Range": {"command": "R4", "params": []},
                    "Range: R5 - 300K ohm Range": {"command": "R5", "params": []},
                    "Range: R6 - 3M ohm Range": {"command": "R6", "params": []},
                    "Range: R7 - 30M ohm Range": {"command": "R7", "params": []},
                    "Range: RA - Autoranging": {"command": "RA", "params": []},

                    # Display Commands
                    "Display: D1 - Return to Normal Display": {"command": "D1", "params": []},
                    "Display: D2text - Write to Display": {"command": "D2", "params": ["Enter text (64 chars) here"]},
                    "Display: D3text - Write to Display (30ms)": {"command": "D3", "params": ["Enter text (64 chars) here"]},
                    "Display: N3 - 3 1/2 Digit Display": {"command": "N3", "params": []},
                    "Display: N4 - 4 1/2 Digit Display": {"command": "N4", "params": []},
                    "Display: N5 - 5 1/2 Digit Display": {"command": "N5", "params": []},
                    
                    # Trigger Commands
                    "Trigger: T1 - Internal Trigger": {"command": "T1", "params": []},
                    "Trigger: T2 - External Trigger": {"command": "T2", "params": []},
                    "Trigger: T3 - Single Trigger": {"command": "T3", "params": []},
                    "Trigger: T4 - Trigger Hold": {"command": "T4", "params": []},
                    "Trigger: T5 - Fast Trigger": {"command": "T5", "params": []},

                    # Autozero
                    "Autozero: Z0 - Autozero off": {"command": "Z0", "params": []},
                    "Autozero: Z1 - Autozero on": {"command": "Z1", "params": []},

                    # Other Commands
                    "Other: B - Read Binary Status": {"command": "B", "params": []},
                    "Other: E - Read Error Register": {"command": "E", "params": []},
                    "Other: K - Clear Serial Poll Register": {"command": "K", "params": []},
                    "Other: Mx - Set SRQ Mask": {"command": "M", "params": ["SRQ Mask (2 hex digits)"]},
                    "Other: S - Return Front/Rear Switch Position": {"command": "S", "params": []},
                    "Other: C - Calibrate": {"command": "C", "params": []}
                },
                "command_prefix": "" # No global prefix for this instrument, commands are standalone
            }
        }

        # Main frame for the entire application, using grid for layout
        self.main_frame = ttk.Frame(master, padding="10 10 10 10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Configure grid weights for responsive layout
        self.main_frame.grid_rowconfigure(0, weight=1) # Top row (graph & controls)
        self.main_frame.grid_rowconfigure(1, weight=0) # Axis buttons row (now part of graph frame)
        self.main_frame.grid_rowconfigure(2, weight=1) # Log areas row
        self.main_frame.grid_rowconfigure(3, weight=0) # New row for serial send bar
        self.main_frame.grid_columnconfigure(0, weight=1) # Left column (graph)
        self.main_frame.grid_columnconfigure(1, weight=1) # Right column (controls)

        # --- Left Column: Graph and Axis Controls (now includes Matplotlib) ---
        self.graph_frame = ttk.LabelFrame(self.main_frame, text="Graph Display", padding="10 10 10 10")
        self.graph_frame.grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsew")
        self.graph_frame.grid_rowconfigure(0, weight=1) # Canvas row
        self.graph_frame.grid_rowconfigure(1, weight=0) # Toolbar row
        self.graph_frame.grid_rowconfigure(2, weight=0) # Axis controls row
        self.graph_frame.grid_columnconfigure(0, weight=1)

        self.graph_title_label = ttk.Label(self.graph_frame, text="Real-time Measurement Plot", font=tkFont.Font(family="Helvetica", size=12, weight="bold"))
        self.graph_title_label.grid(row=0, column=0, columnspan=3, pady=(0, 5), sticky="n")

        # Matplotlib Figure and Axes
        self.fig, self.ax = plt.subplots(figsize=(5, 4), layout='constrained')
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value") # Placeholder, as per user request
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'b-') # Initial empty line for plotting
        self.fig.canvas.manager.set_window_title('') # Hide default matplotlib window title

        # Embed Matplotlib canvas in Tkinter
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas_plot_widget = self.canvas_plot.get_tk_widget()
        self.canvas_plot_widget.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0, 10))

        # Matplotlib Navigation Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas_plot, self.graph_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=1, column=0, columnspan=3, sticky="ew")

        # X/Y Axis and Save Data Controls (moved to a separate frame for better layout)
        self.plot_control_frame = ttk.Frame(self.graph_frame)
        self.plot_control_frame.grid(row=2, column=0, columnspan=3, pady=(5,0))

        self.x_axis_button = ttk.Button(self.plot_control_frame, text="X-Axis", command=self._handle_x_axis)
        self.x_axis_button.grid(row=0, column=0, padx=5)
        self.x_units_label = ttk.Label(self.plot_control_frame, text="Time (s)")
        self.x_units_label.grid(row=1, column=0)

        self.y_axis_button = ttk.Button(self.plot_control_frame, text="Y-Axis", command=self._handle_y_axis)
        self.y_axis_button.grid(row=0, column=1, padx=5)
        self.y_units_label = ttk.Label(self.plot_control_frame, text="Value") # Placeholder
        self.y_units_label.grid(row=1, column=1)

        self.clear_plot_button = ttk.Button(self.plot_control_frame, text="Clear Plot", command=self._clear_plot_data)
        self.clear_plot_button.grid(row=0, column=2, padx=5)
        
        # New "Save Data" button
        self.save_data_button = ttk.Button(self.plot_control_frame, text="Save Data", command=self._handle_save_data)
        self.save_data_button.grid(row=0, column=3, padx=5)

        # Plotting data storage
        self.plot_time_data = []
        self.plot_value_data = []
        self.start_time = time.time() # Reference for relative time plotting
        self.current_measurement_type = None # To track what kind of measurement is being plotted

        # --- Right Column: Instrument, Subcommand, Parameters ---
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Instrument Controls", padding="10 10 10 10")
        self.control_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.control_frame.grid_columnconfigure(0, weight=1) # Allow combobox to expand

        # Moved Save/Load Config Buttons to the top of this frame
        self.config_buttons_frame = ttk.Frame(self.control_frame)
        self.config_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        self.save_config_button = ttk.Button(self.config_buttons_frame, text="Save Config", command=self._handle_save_config)
        self.save_config_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.load_config_button = ttk.Button(self.config_buttons_frame, text="Load Config", command=self._handle_load_config)
        self.load_config_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Instrument Selection (now enabled)
        ttk.Label(self.control_frame, text="Instrument:").pack(anchor="w", pady=(0, 2)) # Changed label
        self.instrument_options = [""] + list(self.instrument_data.keys()) # Dynamically get instrument names
        self.selected_instrument = tk.StringVar(self.master)
        self.selected_instrument.set(self.instrument_options[0]) # default value
        self.instrument_combobox = ttk.Combobox(self.control_frame, textvariable=self.selected_instrument,
                                                values=self.instrument_options, state="readonly") # Enabled
        self.instrument_combobox.pack(fill=tk.X, pady=(0, 10))
        self.instrument_combobox.bind("<<ComboboxSelected>>", self._handle_instrument_change) # Binding re-added

        # --- Subcommand Selection (dynamic based on instrument) ---
        ttk.Label(self.control_frame, text="Select Subcommand:").pack(anchor="w", pady=(0, 2))
        self.subcommand_options = [""] # Will be populated dynamically
        self.selected_subcommand = tk.StringVar(self.master)
        self.selected_subcommand.set(self.subcommand_options[0]) # default value
        self.subcommand_combobox = ttk.Combobox(self.control_frame, textvariable=self.selected_subcommand,
                                                values=self.subcommand_options, state="readonly")
        self.subcommand_combobox.pack(fill=tk.X, pady=(0, 10))
        self.subcommand_combobox.bind("<<ComboboxSelected>>", self._handle_subcommand_change)

        # Sub Parameters (placeholders for now)
        self.param_frame = ttk.Frame(self.control_frame)
        self.param_frame.pack(fill=tk.X, pady=(0, 10))
        self.param_frame.grid_columnconfigure(0, weight=1)
        self.param_frame.grid_columnconfigure(1, weight=1)
        self.param_frame.grid_columnconfigure(2, weight=1)

        # Parameter Entry Widgets with initial generic placeholders
        self.param_a_entry = ttk.Entry(self.param_frame)
        self.param_a_entry.grid(row=0, column=0, padx=2, sticky="ew")
        self.param_b_entry = ttk.Entry(self.param_frame)
        self.param_b_entry.grid(row=0, column=1, padx=2, sticky="ew")
        self.param_c_entry = ttk.Entry(self.param_frame)
        self.param_c_entry.grid(row=0, column=2, padx=2, sticky="ew")

        # Store references to parameter entries for easy access
        self.param_entries = [self.param_a_entry, self.param_b_entry, self.param_c_entry]

        # Send Command Button
        self.send_command_button = ttk.Button(self.control_frame, text="Send Command", command=self._handle_send_command)
        self.send_command_button.pack(fill=tk.X, pady=(0, 10))

        # --- Serial Port Communication Section ---
        self.serial_comm_frame = ttk.LabelFrame(self.main_frame, text="Serial Port Communication", padding="10 10 10 10")
        self.serial_comm_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew") # Placed in row 1, column 1
        self.serial_comm_frame.grid_columnconfigure(0, weight=1) # Make port combobox expand

        # Serial Port Selection
        serial_port_selection_frame = ttk.Frame(self.serial_comm_frame)
        serial_port_selection_frame.pack(fill=tk.X, pady=(0, 5))
        serial_port_selection_frame.grid_columnconfigure(0, weight=1) # Combobox takes most space

        ttk.Label(serial_port_selection_frame, text="COM Port:").grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.available_ports = self._list_serial_ports()
        self.selected_com_port = tk.StringVar(self.master)
        self.selected_com_port.set(self.available_ports[0] if self.available_ports else "")
        self.com_port_combobox = ttk.Combobox(serial_port_selection_frame, textvariable=self.selected_com_port,
                                                values=self.available_ports, state="readonly")
        self.com_port_combobox.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        self.com_port_combobox.bind("<<ComboboxSelected>>", self._add_debug_log_com_selection)

        # Refresh COM Ports Button
        self.refresh_com_button = ttk.Button(serial_port_selection_frame, text="Refresh", command=self._refresh_com_ports)
        self.refresh_com_button.grid(row=1, column=1, sticky="e")


        # Baud Rate Entry
        ttk.Label(self.serial_comm_frame, text="Baud Rate:").pack(anchor="w", pady=(0, 2))
        self.baud_rate = tk.StringVar(self.master, value="115200") # Default baud rate
        self.baud_rate_entry = ttk.Entry(self.serial_comm_frame, textvariable=self.baud_rate)
        self.baud_rate_entry.pack(fill=tk.X, pady=(0, 10))

        # Connect/Disconnect Serial Buttons
        self.serial_buttons_frame = ttk.Frame(self.serial_comm_frame)
        self.serial_buttons_frame.pack(fill=tk.X, pady=(0, 5))
        self.connect_serial_button = ttk.Button(self.serial_buttons_frame, text="Connect Serial", command=self._handle_connect_serial)
        self.connect_serial_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.disconnect_serial_button = ttk.Button(self.serial_buttons_frame, text="Disconnect Serial", command=self._handle_disconnect_serial)
        self.disconnect_serial_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Moved Connection Status (now for Serial)
        self.connection_status_frame = ttk.Frame(self.serial_comm_frame, relief="groove", borderwidth=1, padding=5)
        self.connection_status_frame.pack(fill=tk.X, pady=(10, 0)) # Added padding top
        self.connection_status_canvas = tk.Canvas(self.connection_status_frame, width=20, height=20, bg='#f0f0f0', highlightthickness=0)
        self.connection_status_canvas.pack(side=tk.LEFT, padx=(0, 5))
        self.connection_status_light = self.connection_status_canvas.create_oval(5, 5, 15, 15, fill="red", outline="gray")
        self.connection_status_label = ttk.Label(self.connection_status_frame, text="Serial Status: DISCONNECTED")
        self.connection_status_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.serial_connection_state = "disconnected" # State variable for serial connection

        # --- Bottom Row: Debug and Receive Logs ---
        self.log_frame = ttk.Frame(self.main_frame, padding="10 0 10 10")
        self.log_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(1, weight=1)
        self.log_frame.grid_rowconfigure(0, weight=1)

        # Debug Log
        self.debug_frame = ttk.LabelFrame(self.log_frame, text="Debug Log", padding="5 5 5 5")
        self.debug_frame.grid(row=0, column=0, padx=5, sticky="nsew")
        self.debug_frame.grid_rowconfigure(0, weight=1)
        self.debug_frame.grid_columnconfigure(0, weight=1)
        self.debug_text = tk.Text(self.debug_frame, wrap="word", height=10, bg="#e0e0e0", relief="flat", font=("Consolas", 9))
        self.debug_text.grid(row=0, column=0, sticky="nsew")
        self.debug_scrollbar = ttk.Scrollbar(self.debug_frame, command=self.debug_text.yview)
        self.debug_scrollbar.grid(row=0, column=1, sticky="ns")
        self.debug_text.config(yscrollcommand=self.debug_scrollbar.set)
        # Bind scroll events to debug log for autoscroll control
        self.debug_text.bind("<MouseWheel>", self._on_debug_scroll) # Windows/Linux
        self.debug_text.bind("<Button-4>", self._on_debug_scroll) # macOS scroll up
        self.debug_text.bind("<Button-5>", self._on_debug_scroll) # macOS scroll down


        # Receive Log
        self.receive_frame = ttk.LabelFrame(self.log_frame, text="Receive Log", padding="5 5 5 5")
        self.receive_frame.grid(row=0, column=1, padx=5, sticky="nsew")
        self.receive_frame.grid_rowconfigure(0, weight=1)
        self.receive_frame.grid_columnconfigure(0, weight=1)
        self.receive_text = tk.Text(self.receive_frame, wrap="word", height=10, bg="#e0e0e0", relief="flat", font=("Consolas", 9))
        self.receive_text.grid(row=0, column=0, sticky="nsew")
        self.receive_scrollbar = ttk.Scrollbar(self.receive_frame, command=self.receive_text.yview)
        self.receive_scrollbar.grid(row=0, column=1, sticky="ns")
        self.receive_text.config(yscrollcommand=self.receive_scrollbar.set)
        # Bind scroll events to receive log for autoscroll control
        self.receive_text.bind("<MouseWheel>", self._on_receive_scroll) # Windows/Linux
        self.receive_text.bind("<Button-4>", self._on_receive_scroll) # macOS scroll up
        self.receive_text.bind("<Button-5>", self._on_receive_scroll) # macOS scroll down


        # --- Serial Send Bar at the very bottom ---
        self.serial_send_frame = ttk.Frame(self.main_frame, padding="5 5 5 5")
        self.serial_send_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.serial_send_frame.grid_columnconfigure(0, weight=1) # Entry field takes most space

        # Changed from ttk.Entry to tk.Text for multi-line input and better Shift+Enter handling
        self.serial_entry = tk.Text(self.serial_send_frame, height=1, wrap="word", font=self.default_font)
        self.serial_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        # Bind Enter and Shift+Enter keys
        self.serial_entry.bind("<Return>", self._handle_send_serial_on_enter)
        self.serial_entry.bind("<Shift-Return>", self._handle_newline_on_shift_enter)
        # Apply placeholder and store the internal functions for later control
        self._serial_entry_show_placeholder, self._serial_entry_hide_placeholder = \
            add_placeholder_to_text(self.serial_entry, "Enter serial command here...")

        self.send_serial_button = ttk.Button(self.serial_send_frame, text="Send Serial", command=self._handle_send_serial_command)
        self.send_serial_button.grid(row=0, column=1, sticky="e")


        # Initialize logs
        self._add_debug_log("GUI initialized.")
        self._add_receive_log("Ready to receive data.")

        # Initial setup of subcommands and parameters
        self._update_subcommands_and_params()


    # --- Helper Methods ---

    def _get_timestamp(self):
        """Returns current time in ISO 8601 format with milliseconds and local offset."""
        now = datetime.datetime.now(datetime.timezone.utc).astimezone() # Get local timezone aware datetime
        return now.isoformat(timespec='milliseconds')

    def _add_debug_log(self, message):
        """Adds a timestamped message to the debug log."""
        timestamp = self._get_timestamp()
        # Check if currently at the bottom before inserting
        if self.debug_text.yview()[1] >= 0.99: # Check if scrollbar is at or near the bottom
            self.debug_autoscroll_enabled = True
        else:
            self.debug_autoscroll_enabled = False

        self.debug_text.insert(tk.END, f"{timestamp}: {message}\n")
        if self.debug_autoscroll_enabled:
            self.debug_text.see(tk.END) # Auto-scroll to the end

    def _add_receive_log(self, message):
        """Adds a timestamped message to the receive log."""
        timestamp = self._get_timestamp()
        # Check if currently at the bottom before inserting
        if self.receive_text.yview()[1] >= 0.99: # Check if scrollbar is at or near the bottom
            self.receive_autoscroll_enabled = True
        else:
            self.receive_autoscroll_enabled = False

        self.receive_text.insert(tk.END, f"{timestamp}: RX: {message}\n")
        if self.receive_autoscroll_enabled:
            self.receive_text.see(tk.END) # Auto-scroll to the end

    def _on_debug_scroll(self, event):
        """Handles scroll events for the debug log to control autoscroll."""
        # If user scrolls, disable autoscroll unless they scroll to the very end
        if self.debug_text.yview()[1] < 0.99: # Not at the very bottom
            self.debug_autoscroll_enabled = False
        else: # Scrolled to the bottom
            self.debug_autoscroll_enabled = True
        return "continue" # Allow default scroll behavior

    def _on_receive_scroll(self, event):
        """Handles scroll events for the receive log to control autoscroll."""
        # If user scrolls, disable autoscroll unless they scroll to the very end
        if self.receive_text.yview()[1] < 0.99: # Not at the very bottom
            self.receive_autoscroll_enabled = False
        else: # Scrolled to the bottom
            self.receive_autoscroll_enabled = True
        return "continue" # Allow default scroll behavior


    def _update_gpib_connection_status(self, status):
        """
        Updates the connection status light and label for GPIB (now unused).
        This method is kept for structural integrity but is no longer actively used for the main status.
        """
        self._add_debug_log(f"GPIB Connection status (simulated) changed to: {status.upper()}")

    def _update_serial_connection_status(self, status):
        """Updates the connection status light and label for Serial."""
        self.serial_connection_state = status
        color_map = {
            "disconnected": "red",
            "connecting": "yellow",
            "connected": "green"
        }
        self.connection_status_canvas.itemconfig(self.connection_status_light, fill=color_map.get(status, "gray"))
        self.connection_status_label.config(text=f"Serial Status: {status.upper()}")
        self._add_debug_log(f"Serial Connection status changed to: {status.upper()}")


    def _resize_graph_content(self, event):
        """Redraws the placeholder curve when the canvas is resized."""
        # This method is no longer directly used for the Matplotlib canvas,
        # but the canvas itself should handle resizing through Matplotlib's backend.
        self.fig.tight_layout()
        self.canvas_plot.draw_idle()


    def _list_serial_ports(self):
        """Lists available serial ports."""
        ports = serial.tools.list_ports.comports()
        # Return a list of port names, e.g., ['COM1', 'COM2', '/dev/ttyUSB0']
        return [port.device for port in ports] if ports else ["No COM Ports Found"]

    def _refresh_com_ports(self):
        """Refreshes the list of available COM ports."""
        self._add_debug_log("Refreshing COM ports...")
        current_ports = self._list_serial_ports()
        self.com_port_combobox['values'] = current_ports
        if current_ports:
            # Try to keep the current selection if it's still available
            if self.selected_com_port.get() not in current_ports:
                self.selected_com_port.set(current_ports[0])
        else:
            self.selected_com_port.set("No COM Ports Found")
        self._add_debug_log(f"Available COM ports updated: {current_ports}")

    def _add_debug_log_com_selection(self, event):
        """Logs when a COM port is selected."""
        selected_port = self.selected_com_port.get()
        self._add_debug_log(f"COM Port selected: {selected_port}")

    # --- Plotting Methods ---
    def _initialize_plot(self):
        """Initializes or resets the plot."""
        self.ax.clear() # Clear existing plot
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value") # Default Y-label
        self.ax.set_title("Real-time Measurement")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], 'b-') # Re-create the line object
        self.canvas_plot.draw_idle()
        self.plot_time_data = []
        self.plot_value_data = []
        self.start_time = time.time() # Reset start time for new plot

    def _update_plot(self, value):
        """Updates the plot with new data."""
        timestamp_s = time.time()
        self.plot_time_data.append(timestamp_s - self.start_time) # Relative time
        self.plot_value_data.append(value)

        self.line.set_data(self.plot_time_data, self.plot_value_data)

        # Adjust x-axis limits dynamically
        self.ax.relim()
        self.ax.autoscale_view()
        
        # Adjust y-axis limits dynamically based on data range
        if self.plot_value_data:
            min_val = min(self.plot_value_data)
            max_val = max(self.plot_value_data)
            # Add some padding to the y-axis
            padding = (max_val - min_val) * 0.1 if (max_val - min_val) != 0 else 1.0
            self.ax.set_ylim(min_val - padding, max_val + padding)
        else:
            self.ax.set_ylim(-1, 1) # Default empty range

        self.canvas_plot.draw_idle()

    def _clear_plot_data(self):
        """Clears all plotted data and resets the plot."""
        self._add_debug_log("Clearing plot data.")
        self._initialize_plot() # Re-initialize the plot to clear it
        self.current_measurement_type = None # Reset measurement type
    
    def _handle_save_data(self):
        """
        Saves the plotted time and value data to a CSV file.
        """
        self._add_debug_log("Save Data button clicked.")

        if not self.plot_time_data:
            messagebox.showwarning("Warning", "No data to save. Please connect an instrument and start a measurement first.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Measurement Data"
        )
        
        if not file_path:
            self._add_debug_log("Save Data operation cancelled by user.")
            return

        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp (s)', 'Measurement Value']) # Write header row
                for time_val, value_val in zip(self.plot_time_data, self.plot_value_data):
                    writer.writerow([time_val, value_val])
            
            self._add_debug_log(f"Data successfully saved to: {file_path}")
            messagebox.showinfo("Success", f"Measurement data saved successfully to {file_path}")

        except Exception as e:
            self._add_debug_log(f"Error saving data: {e}")
            messagebox.showerror("Error", f"An error occurred while saving the data: {e}")

    def _handle_x_axis(self):
        """Allows the user to change the X-axis label."""
        self._add_debug_log("X-Axis button clicked.")
        # Create a new top-level window for the dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Change X-Axis Label")
        dialog.geometry("300x100")
        dialog.transient(self.master) # Set as a transient window
        dialog.grab_set() # Make it modal

        label = ttk.Label(dialog, text="Enter new X-axis label:")
        label.pack(pady=5, padx=10)

        entry = ttk.Entry(dialog)
        entry.insert(0, self.x_units_label.cget("text"))
        entry.pack(pady=5, padx=10, fill=tk.X)

        def set_label():
            new_label = entry.get()
            self.x_units_label.config(text=new_label)
            self.ax.set_xlabel(new_label)
            self.canvas_plot.draw_idle()
            self._add_debug_log(f"X-Axis label changed to: {new_label}")
            dialog.destroy()
        
        button = ttk.Button(dialog, text="Set Label", command=set_label)
        button.pack(pady=5)
        entry.bind("<Return>", lambda e: set_label())

    def _handle_y_axis(self):
        """Allows the user to change the Y-axis label."""
        self._add_debug_log("Y-Axis button clicked.")
        dialog = tk.Toplevel(self.master)
        dialog.title("Change Y-Axis Label")
        dialog.geometry("300x100")
        dialog.transient(self.master)
        dialog.grab_set()

        label = ttk.Label(dialog, text="Enter new Y-axis label:")
        label.pack(pady=5, padx=10)

        entry = ttk.Entry(dialog)
        entry.insert(0, self.y_units_label.cget("text"))
        entry.pack(pady=5, padx=10, fill=tk.X)

        def set_label():
            new_label = entry.get()
            self.y_units_label.config(text=new_label)
            self.ax.set_ylabel(new_label)
            self.canvas_plot.draw_idle()
            self._add_debug_log(f"Y-Axis label changed to: {new_label}")
            dialog.destroy()
        
        button = ttk.Button(dialog, text="Set Label", command=set_label)
        button.pack(pady=5)
        entry.bind("<Return>", lambda e: set_label())

    # --- Event Handlers (Simulated Actions) ---

    def _update_subcommands_and_params(self):
        """Updates subcommand dropdown and parameter fields based on selected instrument."""
        selected_instrument_name = self.selected_instrument.get()
        subcommands_for_instrument = [""] # Always start with a blank option

        if selected_instrument_name in self.instrument_data:
            instrument_info = self.instrument_data[selected_instrument_name]
            subcommands_for_instrument.extend(sorted(instrument_info["subcommands"].keys()))

        # Update subcommand combobox values
        self.subcommand_combobox['values'] = subcommands_for_instrument
        self.selected_subcommand.set(subcommands_for_instrument[0]) # Reset subcommand selection

        # Clear and reset parameter fields
        self._update_parameter_placeholders()


    def _update_parameter_placeholders(self):
        """Updates parameter entry placeholders based on selected subcommand."""
        selected_instrument_name = self.selected_instrument.get()
        selected_subcommand_name = self.selected_subcommand.get()

        param_labels = []
        if selected_instrument_name and selected_subcommand_name and \
           selected_instrument_name in self.instrument_data and \
           selected_subcommand_name in self.instrument_data[selected_instrument_name]["subcommands"]:
            param_labels = self.instrument_data[selected_instrument_name]["subcommands"][selected_subcommand_name]["params"]

        # Apply specific placeholders or generic ones
        for i, entry_widget in enumerate(self.param_entries):
            # First, clear the entry
            entry_widget.delete(0, tk.END)
            # Then set the placeholder or hide the entry
            if i < len(param_labels):
                placeholder = param_labels[i]
                add_placeholder_to_entry(entry_widget, placeholder)
                entry_widget.grid() # Make sure it's visible
            else:
                entry_widget.grid_remove() # Hide unused entry widgets


    def _handle_instrument_change(self, event):
        selected_instrument_name = self.selected_instrument.get()
        self._add_debug_log(f"Instrument selected: {selected_instrument_name}")
        self._update_subcommands_and_params()


    def _handle_subcommand_change(self, event):
        selected_instrument_name = self.selected_instrument.get()
        selected_subcommand_name = self.selected_subcommand.get()

        if not selected_instrument_name or selected_instrument_name == "":
            self._add_debug_log("Error: Subcommand selected without an Instrument. Please select an Instrument first.")
            messagebox.showerror("Error", "Please select an Instrument before selecting a subcommand.")
            self.selected_subcommand.set("") # Reset subcommand selection
            return

        self._add_debug_log(f"Subcommand selected: {selected_subcommand_name}")
        self._update_parameter_placeholders()

    def _handle_save_config(self):
        """
        Saves the current application state (instrument, subcommand, params, serial settings)
        to a JSON file.
        """
        self._add_debug_log("Save Config button clicked.")
        
        config = {
            "instrument": self.selected_instrument.get(),
            "subcommand": self.selected_subcommand.get(),
            "params": [e.get() for e in self.param_entries],
            "com_port": self.selected_com_port.get(),
            "baud_rate": self.baud_rate.get()
        }

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(config, f, indent=4)
                self._add_debug_log(f"Configuration saved to: {file_path}")
            except Exception as e:
                self._add_debug_log(f"Error saving config: {e}")
                messagebox.showerror("Error", f"Could not save configuration: {e}")

    def _handle_load_config(self):
        """
        Loads application state from a JSON file.
        """
        self._add_debug_log("Load Config button clicked.")
        file_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r") as f:
                    config = json.load(f)

                # Update UI elements from the loaded config
                if "instrument" in config and config["instrument"] in self.instrument_data:
                    self.selected_instrument.set(config["instrument"])
                    self._handle_instrument_change(None) # Trigger update
                
                if "subcommand" in config:
                    self.selected_subcommand.set(config["subcommand"])
                    self._handle_subcommand_change(None) # Trigger update

                if "params" in config and isinstance(config["params"], list):
                    for i, param_val in enumerate(config["params"]):
                        if i < len(self.param_entries):
                            self.param_entries[i].delete(0, tk.END)
                            # Remove placeholder style before inserting
                            self.param_entries[i].config(style='TEntry')
                            self.param_entries[i].insert(0, param_val)

                if "com_port" in config and config["com_port"] in self.com_port_combobox['values']:
                    self.selected_com_port.set(config["com_port"])
                
                if "baud_rate" in config:
                    self.baud_rate.set(config["baud_rate"])

                self._add_debug_log(f"Configuration loaded from: {file_path}")
                messagebox.showinfo("Success", "Configuration loaded successfully!")

            except Exception as e:
                self._add_debug_log(f"Error loading config: {e}")
                messagebox.showerror("Error", f"Could not load configuration. File format may be incorrect: {e}")

    def _handle_connect_serial(self):
        """
        Connects to the selected serial port.
        Starts a separate thread to read incoming data.
        """
        if self.serial_connection_state == "connected":
            self._add_debug_log("Already connected.")
            messagebox.showinfo("Info", "Serial port is already connected.")
            return

        port = self.selected_com_port.get()
        baud = self.baud_rate.get()
        if port == "No COM Ports Found" or not port:
            messagebox.showwarning("Warning", "Please select a valid COM port.")
            return

        try:
            baud = int(baud)
        except ValueError:
            messagebox.showerror("Error", "Baud rate must be an integer.")
            return
        
        self._update_serial_connection_status("connecting")
        try:
            self.serial_port = serial.Serial(port, baud, timeout=1)
            # Start the read thread only after a successful connection
            self.stop_thread.clear()
            self.serial_read_thread = threading.Thread(target=self._read_serial_data, daemon=True)
            self.serial_read_thread.start()
            self._update_serial_connection_status("connected")
        except serial.SerialException as e:
            self.serial_port = None
            self._update_serial_connection_status("disconnected")
            messagebox.showerror("Connection Error", f"Could not connect to {port}: {e}")

    def _handle_disconnect_serial(self):
        """
        Disconnects from the serial port and stops the read thread.
        """
        if self.serial_connection_state != "connected":
            self._add_debug_log("Not connected, cannot disconnect.")
            return
        
        self._add_debug_log("Disconnecting from serial port...")
        self.stop_thread.set() # Signal the thread to stop
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None
        self._update_serial_connection_status("disconnected")
        self._add_debug_log("Serial port disconnected.")
        
    def _read_serial_data(self):
        """
        Reads data from the serial port in a separate thread.
        Updates the receive log and plot if data is a number.
        This version is more robust against malformed data.
        """
        self._add_debug_log("Serial read thread started.")
        self._read_buffer = b'' # Initialize buffer for this thread
        while not self.stop_thread.is_set():
            try:
                if self.serial_port and self.serial_port.is_open:
                    # Read a small chunk of data to avoid blocking
                    data = self.serial_port.read(64) 
                    if data:
                        self._read_buffer += data
                        while b'\n' in self._read_buffer:
                            line, self._read_buffer = self._read_buffer.split(b'\n', 1)
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            if line_str:
                                self.master.after(0, self._add_receive_log, line_str)
                                
                                # Attempt to parse a numeric value for plotting
                                try:
                                    value = float(line_str)
                                    self.master.after(0, self._update_plot, value)
                                    # Check if a measurement type has been established for the y-axis label
                                    if self.current_measurement_type is None:
                                        self.master.after(0, lambda: self._add_debug_log("Plotting new data, Y-axis label is 'Value'"))
                                        self.current_measurement_type = "Generic"

                                except ValueError:
                                    # The line doesn't contain a valid value for plotting, log it as a normal message
                                    pass
            except serial.SerialException as e:
                self.master.after(0, self._add_debug_log, f"Serial read error: {e}")
                self.master.after(0, self._handle_disconnect_serial)
                break
        self._add_debug_log("Serial read thread stopped.")


    def _send_command_to_serial(self, command):
        """Sends a string command to the serial port, with a newline."""
        if self.serial_port and self.serial_port.is_open:
            try:
                # Add a newline character to the command
                command_with_newline = command + '\n'
                self.serial_port.write(command_with_newline.encode('utf-8'))
                self._add_debug_log(f"TX: {command}")
                return True
            except serial.SerialException as e:
                self._add_debug_log(f"Error sending command: {e}")
                messagebox.showerror("Serial Error", f"Error sending command: {e}")
                return False
        else:
            self._add_debug_log("Serial port is not connected.")
            messagebox.showwarning("Warning", "Serial port is not connected.")
            return False

    def _handle_send_command(self):
        """
        Constructs a command from the UI and sends it via the serial port.
        """
        selected_instrument_name = self.selected_instrument.get()
        selected_subcommand_name = self.selected_subcommand.get()

        if not selected_instrument_name or not selected_subcommand_name:
            messagebox.showwarning("Warning", "Please select an instrument and a subcommand.")
            self._add_debug_log("Attempt to send command failed: instrument or subcommand not selected.")
            return

        # Get the command string from the data structure
        subcommand_info = self.instrument_data[selected_instrument_name]["subcommands"][selected_subcommand_name]
        command_base = subcommand_info["command"]
        
        # Get parameter values from the entry fields
        param_values = [e.get() for e in self.param_entries if e.winfo_ismapped()]
        
        # Build the final command string
        if selected_instrument_name == "Power Supply" or selected_instrument_name == "Chroma DC Load":
            command_prefix = self.instrument_data[selected_instrument_name]["command_prefix"]
            # Filter out placeholders
            params_str = ",".join([p for p in param_values if p != subcommand_info["params"][param_values.index(p)]])
            command = f"{command_prefix}{command_base}"
            if params_str:
                command += f":{params_str}"
        
        elif selected_instrument_name == "HP 3478A Multimeter":
            if command_base == "D2":
                # Special handling for D2text command
                text_to_write = param_values[0] if param_values and param_values[0] != subcommand_info["params"][0] else ""
                command = f"{command_base}{text_to_write.upper()}"
            elif command_base == "D3":
                # Special handling for D3text command
                text_to_write = param_values[0] if param_values and param_values[0] != subcommand_info["params"][0] else ""
                command = f"{command_base}{text_to_write.upper()}"
            elif command_base == "M":
                # Special handling for Mx command
                mask_value = param_values[0] if param_values and param_values[0] != subcommand_info["params"][0] else ""
                command = f"{command_base}{mask_value}"
            else:
                # Other HP commands are simple strings without prefixes or parameters
                command = command_base
        
        else:
            # Fallback for other instruments
            command = command_base + (":" + ",".join(param_values) if param_values else "")

        self._send_command_to_serial(command)


    def _handle_send_serial_on_enter(self, event):
        """Handles sending the raw serial command on Enter key press."""
        # Check for Shift-Enter to allow newlines
        if event.state & 0x0001: # Check for Shift key
            return self._handle_newline_on_shift_enter(event)
            
        command = self.serial_entry.get("1.0", "end-1c").strip()
        if command and not self.serial_entry._has_placeholder:
            self._send_command_to_serial(command)
        
        # Clear the entry and reset placeholder, and prevent a newline from being inserted
        self.serial_entry.delete("1.0", tk.END)
        self._serial_entry_show_placeholder()
        return "break" # Prevents default Enter key behavior (newline insertion)

    def _handle_newline_on_shift_enter(self, event):
        """Allows a newline to be inserted when Shift+Enter is pressed."""
        self.serial_entry.insert(tk.END, "\n")
        return "break" # Prevents default Shift-Enter behavior

    def _handle_send_serial_command(self):
        """Sends the raw serial command from the text box on button click."""
        command = self.serial_entry.get("1.0", "end-1c").strip()
        if command and not self.serial_entry._has_placeholder:
            self._send_command_to_serial(command)

        # Clear the entry and reset placeholder
        self.serial_entry.delete("1.0", tk.END)
        self._serial_entry_show_placeholder()

    def _on_closing(self):
        """
        Gracefully handles application closure.
        Stops the serial read thread and closes the serial port.
        """
        self._add_debug_log("Application closing. Stopping serial thread...")
        self.stop_thread.set()
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GPIBApp(root)
    root.mainloop()