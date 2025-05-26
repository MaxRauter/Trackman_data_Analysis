import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import matplotlib.colors as mcolors
import os
import glob
import re

# Function to get multiple selections as comma-separated values
def get_multi_input(prompt, max_val, default):
    try:
        value = input(f"{prompt} (comma-separated, 0 for all) [{default}]: ")
        if not value.strip():
            return default
        
        if value == "0":
            return 0
        
        # Parse comma-separated values
        indices = [int(idx.strip()) for idx in value.split(",")]
        # Validate indices
        for idx in indices:
            if idx < 1 or idx > max_val:
                print(f"Invalid selection {idx}. Valid range is 1-{max_val}")
                return default
        return indices
    except ValueError:
        print("Invalid input, using default.")
        return default

# Scan for available users
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print(f"Created data directory: {data_dir}")

# Create global plots directory
plots_base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plots')
if not os.path.exists(plots_base_dir):
    os.makedirs(plots_base_dir)
    print(f"Created global plots directory: {plots_base_dir}")

available_users = []
if os.path.exists(data_dir):
    available_users = [d for d in os.listdir(data_dir) 
                      if os.path.isdir(os.path.join(data_dir, d))]

# Display available users
if available_users:
    print("\nAvailable users:")
    for i, user in enumerate(available_users, 1):
        print(f"  {i}: {user}")
else:
    print("\nNo user data directories found. Will create one for you.")

# Get username selection from user
default_user = "maxi"
if available_users and default_user not in available_users:
    default_user = available_users[0]

username_input = input(f"\nEnter username or number [{default_user}]: ").strip()

# Check if input is a number for selection from the list
if username_input and username_input.isdigit():
    user_idx = int(username_input)
    if 1 <= user_idx <= len(available_users):
        username = available_users[user_idx - 1]  # Adjust for 1-based indexing
        print(f"Selected user: {username}")
    else:
        print(f"Invalid selection {user_idx}. Using default: {default_user}")
        username = default_user
elif not username_input:
    username = default_user
else:
    username = username_input.lower()

# Create user directory if it doesn't exist
user_dir = os.path.join(data_dir, username)
if not os.path.exists(user_dir):
    print(f"Creating new user directory for '{username}'...")
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'premium'), exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'range'), exist_ok=True)
    print(f"Created directories for user '{username}' with premium and range ball subdirectories")

# Create user-specific plots directory in the global plots directory
plots_dir = os.path.join(plots_base_dir, username)
if not os.path.exists(plots_dir):
    os.makedirs(plots_dir, exist_ok=True)
    print(f"Created plots directory for user '{username}': {plots_dir}")

# Get ball type selection from user
ball_type = input("\nSelect ball type (premium/range) [range]: ").strip().lower()
if ball_type == "premium":
    ball_filter = "premium"
    # Look for both "premium" and "pro" in filenames
    file_suffix_pattern = "(?:_(?:premium|pro))?"
else:
    # Default to range balls for any other input
    ball_type = "range"  # Normalize for filename consistency
    ball_filter = "range"
    file_suffix_pattern = "(?:_range)?"

# Construct data directory path with username and ball type
data_dir = os.path.join('Data', username, ball_type)

# Check if the directory exists
if not os.path.exists(data_dir):
    print(f"Directory {data_dir} does not exist. Creating it...")
    os.makedirs(data_dir, exist_ok=True)

# Scan the appropriate directory for CSV files
file_pattern = "trackman_*.csv"  # No need to filter by ball type in filename
csv_files = glob.glob(os.path.join(data_dir, file_pattern))

if not csv_files:
    print(f"No {ball_type} ball data files found in {data_dir}")
    exit()

print(f"Found {len(csv_files)} {ball_type} ball data files in {data_dir}")

# Parse filenames to extract date and session information
# Initialize an empty DataFrame to store all data
df = pd.DataFrame()

# Updated regular expression to extract date and session number, allowing optional ball type suffix
# Changed to recognize both "premium" and "pro" as valid suffixes for premium balls
file_pattern = re.compile(r'trackman_(\d+)_session(\d+)(?:_(?:range|premium|pro))?\.csv')

