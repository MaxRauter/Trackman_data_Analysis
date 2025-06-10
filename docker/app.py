# app.py
import dash
from dash import dcc, html, Output, Input, State, ctx, dash_table
import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
import os
import re
import importlib.util
from datetime import datetime
import threading
import numpy as np
from pathlib import Path
import base64
import io
import zipfile

# Import the trackman module for authentication - with comprehensive error handling
TRACKMAN_AVAILABLE = False
try:
    spec = importlib.util.spec_from_file_location("trackman", "trackman.py")
    trackman = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trackman)
    TRACKMAN_AVAILABLE = True
    print("✅ trackman.py loaded successfully - Login and download features available")
except (FileNotFoundError, ModuleNotFoundError, ImportError, AttributeError) as e:
    print(f"⚠️  trackman.py or its dependencies not available: {e}")
    print("ℹ️  Running in Analysis-Only mode - Login and data download features disabled")
    TRACKMAN_AVAILABLE = False
    
    # Create a comprehensive dummy trackman module
    class DummyTrackman:
        TOKEN_DIR = os.path.join(str(Path.home()), "tokens")
        
        def check_saved_tokens(self):
            return {}
        
        def invalidate_token(self, username=None):
            pass
        
        class TrackManAPI:
            def __init__(self):
                self.auth_token = None
                self.headers = {}
            
            def test_connection(self):
                return False
            
            def get_activity_list(self, limit=20):
                return []
            
            def get_range_practice_shots(self, activity_id, ball_type):
                return {"shots": []}
            
            def save_shots_to_csv(self, shot_data, ball_type, username):
                pass
        
        def get_existing_sessions(self, username):
            return set(), set()
    
    trackman = DummyTrackman()
except Exception as e:
    print(f"❌ ERROR loading trackman.py: {e}")
    TRACKMAN_AVAILABLE = False
    
    # Same dummy implementation
    class DummyTrackman:
        TOKEN_DIR = os.path.join(str(Path.home()), "tokens")
        def check_saved_tokens(self):
            return {}
        def invalidate_token(self, username=None):
            pass
        class TrackManAPI:
            def __init__(self):
                self.auth_token = None
                self.headers = {}
            def test_connection(self):
                return False
            def get_activity_list(self, limit=20):
                return []
            def get_range_practice_shots(self, activity_id, ball_type):
                return {"shots": []}
            def save_shots_to_csv(self, shot_data, ball_type, username):
                pass
        def get_existing_sessions(self, username):
            return set(), set()
    
    trackman = DummyTrackman()

# Add a global variable to store the home directory
HOME_DIR = str(Path.home())  # Default to user's home directory

def get_home_dir():
    """Get the current home directory setting"""
    global HOME_DIR
    return HOME_DIR

def set_home_dir(path):
    """Set the home directory for tokens and data storage"""
    global HOME_DIR
    if os.path.exists(path):
        HOME_DIR = path
        return True
    return False

# Update the load_data function to use the home directory
def load_data(username, ball_type, home_dir=None):
    # Check for uploaded data first
    uploaded_df = load_uploaded_data(username)
    if not uploaded_df.empty:
        print(f"DEBUG: Using uploaded data for {username} (ball_type ignored)")
        return uploaded_df
    
    if home_dir is None:
        home_dir = get_home_dir()
    
    data_dir = os.path.join(home_dir, 'Data', username, ball_type)
    if not os.path.exists(data_dir):
        return pd.DataFrame()

    file_pattern = re.compile(r'trackman_(\d+)_session(\d+)(?:_(?:range|premium|pro))?\.csv')
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    df_list = []

    for file_name in csv_files:
        match = file_pattern.match(file_name)
        if not match:
            continue
        date_str, session_num = match.groups()
        file_path = os.path.join(data_dir, file_name)
        try:
            temp_df = pd.read_csv(file_path, on_bad_lines='skip')
        except Exception:
            try:
                temp_df = pd.read_csv(file_path, engine='python')
            except Exception:
                continue

        # Add session metadata if not already present
        if 'Session Date' not in temp_df.columns:
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            temp_df['Session Date'] = formatted_date
            temp_df['Session Number'] = session_num
            temp_df['Ball Type'] = ball_type
            temp_df['Username'] = username
            temp_df['Session ID'] = f"{formatted_date} (Session {session_num})"

        df_list.append(temp_df)

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
    else:
        df = pd.DataFrame()
    return df

