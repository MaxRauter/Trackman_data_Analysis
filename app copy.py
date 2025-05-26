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

# Import the trackman module for authentication
spec = importlib.util.spec_from_file_location("trackman", "trackman.py")
trackman = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trackman)

def load_data(username, ball_type):
    data_dir = os.path.join('Data', username, ball_type)
    if not os.path.exists(data_dir):
        return pd.DataFrame(columns=['Session ID', 'Club', 'carryActual'])

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

        # Only keep relevant columns for Dash app
        keep_cols = ['Session ID', 'Club', 'carryActual']
        for col in keep_cols:
            if col not in temp_df.columns:
                temp_df[col] = None
        temp_df = temp_df[keep_cols]
        df_list.append(temp_df)

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
    else:
        df = pd.DataFrame(columns=['Session ID', 'Club', 'carryActual'])
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
                    }
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
                    dcc.Dropdown(id='user-dropdown', style={'width': '200px', 'display': 'inline-block'}),
                    html.Label("Ball Type:"),
                    dcc.RadioItems(
                        id='ball-type-radio',
                        options=[{'label': 'Range', 'value': 'range'}, {'label': 'Premium', 'value': 'premium'}],
                        value='range',
                        labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                    ),
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
                dcc.Loading(dcc.Graph(id='analysis-plot'), type="circle")
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
)
def update_sessions_and_clubs(username, ball_type, selected_sessions, comparison_mode):
    if not username:
        return [], [], [], [], True
        
    df = load_data(username, ball_type)
    
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
)
def generate_plot(n_clicks, username, ball_type, comparison_mode, plot_type, sessions, clubs):
    if not n_clicks or not sessions or not clubs or not username:
        return go.Figure()
    
    # Ensure sessions and clubs are always lists
    if isinstance(sessions, str):
        sessions = [sessions]
    if isinstance(clubs, str):
        clubs = [clubs]
    
    df = load_data(username, ball_type)
    df = df[df['Session ID'].isin(sessions) & df['Club'].isin(clubs)]
    fig = go.Figure()
    
    # Create a discrete color sequence for sessions
    colors = px.colors.qualitative.Plotly
    
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
                    
                # Calculate statistics
                carry_mean = session_club_data['carryActual'].mean()
                carry_std = session_club_data['carryActual'].std()
                shot_count = len(session_club_data)
                
                club_means.append({
                    'club': club,
                    'session': session,
                    'mean': carry_mean,
                    'std': carry_std,
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
                        
                    carry_mean = session_club_data['carryActual'].mean()
                    carry_std = session_club_data['carryActual'].std()
                    shot_count = len(session_club_data)
                    
                    name = f"{club} - {session} (n={shot_count})"
                    
                    fig.add_trace(go.Bar(
                        x=[club],
                        y=[carry_mean],
                        name=name,
                        error_y=dict(
                            type='data',
                            array=[carry_std],
                            visible=True
                        ),
                        text=[f"Mean: {carry_mean:.1f}yd<br>SD: {carry_std:.1f}yd"],
                        hoverinfo='text+name',
                        marker_color=session_colors[session]
                    ))
            
            # Update layout to respect the sorting
            fig.update_layout(
                title='Mean Carry Distance by Club-Session',
                xaxis_title='Club',
                yaxis_title='Mean Carry Distance (yards)',
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
                        
                    carry_mean = session_club_data['carryActual'].mean()
                    carry_std = session_club_data['carryActual'].std()
                    shot_count = len(session_club_data)
                    
                    name = f"{club} - {session} (n={shot_count})"
                    
                    fig.add_trace(go.Scatter(
                        x=[carry_mean],
                        y=[club],
                        mode='markers',
                        name=name,
                        marker=dict(size=12, opacity=0.8, color=session_colors[session]),
                        error_x=dict(
                            type='data',
                            array=[carry_std],
                            visible=True,
                            color=session_colors[session]
                        ),
                        text=[f"Mean: {carry_mean:.1f}yd<br>SD: {carry_std:.1f}yd"],
                        hoverinfo='text+name'
                    ))
            
            # Update layout to respect the sorting (low to high from top to bottom)
            fig.update_layout(
                title='Mean Carry Distance by Club-Session',
                xaxis_title='Mean Carry Distance (yards)',
                yaxis_title='Club',
                yaxis=dict(
                    categoryorder='array',
                    categoryarray=list(reversed(sorted_clubs))
                )
            )
    else:
        # Club over time - Single club with sessions as rows
        club = clubs[0]  # Only one club in this mode
        
        # Collect session data for sorting by mean distance
        session_data_for_sorting = []
        for session in sessions:
            session_club_data = df[(df['Club'] == club) & (df['Session ID'] == session)]
            
            if len(session_club_data) == 0:
                continue
                
            carry_mean = session_club_data['carryActual'].mean()
            carry_std = session_club_data['carryActual'].std()
            shot_count = len(session_club_data)
            
            session_data_for_sorting.append({
                'session': session,
                'mean': carry_mean,
                'std': carry_std,
                'count': shot_count
            })
        
        # Sort sessions by mean carry distance
        sorted_sessions = [item['session'] for item in sorted(session_data_for_sorting, key=lambda x: x['mean'])]
        
        # Create plots with sorted sessions
        for session_info in sorted(session_data_for_sorting, key=lambda x: x['mean']):
            session = session_info['session']
            carry_mean = session_info['mean']
            carry_std = session_info['std']
            shot_count = session_info['count']
            
            if plot_type == 'histogram':
                fig.add_trace(go.Bar(
                    x=[carry_mean],
                    y=[session],
                    orientation='h',
                    name=f"{session} (n={shot_count})",
                    error_x=dict(type='data', array=[carry_std], visible=True),
                    text=[f"Mean: {carry_mean:.1f}yd<br>SD: {carry_std:.1f}yd"],
                    hoverinfo='text+name'
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=[carry_mean],
                    y=[session],
                    mode='markers',
                    name=f"{session} (n={shot_count})",
                    marker=dict(size=12),
                    error_x=dict(type='data', array=[carry_std], visible=True),
                    text=[f"Mean: {carry_mean:.1f}yd<br>SD: {carry_std:.1f}yd"],
                    hoverinfo='text+name'
                ))
                
        # Layout for time comparison - using sorted sessions
        fig.update_layout(
            title=f'Carry Distance Over Time for {club}',
            xaxis_title='Carry Distance (yards)',
            yaxis_title='Session',
            yaxis=dict(
                categoryorder='array',
                categoryarray=list(reversed(sorted_sessions))  # Reverse so lowest is at top
            )
        )
    
    # Common layout settings
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

if __name__ == '__main__':
    app.run(debug=True)