for file_path in csv_files:
    file_name = os.path.basename(file_path)
    match = file_pattern.match(file_name)
    
    if match:
        date_str, session_num = match.groups()
        
        # Read the CSV file
        temp_df = pd.read_csv(file_path)
        
        # Add session metadata if not already present in the CSV
        if 'Session Date' not in temp_df.columns:
            # Format date properly (assuming YYYYMMDD format in filename)
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            temp_df['Session Date'] = formatted_date
            temp_df['Session Number'] = session_num
            temp_df['Ball Type'] = ball_type
            temp_df['Username'] = username
            
            # Create a unique session identifier that includes both date and session number
            temp_df['Session ID'] = f"{formatted_date} (Session {session_num})"
            
        # Append to the main DataFrame
        df = pd.concat([df, temp_df], ignore_index=True)
    else:
        print(f"Skipping file with invalid naming format: {file_name}")

# Check if we have data
if df.empty:
    print("No valid data found in the CSV files")
    exit()

print(f"Loaded {len(df)} shots from {len(csv_files)} files")

# Find the correct column names
# print("Available columns:", df.columns.tolist())

# These should be the actual column names from your data
club_column = 'Club'  # Update this if your column name is different
carry_actual_column = 'carryActual'  # Update this if your column name is different
date_column = 'Session ID'  # Instead of just 'Session Date'

# Get all unique sessions sorted by date (newest first)
all_sessions = sorted(df[date_column].unique(), reverse=True)

# Count shots per session
session_shot_counts = {}
for session in all_sessions:
    session_shot_counts[session] = len(df[df[date_column] == session])

# Get comparison mode: clubs or single club over time
comparison_mode = input("\nCompare multiple clubs or one club over time? (clubs/time) [clubs]: ").strip().lower()
if comparison_mode == "time":
    compare_over_time = True
else:
    compare_over_time = False