# Update the get_available_users function to use home directory
def get_available_users(home_dir=None):
    if home_dir is None:
        home_dir = get_home_dir()
        
    data_root = os.path.join(home_dir, "Data")
    if not os.path.exists(data_root):
        return []
    return [d for d in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, d))]

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("TrackMan Golf Data Analysis (Dash)"),
    
    # Store components for data persistence
    dcc.Store(id="activities-store", data=[]),
    dcc.Store(id="selected-username-store", data=""),
    dcc.Store(id="filtered-data-store", data=[]),
    dcc.Store(id="home-dir-store", data=str(Path.home())),  # Add this line
    dcc.Store(id="current-token-store", data=None),
    
    dcc.Download(id="download-data"),
    
    # Tabs
    dcc.Tabs(id="main-tabs", value="login", children=[
        # Login Tab
        dcc.Tab(label="Login", value="login", children=[
            html.Div([
                # Home Directory Setting Section
                html.Div([
                    html.H4("Home Directory Settings"),
                    html.Div([
                        html.Label("Home Directory:", style={'margin-right': '10px'}),
                        dcc.Input(
                            id="home-dir-input",
                            type="text",
                            placeholder=f"Enter full path (e.g., {str(Path.home() / 'Golf')})",
                            value=str(Path.home()),
                            style={'width': '500px', 'margin-right': '10px'}
                        ),
                        html.Button("Set Directory", id="set-home-dir-btn"),
                    ], style={'margin-bottom': '10px'}),
                    html.Div([
                        html.Button("Reset to Default", id="reset-home-dir-btn"),
                    ], style={'margin-bottom': '10px'}),
                    html.Div(id="home-dir-status", style={'color': 'green', 'font-weight': 'bold', 'margin-bottom': '20px'}),
                    html.Hr(),
                ]),
                
                html.H3("Saved Logins"),
                html.Div([
                    dcc.Dropdown(
                        id="token-dropdown",
                        placeholder="Select saved user",
                        style={'width': '300px', 'margin-bottom': '10px'}
                    ),
                    html.Div([
                        html.Button("Use Selected Token", id="use-token-btn", style={'margin-right': '10px'}),
                        html.Button("New Login", id="new-login-btn", style={'margin-right': '10px'}),
                        html.Button("Logout Selected", id="logout-btn", style={'margin-right': '10px'}),
                        html.Button("Logout All", id="logout-all-btn"),
                    ], style={'margin-bottom': '20px'}),
                    html.Div([
                        html.Label("Username/Email:", style={'margin-right': '10px'}),
                        dcc.Input(
                            id="username-in",
                            type="text",
                            placeholder="Enter username or email",
                            style={'width': '200px', 'margin-right': '10px'}
                        ),
                    ], style={'margin-bottom': '10px'}),
                    html.Div([
                        html.Label("Password:", style={'margin-right': '10px'}),
                        dcc.Input(
                            id="password-in",
                            type="password",  # <-- This masks the input
                            placeholder="Enter password",
                            style={'width': '200px', 'margin-right': '10px'}
                        ),
                    ], style={'margin-bottom': '10px'}),
                    html.H4("Save New Token"),
                    html.Div([
                        html.Label("Username/Email:", style={'margin-right': '10px'}),
                        dcc.Input(
                            id="username-input",
                            type="text",
                            placeholder="Enter username or email",
                            style={'width': '200px', 'margin-right': '10px'}
                        ),
                        html.Button("Save Token", id="save-token-btn", disabled=True),
                    ], style={'margin-bottom': '20px'}),
                    
                    html.Div(id="login-status", style={'color': 'blue', 'font-weight': 'bold'}),
                ])
            ], style={'padding': '20px'})
        ]),
        
        # Activities Tab
        dcc.Tab(label="Activities", value="activities", children=[
            html.Div([
                html.H3("Ball Type"),
                dcc.Dropdown(
                    id="ball-type-dropdown",
                    options=[
                        {"label": "PREMIUM", "value": "PREMIUM"},
                        {"label": "RANGE", "value": "RANGE"},
                        {"label": "BOTH", "value": "BOTH"},
                    ],
                    value="PREMIUM",
                    clearable=False,
                    style={"width": "200px", "margin-bottom": "10px"}
                ),
                html.Button("Refresh Activities", id="refresh-activities-btn", style={'margin-bottom': '20px'}),
                
                html.H4("Range Practice Activities"),
                dash_table.DataTable(
                    id="activities-table",
                    columns=[
                        {"name": "#", "id": "ID"},
                        {"name": "Date", "id": "Date"},
                        {"name": "Type", "id": "Type"},
                    ],
                    row_selectable="single",
                    selected_rows=[],
                    style_table={"overflowX": "auto"},
                    style_cell={'textAlign': 'left'},
                    style_data_conditional=[
                        {
                            'if': {'row_index': 'odd'},
                            'backgroundColor': 'rgb(248, 248, 248)'
                        }
                    ],
                    style_header={
                        'backgroundColor': 'rgb(230, 230, 230)',
                        'fontWeight': 'bold'
                    },
                    page_current=0,
                    page_size=10
                ),
                
                html.Br(),
                html.Div([
                    html.Button("Download Selected", id="download-selected-btn", style={'margin-right': '10px'}),
                    html.Button("Download All", id="download-all-btn", style={'margin-right': '10px'}),
                ], style={'margin-bottom': '20px'}),
                
                html.Div(id="activities-log", style={
                    'background-color': '#f0f0f0',
                    'border': '1px solid #ccc',
                    'padding': '10px',
                    'height': '200px',
                    'overflow-y': 'scroll',
                    'font-family': 'monospace',
                    'white-space': 'pre-wrap'
                })
            ], style={'padding': '20px'})
        ]),
        
        # Analysis Tab
        dcc.Tab(label="Analysis", value="analysis", children=[
            html.Div([
                # User selection and CSV upload side by side
                html.Div([
                    html.Div([
                        html.Label("User:"),
                        dcc.Dropdown(id='user-dropdown', style={'width': '200px'}),
                    ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top'}),
                    
                    html.Div([
                        html.Label("Upload CSV Files:"),
                        dcc.Upload(
                            id='upload-golf-data',
                            children=html.Div([
                                'Drag & Drop or ',
                                html.A('Select Files')
                            ]),
                            style={
                                'width': '100%',
                                'height': '50px',
                                'lineHeight': '50px',
                                'borderWidth': '1px',
                                'borderStyle': 'dashed',
                                'borderRadius': '5px',
                                'textAlign': 'center',
                                'backgroundColor': '#f9f9f9',
                                'fontSize': '14px'
                            },
                            multiple=True,
                            accept='.csv'
                        ),
                        html.Div([
                            html.Button("Clear All Uploads", id='clear-uploads-btn', 
                                    style={'margin-top': '5px', 'margin-right': '10px', 
                                            'background-color': '#dc3545', 'color': 'white', 
                                            'border': 'none', 'padding': '5px 10px', 'border-radius': '3px'}),
                            html.Button("Show Upload Info", id='show-upload-info-btn',
                                    style={'margin-top': '5px', 'background-color': '#17a2b8', 
                                            'color': 'white', 'border': 'none', 'padding': '5px 10px', 
                                            'border-radius': '3px'})
                        ]),
                    ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top', 'margin-left': '4%'}),
                ], style={'margin-bottom': '10px'}),
                
                # Upload status
                html.Div(id='upload-status', style={'margin-bottom': '10px', 'color': 'green', 'font-weight': 'bold'}),


                html.Div([
                    html.Label("Ball Type:"),
                    dcc.RadioItems(
                        id='ball-type-radio',
                        options=[{'label': 'Range', 'value': 'range'}, {'label': 'Premium', 'value': 'premium'}],
                        value='range',
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    ),
                    html.Small(
                        "Note: Ball type selection is disabled when using uploaded files", 
                        style={'color': 'gray', 'font-style': 'italic', 'margin-left': '10px'}
                    )
                ], style={'margin-bottom': '20px'}),
                
                html.Div([
                    html.Label("Comparison:"),
                    dcc.RadioItems(
                        id='comparison-radio',
                        options=[
                            {'label': 'Multiple Clubs', 'value': 'clubs'},
                            {'label': 'Club Over Time', 'value': 'time'}
                        ],
                        value='clubs',
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    ),
                    html.Label("Plot Type:"),
                    dcc.RadioItems(
                        id='plot-type-radio',
                        options=[
                            {'label': 'Gaussian', 'value': 'gaussian'},
                            {'label': 'Single Datapoints', 'value': 'histogram'}
                        ],
                        value='gaussian',
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    ),
                ], style={'margin-bottom': '20px'}),
                
                html.Div([
                    html.Label("Sessions:"),
                    html.Div([
                        dcc.Dropdown(id='session-dropdown', multi=True, style={'width': '85%', 'display': 'inline-block'}),
                        html.Button("Select All", id='select-all-sessions-btn', style={'width': '15%', 'display': 'inline-block'})
                    ]),
                    html.Label("Clubs:"),
                    html.Div([
                        dcc.Dropdown(id='club-dropdown', multi=True, style={'width': '85%', 'display': 'inline-block'}),
                        html.Button("Select All", id='select-all-clubs-btn', style={'width': '15%', 'display': 'inline-block'})
                    ]),
                    html.Label("Attribute to Plot:"),
                    dcc.Dropdown(
                        id='attribute-dropdown',
                        placeholder="Select attribute to analyze",
                        style={'width': '300px', 'display': 'inline-block', 'margin-right': '20px'}
                    ),
                ], style={'margin-bottom': '20px'}),
                html.Div(
                    id="custom-xy-div",
                    children=[
                        html.Label("Custom X Axis:"),
                        dcc.Dropdown(id="custom-x-dropdown", style={'width': '250px', 'display': 'inline-block', 'margin-right': '20px'}),
                        html.Label("Custom Y Axis:"),
                        dcc.Dropdown(id="custom-y-dropdown", style={'width': '250px', 'display': 'inline-block'}),
                        html.Button("Swap", id="swap-xy-btn", style={
                        'margin-left': '10px', 
                        'padding': '5px 15px', 
                        'background-color': '#007bff', 
                        'color': 'white', 
                        'border': 'none', 
                        'border-radius': '4px',
                        'cursor': 'pointer'
                    }),
                    ],
                    style={'margin-bottom': '20px', 'display': 'none'}  # hidden by default
                ),
                html.Button("Generate Plot", id='plot-btn', n_clicks=0),
                dcc.Loading(dcc.Graph(id='analysis-plot'), type="circle"),
                
                # New table for selected shots
                html.Div([
                    html.H4("Selected Shots"),
                    html.Div([
                        html.Button("Remove Mishits", id='remove-mishits-btn', 
                                    style={'margin-right': '10px', 'margin-bottom': '10px', 'background-color': '#ff6b6b', 'color': 'white', 'border': 'none', 'padding': '8px 16px', 'border-radius': '4px'}),
                        html.Button("Reset All Shots", id='reset-all-shots-btn', 
                                    style={'margin-bottom': '10px', 'background-color': '#28a745', 'color': 'white', 'border': 'none', 'padding': '8px 16px', 'border-radius': '4px'}),
                    ]),
                    dash_table.DataTable(
                        id="selected-shots-table",
                        columns=[
                            {"name": "Session", "id": "Session"},
                            {"name": "Club", "id": "Club"},
                            {"name": "Carry (m)", "id": "Carry", "type": "numeric"},
                            {"name": "Carry Side (m)", "id": "CarrySide", "type": "numeric"},
                            {"name": "Total (m)", "id": "totalActual", "type": "numeric"},
                            {"name": "Curve (m)", "id": "curveActual", "type": "numeric"},
                            {"name": "Height (m)", "id": "maxHeight", "type": "numeric"},
                            {"name": "Ball Speed (km/h)", "id": "ballSpeed", "type": "numeric"},
                            {"name": "Spin Rate (rpm)", "id": "ballSpin", "type": "numeric"},
                            {"name": "Spin Axis (°)", "id": "spinAxis", "type": "numeric"},
                            {"name": "Launch Angle (°)", "id": "LaunchAngle", "type": "numeric"},
                            {"name": "Delete", "id": "Delete", "presentation": "markdown"}
                        ],
                        data=[],  # Will be populated by callback
                        sort_action="native",  # Enable native sorting
                        sort_mode="multi",
                        style_table={"overflowX": "auto"},
                        style_cell={'textAlign': 'left'},
                        style_cell_conditional=[
                            # Column-specific widths
                            {
                                'if': {'column_id': 'Session'},
                                'width': '180px'
                            },
                            {
                                'if': {'column_id': 'Club'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'Carry'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'CarrySide'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'totalActual'},
                                'width': '60px'
                            },
                            {   'if': {'column_id': 'Curve'},
                                'width': '60px'
                            },
                            {   'if': {'column_id': 'spinAxis'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'maxHeight'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'ballSpeed'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'ballSpin'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'LaunchAngle'},
                                'width': '60px'
                            },
                            {
                                'if': {'column_id': 'Delete'},
                                'width': '60px',
                                'textAlign': 'center'
                            }
                        ],
                        style_data_conditional=[
                            {
                                'if': {'row_index': 'odd'},
                                'backgroundColor': 'rgb(248, 248, 248)'
                            },
                            {
                                'if': {
                                    'filter_query': '{deleted} = true',
                                },
                                'backgroundColor': 'rgb(255, 220, 220)',  # Light red for deleted shots
                                'color': 'rgb(128, 128, 128)',
                                'textDecoration': 'line-through'
                            }
                        ],
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'fontWeight': 'bold'
                        },
                        page_current=0,
                        page_size=30  # Limit to 10 rows per page
                    )
                ], style={'margin-top': '20px'}),
            ], style={'padding': '20px'})
        ])
    ])
])

# Login callbacks
@app.callback(
    Output("token-dropdown", "options"),
    Output("token-dropdown", "value"),
    Input("main-tabs", "value"),
    Input("home-dir-store", "data"),  # Add this input
)
def update_token_dropdown(active_tab, home_dir):
    if active_tab == "login":
        # Update trackman module to use the custom home directory BEFORE checking tokens
        if home_dir and home_dir != str(Path.home()):
            # Set the token directory in the trackman module
            trackman.TOKEN_DIR = os.path.join(home_dir, "tokens")
        else:
            # Reset to default if using home directory
            trackman.TOKEN_DIR = os.path.join(str(Path.home()), "tokens")
        
        # Now check for tokens in the correct directory
        tokens = trackman.check_saved_tokens()
        options = [{'label': username, 'value': username} for username in tokens.keys()]
        return options, None
    return [], None

@app.callback(
    Output("login-status", "children"),
    Output("save-token-btn", "disabled"),
    Output("selected-username-store", "data"),
    Output("main-tabs", "value"),  # Add this to control tab switching
    Output("activities-table", "data", allow_duplicate=True),  # Add this to update activities
    Output("activities-store", "data", allow_duplicate=True),  # Add this to store activities
    Output("activities-log", "children", allow_duplicate=True),  # Add this to show log
    Output("current-token-store", "data"),
    Input("use-token-btn", "n_clicks"),
    Input("new-login-btn", "n_clicks"),
    Input("logout-btn", "n_clicks"),
    Input("logout-all-btn", "n_clicks"),
    Input("save-token-btn", "n_clicks"),
    State("token-dropdown", "value"),
    State("username-input", "value"),
    State("username-in", "value"),
    State("password-in", "value"), 
    State("home-dir-store", "data"),
    prevent_initial_call=True
)
def handle_login_actions(use_token, new_login, logout, logout_all, save_token, selected_user, username_input, username, password,home_dir):
    triggered = ctx.triggered_id
    status = ""
    save_disabled = True
    selected_username = ""
    current_tab = "login"  # Default to login tab
    activities_table = []
    activities_store = []
    activities_log = ""
    
    # Set the home directory for token operations FIRST
    if home_dir:
        trackman.TOKEN_DIR = os.path.join(home_dir, "tokens")
    else:
        trackman.TOKEN_DIR = os.path.join(str(Path.home()), "tokens")
    
    # Now get tokens from the correct directory
    api = trackman.TrackManAPI()
    tokens = trackman.check_saved_tokens()
    
    if triggered == "use-token-btn" and selected_user:
        token = tokens.get(selected_user)
        if token:
            api.auth_token = token
            api.headers["Authorization"] = f"Bearer {token}"
            if api.test_connection():
                status = f"Successfully logged in as {selected_user} (Home: {home_dir})"
                save_disabled = False
                selected_username = selected_user
                
                # AUTO-FETCH ACTIVITIES
                try:
                    print(f"DEBUG: Auto-fetching activities for {selected_user}")
                    activities_data = api.get_activity_list(limit=20)
                    if activities_data:
                        # Filter for range practice activities
                        range_activities = [a for a in activities_data if a.get("kind") == "RANGE_PRACTICE"]
                        
                        if range_activities:
                            # Sort chronologically (oldest first)
                            range_activities = sorted(range_activities, key=lambda x: x.get("time", ""))
                            
                            # Prepare table data
                            activities_table = []
                            for i, activity in enumerate(range_activities):
                                activity_time = activity.get("time", "Unknown date")
                                try:
                                    dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                                except Exception:
                                    date_str = activity_time[:16].replace('T', ' ') if activity_time else "Unknown"
                                
                                activities_table.append({
                                    "ID": i + 1,
                                    "Date": date_str,
                                    "Type": activity.get("kind", "Unknown"),
                                })
                            
                            activities_store = range_activities
                            activities_log = f"✅ Auto-loaded {len(range_activities)} range practice activities (sorted chronologically, oldest = #1)"
                            current_tab = "activities"  # Switch to activities tab
                            status += f" | Found {len(range_activities)} activities"
                        else:
                            activities_log = "No range practice activities found"
                            current_tab = "activities"  # Still switch to show the empty state
                    else:
                        activities_log = "No activities found"
                        current_tab = "activities"  # Still switch to show the empty state
                        
                except Exception as e:
                    activities_log = f"❌ Error fetching activities: {str(e)}"
                    print(f"DEBUG: Error auto-fetching activities: {e}")
                    # Don't switch tabs if there's an error
            else:
                status = "Token is invalid, please login again"
        else:
            status = "No token found for selected user"
            
    elif triggered == "new-login-btn":
        status = f"Starting browser login... (Tokens will be saved to: {os.path.join(home_dir, 'tokens')})"

        try:
            # Create API instance and attempt login
            api = trackman.TrackManAPI()
            
            # Start the login process (this will open browser)
            success = api.login(username,password)
            
            if success and api.auth_token:
                # Test the token immediately
                if api.test_connection():
                    status += " - Login successful! Please enter username to save token."
                    save_disabled = False
                    current_token = api.auth_token
                    # AUTO-FETCH ACTIVITIES FOR NEW LOGIN TOO
                    try:
                        print(f"DEBUG: Auto-fetching activities after new login")
                        activities_data = api.get_activity_list(limit=20)
                        if activities_data:
                            # Filter for range practice activities
                            range_activities = [a for a in activities_data if a.get("kind") == "RANGE_PRACTICE"]
                            
                            if range_activities:
                                # Sort chronologically (oldest first)
                                range_activities = sorted(range_activities, key=lambda x: x.get("time", ""))
                                
                                # Prepare table data
                                activities_table = []
                                for i, activity in enumerate(range_activities):
                                    activity_time = activity.get("time", "Unknown date")
                                    try:
                                        dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                                        date_str = dt.strftime("%Y-%m-%d %H:%M")
                                    except Exception:
                                        date_str = activity_time[:16].replace('T', ' ') if activity_time else "Unknown"
                                    
                                    activities_table.append({
                                        "ID": i + 1,
                                        "Date": date_str,
                                        "Type": activity.get("kind", "Unknown"),
                                    })
                                
                                activities_store = range_activities
                                activities_log = f"✅ Auto-loaded {len(range_activities)} range practice activities (sorted chronologically, oldest = #1)"
                                current_tab = "activities"  # Switch to activities tab
                                status += f" | Found {len(range_activities)} activities"
                            else:
                                activities_log = "Login successful but no range practice activities found"
                                current_tab = "activities"
                        else:
                            activities_log = "Login successful but no activities found"
                            current_tab = "activities"
                            
                    except Exception as e:
                        activities_log = f"Login successful but error fetching activities: {str(e)}"
                        print(f"DEBUG: Error auto-fetching activities after new login: {e}")
                        # Don't switch tabs if there's an error
                else:
                    status += " - Login successful but token validation failed."
                    save_disabled = True
            else:
                status += " - Login failed. Please try again."
                save_disabled = True
                
        except Exception as e:
            status += f" - Error: {str(e)}"
            save_disabled = True
            
        selected_username = "user"
        
    elif triggered == "logout-btn" and selected_user:
        trackman.invalidate_token(selected_user)
        status = f"Logged out {selected_user}"
        # Clear activities when logging out
        activities_table = []
        activities_store = []
        activities_log = ""
        
    elif triggered == "logout-all-btn":
        trackman.invalidate_token()
        status = "Logged out all users"
        # Clear activities when logging out all
        activities_table = []
        activities_store = []
        activities_log = ""
        
    elif triggered == "save-token-btn" and username_input:
        # Get the current API instance with token from the new login
        if hasattr(api, 'auth_token') and api.auth_token:
            try:
                # Save the token to file
                token_file = os.path.join(trackman.TOKEN_DIR, f"{username_input}.token")
                os.makedirs(trackman.TOKEN_DIR, exist_ok=True)
                
                with open(token_file, 'w') as f:
                    f.write(api.auth_token)
                
                status = f"Token saved successfully for {username_input}"
                save_disabled = True
                selected_username = username_input
                
                # Keep the activities that were already fetched during login
                # No need to fetch again
                
            except Exception as e:
                status = f"Error saving token: {str(e)}"
        else:
            status = "No active token to save. Please login first."
        
    return status, save_disabled, selected_username, current_tab, activities_table, activities_store, activities_log, current_token

@app.callback(
    Output("activities-log", "children", allow_duplicate=True),
    Output("activities-table", "data", allow_duplicate=True),
    Output("activities-store", "data", allow_duplicate=True),
    Input("refresh-activities-btn", "n_clicks"),
    Input("download-selected-btn", "n_clicks"),
    Input("download-all-btn", "n_clicks"),
    State("selected-username-store", "data"),
    State("ball-type-dropdown", "value"),
    State("activities-table", "selected_rows"),
    State("activities-store", "data"),
    State("activities-table", "data"),  # Add this to preserve existing table data
    State("activities-log", "children"),  # Add this to preserve existing log
    State("current-token-store", "data"),
    prevent_initial_call=True  # Change this back to True
)
def handle_activities_actions(refresh_clicks, download_selected_clicks, download_all_clicks, username, ball_type, selected_rows, 
                            activities, existing_table_data, existing_log,current_token):
    triggered = ctx.triggered_id
    # If no button was clicked, preserve existing data
    if not triggered:
        return existing_log or "", existing_table_data or [], activities or []
    
    if not current_token:
        if not username:
            return "No user logged in. Please login first.", existing_table_data or [], activities or []
        api = trackman.TrackManAPI()
        tokens = trackman.check_saved_tokens()
        token = tokens.get(username)
        if not token:
            return "No valid token found. Please login again.", existing_table_data or [], activities or []
    else:
        api = trackman.TrackManAPI()
        token = current_token

    api.auth_token = token
    api.headers["Authorization"] = f"Bearer {token}"
    
    if triggered == "refresh-activities-btn":
        try:
            # Fetch activities from API
            activities_data = api.get_activity_list(limit=20)
            if not activities_data:
                return "No activities found.", [], []
            
            # Filter for range practice activities
            range_activities = [a for a in activities_data if a.get("kind") == "RANGE_PRACTICE"]
            
            if not range_activities:
                return "No range practice activities found.", [], []
            
            # Sort chronologically (oldest first)
            range_activities = sorted(range_activities, key=lambda x: x.get("time", ""))
            
            # Prepare table data
            table_data = []
            for i, activity in enumerate(range_activities):
                activity_time = activity.get("time", "Unknown date")
                try:
                    dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = activity_time[:16].replace('T', ' ') if activity_time else "Unknown"
                
                table_data.append({
                    "ID": i + 1,
                    "Date": date_str,
                    "Type": activity.get("kind", "Unknown"),
                })
            
            log_message = f"Found {len(range_activities)} range practice activities (sorted chronologically, oldest = #1)"
            return log_message, table_data, range_activities
            
        except Exception as e:
            return f"Error fetching activities: {str(e)}", existing_table_data or [], activities or []
    
    elif triggered in ["download-selected-btn", "download-all-btn"]:
        if not activities:
            return "No activities available. Please refresh activities first.", existing_table_data or [], activities or []
        
        try:
            if triggered == "download-selected-btn":
                if not selected_rows:
                    return "No activity selected. Please select an activity to download.", existing_table_data, activities
                
                selected_idx = selected_rows[0]
                if selected_idx >= len(activities):
                    return "Invalid selection.", existing_table_data, activities
                
                selected_activity = activities[selected_idx]
                log_message = f"Downloading selected activity: {selected_activity.get('time', 'Unknown')[:10]}\n"
                
                # Download logic here
                if ball_type == "BOTH":
                    # Download both premium and range
                    for bt in ["PREMIUM", "RANGE"]:
                        shot_data = api.get_range_practice_shots(selected_activity.get('id'), bt)
                        if shot_data and shot_data.get("shots"):
                            # Add session metadata
                            for shot in shot_data.get("shots", []):
                                shot["session_number"] = selected_idx + 1
                                shot["session_time"] = selected_activity.get("time")
                                shot["session_kind"] = selected_activity.get("kind")
                            save_shots_to_csv(shot_data, ball_type=bt, username=username)
                            log_message += f"Downloaded {len(shot_data.get('shots', []))} {bt} shots\n"
                else:
                    shot_data = api.get_range_practice_shots(selected_activity.get('id'), ball_type)
                    if shot_data and shot_data.get("shots"):
                        # Add session metadata
                        for shot in shot_data.get("shots", []):
                            shot["session_number"] = selected_idx + 1
                            shot["session_time"] = selected_activity.get("time")
                            shot["session_kind"] = selected_activity.get("kind")
                        save_shots_to_csv(shot_data, ball_type=ball_type, username=username)
                        log_message += f"Downloaded {len(shot_data.get('shots', []))} {ball_type} shots\n"
                
                # IMPORTANT: Preserve existing table and activities data
                return log_message, existing_table_data, activities
                
            elif triggered == "download-all-btn":
                log_message = f"Downloading all {len(activities)} activities...\n"
                
                for idx, activity in enumerate(activities):
                    if ball_type == "BOTH":
                        for bt in ["PREMIUM", "RANGE"]:
                            shot_data = api.get_range_practice_shots(activity.get('id'), bt)
                            if shot_data and shot_data.get("shots"):
                                for shot in shot_data.get("shots", []):
                                    shot["session_number"] = idx + 1
                                    shot["session_time"] = activity.get("time")
                                    shot["session_kind"] = activity.get("kind")
                                save_shots_to_csv(shot_data, ball_type=bt, username=username)
                                log_message += f"Session {idx+1}: Downloaded {len(shot_data.get('shots', []))} {bt} shots\n"
                    else:
                        shot_data = api.get_range_practice_shots(activity.get('id'), ball_type)
                        if shot_data and shot_data.get("shots"):
                            for shot in shot_data.get("shots", []):
                                shot["session_number"] = idx + 1
                                shot["session_time"] = activity.get("time")
                                shot["session_kind"] = activity.get("kind")
                            save_shots_to_csv(shot_data, ball_type=ball_type, username=username)
                            log_message += f"Session {idx+1}: Downloaded {len(shot_data.get('shots', []))} shots\n"
                
                # IMPORTANT: Preserve existing table and activities data
                return log_message, existing_table_data, activities
                
        except Exception as e:
            return f"Error during download: {str(e)}", existing_table_data, activities
    
    # Default case - preserve existing data
    return existing_log or "", existing_table_data or [], activities or []

@app.callback(
    Output('ball-type-radio', 'style', allow_duplicate=True),
    Input('user-dropdown', 'value'),
    prevent_initial_call=True
)
def control_ball_type_availability(selected_user):
    """Enable/disable ball type selection based on whether uploaded data is being used"""
    
    if selected_user == 'Uploaded Data':
        # Uploaded data - disable ball type selection
        return {
            'margin-bottom': '20px', 
            'opacity': '0.5', 
            'pointer-events': 'none'
        }
    else:
        # Server data - enable ball type selection
        return {'margin-bottom': '20px'}

@app.callback(
    Output('upload-status', 'children'),
    Output('user-dropdown', 'options', allow_duplicate=True),
    Output('user-dropdown', 'value', allow_duplicate=True),
    Output('ball-type-radio', 'style'),
    Input('upload-golf-data', 'contents'),
    State('upload-golf-data', 'filename'),
    prevent_initial_call=True
)
def handle_file_upload(contents, filenames):
    if not contents:
        return "", [], None, {'margin-bottom': '20px'}
    
    if not isinstance(contents, list):
        contents = [contents]
        filenames = [filenames]
    
    try:
        uploaded_data = {}
        files_metadata = {}
        total_shots = 0
        new_files = 0
        duplicate_files = []
        error_files = []
        
        for content, filename in zip(contents, filenames):
            try:
                # Decode the uploaded file
                content_type, content_string = content.split(',')
                decoded = base64.b64decode(content_string)
                file_size = len(decoded)
                
                # Check for duplicate
                is_duplicate, existing_filename = is_duplicate_file(filename, content_string, file_size)
                
                if is_duplicate:
                    duplicate_files.append(f"{filename} (duplicate of {existing_filename})")
                    continue
                
                # Read CSV
                df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
                
                if df.empty:
                    error_files.append(f"{filename} (empty file)")
                    continue
                
                # Extract user and session info from filename or add defaults
                if 'Session ID' not in df.columns:
                    session_name = filename.replace('.csv', '')
                    df['Session ID'] = session_name
                
                # Add user identifier
                username = 'Uploaded Data'
                if username not in uploaded_data:
                    uploaded_data[username] = []
                
                uploaded_data[username].append(df)
                total_shots += len(df)
                new_files += 1
                
                # Store file metadata
                files_metadata[filename] = {
                    'hash': calculate_file_hash(content_string),
                    'size': file_size,
                    'shots': len(df),
                    'upload_time': datetime.now().isoformat()
                }
                
            except Exception as e:
                error_files.append(f"{filename} (error: {str(e)})")
                continue
        
        # Combine all new uploaded data
        for username, dfs in uploaded_data.items():
            if dfs:  # Only if we have new data
                combined_df = pd.concat(dfs, ignore_index=True)
                store_uploaded_data(username, combined_df, files_metadata)
        
        # Create status message
        status_parts = []
        if new_files > 0:
            status_parts.append(f"✅ Successfully uploaded {new_files} new files with {total_shots} shots")
        
        if duplicate_files:
            status_parts.append(f"⚠️ Ignored {len(duplicate_files)} duplicate files: {', '.join(duplicate_files)}")
        
        if error_files:
            status_parts.append(f"❌ Failed to process {len(error_files)} files: {', '.join(error_files)}")
        
        # Add persistent storage info
        upload_info = get_uploaded_files_info()
        if upload_info['total_files'] > 0:
            status_parts.append(f"📊 Total in memory: {upload_info['total_files']} files, {upload_info['total_shots']} shots")
        
        status = " | ".join(status_parts) if status_parts else "No new files to upload"
        
        # Update user dropdown - check if we have any uploaded data
        current_uploaded_data = load_uploaded_data('Uploaded Data')
        if not current_uploaded_data.empty:
            user_options = [{'label': 'Uploaded Data', 'value': 'Uploaded Data'}]
            selected_user = 'Uploaded Data'
            
            # Disable ball type selection for uploaded data
            ball_type_style = {
                'margin-bottom': '20px', 
                'opacity': '0.5', 
                'pointer-events': 'none'
            }
        else:
            user_options = []
            selected_user = None
            ball_type_style = {'margin-bottom': '20px'}
        
        return status, user_options, selected_user, ball_type_style
        
    except Exception as e:
        return f"❌ Error processing files: {str(e)}", [], None, {'margin-bottom': '20px'}

# Global storage for uploaded data (in production, use Redis or database)
UPLOADED_DATA = {}
UPLOADED_FILES_METADATA = {}  # Track uploaded file metadata to detect duplicates

def calculate_file_hash(content_string):
    """Calculate a hash of the file content to detect duplicates"""
    import hashlib
    return hashlib.md5(content_string.encode()).hexdigest()

def is_duplicate_file(filename, content_string, file_size):
    """Check if this file has already been uploaded"""
    file_hash = calculate_file_hash(content_string)
    
    # Check if we've seen this exact file content before
    for stored_filename, metadata in UPLOADED_FILES_METADATA.items():
        if (metadata['hash'] == file_hash and 
            metadata['size'] == file_size):
            return True, stored_filename
    
    return False, None

def store_uploaded_data(username, df, files_metadata):
    """Store uploaded data globally with metadata tracking"""
    global UPLOADED_DATA, UPLOADED_FILES_METADATA
    
    # Store or append to existing data
    if username in UPLOADED_DATA:
        # Append to existing data
        UPLOADED_DATA[username] = pd.concat([UPLOADED_DATA[username], df], ignore_index=True)
    else:
        UPLOADED_DATA[username] = df
    
    # Store file metadata
    UPLOADED_FILES_METADATA.update(files_metadata)

def load_uploaded_data(username):
    """Load uploaded data"""
    global UPLOADED_DATA
    return UPLOADED_DATA.get(username, pd.DataFrame())

def get_uploaded_files_info():
    """Get information about uploaded files"""
    global UPLOADED_FILES_METADATA, UPLOADED_DATA
    
    info = {
        'total_files': len(UPLOADED_FILES_METADATA),
        'total_shots': sum(len(df) for df in UPLOADED_DATA.values()),
        'files': list(UPLOADED_FILES_METADATA.keys())
    }
    return info

def clear_uploaded_data():
    """Clear all uploaded data (useful for manual refresh)"""
    global UPLOADED_DATA, UPLOADED_FILES_METADATA
    UPLOADED_DATA = {}
    UPLOADED_FILES_METADATA = {}

# Analysis callbacks (existing ones remain the same)
@app.callback(
    Output('session-dropdown', 'options'),
    Output('session-dropdown', 'value'),
    Output('club-dropdown', 'options'),
    Output('club-dropdown', 'value'),
    Output('club-dropdown', 'multi'),
    Input('user-dropdown', 'value'),
    Input('ball-type-radio', 'value'),
    Input('session-dropdown', 'value'),
    Input('comparison-radio', 'value'),
    Input('attribute-dropdown', 'value'),  # Move this to Input to trigger when attribute changes
    prevent_initial_call=True
)
def update_sessions_and_clubs(username, ball_type, selected_sessions, comparison_mode, attribute):
    # Allow the callback to run even if attribute is None initially
    if not username:
        return [], [], [], [], True
    
    # Add this debug print to see what's happening
    print(f"DEBUG: update_sessions_and_clubs called with username={username}, comparison_mode={comparison_mode}, attribute={attribute}")
    
    df = load_data(username, ball_type)
    
    # Add this check for empty dataframe
    if df.empty:
        print(f"DEBUG: No data found for {username}")
        return [], [], [], [], True
    
    # If attribute is None, use carryActual as default or any numeric column
    if not attribute:
        if 'carryActual' in df.columns:
            attribute = 'carryActual'
        else:
            # Find any numeric column
            numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
            if numeric_cols:
                attribute = numeric_cols[0]
            else:
                print("DEBUG: No numeric columns found")
                return [], [], [], [], True
    
    print(f"DEBUG: Using attribute: {attribute}")
    
    # Handle filtering for 2D Map attributes
    if attribute == '2DMapCarry':
        df = df.dropna(subset=['carryActual', 'carrySideActual'])
    elif attribute == '2DMapTotal':
        df = df.dropna(subset=['totalActual', 'totalSideActual'])
    elif attribute == '2DMapCarry-Total':
        df = df.dropna(subset=['carryActual', 'carrySideActual', 'totalActual', 'totalSideActual'])
    elif attribute == 'custom':
        pass
    elif attribute in df.columns:
        df = df.dropna(subset=[attribute])
    
    # Get all available sessions with enhanced information
    sessions = sorted(df['Session ID'].unique())
    session_options = []
    
    for session in sessions:
        session_data = df[df['Session ID'] == session]
        shot_count = len(session_data)
        unique_clubs = session_data['Club'].nunique()
        
        label = f"{session} (clubs: {unique_clubs}, n={shot_count})"
        session_options.append({'label': label, 'value': session})
    
    # Preserve valid selections or reset
    if selected_sessions:
        selected_sessions = [s for s in selected_sessions if s in sessions]
    else:
        selected_sessions = []
    
    # Filter clubs based on selected sessions
    if selected_sessions:
        filtered_df = df[df['Session ID'].isin(selected_sessions)]
    else:
        filtered_df = df
    
    clubs = sorted([c for c in filtered_df['Club'].unique() if pd.notna(c)])
    club_options = [{'label': c, 'value': c} for c in clubs]
    
    # Set multi-selection based on comparison mode
    multi_selection = comparison_mode != 'time'
    
    # For 'time' mode, limit to one club selection
    club_value = []
    if comparison_mode == 'time' and clubs:
        club_value = [clubs[0]] if clubs else []
    
    print(f"DEBUG: Returning {len(session_options)} sessions, {len(club_options)} clubs")
    return session_options, selected_sessions, club_options, club_value, multi_selection

@app.callback(
    Output('comparison-radio', 'value', allow_duplicate=True),
    Input('user-dropdown', 'value'),
    prevent_initial_call=True
)
def set_default_comparison_mode(username):
    """Set default comparison mode when user changes"""
    if username == 'Uploaded Data':
        return 'clubs'  # Set default to clubs comparison
    else:
        return 'clubs'  # Also set default for regular users

@app.callback(
    Output("custom-xy-div", "style"),
    Output("custom-x-dropdown", "options"),
    Output("custom-y-dropdown", "options"),
    Output("custom-x-dropdown", "value"),
    Output("custom-y-dropdown", "value"),
    Input("attribute-dropdown", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value"),
)
def custom_xy(attribute, username, ball_type):
    if attribute != "custom" or not username:
        return {'display': 'none'}, [], [], None, None
    df = load_data(username, ball_type)
    # Only numeric columns
    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    options = [{'label': col, 'value': col} for col in numeric_cols]
    default_x = options[0]['value'] if options else None
    default_y = options[1]['value'] if len(options) > 1 else None
    return {'margin-bottom': '20px', 'display': 'block'}, options, options, default_x, default_y

@app.callback(
    Output("custom-x-dropdown", "value", allow_duplicate=True),
    Output("custom-y-dropdown", "value", allow_duplicate=True),
    Input("swap-xy-btn", "n_clicks"),
    State("custom-x-dropdown", "value"),
    State("custom-y-dropdown", "value"),
    prevent_initial_call=True
)
def swap_xy_attributes(n_clicks, current_x, current_y):
    if not n_clicks or not current_x or not current_y:
        raise dash.exceptions.PreventUpdate
    
    # Swap the values
    return current_y, current_x

@app.callback(
    Output('attribute-dropdown', 'value', allow_duplicate=True),
    Input('user-dropdown', 'value'),
    State('attribute-dropdown', 'options'),
    prevent_initial_call=True
)
def set_default_attribute_for_uploaded_data(username, available_options):
    """Set default attribute when uploaded data is selected"""
    if username == 'Uploaded Data' and available_options:
        # Set a default attribute immediately
        if any(opt['value'] == 'carryActual' for opt in available_options):
            return 'carryActual'
        else:
            return available_options[0]['value']
    
    raise dash.exceptions.PreventUpdate

@app.callback(
    Output("selected-shots-table", "data", allow_duplicate=True),
    Output("filtered-data-store", "data", allow_duplicate=True),
    Output("selected-shots-table", "style_data_conditional", allow_duplicate=True),
    Output("analysis-plot", "figure", allow_duplicate=True),
    Input("selected-shots-table", "active_cell"),
    State("selected-shots-table", "data"),  # This contains the SORTED data
    State("selected-shots-table", "derived_virtual_data"),  # Add this - contains sorted data
    State("filtered-data-store", "data"),
    State("attribute-dropdown", "value"),
    State("comparison-radio", "value"),
    State("plot-type-radio", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value"),
    State("session-dropdown", "value"),
    State("club-dropdown", "value"),
    State("custom-x-dropdown", "value"),
    State("custom-y-dropdown", "value"),
    prevent_initial_call=True
)
def toggle_delete_shot(active_cell, table_data, derived_virtual_data, filtered_data, attribute, comparison_mode, 
                      plot_type, username, ball_type, sessions, clubs, custom_x, custom_y):
    if not active_cell or not table_data or not filtered_data:
        raise dash.exceptions.PreventUpdate
    
    # Check if the clicked cell is the Delete column
    if active_cell["column_id"] != "Delete":
        raise dash.exceptions.PreventUpdate
    
    row_index = active_cell["row"]
    
    # Use derived_virtual_data if available (this respects sorting), otherwise fall back to table_data
    current_table_view = derived_virtual_data if derived_virtual_data else table_data
    
    if row_index >= len(current_table_view):
        raise dash.exceptions.PreventUpdate
    
    # Get the row_id from the correctly sorted data
    row_id = current_table_view[row_index]["row_id"]
    
    print(f"DEBUG: Toggling delete status for row_id: {row_id} (clicked row {row_index})")
    
    # Update table data
    updated_table_data = []
    for row in table_data:
        row_copy = row.copy()
        if row_copy["row_id"] == row_id:
            # Toggle the deleted status
            current_status = row_copy.get("deleted", False)
            row_copy["deleted"] = not current_status
            row_copy["Delete"] = "↶" if not current_status else "❌"
            print(f"DEBUG: Changed row {row_id} from deleted={current_status} to deleted={not current_status}")
        updated_table_data.append(row_copy)
    
    # Update filtered data
    updated_filtered_data = []
    for row in filtered_data:
        row_copy = row.copy()
        if row_copy["row_id"] == row_id:
            current_status = row_copy.get("deleted", False)
            row_copy["deleted"] = not current_status
        updated_filtered_data.append(row_copy)
    
    # Create style data conditional for styling deleted rows
    style_data_conditional = [
        {
            'if': {'row_index': 'odd'},
            'backgroundColor': 'rgb(248, 248, 248)'
        },
        {
            'if': {
                'filter_query': '{deleted} = true',
            },
            'backgroundColor': 'rgb(255, 220, 220)',  # Light red for deleted shots
            'color': 'rgb(128, 128, 128)',
            'textDecoration': 'line-through'
        }
    ]
    
    # Filter out deleted shots for the plot
    plot_data = [row for row in updated_filtered_data if not row.get("deleted", False)]
    
    print(f"DEBUG: Active shots for plot after toggle: {len(plot_data)}")
    
    # Generate updated plot
    if not plot_data:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="No active shots selected",
            height=600,
            xaxis_title="No data",
            yaxis_title="No data"
        )
        return updated_table_data, updated_filtered_data, style_data_conditional, empty_fig
    
    # Generate the plot with the updated data
    updated_fig = generate_plot(1, username, ball_type, comparison_mode, 
                               plot_type, sessions, clubs, attribute, 
                               plot_data, custom_x, custom_y)
    
    # Count total deleted shots for title
    deleted_count = sum(1 for row in updated_filtered_data if row.get("deleted", False))
    if deleted_count > 0:
        current_title = updated_fig.layout.title.text if updated_fig.layout.title else "Analysis"
        updated_fig.update_layout(
            title=f"{current_title} ({deleted_count} shots excluded)"
        )
    
    return updated_table_data, updated_filtered_data, style_data_conditional, updated_fig

def save_shots_to_csv(shots_data, filename=None, ball_type="PREMIUM", username=None):
        """Save shot data to a CSV file"""
        if not shots_data or not shots_data.get("shots"):
            print("No shot data to save")
            return
        
        print(f"DEBUG: Saving shots data to CSV with ball type: {ball_type}, username: {username}, filename: {filename}, shots count: {len(shots_data.get('shots', []))}")
        
        # Create base Data directory
        data_dir = "Data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Include username in path if provided
        if username:
            data_dir = os.path.join(data_dir, username)
            os.makedirs(data_dir, exist_ok=True)
        
        # Create ball type-specific subdirectory
        ball_type_lower = ball_type.lower()
        ball_dir = os.path.join(data_dir, ball_type_lower)
        os.makedirs(ball_dir, exist_ok=True)
        
        # Rest of the method remains the same
        shots = shots_data.get("shots", [])
        
        # Get session date and number for filename
        session_time = ""
        if shots and "session_time" in shots[0]:
            try:
                dt = datetime.fromisoformat(shots[0]["session_time"].replace('Z', '+00:00'))
                session_time = dt.strftime("%Y%m%d")
            except:
                pass
        
        session_num = shots[0].get("session_number", "1") if shots else "1"
        
        # Create filename with directory, date, session number and ball type
        ball_suffix = "_range" if ball_type == "RANGE" else "_pro"
        
        if not session_time:
            filename = f"{ball_dir}/trackman_session{session_num}{ball_suffix}.csv"
        else:
            filename = f"{ball_dir}/trackman_{session_time}_session{session_num}{ball_suffix}.csv"

        # Define measurement fields to include
        measurement_fields = [
            "ballSpeed",
            "ballSpin", 
            "carry",
            "carryActual",
            "carrySide",
            "carrySideActual",
            "curve",
            "curveActual",
            "curveTotal",
            "curveTotalActual",
            "launchAngle",
            "launchDirection",
            "maxHeight",
            "spinAxis",
            "total",
            "totalActual",
            "totalSide",
            "totalSideActual",
            "ballSpinEffective",
            "targetDistance",
            "distanceFromPin",
            "distanceFromPinActual",
            "distanceFromPinTotal",
            "distanceFromPinTotalActual",
            "landingAngle",
            "reducedAccuracy",
        ]

        # Create header
        header = ["Shot Number", "Club", "Bay"] + measurement_fields
        
        # Prepare rows
        rows = [",".join(header)]
        
        # Sort shots by time
        shots.sort(key=lambda x: x.get("time", ""))
        
        # Process each shot
        for idx, shot in enumerate(shots, 1):
            data = shot.get("measurement", {})
            club = shot.get("club", "")
            if club is None:
                club = "Unknown"
            
            # Initialize the row with basic shot info
            row = [
                str(idx),
                str(club),
                str(shot.get("bayName", ""))
            ]
            
            # Add measurement fields
            for field in measurement_fields:
                value = data.get(field, "")
                if isinstance(value, bool):
                    value = str(value)
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                row.append(value)
            
            try:
                rows.append(",".join(row))
            except Exception as e:
                print(f"Error processing row: {row} with error: {e}")
                continue
        
        # Join all rows into a CSV string
        csv_content = "\n".join(rows)
        
        # Write to file
        return csv_content, filename
@app.callback(
    Output("analysis-plot", "figure", allow_duplicate=True),
    Output("selected-shots-table", "data", allow_duplicate=True),
    Output("filtered-data-store", "data", allow_duplicate=True),
    Output("selected-shots-table", "style_data_conditional", allow_duplicate=True),
    Input("reset-all-shots-btn", "n_clicks"),
    State("selected-shots-table", "data"),
    State("filtered-data-store", "data"),
    State("attribute-dropdown", "value"),
    State("comparison-radio", "value"),
    State("plot-type-radio", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value"),
    State("session-dropdown", "value"),
    State("club-dropdown", "value"),
    State("custom-x-dropdown", "value"),
    State("custom-y-dropdown", "value"),
    prevent_initial_call=True
)
def reset_all_shots(n_clicks, table_data, filtered_data, attribute, comparison_mode, 
                    plot_type, username, ball_type, sessions, clubs, custom_x, custom_y):
    if not n_clicks or not table_data or not filtered_data:
        raise dash.exceptions.PreventUpdate
    
    print(f"DEBUG: Resetting all shots - restoring all deleted shots")
    
    # Count how many shots are currently deleted
    deleted_count = sum(1 for row in filtered_data if row.get("deleted", False))
    
    if deleted_count == 0:
        print("DEBUG: No deleted shots to restore")
        raise dash.exceptions.PreventUpdate
    
    # Update table data to restore all shots
    updated_table_data = []
    for row in table_data:
        row_copy = row.copy()
        row_copy["deleted"] = False
        row_copy["Delete"] = "❌"  # Reset to delete symbol
        updated_table_data.append(row_copy)
    
    # Update filtered data to restore all shots
    updated_filtered_data = []
    for row in filtered_data:
        row_copy = row.copy()
        row_copy["deleted"] = False
        updated_filtered_data.append(row_copy)
    
    # Reset style data conditional to default (no deleted row styling)
    style_data_conditional = [
        {
            'if': {'row_index': 'odd'},
            'backgroundColor': 'rgb(248, 248, 248)'
        }
    ]
    
    # Use all shots for the plot (since all are now restored)
    plot_data = updated_filtered_data
    
    print(f"DEBUG: Active shots for plot after reset: {len(plot_data)}")
    
    # Generate the plot with all data restored
    updated_fig = generate_plot(1, username, ball_type, comparison_mode, 
                               plot_type, sessions, clubs, attribute, 
                               custom_data=plot_data, custom_x=custom_x, custom_y=custom_y)
    
    # Update the title to show that shots were restored
    current_title = updated_fig.layout.title.text if updated_fig.layout.title else "Analysis"
    # Remove any existing exclusion text from title
    if " shots excluded)" in current_title:
        current_title = current_title.split(" (")[0]
    if " mishits removed)" in current_title:
        current_title = current_title.split(" (")[0]
    
    updated_fig.update_layout(
        title=f"{current_title} (all {deleted_count} shots restored)"
    )
    
    return updated_fig, updated_table_data, updated_filtered_data, style_data_conditional

@app.callback(
    Output('upload-status', 'children', allow_duplicate=True),
    Output('user-dropdown', 'options', allow_duplicate=True),
    Output('user-dropdown', 'value', allow_duplicate=True),
    Output('ball-type-radio', 'style', allow_duplicate=True),
    Input('clear-uploads-btn', 'n_clicks'),
    prevent_initial_call=True
)
def clear_all_uploads(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    # Get info before clearing
    upload_info = get_uploaded_files_info()
    
    # Clear all uploaded data
    clear_uploaded_data()
    
    status = f"🗑️ Cleared {upload_info['total_files']} uploaded files ({upload_info['total_shots']} shots)"
    
    # Reset user dropdown and ball type style
    return status, [], None, {'margin-bottom': '20px'}

@app.callback(
    Output('upload-status', 'children', allow_duplicate=True),
    Input('show-upload-info-btn', 'n_clicks'),
    prevent_initial_call=True
)
def show_upload_info(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    upload_info = get_uploaded_files_info()
    
    if upload_info['total_files'] == 0:
        return "📊 No files currently uploaded"
    
    files_list = ", ".join(upload_info['files'][:5])  # Show first 5 files
    if len(upload_info['files']) > 5:
        files_list += f" and {len(upload_info['files']) - 5} more..."
    
    return f"📊 Uploaded: {upload_info['total_files']} files, {upload_info['total_shots']} total shots | Files: {files_list}"

@app.callback(
    Output('analysis-plot', 'figure'),
    Input('plot-btn', 'n_clicks'),
    State('user-dropdown', 'value'),
    State('ball-type-radio', 'value'),
    State('comparison-radio', 'value'),
    State('plot-type-radio', 'value'),
    State('session-dropdown', 'value'),
    State('club-dropdown', 'value'),
    State('attribute-dropdown', 'value'),
    State('filtered-data-store', 'data'),
    State('custom-x-dropdown', 'value'),
    State('custom-y-dropdown', 'value'),
)
def generate_plot(n_clicks, username, ball_type, comparison_mode, plot_type, sessions, clubs, attribute, custom_data=None, custom_x=None, custom_y=None,):
    print(f"DEBUG: generate_plot called with:")
    print(f"  n_clicks: {n_clicks}")
    print(f"  username: {username}")
    print(f"  ball_type: {ball_type}")
    print(f"  sessions: {sessions}")
    print(f"  clubs: {clubs}")
    print(f"  attribute: {attribute}")
    print(f"  custom_data: {'Provided' if custom_data else 'Not provided'}")
    print(f"  custom_x: {custom_x}")
    print(f"  custom_y: {custom_y}")
    
    if not n_clicks or not sessions or not clubs or not username or not attribute:
        print("DEBUG: Missing required inputs")
        return go.Figure()
    
    # Ensure sessions and clubs are always lists
    if isinstance(sessions, str):
        sessions = [sessions]
    if isinstance(clubs, str):
        clubs = [clubs]
    
    # Use custom data if provided, otherwise load from file
    if custom_data:
        print(f"DEBUG: Using provided custom data")
        df = pd.DataFrame(custom_data)
        
        # Fix column names for custom data if needed
        if 'Carry' in df.columns and 'carryActual' not in df.columns:
            df['carryActual'] = df['Carry']
        if 'CarrySide' in df.columns and 'carrySideActual' not in df.columns:
            df['carrySideActual'] = df['CarrySide']
            
        print(f"DEBUG: Custom data columns after fix: {df.columns.tolist()}")
    else:
        print(f"DEBUG: Loading data for {username}, {ball_type}")
        df = load_data(username, ball_type)
    
    print(f"DEBUG: Loaded dataframe shape: {df.shape}")
    print(f"DEBUG: Dataframe columns: {list(df.columns)}")
    
    if df.empty:
        print("DEBUG: Dataframe is empty")
        return go.Figure().add_annotation(
            text="No data found",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
    
    # Check for required columns before filtering
    if 'Session ID' in df.columns:
        print(f"DEBUG: Available sessions: {sorted(df['Session ID'].unique())}")
    if 'Club' in df.columns:
        print(f"DEBUG: Available clubs: {sorted(df['Club'].unique())}")
    
    df = df[df['Session ID'].isin(sessions) & df['Club'].isin(clubs)]
    print(f"DEBUG: After filtering by sessions/clubs: {df.shape}")
    
    if attribute == "custom":
        print(f"DEBUG: Generating custom plot for {custom_x} vs {custom_y}")
        if not custom_x or not custom_y:
            return go.Figure().add_annotation(
                text="Please select both X and Y axes for custom plot.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        # Filter out rows where either custom_x or custom_y is null/NaN
        filter_columns = [custom_x, custom_y]
        before_filter = len(df)
        df = df.dropna(subset=filter_columns)
        after_filter = len(df)
        print(f"DEBUG: Filtered from {before_filter} to {after_filter} rows")
        
        if df.empty:
            return go.Figure().add_annotation(
                text=f"No data available for {custom_x} vs {custom_y}",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        # Define sorted_clubs for custom plots (same as 2D maps)
        if comparison_mode == 'clubs':
            # Sort clubs by their average X-axis values for consistent ordering
            club_means = []
            for club in clubs:
                club_data = df[df['Club'] == club]
                if len(club_data) > 0:
                    avg_x = club_data[custom_x].mean()
                    club_means.append((club, avg_x))
            
            # Sort by average X values
            sorted_clubs = [club for club, _ in sorted(club_means, key=lambda x: x[1])]
        else:
            sorted_clubs = clubs  # For 'time' comparison, just use the clubs as-is
        
        print(f"DEBUG: sorted_clubs for custom plot: {sorted_clubs}")
        
        # Create scatter plot
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        # Check if plot_type is histogram (individual shots) or gaussian (means with error ellipses)
        if plot_type == 'histogram':
            if comparison_mode == 'clubs':
                # Multiple clubs comparison - aggregate same clubs across sessions
                colors = px.colors.qualitative.Plotly
                
                for club_idx, club in enumerate(sorted_clubs):
                    # Aggregate all data for this club across all sessions
                    club_data_all_sessions = df[df['Club'] == club]
                    
                    if len(club_data_all_sessions) == 0:
                        continue
                    
                    x_values = club_data_all_sessions[custom_x].tolist()
                    y_values = club_data_all_sessions[custom_y].tolist()
                    shot_count = len(x_values)
                    
                    # Create session breakdown for hover text
                    session_counts = club_data_all_sessions['Session ID'].value_counts().to_dict()
                    session_breakdown = ", ".join([f"{session}: {count}" for session, count in session_counts.items()])
                    
                    name = f"{club} (n={shot_count} total)"
                    
                    fig.add_trace(go.Scatter(
                        x=x_values,
                        y=y_values,
                        mode='markers',
                        name=name,
                        marker=dict(
                            color=colors[club_idx % len(colors)],
                            size=8,
                            opacity=0.7
                        ),
                        text=[f"Club: {club}<br>Sessions: {session_breakdown}<br>{custom_x}: {x}<br>{custom_y}: {y}"
                            for x, y in zip(x_values, y_values)],
                        hoverinfo='text'
                    ))
            else:
                # Club over time mode - single club, multiple sessions (keep existing logic)
                club = clubs[0]
                club_data = df[df['Club'] == club]
                
                session_colors = {session: colors[i % len(colors)] for i, session in enumerate(sessions)}
                
                for i, session in enumerate(sessions):
                    session_data = club_data[club_data['Session ID'] == session]
                    
                    if len(session_data) == 0:
                        continue
                    
                    x_values = session_data[custom_x].tolist()
                    y_values = session_data[custom_y].tolist()
                    shot_count = len(x_values)
                    name = f"{session} (n={shot_count})"
                    
                    fig.add_trace(go.Scatter(
                        x=x_values,
                        y=y_values,
                        mode='markers',
                        name=name,
                        marker=dict(
                            color=session_colors[session],
                            size=8,
                            opacity=0.7
                        ),
                        text=[f"Session: {session}<br>Club: {club}<br>{custom_x}: {x}<br>{custom_y}: {y}" 
                            for x, y in zip(x_values, y_values)],
                        hoverinfo='text'
                    ))
        else:
            # Gaussian mode - show means with error ellipses
            if comparison_mode == 'clubs':
                print(f"DEBUG: Creating custom plot for clubs comparison - aggregated by club")
                
                # Group data by club (aggregate across all sessions)
                for i, club in enumerate(clubs):
                    club_data_all_sessions = df[df['Club'] == club]
                    print(f"DEBUG: Club {club} has {len(club_data_all_sessions)} total data points across all sessions")
                    
                    if len(club_data_all_sessions) == 0:
                        continue
                    
                    # Calculate overall statistics for this club
                    x_mean = club_data_all_sessions[custom_x].mean()
                    y_mean = club_data_all_sessions[custom_y].mean()
                    x_std = club_data_all_sessions[custom_x].std() if len(club_data_all_sessions) > 1 else 0
                    y_std = club_data_all_sessions[custom_y].std() if len(club_data_all_sessions) > 1 else 0
                    
                    # Create session breakdown for hover text
                    session_counts = club_data_all_sessions['Session ID'].value_counts().to_dict()
                    session_breakdown = ", ".join([f"{session}: {count}" for session, count in session_counts.items()])
                    
                    hover_text = (
                        f"Club: {club}<br>"
                        f"Total Shots: {len(club_data_all_sessions)}<br>"
                        f"Sessions: {session_breakdown}<br>"
                        f"Mean {custom_x}: {x_mean:.2f}±{x_std:.2f}<br>"
                        f"Mean {custom_y}: {y_mean:.2f}±{y_std:.2f}"
                    )
                    
                    color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

                    # Draw the mean point
                    fig.add_trace(go.Scatter(
                        x=[x_mean],
                        y=[y_mean],
                        mode='markers',
                        name=f"{club} (n={len(club_data_all_sessions)} total)",
                        marker=dict(size=12, color=color, opacity=0.8),
                        text=hover_text,
                        hoverinfo='text'
                    ))

                    # Add an ellipse for the standard deviation
                    if x_std > 0 and y_std > 0:
                        fig.add_shape(
                            type="circle",
                            xref="x", yref="y",
                            x0=x_mean - x_std, x1=x_mean + x_std,
                            y0=y_mean - y_std, y1=y_mean + y_std,
                            fillcolor=color,
                            opacity=0.2,
                            line=dict(width=0),
                            layer="below"
                        )
                    
                    print(f"DEBUG: Added aggregated data for club {club}")
            else:
                # Mode is 'time' - plot clubs over time (Gaussian mode)
                print(f"DEBUG: Creating custom plot for time comparison - aggregated by club")
                club = clubs[0]
                club_data = df[df['Club'] == club]
                
                # Group by session and calculate statistics
                x_means = []
                y_means = []
                x_errors = []
                y_errors = []
                session_names = []
                hover_texts = []
                
                # Assign unique colors to each session
                session_colors = {session: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] for i, session in enumerate(sessions)}
                
                for i, session in enumerate(sessions):
                    session_data = club_data[club_data['Session ID'] == session]
                    print(f"DEBUG: Session {session} has {len(session_data)} data points")
                    
                    if len(session_data) == 0:
                        continue
                    
                    # x and y are custom attributes
                    x_mean = session_data[custom_x].mean()
                    y_mean = session_data[custom_y].mean()
                    x_std = session_data[custom_x].std() if len(session_data) > 1 else 0
                    y_std = session_data[custom_y].std() if len(session_data) > 1 else 0
                    
                    hover_texts.append(
                        f"Session: {session}<br>"
                        f"Club: {club}<br>"
                        f"Shots: {len(session_data)}<br>"
                        f"Mean {custom_x}: {x_mean:.2f}±{x_std:.2f}<br>"
                        f"Mean {custom_y}: {y_mean:.2f}±{y_std:.2f}"
                    )

                    fig.add_trace(go.Scatter(
                        x=[x_mean],
                        y=[y_mean],
                        mode='markers',
                        name=f"Session {session} (n={len(session_data)} shots)",
                        marker=dict(size=12, color=session_colors[session], opacity=0.8),
                        text=hover_texts,
                        hoverinfo='text'
                    ))

                    # Add an ellipse for the session
                    if x_std > 0 and y_std > 0:
                        fig.add_shape(
                            type="circle",
                            xref="x", yref="y",
                            x0=x_mean - x_std, x1=x_mean + x_std,
                            y0=y_mean - y_std, y1=y_mean + y_std,
                            fillcolor=session_colors[session],
                            opacity=0.2,
                            line=dict(width=0),
                            layer="below"
                        )
                    
                    print(f"DEBUG: Added data points for {club} over time")
        
        # Add reference lines for better visualization (same as 2D maps)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Calculate axis ranges for better presentation
        all_x_values = df[custom_x].values
        all_y_values = df[custom_y].values
        
        x_margin = (max(all_x_values) - min(all_x_values)) * 0.1 if len(all_x_values) > 0 else 10
        y_margin = (max(all_y_values) - min(all_y_values)) * 0.1 if len(all_y_values) > 0 else 10
        
        # Update layout with appropriate axis labels (same style as 2D maps)
        title_suffix = f" - {comparison_mode.title()} Comparison" if comparison_mode == 'clubs' else f" - {clubs[0]} Over Time"
        plot_mode_suffix = " (Mean ± SD)" if plot_type == 'gaussian' else ""
        
        fig.update_layout(
            title=f'Custom Plot: {custom_x} vs {custom_y}{title_suffix}{plot_mode_suffix}',
            height=700,  # Same height as 2D maps
            showlegend=True,
            legend=dict(
                title="Clubs" if comparison_mode == 'clubs' else "Sessions",
                orientation="h",  # Force horizontal orientation for better space usage
            ),
            # axis labels and ranges (same style as 2D maps)
            xaxis=dict(
                range=[min(all_x_values) - x_margin, max(all_x_values) + x_margin],
                title=custom_x,
                side="top",
                title_standoff=15,
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            ),
            yaxis=dict(
                range=[min(all_y_values) - y_margin, max(all_y_values) + y_margin],
                title=custom_y, 
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            )
        )
        
        print(f"DEBUG: Created custom figure with {len(fig.data)} traces")
        return fig
    
    # In the 2D map plotting section, add this before the histogram mode logic
    elif attribute in ['2DMapCarry', '2DMapTotal', '2DMapCarry-Total']:
        print(f"DEBUG: Processing {attribute} - USING REAL DATA")
        
        # Determine which columns to use based on the attribute
        if attribute == '2DMapCarry':
            x_column = 'carryActual'
            y_column = 'carrySideActual'
            filter_columns = ['carryActual', 'carrySideActual']
        elif attribute == '2DMapTotal':
            x_column = 'totalActual'
            y_column = 'totalSideActual'
            filter_columns = ['totalActual', 'totalSideActual']
        else:  # 2DMapCarry-Total
            # For carry-total lines, we need all four columns
            filter_columns = ['carryActual', 'carrySideActual', 'totalActual', 'totalSideActual']
            x_column = None  # Not applicable for line plots
            y_column = None  # Not applicable for line plots
        
        # Filter out rows where any required column is null/NaN
        before_filter = len(df)
        df = df.dropna(subset=filter_columns)
        after_filter = len(df)
        print(f"DEBUG: Filtered from {before_filter} to {after_filter} rows")
        
        if df.empty:
            return go.Figure().add_annotation(
                text=f"No data available for {attribute} (need all required distance and side data)",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        # ADD THIS: Define sorted_clubs for 2D map plots
        if comparison_mode == 'clubs':
            # Sort clubs by their average carry/total distance for consistent ordering
            club_means = []
            for club in clubs:
                club_data = df[df['Club'] == club]
                if len(club_data) > 0:
                    if attribute == '2DMapCarry':
                        avg_distance = club_data['carryActual'].mean()
                    elif attribute == '2DMapTotal':
                        avg_distance = club_data['totalActual'].mean()
                    else:  # 2DMapCarry-Total
                        avg_distance = club_data['carryActual'].mean()  # Use carry for sorting
                    club_means.append((club, avg_distance))
            
            # Sort by average distance
            sorted_clubs = [club for club, _ in sorted(club_means, key=lambda x: x[1])]
        else:
            sorted_clubs = clubs  # For time comparison, just use the clubs as-is
        
        print(f"DEBUG: sorted_clubs for 2D map: {sorted_clubs}")
        
        # Create scatter plot
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        # Check if plot_type is histogram (individual shots) or gaussian (means with error ellipses)
        if plot_type == 'histogram':
            if comparison_mode == 'clubs':
# Multiple clubs comparison - show individual shots as scatter
                # Create unique colors for each club-session combination
                club_session_colors = {}
                color_index = 0
                
                for session in sessions:
                    for club in sorted_clubs:
                        club_session_colors[f"{club}-{session}"] = colors[color_index % len(colors)]
                        color_index += 1
                
                for session in sessions:
                    for club_idx, club in enumerate(sorted_clubs):
                        session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                        
                        if len(session_club_data) == 0:
                            continue
                        
                        if attribute == '2DMapCarry-Total':
                            # Add lines from carry to total position for each shot
                            for idx, row in session_club_data.iterrows():
                                carry_x = float(row['carryActual'])
                                carry_y = float(row['carrySideActual']) 
                                total_x = float(row['totalActual'])
                                total_y = float(row['totalSideActual'])
                                
                                # Add line trace for this shot
                                fig.add_trace(go.Scatter(
                                    x=[carry_x, total_x],
                                    y=[carry_y, total_y],
                                    mode='lines+markers',
                                    line=dict(color=club_session_colors[f"{club}-{session}"], width=2),
                                    marker=dict(
                                        size=8, 
                                        color=club_session_colors[f"{club}-{session}"], 
                                        opacity=0.7,
                                        symbol=[0, 4]  # 0 = circle for carry, 4 = triangle-up for total
                                    ),
                                    name=f"{club} - {session}",
                                    legendgroup=f"{club}-{session}",
                                    showlegend=bool(idx == session_club_data.index[0]),
                                    text=f"Club: {club}<br>Session: {session}<br>Carry: {carry_x:.1f}m, {carry_y:.1f}m<br>Total: {total_x:.1f}m, {total_y:.1f}m",
                                    hoverinfo='text'
                                ))
                        elif attribute == '2DMapCarry':
                            x_values = session_club_data['carryActual'].tolist()
                            y_values = session_club_data['carrySideActual'].tolist()
                            shot_count = len(x_values)
                            name = f"{club} - {session} (n={shot_count})"
                            color_key = f"{club}-{session}"
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>Carry: {x:.1f}m<br>Side: {y:.1f}m"
                                      for x, y in zip(x_values, y_values)],
                                hoverinfo='text'
                            ))
                        elif attribute == '2DMapTotal':
                            x_values = session_club_data['totalActual'].tolist()
                            y_values = session_club_data['totalSideActual'].tolist()
                            shot_count = len(x_values)
                            name = f"{club} - {session} (n={shot_count})"
                            color_key = f"{club}-{session}"
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>Total: {x:.1f}m<br>Side: {y:.1f}m"
                                      for x, y in zip(x_values, y_values)],
                                hoverinfo='text'
                            ))
                        else:
                            # For regular 1D attributes, get individual values directly
                            individual_values = session_club_data[attribute].tolist()
                            shot_count = len(individual_values)
                            
                            # Create y-positions for this club (with some jitter for visibility)
                            y_positions = [club_idx + np.random.uniform(-0.2, 0.2) for _ in individual_values]
                            
                            name = f"{club} - {session} (n={shot_count})"
                            
                            # Use unique color for each club-session combination
                            color_key = f"{club}-{session}"
                            
                            fig.add_trace(go.Scatter(
                                x=individual_values,  # Attribute values on x-axis
                                y=y_positions,        # Club positions on y-axis with jitter
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>{attribute_label}: {val:.2f}" 
                                    for val in individual_values],
                                hoverinfo='text'
                            ))
            else:
                # Club over time mode - single club, multiple sessions
                club = clubs[0]
                club_data = df[df['Club'] == club]
                
                session_colors = {session: colors[i % len(colors)] for i, session in enumerate(sessions)}
                
                for i, session in enumerate(sessions):
                    session_data = club_data[club_data['Session ID'] == session]
                    
                    if len(session_data) == 0:
                        continue
                    
                    # Fix: Handle 2D map attributes properly for club over time mode
                    if attribute == '2DMapCarry-Total':
                        # For carry-total, show lines connecting carry to total for each shot
                        for idx, row in session_data.iterrows():
                            carry_x = float(row['carryActual'])
                            carry_y = float(row['carrySideActual']) 
                            total_x = float(row['totalActual'])
                            total_y = float(row['totalSideActual'])
                            
                            # Add line trace for this shot
                            fig.add_trace(go.Scatter(
                                x=[carry_x, total_x],
                                y=[carry_y, total_y],
                                mode='lines+markers',
                                line=dict(color=session_colors[session], width=2),
                                marker=dict(
                                    size=8, 
                                    color=session_colors[session], 
                                    opacity=0.7,
                                    symbol=[0, 4]  # 0 = circle for carry, 4 = triangle-up for total
                                ),
                                name=f"{session}",
                                legendgroup=session,
                                showlegend=bool(idx == session_data.index[0]),
                                text=f"Session: {session}<br>Club: {club}<br>Carry: {carry_x:.1f}m, {carry_y:.1f}m<br>Total: {total_x:.1f}m, {total_y:.1f}m",
                                hoverinfo='text'
                            ))
                    elif attribute == '2DMapCarry':
                        x_values = session_data['carryActual'].tolist()
                        y_values = session_data['carrySideActual'].tolist()
                        shot_count = len(x_values)
                        name = f"{session} (n={shot_count})"
                        fig.add_trace(go.Scatter(
                            x=x_values,  # Distance values on x-axis
                            y=y_values,  # Side values on y-axis
                            mode='markers',
                            name=name,
                            marker=dict(
                                color=session_colors[session],
                                size=8,
                                opacity=0.7
                            ),
                            text=[f"Session: {session}<br>Club: {club}<br>Distance: {x:.1f}m<br>Side: {y:.1f}m" 
                                for x, y in zip(x_values, y_values)],
                            hoverinfo='text'
                        ))
                    elif attribute == '2DMapTotal':
                        x_values = session_data['totalActual'].tolist()
                        y_values = session_data['totalSideActual'].tolist()
                        shot_count = len(x_values)
                        name = f"{session} (n={shot_count})"
                        fig.add_trace(go.Scatter(
                            x=x_values,  # Distance values on x-axis
                            y=y_values,  # Side values on y-axis
                            mode='markers',
                            name=name,
                            marker=dict(
                                color=session_colors[session],
                                size=8,
                                opacity=0.7
                            ),
                            text=[f"Session: {session}<br>Club: {club}<br>Total: {x:.1f}m<br>Side: {y:.1f}m" 
                                for x, y in zip(x_values, y_values)],
                            hoverinfo='text'
                        ))
                    else:
                        # For regular 1D attributes, get individual values directly
                        individual_values = session_data[attribute].tolist()
                        shot_count = len(individual_values)
                        
                        # Create y-positions for this session (with some jitter for visibility)
                        y_positions = [i + np.random.uniform(-0.2, 0.2) for _ in individual_values]
                        
                        name = f"{session} (n={shot_count})"
                        
                        fig.add_trace(go.Scatter(
                            x=individual_values,  # Attribute values on x-axis
                            y=y_positions,        # Session positions on y-axis with jitter
                            mode='markers',
                            name=name,
                            marker=dict(
                                color=session_colors[session],
                                size=8,
                                opacity=0.7
                            ),
                            text=[f"Session: {session}<br>Club: {club}<br>{attribute_label}: {val:.2f}" 
                                for val in individual_values],
                            hoverinfo='text'
                        ))
                
                # Update layout for club over time mode
                if attribute == '2DMapCarry-Total':
                    fig.update_layout(
                        title=f'{club} - 2D Carry-Total Map Over Time',
                        xaxis_title='Distance (m)',
                        yaxis_title='Side (m): Right(+) / Left(-)'
                    )
                elif attribute in ['2DMapCarry', '2DMapTotal']:
                    distance_type = 'Carry' if attribute == '2DMapCarry' else 'Total'
                    fig.update_layout(
                        title=f'{club} - 2D {distance_type} Map Over Time',
                        xaxis_title=f'{distance_type} Distance (m)',
                        yaxis_title=f'{distance_type} Side (m): Right(+) / Left(-)'
                    )
                else:
                    # Regular attributes - keep the existing layout
                    fig.update_layout(
                        title=f'{club} - {attribute_label} Individual Shots Over Time',
                        xaxis_title=f'{attribute_label}',  # Attribute values on x-axis
                        yaxis=dict(
                            title='Session',
                            tickmode='array',
                            tickvals=list(range(len(sessions))),
                            ticktext=sessions
                        )
                    )
        else:
            # Gaussian mode - for carry-total lines, we'll show mean positions connected by lines
            # Note: This is a simplified implementation - we could enhance it further
            if attribute == '2DMapCarry-Total':
                print(f"DEBUG: Gaussian mode not fully implemented for {attribute} - showing message")
                # Return a figure with a message that this combination isn't supported
                return go.Figure().add_annotation(
                    text="2D Map Carry-Total only works with Histogram mode.<br>Please switch Plot Type to 'Histogram' to view carry-total lines.",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, 
                    showarrow=False,
                    font=dict(size=16),
                    align="center"
                )
            # Original code for showing means with error ellipses (for carry and total only)
            if comparison_mode == 'clubs' and attribute != '2DMapCarry-Total':
                print(f"DEBUG: Creating {attribute} for clubs comparison - aggregated by session")
                
                # Group data by club and session, calculate means and std devs
                for i, club in enumerate(clubs):
                    club_data = df[df['Club'] == club]
                    print(f"DEBUG: Club {club} has {len(club_data)} total data points")
                    
                    if len(club_data) == 0:
                        continue
                    
                    # Group by session and calculate statistics
                    x_means = []
                    y_means = []
                    x_errors = []
                    y_errors = []
                    hover_texts = []
                    
                    for session in sessions:
                        session_data = club_data[club_data['Session ID'] == session]
                        
                        if len(session_data) == 0:
                            continue
                        
                        # x is distance, y is side
                        x_mean = session_data[x_column].mean()
                        y_mean = session_data[y_column].mean()
                        x_std = session_data[x_column].std() if len(session_data) > 1 else 0
                        y_std = session_data[y_column].std() if len(session_data) > 1 else 0
                        
                        x_means.append(x_mean)
                        y_means.append(y_mean)
                        x_errors.append(x_std)
                        y_errors.append(y_std)
                        
                        distance_type = x_column.replace('Actual', '')
                        hover_texts.append(
                            f"Club: {club}<br>"
                            f"Session: {session}<br>"
                            f"Shots: {len(session_data)}<br>"
                            f"Mean {distance_type}: {x_mean:.1f}±{x_std:.1f}m<br>"
                            f"Mean Side: {y_mean:.1f}±{y_std:.1f}m"
                        )
                    
                    color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

                    # Draw the mean points only (no error_x/error_y)
                    fig.add_trace(go.Scatter(
                        x=x_means,
                        y=y_means,
                        mode='markers',
                        name=f"{club} (n={len(x_means)} sessions)",
                        marker=dict(size=12, color=color, opacity=0.8),
                        text=hover_texts,
                        hoverinfo='text'
                    ))

                    # Now add an ellipse for each point
                    for xm, ym, xs, ys in zip(x_means, y_means, x_errors, y_errors):
                        if xs > 0 and ys > 0:
                            fig.add_shape(
                                type="circle",
                                xref="x", yref="y",
                                x0=xm - xs, x1=xm + xs,
                                y0=ym - ys, y1=ym + ys,
                                fillcolor=color,
                                opacity=0.2,
                                line=dict(width=0),
                                layer="below"
                            )
                        
                        print(f"DEBUG: Added {len(x_means)} data points for club {club}")
            # Mode is 'time' - plot clubs over time    
            elif attribute != '2DMapCarry-Total':
                print(f"DEBUG: Creating {attribute} for time comparison - aggregated by club")
                club = clubs[0]
                club_data = df[df['Club'] == club]
                
                # Group by session and calculate statistics
                x_means = []
                y_means = []
                x_errors = []
                y_errors = []
                session_names = []
                hover_texts = []
                
                # Assign unique colors to each session
                session_colors = {session: px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)] for i, session in enumerate(sessions)}
                
                for i, session in enumerate(sessions):
                    session_data = club_data[club_data['Session ID'] == session]
                    print(f"DEBUG: Session {session} has {len(session_data)} data points")
                    
                    if len(session_data) == 0:
                        continue
                    
                    # x is distance, y is side
                    x_mean = session_data[x_column].mean()
                    y_mean = session_data[y_column].mean()
                    x_std = session_data[x_column].std() if len(session_data) > 1 else 0
                    y_std = session_data[y_column].std() if len(session_data) > 1 else 0
                    
                    distance_type = x_column.replace('Actual', '')
                    hover_texts.append(
                        f"Session: {session}<br>"
                        f"Club: {club}<br>"
                        f"Shots: {len(session_data)}<br>"
                        f"Mean {distance_type}: {x_mean:.1f}±{x_std:.1f}m<br>"
                        f"Mean Side: {y_mean:.1f}±{y_std:.1f}m"
                    )

                    fig.add_trace(go.Scatter(
                        x=[x_mean],
                        y=[y_mean],
                        mode='markers',
                        name=f"Session {session} (n={len(session_data)} shots)",
                        marker=dict(size=12, color=session_colors[session], opacity=0.8),
                        text=hover_texts,
                        hoverinfo='text'
                    ))

                    # Add an ellipse for the session
                    if x_std > 0 and y_std > 0:
                        fig.add_shape(
                            type="circle",
                            xref="x", yref="y",
                            x0=x_mean - x_std, x1=x_mean + x_std,
                            y0=y_mean - y_std, y1=y_mean + y_std,
                            fillcolor=session_colors[session],
                            opacity=0.2,
                            line=dict(width=0),
                            layer="below"
                        )
                    
                    print(f"DEBUG: Added data points for {club} over time")
        
        # Add reference lines for better visualization
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Calculate axis ranges for better presentation
        if attribute == '2DMapCarry-Total':
            # For carry-total lines, we need to consider both carry and total positions
            all_x_values = list(df['carryActual'].values) + list(df['totalActual'].values)
            all_y_values = list(df['carrySideActual'].values) + list(df['totalSideActual'].values)
        else:
            all_x_values = df[x_column].values
            all_y_values = df[y_column].values
        
        x_margin = (max(all_x_values) - min(all_x_values)) * 0.1 if len(all_x_values) > 0 else 10
        y_margin = (max(all_y_values) - min(all_y_values)) * 0.1 if len(all_y_values) > 0 else 10
        
        # Update layout with appropriate axis labels
        if attribute == '2DMapCarry-Total':
            distance_type = 'Carry-Total'
            title_suffix = f" - {comparison_mode.title()} Comparison" if comparison_mode == 'clubs' else f" - {clubs[0]} Over Time"
            fig.update_layout(
                title=f'2D {distance_type} Map{title_suffix}',
                height=700,  # Add fixed height
                showlegend=True,
                legend=dict(
                    title="Clubs" if comparison_mode == 'clubs' else "Sessions",
                    orientation="h",  # Force horizontal orientation for better space usage
                ),
                # axis labels and ranges
                xaxis=dict(
                    range=[min(all_x_values) - x_margin, max(all_x_values) + x_margin],
                    title='Distance (m)',
                    side="top",
                    title_standoff=15,
                    zeroline=True,
                    zerolinecolor='gray',
                    zerolinewidth=1
                ),
                yaxis=dict(
                    range=[max(all_y_values) + y_margin, min(all_y_values) - y_margin],  # INVERTED: max to min
                    title='Side (m): Right(+) / Left(-)', 
                    zeroline=True,
                    zerolinecolor='gray',
                    zerolinewidth=1
                )
            )
        else:
            distance_type = x_column.replace('Actual', '')
            title_suffix = f" - {comparison_mode.title()} Comparison" if comparison_mode == 'clubs' else f" - {clubs[0]} Over Time"
            fig.update_layout(
                title=f'2D {distance_type} Map{title_suffix} (Mean ± SD)',
                height=700,  # Add fixed height
                showlegend=True,
                legend=dict(
                    title="Clubs" if comparison_mode == 'clubs' else "Sessions",
                    orientation="h",  # Force horizontal orientation for better space usage
                ),
                # axis labels and ranges
                xaxis=dict(
                    range=[min(all_x_values) - x_margin, max(all_x_values) + x_margin],
                    title=f'{distance_type} Distance (m)',
                    side="top",
                    title_standoff=15,
                    zeroline=True,
                    zerolinecolor='gray',
                    zerolinewidth=1
                ),
                yaxis=dict(
                    range=[max(all_y_values) + y_margin, min(all_y_values) - y_margin],  # INVERTED: max to min
                    title=f'{distance_type} Side (m): Right(+) / Left(-)', 
                    zeroline=True,
                    zerolinecolor='gray',
                    zerolinewidth=1
                )
            )
        
        print(f"DEBUG: Created figure with {len(fig.data)} traces")
        print(f"DEBUG: Figure layout: {fig.layout}")
        print(f"DEBUG: Figure data: {fig.data}")

        return fig
    else:
        # Original plotting logic for other attributes
        # Filter out rows where the selected attribute is null/NaN
        df = df.dropna(subset=[attribute])
        
        if df.empty:
            return go.Figure().add_annotation(
                text="No data available for selected attribute",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        fig = go.Figure()
        
        # Create a discrete color sequence for sessions
        colors = px.colors.qualitative.Plotly
        
        # Get attribute label for display - updated to match allowed attributes only
        label_mapping = {
            'ballSpeed': 'Ball Speed (km/h)',
            'ballSpin': 'Ball Spin (rpm)', 
            'carryActual': 'Carry (m)',
            'carrySideActual': 'Carry Side (m)',
            'curveActual': 'Curve (m)',
            'launchAngle': 'Launch Angle (°)',
            'maxHeight': 'Height (m)',
            'totalActual': 'Total (m)',
            'totalSideActual': 'Total Side (m)',
        }
        
        attribute_label = label_mapping.get(attribute, attribute.replace('_', ' ').title())
        
        # Initialize sorted_clubs here to avoid scope issues
        sorted_clubs = []
        
        if comparison_mode == 'clubs':
            # Multiple clubs comparison - different colors by session
            session_colors = {session: colors[i % len(colors)] for i, session in enumerate(sessions)}
            
            # Collect all club-session data for sorting
            club_data = []
            for club in clubs:
                club_means = []
                for session in sessions:
                    session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                    
                    if len(session_club_data) == 0:
                        continue
                        
                    # Calculate statistics for the selected attribute
                    attr_mean = session_club_data[attribute].mean()
                    attr_std = session_club_data[attribute].std()
                    shot_count = len(session_club_data)
                    
                    club_means.append({
                        'club': club,
                        'session': session,
                        'mean': attr_mean,
                        'std': attr_std,
                        'count': shot_count
                    })
                
                # Only include club if it has data
                if club_means:
                    avg_mean = sum(item['mean'] for item in club_means) / len(club_means)
                    club_data.append({'club': club, 'avg_mean': avg_mean, 'data': club_means})
            
            # Sort clubs by average mean
            sorted_clubs = [item['club'] for item in sorted(club_data, key=lambda x: x['avg_mean'])]
            
            if plot_type == 'histogram':
# Multiple clubs comparison - show individual shots as scatter
                # Create unique colors for each club-session combination
                club_session_colors = {}
                color_index = 0
                
                for session in sessions:
                    for club in sorted_clubs:
                        club_session_colors[f"{club}-{session}"] = colors[color_index % len(colors)]
                        color_index += 1
                
                for session in sessions:
                    for club_idx, club in enumerate(sorted_clubs):
                        session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                        
                        if len(session_club_data) == 0:
                            continue
                        
                        if attribute == '2DMapCarry-Total':
                            # Add lines from carry to total position for each shot
                            for idx, row in session_club_data.iterrows():
                                carry_x = float(row['carryActual'])
                                carry_y = float(row['carrySideActual']) 
                                total_x = float(row['totalActual'])
                                total_y = float(row['totalSideActual'])
                                
                                # Add line trace for this shot
                                fig.add_trace(go.Scatter(
                                    x=[carry_x, total_x],
                                    y=[carry_y, total_y],
                                    mode='lines+markers',
                                    line=dict(color=club_session_colors[f"{club}-{session}"], width=2),
                                    marker=dict(
                                        size=8, 
                                        color=club_session_colors[f"{club}-{session}"], 
                                        opacity=0.7,
                                        symbol=[0, 4]  # 0 = circle for carry, 4 = triangle-up for total
                                    ),
                                    name=f"{club} - {session}",
                                    legendgroup=f"{club}-{session}",
                                    showlegend=bool(idx == session_club_data.index[0]),
                                    text=f"Club: {club}<br>Session: {session}<br>Carry: {carry_x:.1f}m, {carry_y:.1f}m<br>Total: {total_x:.1f}m, {total_y:.1f}m",
                                    hoverinfo='text'
                                ))
                        elif attribute == '2DMapCarry':
                            x_values = session_club_data['carryActual'].tolist()
                            y_values = session_club_data['carrySideActual'].tolist()
                            shot_count = len(x_values)
                            name = f"{club} - {session} (n={shot_count})"
                            color_key = f"{club}-{session}"
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>Carry: {x:.1f}m<br>Side: {y:.1f}m"
                                      for x, y in zip(x_values, y_values)],
                                hoverinfo='text'
                            ))
                        elif attribute == '2DMapTotal':
                            x_values = session_club_data['totalActual'].tolist()
                            y_values = session_club_data['totalSideActual'].tolist()
                            shot_count = len(x_values)
                            name = f"{club} - {session} (n={shot_count})"
                            color_key = f"{club}-{session}"
                            fig.add_trace(go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>Total: {x:.1f}m<br>Side: {y:.1f}m"
                                      for x, y in zip(x_values, y_values)],
                                hoverinfo='text'
                            ))
                        else:
                            # For regular 1D attributes, get individual values directly
                            individual_values = session_club_data[attribute].tolist()
                            shot_count = len(individual_values)
                            
                            # Create y-positions for this club (with some jitter for visibility)
                            y_positions = [club_idx + np.random.uniform(-0.2, 0.2) for _ in individual_values]
                            
                            name = f"{club} - {session} (n={shot_count})"
                            
                            # Use unique color for each club-session combination
                            color_key = f"{club}-{session}"
                            
                            fig.add_trace(go.Scatter(
                                x=individual_values,  # Attribute values on x-axis
                                y=y_positions,        # Club positions on y-axis with jitter
                                mode='markers',
                                name=name,
                                marker=dict(
                                    color=club_session_colors[color_key],
                                    size=8,
                                    opacity=0.7
                                ),
                                text=[f"Club: {club}<br>Session: {session}<br>{attribute_label}: {val:.2f}" 
                                    for val in individual_values],
                                hoverinfo='text'
                            ))
            else:
                # Scatter with sorted clubs on y-axis
                for club_idx, club in enumerate(sorted_clubs):
                    # Calculate how many sessions this club has
                    club_sessions = [session for session in sessions 
                                    if len(df[(df['Club'] == club) & (df['Session ID'] == session)]) > 0]
                    
                    # Create base position for this club
                    base_position = club_idx
                    
                    # If multiple sessions, spread them around the base position
                    if len(club_sessions) > 1:
                        # Create small offsets around the base position
                        session_offsets = []
                        offset_range = 0.3  # Total spread range (adjust as needed)
                        for i, session in enumerate(club_sessions):
                            if len(club_sessions) == 2:
                                # For 2 sessions: -0.15, +0.15
                                offset = (i - 0.5) * (offset_range / 1)
                            else:
                                # For 3+ sessions: spread evenly
                                offset = (i - (len(club_sessions) - 1) / 2) * (offset_range / (len(club_sessions) - 1))
                            session_offsets.append(offset)
                    else:
                        session_offsets = [0]  # Single session, no offset
                    
                    # Add traces for each session of this club
                    for session_idx, session in enumerate(club_sessions):
                        session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                        
                        if len(session_club_data) == 0:
                            continue
                        
                        attr_mean = session_club_data[attribute].mean()
                        attr_std = session_club_data[attribute].std()
                        shot_count = len(session_club_data)
                        
                        # Calculate the y-position with offset
                        y_position = base_position + session_offsets[session_idx]
                        
                        name = f"{club} - {session} (n={shot_count})"
                        
                        fig.add_trace(go.Scatter(
                            x=[attr_mean],
                            y=[y_position],
                            mode='markers',
                            name=name,
                            marker=dict(size=12, opacity=0.8, color=session_colors[session]),
                            error_x=dict(
                                type='data',
                                array=[attr_std],
                                visible=True,
                                color=session_colors[session]
                            ),
                            text=[f"Club: {club}<br>Session: {session}<br>Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                            hoverinfo='text+name'
                        ))

            # Update layout to use custom y-axis labels
            fig.update_layout(
                title=f'Mean {attribute_label} by Club-Session',
                xaxis_title=f'Mean {attribute_label}',
                yaxis_title='Club',
                yaxis=dict(
                    tickmode='array',
                    tickvals=list(range(len(sorted_clubs))),
                    ticktext=sorted_clubs
                )
            )
        else:
            # Club over time mode - single club, multiple sessions
            club = clubs[0]
            club_data = df[df['Club'] == club]
            
            # Group by session and calculate statistics
            session_colors = {session: colors[i % len(colors)] for i, session in enumerate(sessions)}
            
            for i, session in enumerate(sessions):
                session_data = club_data[club_data['Session ID'] == session]
                
                if len(session_data) == 0:
                    continue
                
                attr_mean = session_data[attribute].mean()
                attr_std = session_data[attribute].std()
                shot_count = len(session_data)
                
                if plot_type == 'histogram':
                    # Get all individual values for this session
                    individual_values = session_data[attribute].tolist()
                    shot_count = len(individual_values)
                    
                    # Create y-positions for this session (with some jitter for visibility)
                    y_positions = [i + np.random.uniform(-0.2, 0.2) for _ in individual_values]
                    
                    name = f"{session} (n={shot_count})"
                    fig.add_trace(go.Scatter(
                        x=individual_values,  # Attribute values on x-axis
                        y=y_positions,        # Session positions on y-axis with jitter
                        mode='markers',
                        name=name,
                        marker=dict(
                            color=session_colors[session],
                            size=8,
                            opacity=0.7
                        ),
                        text=[f"Session: {session}<br>Club: {club}<br>{attribute_label}: {val:.2f}" 
                            for val in individual_values],
                        hoverinfo='text'
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=[attr_mean],
                        y=[len(sessions) - 1 - sessions.index(session)],  # Reverse order
                        mode='markers',
                        name=f"{session} (n={shot_count})",
                        marker=dict(size=12, opacity=0.8, color=session_colors[session]),
                        error_x=dict(
                            type='data',
                            array=[attr_std],
                            visible=True,
                            color=session_colors[session]
                        ),
                        text=[f"Club: {club}<br>Session: {session}<br>Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                        hoverinfo='text+name'
                    ))
            
            if plot_type == 'histogram':
                fig.update_layout(
                    title=f'{club} - {attribute_label} Individual Shots Over Time',
                    xaxis_title=f'{attribute_label}',  # Attribute values on x-axis
                    yaxis=dict(
                        title='Session',
                        tickmode='array',
                        tickvals=list(range(len(sessions))),
                        ticktext=sessions
                    )
                )
            else:
                fig.update_layout(
                    title=f'{club} - {attribute_label} Over Time',
                    xaxis_title=f'Mean {attribute_label}',
                    yaxis_title='Session',
                    yaxis=dict(
                        tickmode='array',
                        tickvals=list(range(len(sessions))),
                        ticktext=list(reversed(sessions))
                    )
                )
    
    # Common layout settings for non-2D maps
    fig.update_layout(
        height=600,  # Add fixed height for regular plots
        legend=dict(
            title="Club - Session" if comparison_mode == 'clubs' else "Sessions",
            orientation="h",  # Force horizontal orientation
        ),
        # Move x-axis title to the top
        xaxis=dict(
            side="top",
            title=dict(
                standoff=15
            )
        )
    )
    
    return fig

@app.callback(
    Output('user-dropdown', 'options'),
    Output('user-dropdown', 'value'),
    Input('main-tabs', 'value'),
    Input('home-dir-store', 'data'),  # Add this input
)
def update_user_dropdown(active_tab, home_dir):
    if active_tab == "analysis":
        users = get_available_users(home_dir)
        options = [{'label': u, 'value': u} for u in users]
        value = users[0] if users else None
        return options, value
    return [], None

@app.callback(
    Output('club-dropdown', 'value', allow_duplicate=True),
    Input('select-all-clubs-btn', 'n_clicks'),
    State('club-dropdown', 'options'),
    State('club-dropdown', 'value'),
    State('comparison-radio', 'value'),
    prevent_initial_call=True
)
def select_all_clubs(n_clicks, available_options, current_selection, comparison_mode):
    if n_clicks is None:
        return current_selection
    
    # For time comparison, only select one club
    if comparison_mode == 'time' and available_options:
        return [available_options[0]['value']]
    
    # For club comparison, select all clubs
    return [option['value'] for option in available_options]

@app.callback(
    Output('session-dropdown', 'value', allow_duplicate=True),
    Input('select-all-sessions-btn', 'n_clicks'),
    State('session-dropdown', 'options'),
    State('session-dropdown', 'value'),
    prevent_initial_call=True
)
def select_all_sessions(n_clicks, available_options, current_selection):
    if n_clicks is None:
        return current_selection
    
    # Return all available sessions
    return [option['value'] for option in available_options]

@app.callback(
    Output('attribute-dropdown', 'options'),
    Output('attribute-dropdown', 'value'),
    Input('user-dropdown', 'value'),
    Input('ball-type-radio', 'value'),
)
def update_attribute_dropdown(username, ball_type):
    if not username:
        return [], None
    
    df = load_data(username, ball_type)
    print(f"DEBUG: update_attribute_dropdown - loaded data shape: {df.shape}")
    print(f"DEBUG: update_attribute_dropdown - columns: {list(df.columns)}")
    
    if df.empty:
        return [], None
    
    # Print a sample of the data to see what we're working with
    print(f"DEBUG: Sample data:")
    print(df.head())
    
    # Define the specific attributes we want to include
    allowed_attributes = {
        'ballSpeed': 'Ball Speed (km/h)',
        'ballSpin': 'Ball Spin (rpm)', 
        'carryActual': 'Carry (m)',
        'carrySideActual': 'Carry Side (m)',
        'curveActual': 'Curve (m)',
        'launchAngle': 'Launch Angle (°)',
        'maxHeight': 'Height (m)',
        'totalActual': 'Total (m)',
        'totalSideActual': 'Total Side (m)',
        '2DMapCarry': '2D Map Carry',
        '2DMapTotal': '2D Map Total',
        '2DMapCarry-Total': '2D Map Carry-Total',
        'custom': 'Custom (select X and Y)'
    }
    
    # Check which of the allowed attributes are actually present in the data
    available_options = []
    for col_name, display_label in allowed_attributes.items():
        if col_name == '2DMapCarry':
            # For 2D map carry, check if both carryActual and carrySideActual exist
            carry_exists = 'carryActual' in df.columns and pd.api.types.is_numeric_dtype(df['carryActual'])
            side_exists = 'carrySideActual' in df.columns and pd.api.types.is_numeric_dtype(df['carrySideActual'])
            print(f"DEBUG: carryActual exists: {carry_exists}")
            print(f"DEBUG: carrySideActual exists: {side_exists}")
            
            if carry_exists and side_exists:
                print(f"DEBUG: Adding 2D Map Carry option")
                available_options.append({'label': display_label, 'value': col_name})
        elif col_name == '2DMapTotal':
            # For 2D map total, check if both totalActual and totalSideActual exist
            total_exists = 'totalActual' in df.columns and pd.api.types.is_numeric_dtype(df['totalActual'])
            total_side_exists = 'totalSideActual' in df.columns and pd.api.types.is_numeric_dtype(df['totalSideActual'])
            print(f"DEBUG: totalActual exists: {total_exists}")
            print(f"DEBUG: totalSideActual exists: {total_side_exists}")
            
            if total_exists and total_side_exists:
                print(f"DEBUG: Adding 2D Map Total option")
                available_options.append({'label': display_label, 'value': col_name})
        elif col_name == '2DMapCarry-Total':
            # For 2D map carry-total, check if all four columns exist
            carry_exists = 'carryActual' in df.columns and pd.api.types.is_numeric_dtype(df['carryActual'])
            carry_side_exists = 'carrySideActual' in df.columns and pd.api.types.is_numeric_dtype(df['carrySideActual'])
            total_exists = 'totalActual' in df.columns and pd.api.types.is_numeric_dtype(df['totalActual'])
            total_side_exists = 'totalSideActual' in df.columns and pd.api.types.is_numeric_dtype(df['totalSideActual'])
            print(f"DEBUG: carryActual exists: {carry_exists}")
            print(f"DEBUG: carrySideActual exists: {carry_side_exists}")
            print(f"DEBUG: totalActual exists: {total_exists}")
            print(f"DEBUG: totalSideActual exists: {total_side_exists}")
            
            if carry_exists and carry_side_exists and total_exists and total_side_exists:
                print(f"DEBUG: Adding 2D Map Carry-Total option")
                available_options.append({'label': display_label, 'value': col_name})
        elif col_name == 'custom':
            # Always add custom option
            available_options.append({'label': display_label, 'value': col_name})
        elif col_name in df.columns and pd.api.types.is_numeric_dtype(df[col_name]):
            print(f"DEBUG: Adding {col_name} option")
            available_options.append({'label': display_label, 'value': col_name})
        else:
            print(f"DEBUG: Skipping {col_name} - not found or not numeric")
    
    # Sort options by display label for better user experience
    available_options = sorted(available_options, key=lambda x: x['label'])
    print(f"DEBUG: Available options: {[opt['label'] for opt in available_options]}")
    
    # Default to carry distance if available, otherwise first available option
    default_value = None
    if available_options:
        if 'carryActual' in [opt['value'] for opt in available_options]:
            default_value = 'carryActual'
        else:
            default_value = available_options[0]['value']
    
    print(f"DEBUG: Default value: {default_value}")
    return available_options, default_value

@app.callback(
    Output("selected-shots-table", "data"),
    Output("filtered-data-store", "data"),
    Input("session-dropdown", "value"),
    Input("club-dropdown", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value")
)
def update_selected_shots_table(selected_sessions, selected_clubs, username, ball_type):
    if not selected_sessions or not selected_clubs or not username:
        return [], []

    # Ensure sessions and clubs are always lists
    if isinstance(selected_sessions, str):
        selected_sessions = [selected_sessions]
    if isinstance(selected_clubs, str):
        selected_clubs = [selected_clubs]

    # Load data for the user and ball type
    df = load_data(username, ball_type)

    # Filter data based on selected sessions and clubs
    filtered_df = df[df["Session ID"].isin(selected_sessions) & df["Club"].isin(selected_clubs)]

    # Add a unique identifier for each row to track deletions
    filtered_df = filtered_df.reset_index().rename(columns={"index": "row_id"})

    # Add delete button and deleted status for each row
    filtered_df["Delete"] = "❌"  # Unicode X mark as delete button
    filtered_df["deleted"] = False  # Track deletion status

    # Prepare data for the table
    table_data = filtered_df[["row_id", "Session ID", "Club", "carryActual", "carrySideActual", "totalActual", "curveActual","ballSpeed","ballSpin","spinAxis","maxHeight","launchAngle", "Delete", "deleted"]].rename(
        columns={
            "Session ID": "Session",
            "carryActual": "Carry",
            "carrySideActual": "CarrySide",
            "launchAngle": "LaunchAngle"
        }
    ).to_dict("records")

    # Store the complete filtered dataframe for later use
    store_data = filtered_df.to_dict("records")

    return table_data, store_data

# Add this new callback after the existing callbacks
@app.callback(
    Output("analysis-plot", "figure", allow_duplicate=True),
    Output("selected-shots-table", "data", allow_duplicate=True),
    Output("filtered-data-store", "data", allow_duplicate=True),
    Output("selected-shots-table", "style_data_conditional", allow_duplicate=True),
    Input("remove-mishits-btn", "n_clicks"),
    State("selected-shots-table", "data"),
    State("filtered-data-store", "data"),
    State("attribute-dropdown", "value"),
    State("comparison-radio", "value"),
    State("plot-type-radio", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value"),
    State("session-dropdown", "value"),
    State("club-dropdown", "value"),
    State("custom-x-dropdown", "value"),   # <-- ADD THIS
    State("custom-y-dropdown", "value"),   # <-- ADD THIS
    prevent_initial_call=True
)
def remove_mishits(n_clicks, table_data, filtered_data, attribute, comparison_mode, 
                   plot_type, username, ball_type, sessions, clubs, custom_x, custom_y):
    if not n_clicks or not table_data or not filtered_data:
        raise dash.exceptions.PreventUpdate
    
    try:
        print(f"DEBUG: Analyzing {len(filtered_data)} shots for mishits")
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(filtered_data)
        
        # Initialize mishit detection
        mishit_indices = set()
        
        # Group by club for analysis (each club has different expected values)
        for club in df['Club'].unique():
            club_data = df[df['Club'] == club].copy()
            
            if len(club_data) < 3:  # Need at least 3 shots for statistical analysis
                continue
            
            print(f"DEBUG: Analyzing {len(club_data)} shots for club {club}")
            
            # 1. Carry distance analysis (detect thin hits and fat hits)
            if 'carryActual' in club_data.columns:
                carry_mean = club_data['carryActual'].mean()
                carry_std = club_data['carryActual'].std()
                
                # Shots that are too short (fat hits) or too long (thin hits, but less common)
                # Use 2 standard deviations as threshold
                carry_threshold_low = carry_mean - 2 * carry_std
                carry_threshold_high = carry_mean + 2.5 * carry_std  # Slightly more lenient for long shots
                
                carry_mishits = club_data[
                    (club_data['carryActual'] < carry_threshold_low) | 
                    (club_data['carryActual'] > carry_threshold_high)
                ]['row_id'].tolist()
                
                mishit_indices.update(carry_mishits)
                print(f"DEBUG: Found {len(carry_mishits)} carry distance mishits for {club}")
            
            # 2. Launch angle analysis (very low = thin, very high = fat)
            if 'launchAngle' in club_data.columns:
                launch_mean = club_data['launchAngle'].mean()
                launch_std = club_data['launchAngle'].std()
                
                # More aggressive thresholds for launch angle
                launch_threshold_low = launch_mean - 2.5 * launch_std
                launch_threshold_high = launch_mean + 2.5 * launch_std
                
                launch_mishits = club_data[
                    (club_data['launchAngle'] < launch_threshold_low) | 
                    (club_data['launchAngle'] > launch_threshold_high)
                ]['row_id'].tolist()
                
                mishit_indices.update(launch_mishits)
                print(f"DEBUG: Found {len(launch_mishits)} launch angle mishits for {club}")
            
            # 3. Ball speed analysis (very low = poor contact)
            if 'ballSpeed' in club_data.columns:
                speed_mean = club_data['ballSpeed'].mean()
                speed_std = club_data['ballSpeed'].std()
                
                # Only flag shots that are significantly slower (poor contact)
                speed_threshold_low = speed_mean - 2 * speed_std
                
                speed_mishits = club_data[
                    club_data['ballSpeed'] < speed_threshold_low
                ]['row_id'].tolist()
                
                mishit_indices.update(speed_mishits)
                print(f"DEBUG: Found {len(speed_mishits)} ball speed mishits for {club}")
            
            # 4. Spin rate analysis (extreme spin rates indicate mishits)
            if 'ballSpin' in club_data.columns:
                spin_mean = club_data['ballSpin'].mean()
                spin_std = club_data['ballSpin'].std()
                
                # Very high or very low spin rates
                spin_threshold_low = spin_mean - 2.5 * spin_std
                spin_threshold_high = spin_mean + 2.5 * spin_std
                
                spin_mishits = club_data[
                    (club_data['ballSpin'] < spin_threshold_low) | 
                    (club_data['ballSpin'] > spin_threshold_high)
                ]['row_id'].tolist()
                
                mishit_indices.update(spin_mishits)
                print(f"DEBUG: Found {len(spin_mishits)} spin rate mishits for {club}")
            
            # 5. Extreme side deviation (indicates poor contact/alignment)
            if 'carrySideActual' in club_data.columns:
                side_std = club_data['carrySideActual'].std()
                side_abs_mean = club_data['carrySideActual'].abs().mean()
                
                # Flag shots with extreme side deviation
                side_threshold = side_abs_mean + 2 * side_std
                
                side_mishits = club_data[
                                       club_data['carrySideActual'].abs() > side_threshold
                ]['row_id'].tolist()
                
                mishit_indices.update(side_mishits)
                print(f"DEBUG: Found {len(side_mishits)} side deviation mishits for {club}")
        
        print(f"DEBUG: Total unique mishits identified: {len(mishit_indices)}")
        
        if not mishit_indices:
            print("DEBUG: No mishits detected")
            raise dash.exceptions.PreventUpdate
        
        # Update table data to mark mishits as deleted
        updated_table_data = []
        for row in table_data:
            row_copy = row.copy()
            if row_copy["row_id"] in mishit_indices:
                row_copy["deleted"] = True
                row_copy["Delete"] = "↶"  # Undo symbol
            updated_table_data.append(row_copy)
        
        # Update filtered data to mark mishits as deleted
        updated_filtered_data = []
        for row in filtered_data:
            row_copy = row.copy()
            if row_copy["row_id"] in mishit_indices:
                row_copy["deleted"] = True
            updated_filtered_data.append(row_copy)
        
        # Create style data conditional for greying out deleted rows
        style_data_conditional = [
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
            },
            {
                'if': {
                    'filter_query': '{deleted} = true',
                },
                'backgroundColor': 'rgb(255, 220, 220)',  # Light red for mishits
                'color': 'rgb(128, 128, 128)',
                'textDecoration': 'line-through'
            }
        ]
        
        # Filter out deleted shots for the plot (but keep them in table)
        plot_data = [row for row in updated_filtered_data if not row.get("deleted", False)]
        
        print(f"DEBUG: Active shots for plot after mishit removal: {len(plot_data)}")
        
        # If we removed all shots, return empty plot
        if not plot_data:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title=f"No active shots selected ({len(mishit_indices)} mishits removed)",
                height=600,
                xaxis_title="No data",
                yaxis_title="No data"
            )
            return empty_fig, updated_table_data, updated_filtered_data, style_data_conditional
        
        # Use the generate_plot function with only the non-deleted data
        updated_fig = generate_plot(1, username, ball_type, comparison_mode, 
                                    plot_type, sessions, clubs, attribute, 
                                    custom_data=plot_data, custom_x=custom_x,
        custom_y=custom_y
    )
        
        # Update the title to show how many mishits were removed
        current_title = updated_fig.layout.title.text if updated_fig.layout.title else "Analysis"
        updated_fig.update_layout(
            title=f"{current_title} ({len(mishit_indices)} mishits removed)"
        )
        
        return updated_fig, updated_table_data, updated_filtered_data, style_data_conditional
        
    except Exception as e:
        print(f"ERROR in remove_mishits: {e}")
        raise dash.exceptions.PreventUpdate

# Remove the browse button from the callback inputs and parameters
@app.callback(
    Output("home-dir-status", "children"),
    Output("home-dir-input", "value"),
    Output("home-dir-store", "data"),
    Input("set-home-dir-btn", "n_clicks"),
    Input("reset-home-dir-btn", "n_clicks"),  # Remove browse-home-dir-btn
    State("home-dir-input", "value"),
    State("home-dir-store", "data"),
    prevent_initial_call=True
)
def handle_home_directory_actions(set_clicks, reset_clicks, input_path, current_home_dir):  # Remove browse_clicks parameter
    triggered = ctx.triggered_id
   
    status = ""
    new_path = input_path
    
    if triggered == "set-home-dir-btn" and input_path:
        if os.path.exists(input_path) and os.path.isdir(input_path):
            if set_home_dir(input_path):
                status = f"✅ Home directory set to: {input_path}"
                
                # Create necessary subdirectories
                try:
                    os.makedirs(os.path.join(input_path, "tokens"), exist_ok=True)
                    os.makedirs(os.path.join(input_path, "Data"), exist_ok=True)
                    os.makedirs(os.path.join(input_path, "plots"), exist_ok=True)
                    status += " (Created subdirectories: tokens, Data, plots)"
                except Exception as e:
                    status += f" (Warning: Could not create subdirectories: {e})"
                
                return status, input_path, input_path
            else:
                status = "❌ Failed to set home directory"
        else:
            status = "❌ Invalid directory path. Please enter a valid directory."
            
    elif triggered == "reset-home-dir-btn":
        #default_home = str(Path.home())
        default_home = os.path.join(Path.home(), "Desktop/Golf")
        if set_home_dir(default_home):
            status = f"✅ Home directory reset to default: {default_home}"
            new_path = default_home
            return status, new_path, new_path
        else:
            status = "❌ Failed to reset to default home directory"
    
    return status, new_path, current_home_dir or str(Path.home())

@app.callback(
    Output("download-data", "data", allow_duplicate=True),
    Input("download-selected-btn", "n_clicks"),
    State("selected-username-store", "data"),
    State("ball-type-dropdown", "value"),
    State("activities-table", "selected_rows"),
    State("activities-store", "data"),
    State("current-token-store", "data"),
    prevent_initial_call=True
)
def download_selected_activity(n_clicks, username, ball_type, selected_rows, activities, current_token):
    if not n_clicks or not selected_rows or not activities:
        raise dash.exceptions.PreventUpdate

    selected_idx = selected_rows[0]
    selected_activity = activities[selected_idx]

    api = trackman.TrackManAPI()
    api.auth_token = current_token
    api.headers["Authorization"] = f"Bearer {current_token}"

    if ball_type == "BOTH":
        # Create a zip file for both ball types
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for bt in ["RANGE", "PREMIUM"]:
                shot_data = api.get_range_practice_shots(selected_activity.get('id'), bt)
                if not shot_data or not shot_data.get("shots"):
                    continue
                # Add session metadata
                for shot in shot_data.get("shots", []):
                    shot["session_number"] = selected_idx + 1
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                csv_content, filename = save_shots_to_csv(shot_data, ball_type=bt, username=username)
                # Only the filename part for the zip (not full path)
                zip_file.writestr(os.path.basename(filename), csv_content)
                
        zip_buffer.seek(0)
        return dcc.send_bytes(zip_buffer.getvalue(), "trackman_sessions.zip")
    else:
        # Download the shot data
        shot_data = api.get_range_practice_shots(selected_activity.get('id'), ball_type)
        if not shot_data or not shot_data.get("shots"):
            raise dash.exceptions.PreventUpdate
        
        csv_content,filename = save_shots_to_csv(shot_data, ball_type=ball_type, username=username)

        # Return as CSV download
        return dcc.send_bytes(csv_content.encode("utf-8"), filename)

@app.callback(
    Output("download-data", "data"),
    Input("download-all-btn", "n_clicks"),
    State("selected-username-store", "data"),
    State("ball-type-dropdown", "value"),
    State("activities-store", "data"),
    State("current-token-store", "data"),
    prevent_initial_call=True
)
def download_all_activities(n_clicks, username, ball_type, activities, current_token):
    if not n_clicks or not activities:
        raise dash.exceptions.PreventUpdate

    api = trackman.TrackManAPI()
    api.auth_token = current_token
    api.headers["Authorization"] = f"Bearer {current_token}"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, activity in enumerate(activities):
            if ball_type == "BOTH":
                for bt in ["RANGE", "PREMIUM"]:
                    shot_data = api.get_range_practice_shots(activity.get('id'), bt)
                    if not shot_data or not shot_data.get("shots"):
                        continue
                    # Add session metadata
                    for shot in shot_data.get("shots", []):
                        shot["session_number"] = idx + 1
                        shot["session_time"] = activity.get("time")
                        shot["session_kind"] = activity.get("kind")
                    csv_content, filename = save_shots_to_csv(shot_data, ball_type=bt, username=username)
                    # Only the filename part for the zip (not full path)
                    zip_file.writestr(os.path.basename(filename), csv_content)
            else:
                shot_data = api.get_range_practice_shots(activity.get('id'), ball_type)
                if not shot_data or not shot_data.get("shots"):
                    continue
                # Add session metadata
                for shot in shot_data.get("shots", []):
                    shot["session_number"] = idx + 1
                    shot["session_time"] = activity.get("time")
                    shot["session_kind"] = activity.get("kind")
                csv_content, filename = save_shots_to_csv(shot_data, ball_type=ball_type, username=username)
                # Only the filename part for the zip (not full path)
                zip_file.writestr(os.path.basename(filename), csv_content)

    zip_buffer.seek(0)
    return dcc.send_bytes(zip_buffer.getvalue(), "trackman_sessions.zip")

# Add a function to save plots to the home directory
def save_plot_to_home(fig, filename, home_dir=None):
    """Save a plotly figure to the plots directory in home_dir"""
    if home_dir is None:
        home_dir = get_home_dir()
    
    plots_dir = os.path.join(home_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    # Save as HTML
    html_path = os.path.join(plots_dir, f"{filename}.html")
    fig.write_html(html_path)
    
    # Save as PNG (requires kaleido)
    try:
        png_path = os.path.join(plots_dir, f"{filename}.png")
        fig.write_image(png_path, width=1200, height=800)
        return f"Plot saved to: {html_path} and {png_path}"
    except Exception as e:
        return f"Plot saved to: {html_path} (PNG save failed: {e})"

if __name__ == '__main__':
    app.run_server(debug=True, port=8050)  # Set use_reloader=False to avoid double callbacks