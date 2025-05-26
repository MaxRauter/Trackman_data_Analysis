import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import os
import sys
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy.stats import norm
from datetime import datetime
import importlib.util
plt.style.use("seaborn-v0_8-darkgrid")

# Import the trackman module
spec = importlib.util.spec_from_file_location("trackman", "trackman.py")
trackman = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trackman)

class TrackManGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TrackMan Golf Data")
        self.geometry("800x600")
        self.minsize(1200, 800)
        
        # Ensure program terminates when window is closed
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Set up instance variables
        self.api = trackman.TrackManAPI()
        self.activities = []
        self.available_tokens = {}
        self.selected_username = None
        self.selected_token = None
        self.status_var = tk.StringVar(value="Ready")
        
        # Create main container with padding
        self.main_frame = ttk.Frame(self, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for different tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create frames for each tab
        self.login_frame = ttk.Frame(self.notebook, padding=10)
        self.activities_frame = ttk.Frame(self.notebook, padding=10)
        self.analysis_frame = ttk.Frame(self.notebook, padding=10)
        
        # Add frames to notebook
        self.notebook.add(self.login_frame, text="Login")
        self.notebook.add(self.activities_frame, text="Activities")
        self.notebook.add(self.analysis_frame, text="Analysis")
        
        # Setup login tab
        self.setup_login_tab()
        
        # Setup activities tab
        self.setup_activities_tab()
        
        # Setup analysis tab
        self.setup_analysis_tab()
        
        # Status bar at bottom
        status_frame = ttk.Frame(self.main_frame)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT)
        
        # Check for saved tokens on startup
        self.load_saved_tokens()
        
        # Schedule window activation after main initialization
        # Use a longer delay and more aggressive approach
        self.after(10, self.activate_window)  # First attempt very quickly
        self.after(300, self.activate_window)  # Second attempt after UI is more likely fully loaded
        self.after(1000, self.activate_window)  # Final attempt to ensure it works

    def activate_window(self):
        """Force the window to appear in front and get focus"""
        self.attributes("-topmost", True)
        self.lift()  # Lift the window
        self.focus_force()  # Force focus
        self.after(100, lambda: self.attributes("-topmost", False))  # Then allow other windows to go on top

    def setup_login_tab(self):
        # Frame for saved tokens
        token_frame = ttk.LabelFrame(self.login_frame, text="Saved Logins", padding=10)
        token_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Listbox for tokens
        self.token_listbox = tk.Listbox(token_frame, height=5)
        self.token_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Scrollbar for listbox
        token_scrollbar = ttk.Scrollbar(token_frame, orient=tk.VERTICAL, command=self.token_listbox.yview)
        token_scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.token_listbox.configure(yscrollcommand=token_scrollbar.set)
        
        # Button frame
        login_button_frame = ttk.Frame(self.login_frame)
        login_button_frame.pack(fill=tk.X, pady=10)
        
        # Buttons
        self.use_token_btn = ttk.Button(login_button_frame, text="Use Selected Token", command=self.use_selected_token)
        self.use_token_btn.pack(side=tk.LEFT, padx=5)
        
        self.new_login_btn = ttk.Button(login_button_frame, text="New Login", command=self.start_new_login)
        self.new_login_btn.pack(side=tk.LEFT, padx=5)
        
        self.logout_btn = ttk.Button(login_button_frame, text="Logout Selected", command=self.logout_selected)
        self.logout_btn.pack(side=tk.LEFT, padx=5)
        
        self.logout_all_btn = ttk.Button(login_button_frame, text="Logout All", command=self.logout_all)
        self.logout_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Username input for saving new token
        username_frame = ttk.Frame(self.login_frame)
        username_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(username_frame, text="Username/Email:").pack(side=tk.LEFT, padx=5)
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(username_frame, textvariable=self.username_var, width=30)
        self.username_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.save_username_btn = ttk.Button(username_frame, text="Save Token", command=self.save_token)
        self.save_username_btn.pack(side=tk.LEFT, padx=5)
        self.save_username_btn.config(state="disabled")

    def setup_activities_tab(self):
        # Ball type selection
        ball_frame = ttk.Frame(self.activities_frame)
        ball_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ball_frame, text="Ball Type:").pack(side=tk.LEFT, padx=5)
        
        self.ball_type_var = tk.StringVar(value="PREMIUM")
        ball_type_combo = ttk.Combobox(ball_frame, textvariable=self.ball_type_var, 
                                      values=["PREMIUM", "RANGE", "BOTH"], width=10, state="readonly")
        ball_type_combo.pack(side=tk.LEFT, padx=5)
        
        # Refresh button
        refresh_btn = ttk.Button(ball_frame, text="Refresh Activities", command=self.fetch_activities)
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # Activity selection frame
        activity_frame = ttk.LabelFrame(self.activities_frame, text="Range Practice Activities", padding=10)
        activity_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create a frame for the treeview and scrollbar
        tree_frame = ttk.Frame(activity_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview for activities - keep same columns but Type will include shot count
        columns = ("ID", "Date", "Type")
        self.activity_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        # Define headings
        self.activity_tree.heading("ID", text="#")
        self.activity_tree.heading("Date", text="Date")
        self.activity_tree.heading("Type", text="Type (Shot Count)")
        
        # Define column widths - make Type column wider to accommodate shot count
        self.activity_tree.column("ID", width=50, stretch=False)
        self.activity_tree.column("Date", width=150)
        self.activity_tree.column("Type", width=200)
        
        # Add scrollbar
        activity_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=activity_scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        activity_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons frame
        action_frame = ttk.Frame(self.activities_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        download_selected_btn = ttk.Button(action_frame, text="Download Selected", command=self.download_selected)
        download_selected_btn.pack(side=tk.LEFT, padx=5)
        
        download_all_btn = ttk.Button(action_frame, text="Download All", command=self.download_all)
        download_all_btn.pack(side=tk.LEFT, padx=5)
        
        download_missing_btn = ttk.Button(action_frame, text="Download Missing", command=self.download_missing)
        download_missing_btn.pack(side=tk.LEFT, padx=5)
        
        # Add analyze button
        analyze_btn = ttk.Button(action_frame, text="Analyze Data", command=self.analyze_data)
        analyze_btn.pack(side=tk.LEFT, padx=5)
        
        # Output log
        log_frame = ttk.LabelFrame(self.activities_frame, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

    def setup_analysis_tab(self):
        # Main vertical split: controls on top, selections+plot below
        main_vsplit = ttk.Frame(self.analysis_frame)
        main_vsplit.pack(fill=tk.BOTH, expand=True)
    
        # --- Controls Row 1 ---
        controls_row1 = ttk.Frame(main_vsplit)
        controls_row1.pack(fill=tk.X, pady=(0, 2))
    
        ttk.Label(controls_row1, text="User:").pack(side=tk.LEFT, padx=5)
        self.user_var = tk.StringVar()
        self.user_combo = ttk.Combobox(controls_row1, textvariable=self.user_var, state="readonly", width=15)
        self.user_combo.pack(side=tk.LEFT, padx=5)
        self.user_combo.bind("<<ComboboxSelected>>", self.on_user_selected)
    
        refresh_btn = ttk.Button(controls_row1, text="⟳", width=3, command=self.refresh_analysis_data)
        refresh_btn.pack(side=tk.LEFT, padx=5)
    
        # Ball type
        ttk.Label(controls_row1, text="Ball Type:").pack(side=tk.LEFT, padx=5)
        self.analysis_ball_type_var = tk.StringVar(value="range")
        def toggle_ball_type():
            # Toggle between "range" and "premium"
            current = self.analysis_ball_type_var.get()
            new = "premium" if current == "range" else "range"
            self.analysis_ball_type_var.set(new)
            self.on_ball_type_selected(None)
        
        self.ball_type_toggle = ttk.Checkbutton(
            controls_row1,
            text="Premium",
            variable=self.analysis_ball_type_var,
            onvalue="premium",
            offvalue="range",
            command=toggle_ball_type
        )
        self.ball_type_toggle.pack(side=tk.LEFT, padx=5)
    
        # --- Controls Row 2 ---
        controls_row2 = ttk.Frame(main_vsplit)
        controls_row2.pack(fill=tk.X, pady=(0, 10))
    
        # Comparison mode (now in row 2)
        ttk.Label(controls_row2, text="Comparison:").pack(side=tk.LEFT, padx=5)
        self.comparison_mode_var = tk.StringVar(value="clubs")
        self.club_mode_rb = ttk.Radiobutton(controls_row2, text="Multiple Clubs", 
                                            variable=self.comparison_mode_var, value="clubs",
                                            command=self.on_comparison_mode_changed)
        self.club_mode_rb.pack(side=tk.LEFT, padx=5)
        self.time_mode_rb = ttk.Radiobutton(controls_row2, text="Club Over Sessions", 
                                            variable=self.comparison_mode_var, value="time",
                                            command=self.on_comparison_mode_changed)
        self.time_mode_rb.pack(side=tk.LEFT, padx=5)
    
        # Plot type
        ttk.Label(controls_row2, text="Plot Type:").pack(side=tk.LEFT, padx=5)
        self.plot_type_var = tk.StringVar(value="gaussian")
        gaussian_rb = ttk.Radiobutton(controls_row2, text="Gaussian", 
                                      variable=self.plot_type_var, value="gaussian")
        gaussian_rb.pack(side=tk.LEFT, padx=5)
        histogram_rb = ttk.Radiobutton(controls_row2, text="Histogram", 
                                       variable=self.plot_type_var, value="histogram")
        histogram_rb.pack(side=tk.LEFT, padx=5)
    
        # --- Bottom horizontal split: selections (left), plot (right) ---
        bottom_hsplit = ttk.Frame(main_vsplit)
        bottom_hsplit.pack(fill=tk.BOTH, expand=True)
    
        # Left: Sessions and Clubs (stacked vertically)
        left_selection = ttk.Frame(bottom_hsplit)
        left_selection.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=5)
    
        # Sessions frame
        self.sessions_frame = ttk.LabelFrame(left_selection, text="Sessions", padding=10)
        self.sessions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        sessions_list_frame = ttk.Frame(self.sessions_frame)
        sessions_list_frame.pack(fill=tk.BOTH, expand=True)
        self.sessions_listbox = tk.Listbox(sessions_list_frame, selectmode=tk.SINGLE, height=8)
        self.sessions_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sessions_scrollbar = ttk.Scrollbar(sessions_list_frame, orient=tk.VERTICAL, command=self.sessions_listbox.yview)
        sessions_scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.sessions_listbox.configure(yscrollcommand=sessions_scrollbar.set)
        self.continue_btn = ttk.Button(self.sessions_frame, text="Continue", command=self.on_continue_sessions)
        self.continue_btn.pack(fill=tk.X, pady=5)
        self.continue_btn.config(state="disabled")
    
        # Clubs frame
        self.clubs_frame = ttk.LabelFrame(left_selection, text="Clubs", padding=10)
        self.clubs_frame.pack(fill=tk.BOTH, expand=True)
        clubs_list_frame = ttk.Frame(self.clubs_frame)
        clubs_list_frame.pack(fill=tk.BOTH, expand=True)
        self.clubs_listbox = tk.Listbox(clubs_list_frame, selectmode=tk.MULTIPLE, height=8)
        self.clubs_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        clubs_scrollbar = ttk.Scrollbar(clubs_list_frame, orient=tk.VERTICAL, command=self.clubs_listbox.yview)
        clubs_scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.clubs_listbox.configure(yscrollcommand=clubs_scrollbar.set)
    
        # --- Plot and Save buttons BELOW clubs selection ---
        plot_btn_frame = ttk.Frame(left_selection)
        plot_btn_frame.pack(fill=tk.X, pady=(10, 0))
        self.plot_btn = ttk.Button(plot_btn_frame, text="Generate Plot", command=self.generate_plot)
        self.plot_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.plot_btn.config(state="disabled")
        self.save_plot_btn = ttk.Button(plot_btn_frame, text="Save Plot", command=self.save_plot)
        self.save_plot_btn.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.save_plot_btn.config(state="disabled")
    
        # Right: Plot area (takes most of the space)
        self.plot_frame = ttk.LabelFrame(bottom_hsplit, text="Plot", padding=10)
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.plot_canvas = None
        self.current_figure = None
    
        # Bindings for both modes (will be updated in on_comparison_mode_changed)
        self.sessions_listbox.bind("<<ListboxSelect>>", self.on_sessions_selected)
        self.clubs_listbox.bind("<<ListboxSelect>>", self.on_club_selected)
    
        # Scan for available users on tab setup
        self.update_available_users()
        self.on_comparison_mode_changed()

    def on_user_selected(self, event):
        """Handle user selection in the analysis tab."""
        self.load_data_for_analysis()

    def on_sessions_selected(self, event):
        """Enable Continue button if at least one session is selected."""
        if self.sessions_listbox.curselection():
            self.continue_btn.config(state="normal")
        else:
            self.continue_btn.config(state="disabled")

    def on_continue_sessions(self):
        comparison_mode = self.comparison_mode_var.get()
        session_indices = self.sessions_listbox.curselection()
        self.clubs_listbox.config(state="normal")
        self.plot_btn.config(state="disabled")
        if not session_indices:
            messagebox.showwarning("Selection Required", "Please select at least one session.")
            return

        # Extract session IDs
        selected_sessions = []
        for idx in session_indices:
            session_text = self.sessions_listbox.get(idx)
            match = re.match(r"([^(]+\(Session \d+\))", session_text)
            if match:
                selected_sessions.append(match.group(1).strip())

        # Store for use in generate_plot
        if comparison_mode == "time":
            self.selected_sessions_for_time = selected_sessions
        else:
            self.selected_sessions_for_clubs = selected_sessions  # <-- store as list
    
        # Filter clubs based on selected sessions
        df = self.analysis_df.copy()
        df = df[df['Session ID'].isin(selected_sessions)]
        clubs_array = df['Club'].unique()
        all_clubs = []
        for club in clubs_array:
            if pd.notna(club) and club is not None:
                club_str = str(club)
                if not (club_str.startswith('-') or club_str.replace('.', '', 1).isdigit()):
                    all_clubs.append(club_str)
        all_clubs = sorted(all_clubs)
    
        # Populate clubs listbox
        self.clubs_listbox.config(state="normal")
        self.clubs_listbox.delete(0, tk.END)
        for club in all_clubs:
            club_data = df[df['Club'].astype(str) == club]
            club_shot_count = len(club_data)
            club_session_count = len(club_data['Session ID'].unique())
            self.clubs_listbox.insert(tk.END, f"{club} ({club_shot_count} shots across {club_session_count} sessions)")
    
        # Enable plot button only after a club is selected
        self.clubs_listbox.bind("<<ListboxSelect>>", self.on_club_selected)
        self.plot_btn.config(state="disabled")

    def on_club_selected(self, event):
        """Enable plot button when a club is selected."""
        if self.clubs_listbox.curselection():
            self.plot_btn.config(state="normal")
        else:
            self.plot_btn.config(state="disabled")

    def on_comparison_mode_changed(self):
        comparison_mode = self.comparison_mode_var.get()
        self.clubs_listbox.delete(0, tk.END)
        self.sessions_listbox.selection_clear(0, tk.END)
        self.plot_btn.config(state="disabled")
        self.clubs_listbox.config(state="disabled")
        self.continue_btn.config(state="disabled")
        if comparison_mode == "time":
            self.sessions_listbox.config(selectmode=tk.MULTIPLE)
            self.clubs_listbox.config(selectmode=tk.SINGLE, state="disabled")
            self.clubs_frame.configure(text="Select a Club")
            self.sessions_frame.configure(text="Select Sessions and Continue")
            self.sessions_listbox.bind("<<ListboxSelect>>", self.on_sessions_selected)
            self.clubs_listbox.bind("<<ListboxSelect>>", self.on_club_selected)
        else:
            self.sessions_listbox.config(selectmode=tk.MULTIPLE)
            self.clubs_listbox.config(selectmode=tk.MULTIPLE, state="disabled")
            self.clubs_frame.configure(text="Select Clubs")
            self.sessions_frame.configure(text="Select Sessions and Continue")
            self.sessions_listbox.bind("<<ListboxSelect>>", self.on_sessions_selected)
            self.clubs_listbox.bind("<<ListboxSelect>>", self.on_club_selected)
        self.load_data_for_analysis()

    def on_ball_type_selected(self, event):
        """Handle ball type selection in the analysis tab."""
        self.load_data_for_analysis()

    def on_closing(self):
        """Handle window close event to ensure application terminates properly"""
        self.destroy()
        sys.exit(0)  # Ensure any background threads are terminated

    def load_data_for_analysis(self):
        """Load sessions and clubs based on current selections."""
        username = self.user_var.get()
        ball_type = self.analysis_ball_type_var.get()
        
        if not username:
            return
            
        # Clear the selection listboxes
        self.sessions_listbox.delete(0, tk.END)
        self.clubs_listbox.delete(0, tk.END)
        
        # Construct data directory path with username and ball type
        data_dir = os.path.join('Data', username, ball_type)
        
        # Check if the directory exists
        if not os.path.exists(data_dir):
            self.log(f"Directory {data_dir} does not exist.")
            return
            
        # Scan the appropriate directory for CSV files
        file_pattern = "trackman_*.csv"
        csv_files = glob.glob(os.path.join(data_dir, file_pattern))
        
        if not csv_files:
            self.log(f"No {ball_type} ball data files found in {data_dir}")
            return
            
        self.log(f"Found {len(csv_files)} {ball_type} ball data files in {data_dir}")
        
        # Parse filenames to extract date and session information
        # Initialize an empty DataFrame to store all data
        df = pd.DataFrame()
        
        # Regular expression to extract date and session number
        file_pattern = re.compile(r'trackman_(\d+)_session(\d+)(?:_(?:range|premium|pro))?\.csv')
        
        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            match = file_pattern.match(file_name)
            
            if match:
                date_str, session_num = match.groups()
                
                # Read the CSV file with error handling
                try:
                    # Try to read with C engine first
                    temp_df = pd.read_csv(file_path, on_bad_lines='skip')
                except Exception as e:
                    self.log(f"Error reading {file_name}: {str(e)}")
                    try:
                        # Fall back to Python engine which is more forgiving
                        temp_df = pd.read_csv(file_path, engine='python')
                        self.log(f"Successfully read {file_name} using Python engine")
                    except Exception as e:
                        self.log(f"Failed to read {file_name}: {str(e)}")
                        continue
                
                # Add session metadata if not already present in the CSV
                if 'Session Date' not in temp_df.columns:
                    # Format date properly (assuming YYYYMMDD format in filename)
                    formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    temp_df['Session Date'] = formatted_date
                    temp_df['Session Number'] = session_num
                    temp_df['Ball Type'] = ball_type
                    temp_df['Username'] = username
                    
                    # Create a unique session identifier
                    temp_df['Session ID'] = f"{formatted_date} (Session {session_num})"
                    
                # Append to the main DataFrame
                df = pd.concat([df, temp_df], ignore_index=True)
            else:
                self.log(f"Skipping file with invalid naming format: {file_name}")
                
        # Check if we have data
        if df.empty:
            self.log("No valid data found in the CSV files")
            return
            
        # Save the loaded dataframe for later use
        self.analysis_df = df
        
        # Populate both listboxes regardless of mode
        
        # 1. Populate sessions listbox
        all_sessions = sorted(df['Session ID'].unique(), reverse=True)
        # Count shots per session
        session_shot_counts = {}
        for session in all_sessions:
            session_shot_counts[session] = len(df[df['Session ID'] == session])
        
        # Display available sessions
        for i, session in enumerate(all_sessions, 1):
            shot_count = session_shot_counts[session]
            self.sessions_listbox.insert(tk.END, f"{session} ({shot_count} shots)")
        
        # 2. Populate clubs listbox
        # Get all unique clubs, handling mixed types properly
        clubs_array = df['Club'].unique()
        # Filter out NaN values and convert to strings
        all_clubs = []
        for club in clubs_array:
            if pd.notna(club) and club is not None:
                club_str = str(club)
                # Skip numeric-looking values that aren't actual club names
                if not (club_str.startswith('-') or club_str.replace('.', '', 1).isdigit()):
                    all_clubs.append(club_str)
        
        all_clubs = sorted(all_clubs)
        
        # Display available clubs
        for i, club in enumerate(all_clubs, 1):
            # When filtering by club, also convert to string for comparison
            club_data = df[df['Club'].astype(str) == club]
            club_shot_count = len(club_data)
            club_session_count = len(club_data['Session ID'].unique())
            self.clubs_listbox.insert(tk.END, f"{club} ({club_shot_count} shots across {club_session_count} sessions)")
                
        # Update selection mode based on comparison mode
        comparison_mode = self.comparison_mode_var.get()
        if comparison_mode == "time":
            # Club Over Time mode - only allow single selection for clubs
            self.clubs_listbox.config(selectmode=tk.SINGLE)
        else:
            # Multiple Clubs mode - allow multiple selections
            self.clubs_listbox.config(selectmode=tk.MULTIPLE)
        
        self.log("Data loaded for analysis. Select options and click Generate Plot.")

    def refresh_analysis_data(self):
        """Refresh the analysis data and reload."""
        self.update_available_users()
        self.load_data_for_analysis()

    def on_sessions_or_clubs_selected(self, event=None):
        """Enable plot button if a session and at least one club are selected in clubs mode."""
        if self.comparison_mode_var.get() == "clubs":
            session_selected = bool(self.sessions_listbox.curselection())
            clubs_selected = bool(self.clubs_listbox.curselection())
            if session_selected and clubs_selected:
                self.plot_btn.config(state="normal")
            else:
                self.plot_btn.config(state="disabled")

    def generate_plot(self):
        """Generate plot based on current selections."""
        if not hasattr(self, 'analysis_df') or self.analysis_df.empty:
            messagebox.showwarning("No Data", "No data available for plotting.")
            return

        df = self.analysis_df  # Use the loaded dataframe
        username = self.user_var.get()
        ball_type = self.analysis_ball_type_var.get()
        plot_type = self.plot_type_var.get()
        comparison_mode = self.comparison_mode_var.get()

        # Create a new figure
        if self.current_figure:
            plt.close(self.current_figure)
        self.current_figure = plt.figure(figsize=(12, 8), dpi=120, constrained_layout=True)
        if comparison_mode == "time":
            # --- STEP 1: Get sessions selected at "Continue" ---
            # Assume you store the session IDs (e.g. "2025-05-16 (Session 1)") in self.selected_sessions_for_time
            selected_sessions = getattr(self, "selected_sessions_for_time", None)
            if not selected_sessions:
                messagebox.showwarning("Selection Required", "Please select sessions and click Continue.")
                return

            # --- STEP 2: Get selected club ---
            club_selections = self.clubs_listbox.curselection()
            if not club_selections:
                messagebox.showwarning("Selection Required", "Please select a club.")
                return
            club_idx = club_selections[0]
            club_text = self.clubs_listbox.get(club_idx)
            selected_club = club_text.split(" (")[0]  # Extract club name

            # Filter data for selected sessions and club
            df = df[df['Session ID'].isin(selected_sessions)]
            club_df = df[df['Club'].astype(str) == selected_club]

            if len(club_df) == 0:
                self.log(f"No data for {selected_club} in selected sessions")
                return

            self.current_plot_filename = f'{username}_{selected_club}_over_time_selected_sessions_{plot_type}_{ball_type}.png'

            all_sessions = sorted(club_df['Session ID'].unique(), reverse=True)
            colors = plt.cm.tab20.colors

            for i, session in enumerate(all_sessions, 1):
                session_data = club_df[club_df['Session ID'] == session]
                all_carry_values = session_data['carryActual'].dropna().astype(float)

                if len(all_carry_values) < 3:
                    self.log(f"Skipping {session}: only {len(all_carry_values)} shots")
                    continue

                self.log(f"{session}: {len(all_carry_values)} shots")

                if len(all_carry_values) > 4:
                    Q1 = np.percentile(all_carry_values, 25)
                    Q3 = np.percentile(all_carry_values, 75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    outlier_mask = (all_carry_values >= lower_bound) & (all_carry_values <= upper_bound)
                    carry_values = all_carry_values[outlier_mask]
                    outliers = all_carry_values[~outlier_mask]
                    n_outliers = len(outliers)
                    self.log(f"  - {n_outliers} outliers removed")
                else:
                    carry_values = all_carry_values
                    outliers = []

                if len(carry_values) > 1:
                    mu, std = norm.fit(carry_values)
                    # Format session label as "DD/MM,Sxx"
                    try:
                        date_part = session.split(' ')[0]
                        session_num = re.search(r'Session (\d+)', session)
                        if date_part and session_num:
                            date_fmt = datetime.strptime(date_part, "%Y-%m-%d").strftime("%d/%m")
                            session_label = f"{date_fmt},S{session_num.group(1)}"
                        else:
                            session_label = session
                    except Exception:
                        session_label = session
                    if plot_type == 'gaussian':
                        x = np.linspace(max(0, min(carry_values) * 0.8), max(carry_values) * 1.2, 1000)
                        pdf = norm.pdf(x, mu, std)
                        pdf_normalized = pdf / pdf.max()
                        plt.plot(
                            x, pdf_normalized,
                            label=f'{session_label}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                            color=colors[i % len(colors)+1],
                            linewidth=2.5,
                            #marker='o',
                            #markevery=80,
                            #markersize=4
                        )
                        plt.plot(carry_values, np.zeros_like(carry_values) - 0.02 * (i+1), '|',
                                color=colors[i % len(colors) +1], alpha=0.7, markersize=10)
                        if len(outliers) > 0:
                            plt.plot(outliers, np.zeros_like(outliers) - 0.02 * (i+1), 'x',
                                    color=colors[i % len(colors) +1], alpha=0.7, markersize=8)
                    else:
                        bins = np.arange(min(carry_values) - 5, max(carry_values) + 5, 5)
                        plt.hist(carry_values, bins=bins, alpha=0.6,
                                label=f'{session_label}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                                color=colors[i % len(colors) +1])

            if plot_type == 'gaussian':
                title = f'{selected_club} Carry Distance Over Time ({username}, {ball_type})'
                ylabel = 'Normalized Probability Density'
                plt.ylim(-0.02 * len(all_sessions) - 0.05, 1.1)
            else:
                title = f'{selected_club} Carry Distance Over Time ({username}, {ball_type})'
                ylabel = 'Number of Shots'
                
            if plot_type == 'gaussian':
                title = f'{selected_club} Carry Distance Over Time ({username}, {ball_type})'
                ylabel = 'Normalized Probability Density'
                plt.ylim(-0.02 * len(all_sessions) - 0.05, 1.1)
            else:
                title = f'{selected_club} Carry Distance Over Time ({username}, {ball_type})'
                ylabel = 'Number of Shots'

            # ... after plotting ...
            plt.xlabel('Carry Distance (m)', fontsize=11)
            plt.ylabel(ylabel, fontsize=11)
            plt.title(title, fontsize=13)
            plt.tick_params(axis='both', which='major', labelsize=10)
            plt.grid(True)
            plt.legend(fontsize=9, loc='best')  # Legend inside plot
            plt.xlim(0, 200)
            plt.tight_layout(pad=4)
            
            self.display_plot()
            self.save_plot_btn.config(state="normal")
                
        else:  #clubs comparison mode
            selected_sessions = getattr(self, "selected_sessions_for_clubs", None)
            if not selected_sessions:
                messagebox.showwarning("Selection Required", "Please select session(s) and click Continue.")
                return
            # Get selected clubs (can be multiple)
            club_indices = self.clubs_listbox.curselection()
            if not club_indices:
                messagebox.showwarning("Selection Required", "Please select at least one club.")
                return
            selected_clubs = [self.clubs_listbox.get(i).split(" (")[0] for i in club_indices]
        
            # Filter data to only include the selected sessions
            df = df[df['Session ID'].isin(selected_sessions)]
        
            # Prepare plot filename
            clubs_str = "_".join(selected_clubs)
            sessions_str = "_".join([s.replace(" ", "_") for s in selected_sessions])
            self.current_plot_filename = f'{username}_club_carry_{plot_type}_{sessions_str}_{clubs_str}_{ball_type}.png'
        
            # Plot for each selected club (combining all shots for that club across sessions)
            colors = plt.cm.tab20.colors
            stats = {}
            for i, club in enumerate(selected_clubs, 1):
                club_data = df[df['Club'] == club]
                all_carry_values = club_data['carryActual'].dropna().astype(float)
        
                if len(all_carry_values) < 1:
                    self.log(f"No data for {club}")
                    continue
        
                self.log(f"{club}: {len(all_carry_values)} shots")
        
                if len(all_carry_values) > 4:
                    Q1 = np.percentile(all_carry_values, 25)
                    Q3 = np.percentile(all_carry_values, 75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    outlier_mask = (all_carry_values >= lower_bound) & (all_carry_values <= upper_bound)
                    carry_values = all_carry_values[outlier_mask]
                    outliers = all_carry_values[~outlier_mask]
                    n_outliers = len(outliers)
                    self.log(f"  - {n_outliers} outliers removed")
                else:
                    carry_values = all_carry_values
                    outliers = []
        
                if len(carry_values) > 1:
                    mu, std = norm.fit(carry_values)
                    stats[club] = {'mean': mu, 'std': std}
                    if plot_type == 'gaussian':
                        x = np.linspace(max(0, min(carry_values) * 0.8), max(carry_values) * 1.2, 1000)
                        pdf = norm.pdf(x, mu, std)
                        pdf_normalized = pdf / pdf.max()
                        plt.plot(x, pdf_normalized,
                                 label=f'{club}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                                 color=colors[i % len(colors) +1],
                                 linewidth=2)
                        plt.plot(carry_values, np.zeros_like(carry_values) - 0.02 * (i+1), '|',
                                 color=colors[i % len(colors) +1], alpha=0.7, markersize=10)
                        if len(outliers) > 0:
                            plt.plot(outliers, np.zeros_like(outliers) - 0.02 * (i+1), 'x',
                                     color=colors[i % len(colors) +1], alpha=0.7, markersize=8)
                    else:
                        bins = np.arange(min(carry_values) - 5, max(carry_values) + 5, 5)
                        plt.hist(carry_values, bins=bins, alpha=0.6,
                                 label=f'{club}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                                 color=colors[i % len(colors) +1])
        
            # Set plot title and labels
            if plot_type == 'gaussian':
                title = f'Carry Distance by Club ({username}, {ball_type}, {"multiple sessions"})'
                ylabel = 'Normalized Probability Density'
                plt.ylim(-0.02 * len(selected_clubs) - 0.05, 1.1)
            else:
                title = f'Carry Distance by Club ({username}, {ball_type}, {"multiple sessions"})'
                ylabel = 'Number of Shots'
        
            plt.xlabel('Carry Distance (m)', fontsize=11)
            plt.ylabel(ylabel, fontsize=11)
            plt.title(title, fontsize=13)
            plt.tick_params(axis='both', which='major', labelsize=10)
            plt.grid(True)
            plt.legend(fontsize=9, loc='best')
            plt.xlim(0, 200)
            plt.tight_layout(pad=4)
        
            self.display_plot()
            self.save_plot_btn.config(state="normal")
        
    def display_plot(self):
        """Display the current matplotlib figure in the GUI."""
        if self.plot_canvas:
            self.plot_canvas.get_tk_widget().destroy()
        self.plot_canvas = FigureCanvasTkAgg(self.current_figure, master=self.plot_frame)
        self.plot_canvas.draw()
        self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def save_plot(self):
        """Save the current plot to a file."""
        if not self.current_figure:
            return
            
        # Create plots directory for user if it doesn't exist
        username = self.user_var.get()
        plots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots', username)
        if not os.path.exists(plots_dir):
            os.makedirs(plots_dir, exist_ok=True)
            
        # Full path to save file
        output_filename = os.path.join(plots_dir, self.current_plot_filename)
        
        # Ask for save location
        filepath = filedialog.asksaveasfilename(
            initialdir=plots_dir,
            initialfile=self.current_plot_filename,
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        
        if filepath:
            # Save the plot
            self.current_figure.savefig(filepath, dpi=300)
            self.log(f"Plot saved to {filepath}")

    def load_saved_tokens(self):
        self.available_tokens = trackman.check_saved_tokens()
        self.token_listbox.delete(0, tk.END)
        
        if self.available_tokens:
            for username in self.available_tokens.keys():
                self.token_listbox.insert(tk.END, username)
            self.log("Found saved tokens. Select a user or login as new.")
        else:
            self.log("No saved tokens found. Please login.")
        
        # Update user dropdown in analysis tab
        self.update_available_users()

    def use_selected_token(self):
        selection = self.token_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select a user from the list.")
            return
        
        idx = selection[0]
        username = self.token_listbox.get(idx)
        self.selected_username = username
        self.selected_token = self.available_tokens[username]
        
        self.log(f"Using saved token for {username}")
        self.status_var.set(f"Logged in as {username}")
        
        # Set the token in the API
        self.api.auth_token = self.selected_token
        self.api.headers["Authorization"] = f"Bearer {self.selected_token}"
        
        # Test if the token is still valid
        if self.api.test_connection():
            self.log("Token is valid, authentication successful!")
            self.fetch_activities()
            self.notebook.select(1)  # Switch to activities tab
        else:
            self.log("Token is no longer valid, please login again.")
            self.selected_token = None
            self.selected_username = None

    def update_available_users(self):
        """Update the user dropdown with available users."""
        if hasattr(self, "user_combo"):
            users = list(self.available_tokens.keys()) if hasattr(self, "available_tokens") else []
            self.user_combo['values'] = users
            if users:
                self.user_combo.current(0)

    def start_new_login(self):
        self.log("Starting browser login...")
        
        def login_thread_func():
            success = self.api.login(None, None)
            if success and self.api.auth_token:
                self.after(100, lambda: self.handle_successful_login())
            else:
                self.after(100, lambda: self.log("Authentication failed"))

        threading.Thread(target=login_thread_func).start()

    def handle_successful_login(self):
        self.log("Authentication successful!")
        self.save_username_btn.config(state="normal")
        self.fetch_activities()
        self.notebook.select(1)  # Switch to activities tab

    def save_token(self):
        username = self.username_var.get().strip()
        if not username:
            messagebox.showwarning("Input Required", "Please enter a username to save the token.")
            return
            
        if not self.api.auth_token:
            messagebox.showwarning("Login Required", "You need to login first.")
            return
            
        trackman.save_token(self.api.auth_token, username)
        self.selected_username = username
        self.log(f"Token saved for {username}")
        self.status_var.set(f"Logged in as {username}")
        self.load_saved_tokens()

    def logout_selected(self):
        selection = self.token_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select a user to logout.")
            return
            
        idx = selection[0]
        username = self.token_listbox.get(idx)
        
        trackman.invalidate_token(username)
        self.log(f"Logged out {username}")
        
        if username == self.selected_username:
            self.selected_username = None
            self.selected_token = None
            self.status_var.set("Ready")
            
        self.load_saved_tokens()

    def logout_all(self):
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to logout all users?"):
            trackman.invalidate_token()
            self.log("Logged out all users")
            self.selected_username = None
            self.selected_token = None
            self.status_var.set("Ready")
            self.load_saved_tokens()

    def fetch_activities(self):
        if not self.api.auth_token:
            messagebox.showwarning("Login Required", "Please login first.")
            return
            
        self.log("Fetching activities...")
        
        def fetch_thread():
            activities = self.api.get_activity_list(limit=20)
            
            if not activities:
                self.after(100, lambda: self.log("No activities found"))
                return
                
            # Filter for RANGE_PRACTICE activities
            range_activities = [act for act in activities if act.get("kind") == "RANGE_PRACTICE"]
            self.activities = range_activities
            
            self.after(100, lambda: self.update_activity_list())
            
        threading.Thread(target=fetch_thread).start()

    def update_activity_list(self):
        # Clear current items
        for item in self.activity_tree.get_children():
            self.activity_tree.delete(item)

        # Sort activities chronologically (oldest first)
        self.activities = sorted(self.activities, key=lambda x: x.get("time", ""))

        # Add activities to treeview in chronological order with shot counts
        for i, activity in enumerate(self.activities):
            activity_time = activity.get("time", "Unknown date")
            try:
                dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = activity_time[:16].replace('T', ' ')
                
            activity_type = activity.get("kind", "Unknown")
            
            # Get the total shot count from the activity data
            total_shots = activity.get("totalCount", 0)
            
            # Display with shot count
            display_text = f"{activity_type} ({total_shots} shots)"
            
            # Now session number (i+1) corresponds to chronological order
            self.activity_tree.insert("", tk.END, values=(i+1, date_str, display_text))
            
        self.log(f"Found {len(self.activities)} range practice activities (sorted chronologically)")

    def download_selected(self):
        selection = self.activity_tree.selection()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select an activity to download.")
            return
            
        item = selection[0]
        idx = int(self.activity_tree.item(item, "values")[0]) - 1
        
        if idx < 0 or idx >= len(self.activities):
            self.log("Invalid selection")
            return
            
        selected_activity = self.activities[idx]
        ball_type = self.ball_type_var.get()
        
        self.log(f"Processing activity {idx+1} for {ball_type} balls...")
        
        def download_thread():
            if ball_type == "BOTH":
                # Process both PREMIUM and RANGE balls
                shot_data_pro = self.api.get_range_practice_shots(selected_activity.get('id'), "PREMIUM")
                pro_shots = shot_data_pro.get("shots", []) if shot_data_pro else []
                
                # Add session info
                for shot in pro_shots:
                    shot["session_number"] = idx + 1
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                shot_data_range = self.api.get_range_practice_shots(selected_activity.get('id'), "RANGE")
                range_shots = shot_data_range.get("shots", []) if shot_data_range else []
                
                # Add session info
                for shot in range_shots:
                    shot["session_number"] = idx + 1
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                self.after(100, lambda: self.log(f"Retrieved {len(pro_shots)} premium shots and {len(range_shots)} range shots"))
                
                # Save directly
                self.ask_save_shots(shot_data_pro, shot_data_range)
            else:
                # Process single ball type
                shot_data = self.api.get_range_practice_shots(selected_activity.get('id'), ball_type)
                
                if not shot_data:
                    self.after(100, lambda: self.log("Failed to retrieve shot data"))
                    return
                
                # Add session info
                shots = shot_data.get("shots", [])
                for shot in shots:
                    shot["session_number"] = idx + 1
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                self.after(100, lambda: self.log(f"Retrieved {len(shots)} shots"))
                
                # Save directly
                self.ask_save_single(shot_data, ball_type)
        
        threading.Thread(target=download_thread).start()

    def download_all(self):
        if not self.activities:
            messagebox.showwarning("No Activities", "No activities available to download.")
            return
            
        ball_type = self.ball_type_var.get()
        self.log(f"Processing all activities for {ball_type} balls...")
        
        def download_thread():
            if ball_type == "BOTH":
                all_shot_data_pro = []
                all_shot_data_range = []
                
                for idx, activity in enumerate(self.activities):
                    self.after(100, lambda i=idx: self.log(f"Processing activity {i+1}/{len(self.activities)}..."))
                    
                    # Process PREMIUM balls
                    shot_data_pro = self.api.get_range_practice_shots(activity.get('id'), "PREMIUM")
                    if shot_data_pro and shot_data_pro.get("shots"):
                        shots = shot_data_pro.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_pro.append(shot_data_pro)
                        self.after(100, lambda i=idx, n=len(shots): self.log(f"Activity {i+1}: Downloaded {n} PREMIUM ball shots"))
                    
                    # Process RANGE balls
                    shot_data_range = self.api.get_range_practice_shots(activity.get('id'), "RANGE")
                    if shot_data_range and shot_data_range.get("shots"):
                        shots = shot_data_range.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_range.append(shot_data_range)
                        self.after(100, lambda i=idx, n=len(shots): self.log(f"Activity {i+1}: Downloaded {n} RANGE ball shots"))
                
                # Save directly
                self.ask_save_all(all_shot_data_pro, all_shot_data_range)
            else:
                # Process for single ball type
                all_shot_data = []
                
                for idx, activity in enumerate(self.activities):
                    self.after(100, lambda i=idx: self.log(f"Processing activity {i+1}/{len(self.activities)}..."))
                    
                    shot_data = self.api.get_range_practice_shots(activity.get('id'), ball_type)
                    
                    if shot_data:
                        shots = shot_data.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        
                        all_shot_data.append(shot_data)
                        self.after(100, lambda i=idx, n=len(shots): self.log(f"Activity {i+1}: Downloaded {n} {ball_type} ball shots"))
                
                # Save directly
                self.ask_save_all_single(all_shot_data, ball_type)
        
        threading.Thread(target=download_thread).start()

    def analyze_data(self):
        """Switch to the Analysis tab and refresh data."""
        self.notebook.select(2)  # Switch to Analysis tab (index 2)
        self.update_available_users()

    def download_missing(self):
        if not self.activities:
            messagebox.showwarning("No Activities", "No activities available to check for missing sessions.")
            return
        
        ball_type = self.ball_type_var.get()
        if ball_type != "BOTH":
            ball_type = "BOTH"  # Always check both types when looking for missing
            self.ball_type_var.set("BOTH")
            
        self.log("Checking for missing sessions...")
        
        def download_thread():
            # Get existing sessions
            existing_pro_sessions, existing_range_sessions = trackman.get_existing_sessions(self.selected_username)
            
            # Find missing activities
            missing_activities = []
            
            for idx, activity in enumerate(self.activities):
                # Convert activity time to date string
                activity_time = activity.get("time", "")
                activity_date = ""
                
                if activity_time:
                    try:
                        dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                        activity_date = dt.strftime("%Y%m%d")
                    except:
                        continue
                
                # Session number is now correctly idx + 1 (oldest = 1)
                session_num = str(idx + 1)
                
                # Check which sessions are missing
                pro_missing = (activity_date, session_num) not in existing_pro_sessions
                range_missing = (activity_date, session_num) not in existing_range_sessions
                
                if pro_missing or range_missing:
                    missing_balls = []
                    if pro_missing:
                        missing_balls.append("PREMIUM")
                    if range_missing:
                        missing_balls.append("RANGE")
                        
                    missing_ball_str = "/".join(missing_balls)
                    self.after(100, lambda a=activity, b=missing_ball_str: 
                              self.log(f"Missing: {a.get('kind')} - {a.get('time')[:10]} ({b})"))
                    
                    missing_activities.append((idx, activity, missing_balls))
            
            if not missing_activities:
                self.after(100, lambda: self.log("All sessions are already saved. No missing sessions found."))
                return
                
            self.ask_download_missing(missing_activities, len(missing_activities))
                
        threading.Thread(target=download_thread).start()

    def ask_save_shots(self, shot_data_pro, shot_data_range):
        # Remove the confirmation dialog and directly save
        if shot_data_pro and shot_data_pro.get("shots"):
            self.api.save_shots_to_csv(shot_data_pro, ball_type="PREMIUM", username=self.selected_username)
            self.log(f"Saved premium ball data")
            
        if shot_data_range and shot_data_range.get("shots"):
            self.api.save_shots_to_csv(shot_data_range, ball_type="RANGE", username=self.selected_username)
            self.log(f"Saved range ball data")

    def ask_save_single(self, shot_data, ball_type):
        # Remove the confirmation dialog and directly save
        self.api.save_shots_to_csv(shot_data, ball_type=ball_type, username=self.selected_username)
        self.log(f"Saved {ball_type} ball data")

    def ask_save_all(self, all_shot_data_pro, all_shot_data_range):
        # Remove the confirmation dialog and directly save
        if all_shot_data_pro:
            self.api.save_combined_shots_to_csv(all_shot_data_pro, ball_type="PREMIUM", username=self.selected_username)
            self.log("Saved all premium ball data")
            
        if all_shot_data_range:
            self.api.save_combined_shots_to_csv(all_shot_data_range, ball_type="RANGE", username=self.selected_username)
            self.log("Saved all range ball data")

    def ask_save_all_single(self, all_shot_data, ball_type):
        # Remove the confirmation dialog and directly save
        self.api.save_combined_shots_to_csv(all_shot_data, ball_type=ball_type, username=self.selected_username)
        self.log(f"Saved all {ball_type} ball data")

    def ask_download_missing(self, missing_activities, count):
        # Remove the confirmation dialog and directly download/save
        def process_thread():
            all_shot_data_pro = []
            all_shot_data_range = []
            
            for idx, activity, missing_types in missing_activities:
                self.after(100, lambda i=idx: self.log(f"Processing activity {i+1}/{len(missing_activities)}..."))
                
                # Process PREMIUM balls if needed
                if "PREMIUM" in missing_types:
                    shot_data_pro = self.api.get_range_practice_shots(activity.get('id'), "PREMIUM")
                    if shot_data_pro and shot_data_pro.get("shots"):
                        shots = shot_data_pro.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_pro.append(shot_data_pro)
                        self.after(100, lambda i=idx, n=len(shots): 
                                 self.log(f"Activity {i+1}: Downloaded {n} PREMIUM ball shots"))
                
                # Process RANGE balls if needed
                if "RANGE" in missing_types:
                    shot_data_range = self.api.get_range_practice_shots(activity.get('id'), "RANGE")
                    if shot_data_range and shot_data_range.get("shots"):
                        shots = shot_data_range.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_range.append(shot_data_range)
                        self.after(100, lambda i=idx, n=len(shots): 
                                 self.log(f"Activity {i+1}: Downloaded {n} RANGE ball shots"))
            
            # Save the data
            if all_shot_data_pro:
                self.api.save_combined_shots_to_csv(all_shot_data_pro, ball_type="PREMIUM", username=self.selected_username)
                self.after(100, lambda: self.log("Saved missing premium ball data"))
            
            if all_shot_data_range:
                self.api.save_combined_shots_to_csv(all_shot_data_range, ball_type="RANGE", username=self.selected_username)
                self.after(100, lambda: self.log("Saved missing range ball data"))
        
        threading.Thread(target=process_thread).start()

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        print(message)  # Also print to console for debugging

if __name__ == "__main__":
    app = TrackManGUI()
    app.mainloop()