if compare_over_time:
    # Get all unique clubs
    all_clubs = sorted(df[club_column].unique())

    # Display available clubs with numbers, including session counts
    print("\nAvailable Clubs:")
    for i, club in enumerate(all_clubs, 1):
        club_data = df[df[club_column] == club]
        club_shot_count = len(club_data)
        club_session_count = len(club_data[date_column].unique())
        print(f"  {i}: {club} ({club_shot_count} shots across {club_session_count} sessions)")

    # Get user input for club
    club_idx = get_multi_input("\nSelect a club by number", len(all_clubs), 1)
    if club_idx == 0:
        selected_club = all_clubs[0]  # Default to first club
    else:
        selected_club = all_clubs[club_idx[0]-1]
    
    print(f"\nAnalyzing {selected_club} across all sessions")
    
    # Filter data for this club
    df = df[df[club_column] == selected_club]
    
    # If no data, exit
    if len(df) == 0:
        print(f"No data for {selected_club}")
        exit()
    
    # Get user input for plot type
    plot_type = input("\nType of plot (gaussian/histogram) [gaussian]: ").strip().lower()
    if plot_type != "histogram":
        plot_type = "gaussian"
    
    output_filename = os.path.join(plots_dir, f'{username}_{selected_club}_over_time_{plot_type}_{ball_type}.png')
    
    # Create a plot
    plt.figure(figsize=(14, 10))
    colors = plt.cm.tab20.colors
    
    # For this club, plot data by session
    for i, session in enumerate(all_sessions, 1):
        # Filter data for this session
        session_data = df[df[date_column] == session]
        all_carry_values = session_data[carry_actual_column].dropna().astype(float)
        
        if len(all_carry_values) < 3:  # Need at least 3 shots for meaningful analysis
            print(f"Skipping {session}: only {len(all_carry_values)} shots")
            continue
            
        print(f"{session}: {len(all_carry_values)} shots")
        
        if len(all_carry_values) > 4:  # Need enough data for quartile calculation
            # Remove outliers using IQR method
            Q1 = np.percentile(all_carry_values, 25)
            Q3 = np.percentile(all_carry_values, 75)
            IQR = Q3 - Q1
            
            # Define bounds for what's considered an outlier (1.5 * IQR is standard)
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            # Filter out outliers but keep them for the rug plot
            outlier_mask = (all_carry_values >= lower_bound) & (all_carry_values <= upper_bound)
            carry_values = all_carry_values[outlier_mask]
            
            outliers = all_carry_values[~outlier_mask]
            n_outliers = len(outliers)
            
            print(f"  - {n_outliers} outliers removed")
        else:
            # Not enough data to reliably detect outliers
            carry_values = all_carry_values
        
        if len(carry_values) > 1:
            # Calculate statistics
            mu, std = norm.fit(carry_values)
            
            # Different plotting based on user choice
            if plot_type == 'gaussian':
                # Create x values and calculate PDF
                x = np.linspace(max(0, min(carry_values) * 0.8), max(carry_values) * 1.2, 1000)
                pdf = norm.pdf(x, mu, std)
                
                # Normalize for better visualization
                pdf_normalized = pdf / pdf.max()
                
                # Convert session date to more readable format if needed
                session_label = session
                
                # Plot the distribution
                plt.plot(x, pdf_normalized, 
                         label=f'{session_label}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}', 
                         color=colors[i % len(colors)], 
                         linewidth=2)
                
                # Add a rug plot to show actual data points
                plt.plot(carry_values, np.zeros_like(carry_values) - 0.02 * (i+1), '|', 
                        color=colors[i % len(colors)], alpha=0.7, markersize=10)
                
                # Mark outliers with 'x' if any
                if 'outliers' in locals() and len(outliers) > 0:
                    plt.plot(outliers, np.zeros_like(outliers) - 0.02 * (i+1), 'x', 
                            color=colors[i % len(colors)], alpha=0.7, markersize=8)
            
            else:  # Histogram plot
                # Plot histogram with transparency
                bins = np.arange(min(carry_values) - 5, max(carry_values) + 5, 5)  # 5-yard bins
                plt.hist(carry_values, bins=bins, alpha=0.6, 
                         label=f'{session}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                         color=colors[i % len(colors)])
    
    # Set title and labels for time comparison
    if plot_type == 'gaussian':
        title = f'{selected_club} Carry Distance Over Time ({username}, {ball_type})'
        ylabel = 'Normalized Probability Density'
        # Set y-limits specific to Gaussian plots
        plt.ylim(-0.02 * len(all_sessions) - 0.05, 1.1) 
    else:
        title = f'{selected_club} Carry Distance Histograms Over Time ({username}, {ball_type})'
        ylabel = 'Number of Shots'
    
else:
    # Original code for comparing multiple clubs
    # Display available sessions with numbers and shot counts
    print("\nAvailable Sessions:")
    for i, session in enumerate(all_sessions, 1):
        shot_count = session_shot_counts[session]
        print(f"  {i}: {session} ({shot_count} shots)")

    # Get user input for sessions
    selected_indices = get_multi_input("\nSelect sessions by number", len(all_sessions), 0)

    # Get user input for plot type
    plot_type = input("\nType of plot (gaussian/histogram) [gaussian]: ").strip().lower()
    if plot_type != "histogram":
        plot_type = "gaussian"

    # Filter by selected sessions if requested
    if selected_indices != 0:
        # Convert indices to session dates (adjusting for 1-based indexing)
        selected_sessions = [all_sessions[idx-1] for idx in selected_indices]
        
        # Filter data to only include these sessions
        df = df[df[date_column].isin(selected_sessions)]
        print(f"\nAnalyzing data from {len(selected_sessions)} selected sessions:")
        for session in selected_sessions:
            print(f"  - {session} ({session_shot_counts[session]} shots)")
        
        # Update output filename to reflect specific sessions selected
        # Extract session numbers from Session IDs to include in filename
        session_numbers = []
        for session in selected_sessions:
            # Extract session number from format like "2025-01-01 (Session 2)"
            match = re.search(r'\(Session (\d+)\)', session)
            if match:
                session_numbers.append(match.group(1))
            
        # Create a string of session numbers separated by underscores
        session_str = "sessions_" + "_".join(session_numbers)
        
        # Update output filename with specific session numbers and ball type
        output_filename = os.path.join(plots_dir, f'{username}_club_carry_{plot_type}_{session_str}_{ball_type}.png')
    else:
        print("\nAnalyzing data from all sessions")
        total_shots = sum(session_shot_counts.values())
        print(f"Total: {total_shots} shots across {len(all_sessions)} sessions")
        output_filename = os.path.join(plots_dir, f'{username}_club_carry_{plot_type}_all_sessions_{ball_type}.png')

    # Extract unique clubs and sort them in a logical order
    club_order = ['4Iron', '5Iron', '6Iron', '7Iron', '8Iron', '9Iron', 'PitchingWedge', '60Wedge']
    unique_clubs = df[club_column].unique()
    clubs = [club for club in club_order if club in unique_clubs]
    clubs.extend([club for club in unique_clubs if club not in club_order])

    # Create a plot
    plt.figure(figsize=(14, 10))
    colors = plt.cm.tab20.colors

    # Dictionary to store statistics for annotation
    stats = {}

    # For each club, process data and plot
    for i, club in enumerate(clubs, 1):
        # Filter data for this club
        club_data = df[df[club_column] == club]
        all_carry_values = club_data[carry_actual_column].dropna().astype(float)
        
        if len(all_carry_values) < 1:
            print(f"No data for {club}")
            continue
            
        print(f"{club}: {len(all_carry_values)} shots")
        
        if len(all_carry_values) > 4:  # Need enough data for quartile calculation
            # Remove outliers using IQR method
            Q1 = np.percentile(all_carry_values, 25)
            Q3 = np.percentile(all_carry_values, 75)
            IQR = Q3 - Q1
            
            # Define bounds for what's considered an outlier (1.5 * IQR is standard)
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            # Filter out outliers but keep them for the rug plot
            outlier_mask = (all_carry_values >= lower_bound) & (all_carry_values <= upper_bound)
            carry_values = all_carry_values[outlier_mask]
            
            outliers = all_carry_values[~outlier_mask]
            n_outliers = len(outliers)
            
            print(f"  - {n_outliers} outliers removed")
        else:
            # Not enough data to reliably detect outliers
            carry_values = all_carry_values
        
        if len(carry_values) > 1:
            # Calculate statistics
            mu, std = norm.fit(carry_values)
            stats[club] = {'mean': mu, 'std': std}
            
            # Different plotting based on user choice
            if plot_type == 'gaussian':
                # Create x values and calculate PDF
                x = np.linspace(max(0, min(carry_values) * 0.8), max(carry_values) * 1.2, 1000)
                pdf = norm.pdf(x, mu, std)
                
                # Normalize for better visualization
                pdf_normalized = pdf / pdf.max()
                
                # Plot the distribution
                plt.plot(x, pdf_normalized, 
                         label=f'{club}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}', 
                         color=colors[i % len(colors)], 
                         linewidth=2)
                
                # Add a rug plot to show actual data points
                plt.plot(carry_values, np.zeros_like(carry_values) - 0.02 * (i+1), '|', 
                        color=colors[i % len(colors)], alpha=0.7, markersize=10)
                
                # Mark outliers with 'x' if any
                if len(all_carry_values) > 4:
                    plt.plot(outliers, np.zeros_like(outliers) - 0.02 * (i+1), 'x', 
                            color=colors[i % len(colors)], alpha=0.7, markersize=8)
            
            else:  # Histogram plot
                # Plot histogram with transparency
                bins = np.arange(min(carry_values) - 5, max(carry_values) + 5, 5)  # 5-yard bins
                plt.hist(carry_values, bins=bins, alpha=0.6, 
                         label=f'{club}: μ={mu:.1f}m, σ={std:.1f}m, n={len(carry_values)}',
                         color=colors[i % len(colors)])

    # Determine plot title based on session selection and plot type
    if selected_indices != 0:
        title_sessions = f'Selected {len(selected_sessions)} Sessions'
    else:
        title_sessions = 'All Sessions'

    if plot_type == 'gaussian':
        title = f'Carry Distance Distributions by Club ({username}, {ball_type}, {title_sessions})'
        ylabel = 'Normalized Probability Density'
        # Set y-limits specific to Gaussian plots
        plt.ylim(-0.02 * len(clubs) - 0.05, 1.1) 
    else:
        title = f'Carry Distance Histograms by Club ({username}, {ball_type}, {title_sessions})'
        ylabel = 'Number of Shots'
        # For histograms, let matplotlib set appropriate y-limits

# Enhance the plot
plt.xlabel('Carry Distance (yards)', fontsize=12)
plt.ylabel(ylabel, fontsize=12)
plt.title(title, fontsize=16)
plt.grid(True, alpha=0.3)
plt.legend(fontsize=10, loc='upper left', bbox_to_anchor=(1, 1))
plt.xlim(0, 200)

# Save and show the plot
plt.tight_layout()
plt.savefig(output_filename, dpi=300)
plt.show()