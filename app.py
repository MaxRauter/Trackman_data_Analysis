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

# Import the trackman module for authentication
spec = importlib.util.spec_from_file_location("trackman", "trackman.py")
trackman = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trackman)

def load_data(username, ball_type):
    data_dir = os.path.join('Data', username, ball_type)
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

def get_available_users():
    data_root = "Data"
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
    
    # Tabs
    dcc.Tabs(id="main-tabs", value="login", children=[
        # Login Tab
        dcc.Tab(label="Login", value="login", children=[
            html.Div([
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
                        {"name": "Total Shots", "id": "TotalShots"},
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
                    page_size=10  # Limit to 10 rows per page
                ),
                
                html.Br(),
                html.Div([
                    html.Button("Download Selected", id="download-selected-btn", style={'margin-right': '10px'}),
                    html.Button("Download All", id="download-all-btn", style={'margin-right': '10px'}),
                    html.Button("Download Missing", id="download-missing-btn"),
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
                html.Div([
                    html.Label("User:"),
                    dcc.Dropdown(id='user-dropdown', style={'width': '200px', 'display': 'inline-block', 'margin-right': '10px'}),
                    html.Label("Ball Type:"),
                    dcc.RadioItems(
                        id='ball-type-radio',
                        options=[{'label': 'Range', 'value': 'range'}, {'label': 'Premium', 'value': 'premium'}],
                        value='range',
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    ),
                ], style={'margin-bottom': '20px'}),
                
                html.Div([
                    html.Label("Attribute to Plot:"),
                    dcc.Dropdown(
                        id='attribute-dropdown',
                        placeholder="Select attribute to analyze",
                        style={'width': '300px', 'display': 'inline-block', 'margin-right': '20px'}
                    ),
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
                            {'label': 'Histogram', 'value': 'histogram'}
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
                ], style={'margin-bottom': '20px'}),
                html.Button("Generate Plot", id='plot-btn', n_clicks=0),
                dcc.Loading(dcc.Graph(id='analysis-plot'), type="circle"),
                
                # New table for selected shots
                html.Div([
                    html.H4("Selected Shots"),
                    dash_table.DataTable(
                        id="selected-shots-table",
                        columns=[
                            {"name": "Session", "id": "Session"},
                            {"name": "Club", "id": "Club"},
                            {"name": "Carry (m)", "id": "Carry"},
                            {"name": "Carry Side (m)", "id": "CarrySide"},
                            {"name": "Launch Angle (°)", "id": "LaunchAngle"},
                            {"name": "Delete", "id": "Delete", "presentation": "markdown"}
                        ],
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
                        page_size=10  # Limit to 10 rows per page
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
    Input("main-tabs", "value")  # Trigger when login tab is selected
)
def update_token_dropdown(active_tab):
    if active_tab == "login":
        tokens = trackman.check_saved_tokens()
        options = [{'label': username, 'value': username} for username in tokens.keys()]
        return options, None
    return [], None

@app.callback(
    Output("login-status", "children"),
    Output("save-token-btn", "disabled"),
    Output("selected-username-store", "data"),
    Input("use-token-btn", "n_clicks"),
    Input("new-login-btn", "n_clicks"),
    Input("logout-btn", "n_clicks"),
    Input("logout-all-btn", "n_clicks"),
    Input("save-token-btn", "n_clicks"),
    State("token-dropdown", "value"),
    State("username-input", "value"),
    prevent_initial_call=True
)
def handle_login_actions(use_token, new_login, logout, logout_all, save_token, selected_user, username_input):
    triggered = ctx.triggered_id
    status = ""
    save_disabled = True
    selected_username = ""
    
    api = trackman.TrackManAPI()
    tokens = trackman.check_saved_tokens()
    
    if triggered == "use-token-btn" and selected_user:
        token = tokens.get(selected_user)
        if token:
            api.auth_token = token
            api.headers["Authorization"] = f"Bearer {token}"
            if api.test_connection():
                status = f"Successfully logged in as {selected_user}"
                save_disabled = False
                selected_username = selected_user
            else:
                status = "Token is invalid, please login again"
        else:
            status = "No token found for selected user"
            
    elif triggered == "new-login-btn":
        status = "Starting browser login... (Note: This would open a browser window in the full implementation)"
        # In a real implementation, you would start the login flow here
        save_disabled = False
        
    elif triggered == "logout-btn" and selected_user:
        trackman.invalidate_token(selected_user)
        status = f"Logged out {selected_user}"
        
    elif triggered == "logout-all-btn":
        trackman.invalidate_token()
        status = "Logged out all users"
        
    elif triggered == "save-token-btn" and username_input:
        # In a real implementation, you would use the actual token from login
        # For now, this is just a placeholder
        status = f"Token save functionality would be implemented here for {username_input}"
        save_disabled = True
        
    return status, save_disabled, selected_username

# Activities callbacks
@app.callback(
    Output("activities-log", "children"),
    Output("activities-table", "data"),
    Output("activities-store", "data"),
    Input("refresh-activities-btn", "n_clicks"),
    Input("download-selected-btn", "n_clicks"),
    Input("download-all-btn", "n_clicks"),
    Input("download-missing-btn", "n_clicks"),
    State("selected-username-store", "data"),
    State("ball-type-dropdown", "value"),
    State("activities-table", "selected_rows"),
    State("activities-store", "data"),
    prevent_initial_call=True,
)
def handle_activities_actions(refresh_clicks, download_selected_clicks, download_all_clicks, 
                            download_missing_clicks, username, ball_type, selected_rows, activities):
    triggered = ctx.triggered_id
    
    if not username:
        return "No user logged in. Please login first.", [], []
    
    # Initialize API with stored credentials
    api = trackman.TrackManAPI()
    tokens = trackman.check_saved_tokens()
    token = tokens.get(username)
    
    if not token:
        return "No valid token found. Please login again.", [], []
    
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
                
                # Get total shot count from activity
                total_shots = activity.get("totalCount", 0)
                
                table_data.append({
                    "ID": i + 1,
                    "Date": date_str,
                    "Type": activity.get("kind", "Unknown"),
                    "TotalShots": total_shots
                })
            
            log_message = f"Found {len(range_activities)} range practice activities (sorted chronologically, oldest = #1)"
            return log_message, table_data, range_activities
            
        except Exception as e:
            return f"Error fetching activities: {str(e)}", [], []
    
    elif triggered in ["download-selected-btn", "download-all-btn", "download-missing-btn"]:
        if not activities:
            return "No activities available. Please refresh activities first.", [], []
        
        try:
            if triggered == "download-selected-btn":
                if not selected_rows:
                    return "No activity selected. Please select an activity to download.", [], []
                
                selected_idx = selected_rows[0]
                if selected_idx >= len(activities):
                    return "Invalid selection.", [], []
                
                selected_activity = activities[selected_idx]
                log_message = f"Downloading selected activity: {selected_activity.get('time', 'Unknown')[:10]}\n"
                
                # Download logic here - similar to interface.py
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
                            api.save_shots_to_csv(shot_data, ball_type=bt, username=username)
                            log_message += f"Downloaded {len(shot_data.get('shots', []))} {bt} shots\n"
                else:
                    shot_data = api.get_range_practice_shots(selected_activity.get('id'), ball_type)
                    if shot_data and shot_data.get("shots"):
                        # Add session metadata
                        for shot in shot_data.get("shots", []):
                            shot["session_number"] = selected_idx + 1
                            shot["session_time"] = selected_activity.get("time")
                            shot["session_kind"] = selected_activity.get("kind")
                        api.save_shots_to_csv(shot_data, ball_type=ball_type, username=username)
                        log_message += f"Downloaded {len(shot_data.get('shots', []))} {ball_type} shots\n"
                
                return log_message, [], []
                
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
                                api.save_shots_to_csv(shot_data, ball_type=bt, username=username)
                                log_message += f"Session {idx+1}: Downloaded {len(shot_data.get('shots', []))} {bt} shots\n"
                    else:
                        shot_data = api.get_range_practice_shots(activity.get('id'), ball_type)
                        if shot_data and shot_data.get("shots"):
                            for shot in shot_data.get("shots", []):
                                shot["session_number"] = idx + 1
                                shot["session_time"] = activity.get("time")
                                shot["session_kind"] = activity.get("kind")
                            api.save_shots_to_csv(shot_data, ball_type=ball_type, username=username)
                            log_message += f"Session {idx+1}: Downloaded {len(shot_data.get('shots', []))} shots\n"
                
                return log_message, [], []
                
            elif triggered == "download-missing-btn":
                # Check for missing sessions
                existing_pro_sessions, existing_range_sessions = trackman.get_existing_sessions(username)
                missing_activities = []
                
                for idx, activity in enumerate(activities):
                    # Convert activity time to date string
                    activity_time = activity.get("time", "")
                    activity_date = ""
                    
                    if activity_time:
                        try:
                            dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                            activity_date = dt.strftime("%Y%m%d")
                        except:
                            continue
                    
                    session_num = str(idx + 1)
                    
                    # Check which sessions are missing
                    pro_missing = (activity_date, session_num) not in existing_pro_sessions
                    range_missing = (activity_date, session_num) not in existing_range_sessions
                    
                    if ball_type == "PREMIUM" and pro_missing:
                        missing_activities.append((idx, activity, ["PREMIUM"]))
                    elif ball_type == "RANGE" and range_missing:
                        missing_activities.append((idx, activity, ["RANGE"]))
                    elif ball_type == "BOTH" and (pro_missing or range_missing):
                        missing_balls = []
                        if pro_missing:
                            missing_balls.append("PREMIUM")
                        if range_missing:
                            missing_balls.append("RANGE")
                        missing_activities.append((idx, activity, missing_balls))
                
                if not missing_activities:
                    return "All sessions are already saved. No missing sessions found.", [], []
                
                log_message = f"Found {len(missing_activities)} missing sessions. Downloading...\n"
                
                for idx, activity, missing_ball_types in missing_activities:
                    for bt in missing_ball_types:
                        shot_data = api.get_range_practice_shots(activity.get('id'), bt)
                        if shot_data and shot_data.get("shots"):
                            for shot in shot_data.get("shots", []):
                                shot["session_number"] = idx + 1
                                shot["session_time"] = activity.get("time")
                                shot["session_kind"] = activity.get("kind")
                            api.save_shots_to_csv(shot_data, ball_type=bt, username=username)
                            log_message += f"Session {idx+1}: Downloaded {len(shot_data.get('shots', []))} {bt} shots\n"
                
                return log_message, [], []
                
        except Exception as e:
            return f"Error during download: {str(e)}", [], []
    
    return "", [], []

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
    Input('attribute-dropdown', 'value'),
)
def update_sessions_and_clubs(username, ball_type, selected_sessions, comparison_mode, attribute):
    if not username or not attribute:
        return [], [], [], [], True
        
    df = load_data(username, ball_type)
    
    # Handle filtering for 2D Map Carry
    if attribute == '2DMapCarry':
        # Filter out rows where either carryActual or carrySideActual is null/NaN
        df = df.dropna(subset=['carryActual', 'carrySideActual'])
    else:
        # Filter out rows where the selected attribute is null/NaN
        df = df.dropna(subset=[attribute])
    
    # Get all available sessions
    sessions = sorted(df['Session ID'].unique())
    session_options = [{'label': s, 'value': s} for s in sessions]
    
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
    
    # Get clubs from filtered data
    clubs = sorted([c for c in filtered_df['Club'].unique() if pd.notna(c)])
    club_options = [{'label': c, 'value': c} for c in clubs]
    
    # Set multi-selection based on comparison mode
    multi_selection = comparison_mode != 'time'
    
    # For 'time' mode, limit to one club selection
    club_value = []
    if comparison_mode == 'time' and clubs:
        club_value = [clubs[0]] if clubs else []
    
    return session_options, selected_sessions, club_options, club_value, multi_selection

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
    State('filtered-data-store', 'data'),  # Add this state parameter
)
def generate_plot(n_clicks, username, ball_type, comparison_mode, plot_type, sessions, clubs, attribute, custom_data=None):
    print(f"DEBUG: generate_plot called with:")
    print(f"  n_clicks: {n_clicks}")
    print(f"  username: {username}")
    print(f"  ball_type: {ball_type}")
    print(f"  sessions: {sessions}")
    print(f"  clubs: {clubs}")
    print(f"  attribute: {attribute}")
    print(f"  custom_data: {'Provided' if custom_data else 'Not provided'}")
    
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
    
    # Handle 2D Map Carry specially
    if attribute == '2DMapCarry':
        print("DEBUG: Processing 2D Map Carry - USING REAL DATA")
        
        # Filter out rows where either carryActual or carrySideActual is null/NaN
        before_filter = len(df)
        df = df.dropna(subset=['carryActual', 'carrySideActual'])
        after_filter = len(df)
        print(f"DEBUG: Filtered from {before_filter} to {after_filter} rows")
        
        if df.empty:
            return go.Figure().add_annotation(
                text="No data available for 2D Map Carry (need both Carry and Carry Side data)",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
        
        print(f"DEBUG: Data sample:")
        print(f"  carrySideActual: {df['carrySideActual'].head().tolist()}")
        print(f"  carryActual: {df['carryActual'].head().tolist()}")
        print(f"  Clubs: {df['Club'].unique().tolist()}")
        
        # Create scatter plot
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        # Check if plot_type is histogram (individual shots) or gaussian (means with error ellipses)
        if plot_type == 'histogram':
            # Plot individual shots
            if comparison_mode == 'clubs':
                # Add this debug information
                print(f"DEBUG: Starting 2D Map histogram plot with {len(df)} rows")
                print(f"DEBUG: Available columns before filtering: {df.columns.tolist()}")
                print(f"DEBUG: Selected sessions: {sessions}")
                print(f"DEBUG: Selected clubs: {clubs}")
                
                for i, club in enumerate(clubs):
                    club_data = df[df['Club'] == club]
                    print(f"DEBUG: Found {len(club_data)} rows for club {club}")
                    
                    if len(club_data) == 0:
                        continue
                    
                    color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]
                    
                    for session in sessions:
                        # Check both column names for sessions
                        session_data = None
                        if 'Session ID' in club_data.columns:
                            session_data = club_data[club_data['Session ID'] == session]
                            session_col = 'Session ID'
                        elif 'Session' in club_data.columns:
                            session_data = club_data[club_data['Session'] == session]
                            session_col = 'Session'
                        else:
                            print(f"ERROR: Can't find session column for {session}")
                            continue
                        
                        print(f"DEBUG: Found {len(session_data)} rows for {session} using '{session_col}'")
                        
                        if len(session_data) == 0:
                            continue
                        
                        # Ensure access to carry and carrySide data
                        x_column = 'carryActual'
                        y_column = 'carrySideActual'
                        
                        # Make sure the data is numeric
                        session_data[x_column] = pd.to_numeric(session_data[x_column], errors='coerce')
                        session_data[y_column] = pd.to_numeric(session_data[y_column], errors='coerce')
                        
                        # Drop any NaN values
                        session_data = session_data.dropna(subset=[x_column, y_column])
                        
                        if len(session_data) == 0:
                            print(f"DEBUG: No valid numeric data for {club} - {session}")
                            continue
                        
                        # Print first few values to debug
                        print(f"DEBUG: First few x values: {session_data[x_column].head().tolist()}")
                        print(f"DEBUG: First few y values: {session_data[y_column].head().tolist()}")
                        
                        # Add trace
                        fig.add_trace(go.Scatter(
                            x=session_data[x_column],
                            y=session_data[y_column],
                            mode='markers',
                            name=f"{club} - {session} (n={len(session_data)})",
                            marker=dict(size=8, color=color, opacity=0.7),
                            text=[f"Club: {club}<br>Session: {session}<br>Carry: {x:.1f}m<br>Side: {y:.1f}m"
                                  for x, y in zip(session_data[x_column], session_data[y_column])],
                            hoverinfo='text'
                        ))
                        
                        print(f"DEBUG: Added trace with {len(session_data)} valid points")
                        
                        
            # After adding all traces, update the layout to ensure proper scaling
            if len(fig.data) > 0:  # Only if we actually added traces
                # Collect all x and y values across all traces
                all_x = []
                all_y = []
                for trace in fig.data:
                    if hasattr(trace, 'x') and trace.x is not None:
                        all_x.extend([x for x in trace.x if pd.notna(x)])
                    if hasattr(trace, 'y') and trace.y is not None:
                        all_y.extend([y for y in trace.y if pd.notna(y)])
                
                print(f"DEBUG: Calculated {len(all_x)} valid x points and {len(all_y)} valid y points")
                
                if all_x and all_y:
                    x_min = min(all_x)
                    x_max = max(all_x)
                    y_min = min(all_y)
                    y_max = max(all_y)
                    
                    x_margin = (x_max - x_min) * 0.1 if x_min != x_max else 10
                    y_margin = (y_max - y_min) * 0.1 if y_min != y_max else 5
                    
                    print(f"DEBUG: Setting x range to [{x_min-x_margin}, {x_max+x_margin}]")
                    print(f"DEBUG: Setting y range to [{y_max+y_margin}, {y_min-y_margin}] (inverted)")
                    
                    # Configure the overall layout
                    fig.update_layout(
                        title=f"2D Shot Distribution - {'' if comparison_mode == 'clubs' else clubs[0] + ' '}Histogram Plot",
                        xaxis=dict(
                            range=[x_min - x_margin, x_max + x_margin],
                            title='Carry Distance (m)',
                            side="top",
                            title_standoff=15,
                        ),
                        yaxis=dict(
                            range=[y_max + y_margin, y_min - y_margin],  # Inverted Y axis
                            title='Carry Side (m): Right(+) / Left(-)'
                        ),
                        showlegend=True
                    )
                    
                    # Add reference lines
                    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
                else:
                    print("DEBUG: Could not calculate axes ranges - no valid points")
            else:
                # Club over time - plot individual shots by session
                club = clubs[0]
                club_data = df[df['Club'] == club]
                print(f"DEBUG: Found {len(club_data)} rows for club {club}")
                
                # Assign unique colors to each session
                session_colors = {session: colors[i % len(colors)] for i, session in enumerate(sessions)}
                
                for session in sessions:
                    # First determine which column to use for session filtering
                    if 'Session ID' in club_data.columns:
                        session_data = club_data[club_data['Session ID'] == session]
                        session_col = 'Session ID'
                    elif 'Session' in club_data.columns:
                        session_data = club_data[club_data['Session'] == session]
                        session_col = 'Session'
                    else:
                        print(f"ERROR: Can't find session column for {session}")
                        continue
                        
                    print(f"DEBUG: Found {len(session_data)} rows for {session} using '{session_col}'")
                    
                    if len(session_data) == 0:
                        continue
                    
                    # Ensure we have numeric data
                    session_data['carryActual'] = pd.to_numeric(session_data['carryActual'], errors='coerce')
                    session_data['carrySideActual'] = pd.to_numeric(session_data['carrySideActual'], errors='coerce')
                    
                    # Drop any NaN values
                    session_data = session_data.dropna(subset=['carryActual', 'carrySideActual'])
                    
                    if len(session_data) == 0:
                        print(f"DEBUG: No valid numeric data for {session}")
                        continue
                        
                    fig.add_trace(go.Scatter(
                        x=session_data['carryActual'],
                        y=session_data['carrySideActual'],
                        mode='markers',
                        name=f"{session} (n={len(session_data)})",
                        marker=dict(size=8, color=session_colors[session], opacity=0.7),
                        text=[f"Session: {session}<br>Club: {club}<br>Carry: {x:.1f}m<br>Side: {y:.1f}m"
                              for x, y in zip(session_data['carryActual'], session_data['carrySideActual'])],
                        hoverinfo='text'
                    ))
                
                print(f"DEBUG: Added {len(club_data)} individual shots for club {club}")
        else:
            # Original code for showing means with error ellipses
            if comparison_mode == 'clubs':
                print("DEBUG: Creating 2D map for clubs comparison - aggregated by session")
                
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
                        
                        # SWAPPED: x is now carry, y is now carry side
                        x_mean = session_data['carryActual'].mean()
                        y_mean = session_data['carrySideActual'].mean()
                        x_std = session_data['carryActual'].std() if len(session_data) > 1 else 0
                        y_std = session_data['carrySideActual'].std() if len(session_data) > 1 else 0
                        
                        x_means.append(x_mean)
                        y_means.append(y_mean)
                        x_errors.append(x_std)
                        y_errors.append(y_std)
                        
                        hover_texts.append(
                            f"Club: {club}<br>"
                            f"Session: {session}<br>"
                            f"Shots: {len(session_data)}<br>"
                            f"Mean Carry: {x_mean:.1f}±{x_std:.1f}m<br>"
                            f"Mean Side: {y_mean:.1f}±{y_std:.1f}m"
                        )
                    
                    color = px.colors.qualitative.Plotly[i % len(px.colors.qualitative.Plotly)]

                    # Draw the mean‐points only (no error_x/error_y)
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
            else:
                print("DEBUG: Creating 2D map for time comparison - aggregated by club")
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
                    
                    # SWAPPED: x is now carry, y is now carry side
                    x_mean = session_data['carryActual'].mean()
                    y_mean = session_data['carrySideActual'].mean()
                    x_std = session_data['carryActual'].std() if len(session_data) > 1 else 0
                    y_std = session_data['carrySideActual'].std() if len(session_data) > 1 else 0
                    
                    hover_texts.append(
                        f"Session: {session}<br>"
                        f"Club: {club}<br>"
                        f"Shots: {len(session_data)}<br>"
                        f"Mean Carry: {x_mean:.1f}±{x_std:.1f}m<br>"
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
                    
                    print(f"DEBUG: Added {len(x_means)} data points for {club} over time")
        
        # Add reference lines for better visualization
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Calculate axis ranges for better presentation
        # SWAPPED: x values are now carry, y values are now carry side
        x_values = df['carryActual'].values
        y_values = df['carrySideActual'].values
        
        x_margin = (max(x_values) - min(x_values)) * 0.1 if len(x_values) > 0 else 10
        y_margin = (max(y_values) - min(y_values)) * 0.1 if len(y_values) > 0 else 10
        
        # Update layout with swapped axis labels
        title_suffix = f" - {comparison_mode.title()} Comparison" if comparison_mode == 'clubs' else f" - {clubs[0]} Over Time"
        fig.update_layout(
            title=f'2D Carry Map{title_suffix} (Mean ± SD)',
            showlegend=True,
            legend=dict(
                title="Clubs" if comparison_mode == 'clubs' else "Sessions",
                orientation="h" if len(clubs) * len(sessions) > 6 else "v",
            ),
            # Remove custom height to match other plots
            # SWAPPED axis labels and ranges
            xaxis=dict(
                range=[min(x_values) - x_margin, max(x_values) + x_margin],
                title='Carry Distance (m)',
                side="top",
                title_standoff=15,
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            ),
            yaxis=dict(
                range=[max(y_values) + y_margin, min(y_values) - y_margin],  # INVERTED: max to min
                title='Carry Side (m): Right(+) / Left(-)', 
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            )
        )
        
        print(f"DEBUG: Created figure with {len(fig.data)} traces")
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
            'ballSpeed': 'Ball Speed (mph)',
            'ballSpin': 'Ball Spin (rpm)', 
            'carryActual': 'Carry (m)',
            'carrySideActual': 'Carry Side (m)',
            'curveActual': 'Curve (m)',
            'launchAngle': 'Launch Angle (°)',
            'maxHeight': 'Height (m)',
            'totalActual': 'Total (m)',
            'totalSideActual': 'Total Side (m)'
        }
        
        attribute_label = label_mapping.get(attribute, attribute.replace('_', ' ').title())
        
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
                # Create bar chart with sorted clubs on x-axis
                for session in sessions:
                    for club in sorted_clubs:
                        session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                        
                        if len(session_club_data) == 0:
                            continue
                            
                        attr_mean = session_club_data[attribute].mean()
                        attr_std = session_club_data[attribute].std()
                        shot_count = len(session_club_data)
                        
                        name = f"{club} - {session} (n={shot_count})"
                        
                        fig.add_trace(go.Bar(
                            x=[club],
                            y=[attr_mean],
                            name=name,
                            error_y=dict(
                                type='data',
                                array=[attr_std],
                                visible=True
                            ),
                            text=[f"Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                            hoverinfo='text+name',
                            marker_color=session_colors[session]
                        ))
                
                # Update layout to respect the sorting
                fig.update_layout(
                    title=f'Mean {attribute_label} by Club-Session',
                    xaxis_title='Club',
                    yaxis_title=f'Mean {attribute_label}',
                    barmode='group',
                    xaxis=dict(
                        categoryorder='array',
                        categoryarray=sorted_clubs
                    )
                )
            else:
                # Scatter with sorted clubs on y-axis (reversed to have lowest at top)
                for session in sessions:
                    for club in sorted_clubs:
                        session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                        
                        if len(session_club_data) == 0:
                            continue
                            
                        attr_mean = session_club_data[attribute].mean()
                        attr_std = session_club_data[attribute].std()
                        shot_count = len(session_club_data)
                        
                        name = f"{club} - {session} (n={shot_count})"
                        
                        fig.add_trace(go.Scatter(
                            x=[attr_mean],
                            y=[club],
                            mode='markers',
                            name=name,
                            marker=dict(size=12, opacity=0.8, color=session_colors[session]),
                            error_x=dict(
                                type='data',
                                array=[attr_std],
                                visible=True,
                                color=session_colors[session]
                            ),
                            text=[f"Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                            hoverinfo='text+name'
                        ))
                
                # Update layout to respect the sorting (low to high from top to bottom)
                fig.update_layout(
                    title=f'Mean {attribute_label} by Club-Session',
                    xaxis_title=f'Mean {attribute_label}',
                    yaxis_title='Club',
                    yaxis=dict(
                        categoryorder='array',
                        categoryarray=list(reversed(sorted_clubs))
                    )
                )
        else:
            # Club over time - Single club with sessions as rows
            club = clubs[0]  # Only one club in this mode
            
            # Collect session data for sorting by mean value
            session_data_for_sorting = []
            for session in sessions:
                session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
                
                if len(session_club_data) == 0:
                    continue
                    
                attr_mean = session_club_data[attribute].mean()
                attr_std = session_club_data[attribute].std()
                shot_count = len(session_club_data)
                
                session_data_for_sorting.append({
                    'session': session,
                    'mean': attr_mean,
                    'std': attr_std,
                    'count': shot_count
                })
            
            # Sort sessions by mean value
            sorted_sessions = [item['session'] for item in sorted(session_data_for_sorting, key=lambda x: x['mean'])]
            
            # Create plots with sorted sessions
            for session_info in sorted(session_data_for_sorting, key=lambda x: x['mean']):
                session = session_info['session']
                attr_mean = session_info['mean']
                attr_std = session_info['std']
                shot_count = session_info['count']
                
                if plot_type == 'histogram':
                    fig.add_trace(go.Bar(
                        x=[attr_mean],
                        y=[session],
                        orientation='h',
                        name=f"{session} (n={shot_count})",
                        error_x=dict(type='data', array=[attr_std], visible=True),
                        text=[f"Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                        hoverinfo='text+name'
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=[attr_mean],
                        y=[session],
                        mode='markers',
                        name=f"{session} (n={shot_count})",
                        marker=dict(size=12),
                        error_x=dict(type='data', array=[attr_std], visible=True),
                        text=[f"Mean: {attr_mean:.2f}<br>SD: {attr_std:.2f}"],
                        hoverinfo='text+name'
                    ))
                    
            # Layout for time comparison - using sorted sessions
            fig.update_layout(
                title=f'{attribute_label} Over Time for {club}',
                xaxis_title=attribute_label,
                yaxis_title='Session',
                yaxis=dict(
                    categoryorder='array',
                    categoryarray=list(reversed(sorted_sessions))  # Reverse so lowest is at top
                )
            )
        
        # Common layout settings for non-2D maps
        fig.update_layout(
            legend=dict(
                title="Club - Session" if comparison_mode == 'clubs' else "Sessions",
                orientation="h" if len(clubs) * len(sessions) > 6 else "v",
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
    Input('main-tabs', 'value')  # Trigger when analysis tab is selected
)
def update_user_dropdown(active_tab):
    if active_tab == "analysis":
        users = get_available_users()
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
        'ballSpeed': 'Ball Speed (mph)',
        'ballSpin': 'Ball Spin (rpm)', 
        'carryActual': 'Carry (m)',
        'carrySideActual': 'Carry Side (m)',
        'curveActual': 'Curve (m)',
        'launchAngle': 'Launch Angle (°)',
        'maxHeight': 'Height (m)',
        'totalActual': 'Total (m)',
        'totalSideActual': 'Total Side (m)',
        '2DMapCarry': '2D Map Carry'  # Add the new 2D map option
    }
    
    # Check which of the allowed attributes are actually present in the data
    available_options = []
    for col_name, display_label in allowed_attributes.items():
        if col_name == '2DMapCarry':
            # For 2D map, check if both carryActual and carrySideActual exist
            carry_exists = 'carryActual' in df.columns and pd.api.types.is_numeric_dtype(df['carryActual'])
            side_exists = 'carrySideActual' in df.columns and pd.api.types.is_numeric_dtype(df['carrySideActual'])
            print(f"DEBUG: carryActual exists: {carry_exists}")
            print(f"DEBUG: carrySideActual exists: {side_exists}")
            
            if carry_exists and side_exists:
                print(f"DEBUG: Adding 2D Map Carry option")
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

    # Add delete button for each row
    filtered_df["Delete"] = "❌" # Unicode X mark as delete button

    # Prepare data for the table
    table_data = filtered_df[["row_id", "Session ID", "Club", "carryActual", "carrySideActual", "launchAngle", "Delete"]].rename(
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

# Add this new callback to handle deletion and update the plot
@app.callback(
    Output("analysis-plot", "figure", allow_duplicate=True),
    Output("selected-shots-table", "data", allow_duplicate=True),
    Output("filtered-data-store", "data", allow_duplicate=True),
    Input("selected-shots-table", "active_cell"),
    Input("selected-shots-table", "page_current"),
    Input("selected-shots-table", "page_size"),
    State("selected-shots-table", "data"),
    State("filtered-data-store", "data"),
    State("analysis-plot", "figure"),
    State("attribute-dropdown", "value"),
    State("comparison-radio", "value"),
    State("plot-type-radio", "value"),
    State("user-dropdown", "value"),
    State("ball-type-radio", "value"),
    State("session-dropdown", "value"),
    State("club-dropdown", "value"),
    prevent_initial_call=True
)
def delete_shot(active_cell, page_current, page_size, table_data, filtered_data, current_figure, attribute, comparison_mode, 
               plot_type, username, ball_type, sessions, clubs):
    # If triggered by page change, don't process
    if dash.callback_context.triggered[0]['prop_id'].split('.')[1] in ['page_current', 'page_size']:
        raise dash.exceptions.PreventUpdate
        
    if not active_cell or active_cell["column_id"] != "Delete":
        raise dash.exceptions.PreventUpdate

    # Calculate the actual index in the full table data
    actual_index = (page_current or 0) * page_size + active_cell["row"]
    
    try:
        # Get the row ID of the clicked row
        if actual_index >= len(table_data):
            print(f"ERROR: Index {actual_index} out of bounds for table_data length {len(table_data)}")
            raise dash.exceptions.PreventUpdate
            
        row_to_delete = table_data[actual_index]["row_id"]
        print(f"DEBUG: Deleting row_id {row_to_delete} from page {page_current}, row {active_cell['row']}")
        
        # Remove the shot from filtered data
        updated_filtered_data = [row for row in filtered_data if row["row_id"] != row_to_delete]
        
        # Update table data
        updated_table_data = [row for row in table_data if row["row_id"] != row_to_delete]
        
        print(f"DEBUG: Removed row. Original count: {len(filtered_data)}, New count: {len(updated_filtered_data)}")
        
        # If we removed all shots, return empty plot
        if not updated_filtered_data:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="No shots selected",
                xaxis_title="Carry Distance (m)",
                yaxis_title="Carry Side (m)"
            )
            return empty_fig, updated_table_data, updated_filtered_data

        # Use the generate_plot function with the updated filtered data
        updated_fig = generate_plot(1, username, ball_type, comparison_mode, 
                                    plot_type, sessions, clubs, attribute, 
                                    custom_data=updated_filtered_data)
        return updated_fig, updated_table_data, updated_filtered_data
    except Exception as e:
        print(f"ERROR in delete_shot: {e}")
        return current_figure, table_data, filtered_data
    
if __name__ == '__main__':
    app.run_server(debug=True, port=8050)  # Set use_reloader=False to avoid double callbacks