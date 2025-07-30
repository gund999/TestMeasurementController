import tkinter as tk
from tkinter import ttk
from tkinter import font as tkFont
from tkinter import messagebox
import datetime
import time # For simulating delays
import serial # Import the pyserial library
import serial.tools.list_ports # To list available COM ports
import threading # For running serial read in a separate thread

# Import matplotlib for plotting
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# Helper function to add placeholder text to ttk.Entry widgets
def add_placeholder_to_entry(entry, placeholder_text):
    # Set initial text and style
    entry.delete(0, tk.END) # Clear existing text
    entry.insert(0, placeholder_text)
    entry.config(style='Placeholder.TEntry') # Apply placeholder style

    def on_focus_in(event):
        if entry.get() == placeholder_text and entry.cget('style') == 'Placeholder.TEntry':
            entry.delete(0, tk.END)
            entry.config(style='TEntry') # Switch to default style for active text

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder_text)
            entry.config(style='Placeholder.TEntry') # Switch back to placeholder style

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)

# Helper function to add placeholder text to tk.Text widgets
def add_placeholder_to_text(text_widget, placeholder_text):
    text_widget.tag_configure("placeholder", foreground="grey")
    # Store the placeholder text directly on the widget for easy access
    text_widget._placeholder_text = placeholder_text
    text_widget._has_placeholder = False # Internal state to track if placeholder is active

    def show_placeholder_internal():
        # Only show placeholder if the widget is truly empty and doesn't already have one
        if not text_widget.get("1.0", tk.END).strip() and not text_widget._has_placeholder:
            text_widget.delete("1.0", tk.END) # Clear to ensure no stray characters
            text_widget.insert("1.0", text_widget._placeholder_text, "placeholder")
            text_widget.config(fg="grey")
            text_widget._has_placeholder = True

    def hide_placeholder_internal(event=None): # event=None for manual calls
        if text_widget._has_placeholder:
            text_widget.delete("1.0", tk.END)
            text_widget.tag_remove("placeholder", "1.0", tk.END)
            text_widget.config(fg="black")
            text_widget._has_placeholder = False

    def check_placeholder_internal(event):
        # On focus out, if the widget is empty, re-show placeholder
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
                    "Set Voltage": {"params": ["Voltage (V)", "Channel"]},
                    "Set Current Limit": {"params": ["Current (A)", "Channel"]},
                    "Output ON/OFF": {"params": ["State (ON/OFF)"]},
                    "Measure Output": {"params": []}
                },
                "command_prefix": "PS:"
            },
            "Chroma DC Load": {
                "subcommands": {
                    "Set Current": {"params": ["Current (A)", "Mode (CC/CR/CP)"]},
                    "Set Voltage": {"params": ["Voltage (V)"]},
                    "Load ON/OFF": {"params": ["State (ON/OFF)"]},
                    "Measure Input": {"params": []}
                },
                "command_prefix": "LOAD:"
            },
            "HP 3478A Multimeter": {
                "subcommands": {
                    "HOME Command": {"params": []}, # Added HOME Command
                    "Measure DC Voltage": {"params": []},
                    "Measure AC Volts": {"params": []}, # Added AC Volts
                    "Measure 2-Wire Ohms": {"params": []}, # Added 2-Wire Ohms
                    "Measure 4-Wire Ohms": {"params": []}, # Added 4-Wire Ohms
                    "Measure DC Current": {"params": []}, # Added DC Current
                    "Measure AC Current": {"params": []}, # Added AC Current
                    "Measure Extended Ohms": {"params": []}, # Added Extended Ohms
                    "Clear Display": {"params": []}, # Added Clear Display
                    "Write to Display": {"params": ["Enter text in all caps here"]}, # Specific placeholder
                    "Read IDN": {"params": []}
                },
                "command_prefix": "HP3478A:" # This prefix will be overridden by specific command logic for "Write to Display"
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
        self.graph_title_label.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="n") # Adjust grid placement

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
        self.canvas_plot_widget.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        # Matplotlib Navigation Toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas_plot, self.graph_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=1, column=0, columnspan=2, sticky="ew")

        # X/Y Axis Buttons and Labels (moved to a separate frame for better layout)
        self.axis_control_frame = ttk.Frame(self.graph_frame)
        self.axis_control_frame.grid(row=2, column=0, columnspan=2, pady=(5,0))

        self.x_axis_button = ttk.Button(self.axis_control_frame, text="X-Axis", command=self._handle_x_axis)
        self.x_axis_button.grid(row=0, column=0, padx=5)
        self.x_units_label = ttk.Label(self.axis_control_frame, text="Time")
        self.x_units_label.grid(row=1, column=0)

        self.y_axis_button = ttk.Button(self.axis_control_frame, text="Y-Axis", command=self._handle_y_axis)
        self.y_axis_button.grid(row=0, column=1, padx=5)
        self.y_units_label = ttk.Label(self.axis_control_frame, text="Value") # Placeholder
        self.y_units_label.grid(row=1, column=1)

        self.clear_plot_button = ttk.Button(self.axis_control_frame, text="Clear Plot", command=self._clear_plot_data)
        self.clear_plot_button.grid(row=0, column=2, padx=5)


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
        ttk.Label(self.serial_comm_frame, text="COM Port:").pack(anchor="w", pady=(0, 2))
        self.available_ports = self._list_serial_ports()
        self.selected_com_port = tk.StringVar(self.master)
        self.selected_com_port.set(self.available_ports[0] if self.available_ports else "")
        self.com_port_combobox = ttk.Combobox(self.serial_comm_frame, textvariable=self.selected_com_port,
                                               values=self.available_ports, state="readonly")
        self.com_port_combobox.pack(fill=tk.X, pady=(0, 5))
        self.com_port_combobox.bind("<<ComboboxSelected>>", self._add_debug_log_com_selection)

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

        self.receive_text.insert(tk.END, f"{timestamp}: {message}\n")
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
        """Updates the connection status light and label for GPIB (now unused)."""
        # This method is kept for structural integrity but is no longer actively used for the main status
        # self.connection_state = status # This state variable is now unused for the main status
        # color_map = {
        #     "disconnected": "red",
        #     "connecting": "yellow",
        #     "connected": "green"
        # }
        # self.connection_status_canvas.itemconfig(self.connection_status_light, fill=color_map.get(status, "gray"))
        # self.connection_status_label.config(text=f"Connection Status: {status.upper()}")
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

    def _update_plot(self, timestamp_s, value):
        """Updates the plot with new data."""
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
            placeholder = param_labels[i] if i < len(param_labels) else f"Sub Param {chr(65+i)}"
            add_placeholder_to_entry(entry_widget, placeholder)


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
        self._add_debug_log("Save Config button clicked.")
        messagebox.showinfo("Save Configuration", "Configuration saved (simulated).")

    def _handle_load_config(self):
        self._add_debug_log("Load Config button clicked.")
        messagebox.showinfo("Load Configuration", "Configuration loaded (simulated).")

    def _handle_x_axis(self):
        self._add_debug_log("X-Axis button clicked. (Simulated axis control)")
        messagebox.showinfo("X-Axis Control", "X-Axis control panel would open here.")

    def _handle_y_axis(self):
        self._add_debug_log("Y-Axis button clicked. (Simulated axis control)")
        messagebox.showinfo("Y-Axis Control", "Y-Axis control panel would open here.")

    def _handle_send_command(self):
        instrument = self.selected_instrument.get()
        subcommand = self.selected_subcommand.get()
        param_values_raw = [entry.get().strip() for entry in self.param_entries]

        # Filter out placeholder text if it's still present
        param_values = []
        if instrument and subcommand and \
           instrument in self.instrument_data and \
           subcommand in self.instrument_data[instrument]["subcommands"]:
            expected_params = self.instrument_data[instrument]["subcommands"][subcommand]["params"]
            for i, val in enumerate(param_values_raw):
                # Ensure we don't go out of bounds for expected_params
                if i < len(expected_params) and val == expected_params[i]:
                    param_values.append("") # It's still the placeholder, treat as empty
                else:
                    param_values.append(val)
        else:
            # If instrument or subcommand is not valid/selected, treat all params as raw
            param_values = param_values_raw

        if not instrument or instrument == "":
            self._add_debug_log("Error: No Instrument selected. Cannot send command.")
            messagebox.showerror("Error", "Please select an Instrument.")
            return
        if not subcommand or subcommand == "":
            self._add_debug_log("Error: No subcommand selected. Cannot send command.")
            messagebox.showerror("Error", "Please select a subcommand.")
            return

        # --- Command Construction Logic ---
        final_command = ""
        # Reset current measurement type for plotting
        self.current_measurement_type = None

        if instrument == "HP 3478A Multimeter":
            if subcommand == "HOME Command":
                final_command = "H0"
            elif subcommand == "Measure DC Voltage":
                final_command = "H1"
                self.current_measurement_type = "DC Volts"
            elif subcommand == "Measure AC Volts":
                final_command = "H2"
                self.current_measurement_type = "AC Volts"
            elif subcommand == "Measure 2-Wire Ohms":
                final_command = "H3"
            elif subcommand == "Measure 4-Wire Ohms":
                final_command = "H4"
            elif subcommand == "Measure DC Current":
                final_command = "H5"
                self.current_measurement_type = "DC Current"
            elif subcommand == "Measure AC Current":
                final_command = "H6"
                self.current_measurement_type = "AC Current"
            elif subcommand == "Measure Extended Ohms":
                final_command = "H7"
            elif subcommand == "Clear Display":
                final_command = "D1"
            elif subcommand == "Write to Display":
                text_to_display = param_values[0] if param_values else ""
                if not text_to_display:
                    self._add_debug_log("Error: Display text cannot be empty for 'Write to Display'. Sending aborted.")
                    messagebox.showerror("Error", "Please enter text for the display.")
                    return
                final_command = f'wrt 723 D2{text_to_display}'
        else:
            # Generic command construction for other instruments/subcommands
            instrument_prefix = self.instrument_data[instrument].get("command_prefix", "")
            params_str = " ".join([p for p in param_values if p]) # Join only non-empty params
            final_command = f"{instrument_prefix}{subcommand} {params_str}".strip()

        self._add_debug_log(f"Final command to send: '{final_command}'")

        # If a measurement command is sent, clear the plot before new data comes in
        if self.current_measurement_type:
            self._clear_plot_data()
            self.ax.set_ylabel(f"Value ({self.current_measurement_type})") # Update Y-label
            self.ax.set_title(f"Real-time {self.current_measurement_type} Measurement")
            self.canvas_plot.draw_idle()


        # --- Actual Serial Send ---
        if self.serial_port and self.serial_port.is_open:
            try:
                # Encode the string to bytes before sending over serial
                # Add a newline character commonly used for serial commands
                command_bytes = (final_command + '\n').encode('ascii')
                self.serial_port.write(command_bytes)
                # Removed the "(Bytes: ...)" part from the debug log
                self._add_debug_log(f"Sent command from 'Send Command' button: '{final_command}'")
                # The _serial_reader_thread will now automatically pick up any response
            except serial.SerialException as e:
                self._add_debug_log(f"Error sending command from 'Send Command' button: {e}")
                messagebox.showerror("Send Command Error", f"Error sending command via serial:\n{e}")
            except Exception as e:
                self._add_debug_log(f"An unexpected error occurred while sending command from 'Send Command' button: {e}")
                messagebox.showerror("Send Command Error", f"An unexpected error occurred:\n{e}")
        else:
            self._add_debug_log("Serial port is not connected. Cannot send command from 'Send Command' button.")
            messagebox.showerror("Serial Connection Required", "Serial port is not connected. Please connect first using the 'Connect Serial' button.")

    def _handle_connect_serial(self):
        """Attempts to connect to the selected serial port."""
        port = self.selected_com_port.get()
        baud = self.baud_rate.get()

        if not port or port == "No COM Ports Found":
            self._add_debug_log("Error: No COM port selected or found.")
            messagebox.showerror("Serial Connect Error", "Please select a valid COM port.")
            return

        try:
            baud_int = int(baud)
            self._add_debug_log(f"Attempting to connect to serial port {port} at {baud_int} baud...")
            self._update_serial_connection_status("connecting") # Update status to yellow
            self.serial_port = serial.Serial(port, baud_int, timeout=0.1) # Non-blocking read timeout for thread
            self._add_debug_log(f"Successfully connected to {port}")
            messagebox.showinfo("Serial Connection", f"Connected to {port} at {baud_int} baud.")
            self.connect_serial_button.config(state=tk.DISABLED)
            self.disconnect_serial_button.config(state=tk.NORMAL)
            self._update_serial_connection_status("connected") # Update status to green

            # Start the serial reading thread
            self.stop_thread.clear() # Ensure the stop event is clear
            self.serial_read_thread = threading.Thread(target=self._serial_reader_thread, daemon=True)
            self.serial_read_thread.start()

        except ValueError:
            self._add_debug_log(f"Error: Invalid baud rate '{baud}'. Must be an integer.")
            messagebox.showerror("Serial Connect Error", "Invalid Baud Rate. Please enter a number.")
            self._update_serial_connection_status("disconnected") # Back to red on error
        except serial.SerialException as e:
            self._add_debug_log(f"Error connecting to serial port {port}: {e}")
            messagebox.showerror("Serial Connect Error", f"Could not open serial port {port}:\n{e}")
            self._update_serial_connection_status("disconnected") # Back to red on error
        except Exception as e:
            self._add_debug_log(f"An unexpected error occurred during serial connection: {e}")
            messagebox.showerror("Serial Connect Error", f"An unexpected error occurred:\n{e}")
            self._update_serial_connection_status("disconnected") # Back to red on error

    def _handle_disconnect_serial(self):
        """Closes the serial port if open and stops the reading thread."""
        if self.serial_port and self.serial_port.is_open:
            try:
                # Signal the thread to stop
                self.stop_thread.set()
                # Wait for the thread to finish (with a timeout to prevent GUI freeze)
                if self.serial_read_thread and self.serial_read_thread.is_alive():
                    self.serial_read_thread.join(timeout=0.5) # Give it some time to exit
                    if self.serial_read_thread.is_alive():
                        self._add_debug_log("Warning: Serial read thread did not terminate gracefully.")

                self.serial_port.close()
                self._add_debug_log(f"Disconnected from serial port {self.serial_port.port}")
                messagebox.showinfo("Serial Disconnection", "Serial port disconnected.")
                self.connect_serial_button.config(state=tk.NORMAL)
                self.disconnect_serial_button.config(state=tk.DISABLED)
                self.serial_port = None # Clear the serial port object
                self._update_serial_connection_status("disconnected") # Update status to red
            except Exception as e:
                self._add_debug_log(f"Error disconnecting serial port: {e}")
                messagebox.showerror("Serial Disconnect Error", f"Error disconnecting serial port:\n{e}")
                self._update_serial_connection_status("disconnected") # Ensure red on error
        else:
            self._add_debug_log("Serial port is not open to disconnect.")
            messagebox.showwarning("Serial Disconnection", "Serial port is not currently connected.")
            self._update_serial_connection_status("disconnected") # Ensure red if already disconnected

    def _serial_reader_thread(self):
        """Function to run in a separate thread to read serial data."""
        self._add_debug_log("Serial reader thread started.")
        self.serial_receive_buffer = bytearray() # Initialize buffer for this thread run

        while not self.stop_thread.is_set() and self.serial_port and self.serial_port.is_open:
            try:
                # Read all available bytes from the serial buffer
                # The timeout on serial.Serial ensures read_all() doesn't block indefinitely
                data = self.serial_port.read_all()
                if data:
                    self.serial_receive_buffer.extend(data) # Add new data to buffer

                # Process buffer line by line
                # Look for newline character (b'\n') as a delimiter
                while b'\n' in self.serial_receive_buffer:
                    # Find the index of the first newline
                    newline_index = self.serial_receive_buffer.find(b'\n')
                    # Extract the complete line (including newline)
                    line_bytes = self.serial_receive_buffer[:newline_index + 1]
                    # Remove the processed line from the buffer
                    self.serial_receive_buffer = self.serial_receive_buffer[newline_index + 1:]

                    try:
                        # Decode and strip whitespace (including the newline and carriage return)
                        decoded_line = line_bytes.decode('ascii').strip()
                        self._add_receive_log(f"Serial RX: {decoded_line}")

                        # Attempt to parse received data as a float for plotting
                        if self.current_measurement_type:
                            try:
                                value = float(decoded_line)
                                current_time = time.time()
                                # Schedule plot update on the main Tkinter thread
                                self.master.after(0, self._update_plot, current_time, value)
                            except ValueError:
                                self._add_debug_log(f"Could not convert received data '{decoded_line}' to float for plotting.")

                    except UnicodeDecodeError:
                        self._add_debug_log(f"Serial RX (decode error, raw bytes): {line_bytes.hex()}")
                
                # Optional: Implement a buffer size limit to prevent excessive memory usage
                # if len(self.serial_receive_buffer) > 1024: # Example limit
                #     self._add_debug_log("Warning: Serial receive buffer exceeding limit, clearing.")
                #     self.serial_receive_buffer.clear()


                time.sleep(0.01) # Small delay to prevent busy-waiting

            except serial.SerialException as e:
                self._add_debug_log(f"Serial read error: {e}")
                self.master.after(0, self._handle_disconnect_serial) # Attempt to disconnect on error
                break # Exit thread loop on error
            except Exception as e:
                self._add_debug_log(f"Unexpected error in serial reader thread: {e}")
                break # Exit thread loop on unexpected error
        self._add_debug_log("Serial reader thread stopped.")

    def _handle_send_serial_command(self):
        """Handles sending text from the serial command input bar."""
        # Get text from the Text widget, from start (1.0) to end-1c (end minus one character, to exclude newline)
        serial_command = self.serial_entry.get("1.0", tk.END).strip()

        # Clear the entry field after sending
        self.serial_entry.delete("1.0", tk.END)
        # Re-apply placeholder if the field is empty
        # Call the stored internal function to ensure proper placeholder re-display
        self._serial_entry_show_placeholder()

        if not serial_command or serial_command == self.serial_entry._placeholder_text: # Check against actual placeholder text
            self._add_debug_log("No serial command entered.")
            messagebox.showwarning("Warning", "Please enter a command to send via serial.")
            return

        if self.serial_port and self.serial_port.is_open:
            try:
                # Encode the string to bytes before sending over serial
                # Add a newline character commonly used for serial commands
                command_bytes = (serial_command + '\n').encode('ascii')
                self.serial_port.write(command_bytes)
                # Removed the "(Bytes: ...)" part from the debug log
                self._add_debug_log(f"Sent serial command: '{serial_command}'")

                # The _serial_reader_thread will now automatically pick up any response
            except serial.SerialException as e:
                self._add_debug_log(f"Error sending serial command: {e}")
                messagebox.showerror("Serial Send Error", f"Error sending command:\n{e}")
            except Exception as e:
                self._add_debug_log(f"An unexpected error occurred while sending serial command: {e}")
                messagebox.showerror("Serial Send Error", f"An unexpected error occurred:\n{e}")
        else:
            self._add_debug_log("Serial port is not connected. Cannot send command.")
            messagebox.showerror("Serial Send Error", "Serial port is not connected. Please connect first.")

    def _handle_send_serial_on_enter(self, event):
        """Event handler for pressing Enter in the serial entry field."""
        self._handle_send_serial_command()
        return "break" # Prevents the default Tkinter newline insertion

    def _handle_newline_on_shift_enter(self, event):
        """Event handler for pressing Shift+Enter in the serial entry field."""
        # Insert a newline character at the current cursor position
        self.serial_entry.insert(tk.INSERT, "\n")
        # Ensure the cursor stays at the end of the newly inserted newline
        self.serial_entry.see(tk.INSERT)
        return "break" # Prevents the default Tkinter newline insertion

    def _on_closing(self):
        """Handles proper shutdown when the Tkinter window is closed."""
        self._add_debug_log("Application closing. Attempting to disconnect serial port...")
        self._handle_disconnect_serial() # Disconnect serial and stop thread
        self.master.destroy() # Destroy the Tkinter window


# Running the application
if __name__ == "__main__":
    root = tk.Tk()
    app = GPIBApp(root)

    # Apply initial placeholders for parameter entries
    app._update_parameter_placeholders() # Call this after app is initialized
    app._initialize_plot() # Initialize the plot when the app starts

    root.mainloop()
