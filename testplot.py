import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
from glob import glob

# Ask user to pick a user directory from Data
data_root = "Data"
users = [d for d in os.listdir(data_root) if os.path.isdir(os.path.join(data_root, d))]
print("Available users:")
for idx, user in enumerate(users):
    print(f"{idx + 1}: {user}")
user_idx = int(input("Select a user by number: ")) - 1
selected_user = users[user_idx]

premium_dir = os.path.join(data_root, selected_user, "premium")
range_dir = os.path.join(data_root, selected_user, "range")

def load_data_file(file_path):
    """Load a data file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == '.csv':
            return pd.read_csv(file_path)
        elif ext in ['.xlsx', '.xls']:
            return pd.read_excel(file_path)
        else:
            print(f"Unsupported file type: {ext}")
            return None
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def find_session_files():
    """Find files across both directories and organize by session ID."""
    import re
    premium_files = glob(os.path.join(premium_dir, "*.*"))
    range_files = glob(os.path.join(range_dir, "*.*"))
    
    premium_sessions = {}
    range_sessions = {}
    
    # Pattern to extract session ID from filename
    session_pattern = re.compile(r'_session(\d+)_')
    
    # Load premium data
    for file in premium_files:
        if os.path.isfile(file):
            data = load_data_file(file)
            if data is not None:
                # Extract session ID from filename
                filename = os.path.basename(file)
                match = session_pattern.search(filename)
                if match:
                    # Extract the session ID including the surrounding pattern
                    full_match = filename[match.start():match.end()]
                    session_id = full_match  # Use the entire pattern like "_session1_"
                elif 'session' in data.columns:
                    session_id = str(data['session'].iloc[0])
                else:
                    # Use filename as fallback
                    session_id = os.path.basename(file).split('.')[0]
                
                premium_sessions[session_id] = (file, data)
    
    # Load range data
    for file in range_files:
        if os.path.isfile(file):
            data = load_data_file(file)
            if data is not None:
                # Extract session ID from filename
                filename = os.path.basename(file)
                match = session_pattern.search(filename)
                if match:
                    # Extract the session ID including the surrounding pattern
                    full_match = filename[match.start():match.end()]
                    session_id = full_match  # Use the entire pattern like "_session1_"
                elif 'session' in data.columns:
                    session_id = str(data['session'].iloc[0])
                else:
                    # Use filename as fallback
                    session_id = os.path.basename(file).split('.')[0]
                
                range_sessions[session_id] = (file, data)
    
    return premium_sessions, range_sessions

def compare_carry_total_distances():
    """Compare carryActual and totalActual between premium and range data, grouped by club."""
    premium_sessions, range_sessions = find_session_files()
    
    session = input("Enter the session number (e.g., 1, 2, etc.): ")
    # Look specifically for _sessionx_ in both datasets
    session_id = f"_session{session}_"
    
    if session_id in premium_sessions and session_id in range_sessions:
        print(f"Analyzing session: {session_id}")
        
        # Get data for the selected session
        _, premium_data = premium_sessions[session_id]
        _, range_data = range_sessions[session_id]
        
        # Check for required columns
        required_cols = ['carryActual', 'totalActual', 'Club']
        
        if all(col in premium_data.columns for col in required_cols) and \
           all(col in range_data.columns for col in required_cols):
            
            # Find common clubs between both datasets
            premium_clubs = set(premium_data['Club'].unique())
            range_clubs = set(range_data['Club'].unique())
            common_clubs = premium_clubs.intersection(range_clubs)
            
            if not common_clubs:
                print("No common clubs found between premium and range data.")
                print(f"Premium clubs: {premium_clubs}")
                print(f"Range clubs: {range_clubs}")
                return
                
            # Create plots for carry and total distance
            fig1, ax1 = plt.subplots(figsize=(12, 8))
            fig2, ax2 = plt.subplots(figsize=(12, 8))
            
            # Track statistics for summary
            stats = []
            
            # Colors for consistent club representation
            club_colors = plt.cm.tab10(np.linspace(0, 1, len(common_clubs)))
            
            # Plot each club's data
            for i, club in enumerate(sorted(common_clubs)):
                color = club_colors[i]
                
                # Filter data for this club
                premium_club_data = premium_data[premium_data['Club'] == club]
                range_club_data = range_data[range_data['Club'] == club]
                
                # Calculate statistics
                premium_carry_mean = premium_club_data['carryActual'].mean()
                premium_carry_std = premium_club_data['carryActual'].std()
                range_carry_mean = range_club_data['carryActual'].mean()
                range_carry_std = range_club_data['carryActual'].std()
                
                premium_total_mean = premium_club_data['totalActual'].mean()
                premium_total_std = premium_club_data['totalActual'].std()
                range_total_mean = range_club_data['totalActual'].mean()
                range_total_std = range_club_data['totalActual'].std()
                
                # Calculate absolute and percentage differences
                carry_diff = premium_carry_mean - range_carry_mean
                carry_diff_pct = (carry_diff / range_carry_mean * 100) if range_carry_mean != 0 else 0
                
                total_diff = premium_total_mean - range_total_mean
                total_diff_pct = (total_diff / range_total_mean * 100) if range_total_mean != 0 else 0
                
                # Store statistics
                stats.append({
                    'club': club,
                    'premium_carry_mean': premium_carry_mean,
                    'premium_carry_std': premium_carry_std,
                    'range_carry_mean': range_carry_mean,
                    'range_carry_std': range_carry_std,
                    'premium_total_mean': premium_total_mean,
                    'premium_total_std': premium_total_std,
                    'range_total_mean': range_total_mean,
                    'range_total_std': range_total_std,
                    'carry_diff': carry_diff,
                    'carry_diff_pct': carry_diff_pct,
                    'total_diff': total_diff,
                    'total_diff_pct': total_diff_pct
                })
                
                # Plot carry distance
                x_premium = i - 0.2
                x_range = i + 0.2
                
                # Carry distance plot
                ax1.bar(x_premium, premium_carry_mean, width=0.4, color=color, alpha=0.7, 
                       label=f"{club} Premium" if i == 0 else None)
                ax1.bar(x_range, range_carry_mean, width=0.4, color=color, alpha=0.3,
                       label=f"{club} Range" if i == 0 else None)
                
                # Add error bars for standard deviation
                ax1.errorbar(x_premium, premium_carry_mean, yerr=premium_carry_std, 
                           fmt='none', color='black', capsize=5)
                ax1.errorbar(x_range, range_carry_mean, yerr=range_carry_std, 
                           fmt='none', color='black', capsize=5)
                
                # Add percentage difference text above bars
                y_pos = max(premium_carry_mean, range_carry_mean) + max(premium_carry_std, range_carry_std) + 5
                ax1.text(i, y_pos, f"{carry_diff_pct:.1f}%", ha='center', fontsize=9, 
                        color='red' if carry_diff_pct < 0 else 'green')
                
                # Total distance plot
                ax2.bar(x_premium, premium_total_mean, width=0.4, color=color, alpha=0.7,
                       label=f"{club} Premium" if i == 0 else None)
                ax2.bar(x_range, range_total_mean, width=0.4, color=color, alpha=0.3,
                       label=f"{club} Range" if i == 0 else None)
                
                # Add error bars for standard deviation
                ax2.errorbar(x_premium, premium_total_mean, yerr=premium_total_std, 
                           fmt='none', color='black', capsize=5)
                ax2.errorbar(x_range, range_total_mean, yerr=range_total_std, 
                           fmt='none', color='black', capsize=5)
                
                # Add percentage difference text above bars
                y_pos = max(premium_total_mean, range_total_mean) + max(premium_total_std, range_total_std) + 5
                ax2.text(i, y_pos, f"{total_diff_pct:.1f}%", ha='center', fontsize=9,
                        color='red' if total_diff_pct < 0 else 'green')
            
            # Finalize carry distance plot
            ax1.set_title(f'Carry Distance by Club - Session {session_id}')
            ax1.set_ylabel('Carry Distance (yards)')
            ax1.set_xticks(range(len(common_clubs)))
            ax1.set_xticklabels(sorted(common_clubs))
            ax1.grid(alpha=0.3, axis='y')
            
            # Create a custom legend
            ax1.legend(['Premium', 'Range'])
            
            # Finalize total distance plot
            ax2.set_title(f'Total Distance by Club - Session {session_id}')
            ax2.set_ylabel('Total Distance (yards)')
            ax2.set_xticks(range(len(common_clubs)))
            ax2.set_xticklabels(sorted(common_clubs))
            ax2.grid(alpha=0.3, axis='y')
            
            # Create a custom legend
            ax2.legend(['Premium', 'Range'])
            
            plt.tight_layout()
            plt.show()
            
            # Print statistics
            print("\nClub-by-Club Statistics:")
            print("=" * 100)
            print(f"{'Club':<8} | {'Premium Carry':<20} | {'Range Carry':<20} | {'Diff':<9} | {'Premium Total':<20} | {'Range Total':<20} | {'Diff':<9}")
            print("-" * 100)
            
            for stat in stats:
                club = stat['club']
                premium_carry = f"{stat['premium_carry_mean']:.1f} ± {stat['premium_carry_std']:.1f}"
                range_carry = f"{stat['range_carry_mean']:.1f} ± {stat['range_carry_std']:.1f}"
                carry_diff = f"{stat['carry_diff']:.1f} ({stat['carry_diff_pct']:.1f}%)"
                premium_total = f"{stat['premium_total_mean']:.1f} ± {stat['premium_total_std']:.1f}"
                range_total = f"{stat['range_total_mean']:.1f} ± {stat['range_total_std']:.1f}"
                total_diff = f"{stat['total_diff']:.1f} ({stat['total_diff_pct']:.1f}%)"
                
                print(f"{club:<8} | {premium_carry:<20} | {range_carry:<20} | {carry_diff:<9} | {premium_total:<20} | {range_total:<20} | {total_diff:<9}")
            
        else:
            missing_cols = [col for col in required_cols if col not in premium_data.columns or col not in range_data.columns]
            print(f"Missing columns: {missing_cols}")
            print(f"Premium columns: {premium_data.columns.tolist()}")
            print(f"Range columns: {range_data.columns.tolist()}")
    else:
        print(f"Session '{session_id}' not found in both datasets.")
        if session_id in premium_sessions:
            print(f"Found in premium data but not in range data.")
        elif session_id in range_sessions:
            print(f"Found in range data but not in premium data.")
        else:
            print(f"Not found in either dataset.")

if __name__ == "__main__":
    compare_carry_total_distances()