import requests
import json
import os
import sys
import base64
import hashlib
import secrets
import urllib.parse
from datetime import datetime
import time
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import re
from pathlib import Path


# Default token directory
TOKEN_DIR = os.path.join(str(Path.home()), "tokens")

def check_saved_tokens():
    """Check for saved tokens and return a dictionary of username -> token"""
    if not os.path.exists(TOKEN_DIR):
        return {}
    token_dir = TOKEN_DIR
    os.makedirs(TOKEN_DIR, exist_ok=True)
    
    token_file = os.path.join(TOKEN_DIR, "trackman_tokens.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                tokens_data = json.load(f)
            
            # Debugging: Check raw token data
            print(f"DEBUG: Raw token data: {tokens_data}")
            
            current_time = time.time()
            valid_tokens = {}
            
            for username, data in tokens_data.items():
                timestamp = data.get("timestamp", 0)
                if current_time - timestamp < 86400 * 99999999:  # 5 days
                    valid_tokens[username] = data.get("token")
            
            # Debugging: Check valid tokens
            print(f"DEBUG: Valid tokens: {valid_tokens}")
            return valid_tokens
        except Exception as e:
            print(f"Error reading tokens file: {e}")
    
    return {}

def save_token(token, username):
    """Save authentication token with username to file"""
    if not token or not username:
        return False
    
    token_dir = "token"
    os.makedirs(token_dir, exist_ok=True)
    
    token_file = os.path.join(token_dir, "trackman_tokens.json")
    
    # Load existing tokens
    tokens_data = {}
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                tokens_data = json.load(f)
        except:
            pass
    
    # Update token for this username
    tokens_data[username] = {
        "token": token,
        "timestamp": time.time()
    }
    
    try:
        with open(token_file, 'w') as f:
            json.dump(tokens_data, f, indent=2)
        print(f"Token saved for user: {username}")
        return True
    except Exception as e:
        print(f"Error saving token file: {e}")
        return False

def invalidate_token(username=None):
    """Remove a specific user's token or all tokens"""
    token_file = os.path.join("token", "trackman_tokens.json")
    if not os.path.exists(token_file):
        return False
        
    try:
        if username is None:
            # Remove the entire file
            os.remove(token_file)
            print("All tokens invalidated successfully")
        else:
            # Just remove the specific user
            with open(token_file, 'r') as f:
                tokens_data = json.load(f)
            
            if username in tokens_data:
                del tokens_data[username]
                with open(token_file, 'w') as f:
                    json.dump(tokens_data, f, indent=2)
                print(f"Token for {username} invalidated successfully")
            else:
                print(f"No token found for {username}")
        return True
    except Exception as e:
        print(f"Error invalidating token: {e}")
    return False

def get_existing_sessions(username=None):
    """Scan the Data folders to find which sessions are already saved"""
    pro_sessions = set()
    range_sessions = set()
    
    base_dir = "Data"
    if username:
        base_dir = os.path.join(base_dir, username)
    
    # Check pro files
    pro_dir = os.path.join(base_dir, "pro")
    if os.path.exists(pro_dir):
        for filename in os.listdir(pro_dir):
            if filename.startswith("trackman_") and filename.endswith("_pro.csv"):
                # Extract date and session number
                match = re.search(r'trackman_(\d+)_session(\d+)_pro\.csv', filename)
                if match:
                    date_str, session_num = match.groups()
                    pro_sessions.add((date_str, session_num))
    
    # Check range files
    range_dir = os.path.join(base_dir, "range")
    if os.path.exists(range_dir):
        for filename in os.listdir(range_dir):
            if filename.startswith("trackman_") and filename.endswith("_range.csv"):
                # Extract date and session number
                match = re.search(r'trackman_(\d+)_session(\d+)_range\.csv', filename)
                if match:
                    date_str, session_num = match.groups()
                    range_sessions.add((date_str, session_num))
    
    return pro_sessions, range_sessions

def open_in_serum(url, username=None, password=None):
    """
    Open a URL in the Serum browser.
    
    Args:
        url (str): The URL to open.
    """
    # Serum is a custom browser, replace with actual command to open it
    # This is a placeholder for demonstration purposes
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")  # optional, helps debugging
    options.add_argument("--window-size=1920x1080")
    print("Opening Serum browser...")
    #driver = webdriver.Chrome()
    # comment this line to see the browser in action
    # options.add_argument("--headless")  
    driver = webdriver.Chrome(seleniumwire_options={}, options=options)
    # Automated login with the credentials you provided
    email = "maxifb@live.at"
    password_value = "Maxi1610"  # You'll need to set this
    token = None
    print("DEBUG: Looking for email input field...")
    try:
        driver.get(url)
        # Wait for and fill the email field (using the correct selectors)
        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#Email, input[name='Email'], input.email-input"))
        )
        print("DEBUG: Found email input field")
        
        email_input.clear()
        email_input.send_keys(email)
        print(f"DEBUG: Entered email: {email}")
        
        # Look for password field
        print("DEBUG: Looking for password input field...")
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#Password, input[name='Password'], input.password-input"))
        )
        print("DEBUG: Found password input field")
        
        password_input.clear()
        password_input.send_keys(password_value)
        print("DEBUG: Entered password")
        
        # Try to find and click the submit button
        print("DEBUG: Looking for submit button...")
        submit_btn = None
        
        # Try multiple selectors for the submit button
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']", 
            ".btn-primary",
            "button:contains('Log in')",
            "button:contains('Sign in')",
            "button:contains('Login')"
        ]
        
        for selector in submit_selectors:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if submit_btn:
                    break
            except:
                continue
        
        if submit_btn:
            submit_btn.click()
            print("DEBUG: Clicked submit button")
        else:
            # Alternative: press Enter on password field
            password_input.send_keys(Keys.RETURN)
            print("DEBUG: Pressed Enter on password field")
            
        print(f"Retrieving token...")
    
        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.ID, "ga4-activities-card"))
        )
        
        # Then search through network requests
        for request in driver.requests:
            if request.response:
                if "" in request.url and request.response.status_code == 200:
                    # Option A: Check Authorization header
                    auth_header = request.headers.get("Authorization")
                    if auth_header and "Bearer" in auth_header:
                        token = auth_header.split(" ")[1]
                        break

                    # Option B: Check JSON body
                    try:
                        body2 = request.body.decode()
                        data2 = urllib.parse.parse_qs(body2)      
                        body = request.response.body.decode()
                        data = json.loads(body)
                        if data2.get('email', [None])[0]:
                            print(f"Email: {data['email'][0]}")
                            
                        if "authorization" in data:
                            token = data["authorization"]
                            break
                    except:
                        continue
                    
    except Exception as e:
        print(f"DEBUG: Could not complete login form: {e}")
        # Print page source for debugging
        print("DEBUG: Current page source snippet:")
        print(driver.page_source[:2000])
                
        #time.sleep(500)  # Wait for the page to load
        
    finally:
        driver.quit()
    if token:
        return token
    else:
        return None

class TrackManAPI:
    def __init__(self):
        self.base_url = "https://api.trackmangolf.com/graphql"
        self.auth_token = None
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        self.client_id = "dr-web.4633fada-3b16-490f-8de7-2aa67158a1d6"
        self.redirect_uri = "https://portal.trackmangolf.com/account/callback"  # Removed /callback
        self.auth_url = "https://login.trackmangolf.com/connect/authorize"
        self.token_url = "https://login.trackmangolf.com/connect/token"
    
    def generate_code_verifier(self):
        """Generate a secure random code verifier for PKCE"""
        # Generate a code verifier with proper length (between 43-128 chars)
        # OAuth PKCE spec requires at least 43 chars, but not more than 128
        code_verifier = secrets.token_urlsafe(96)  # Will generate ~128 chars
        if len(code_verifier) > 128:
            code_verifier = code_verifier[:128]
        return code_verifier

    def generate_code_challenge(self, code_verifier):
        """Generate code challenge from code verifier using SHA256"""
        # Ensure proper base64url encoding without padding characters
        hashed = hashlib.sha256(code_verifier.encode()).digest()
        encoded = base64.urlsafe_b64encode(hashed).decode()
        # Remove padding characters as per RFC 7636
        return encoded.rstrip('=')
    
    def login(self, username=None, password=None):
        """Authenticate with TrackMan API using saved token or PKCE flow"""
        
        # First check if we have a saved token
        saved_tokens = check_saved_tokens()
        # First check if we have a saved token for this username
        if username:
            saved_tokens = check_saved_tokens()
            if username in saved_tokens:
                print(f"Testing saved token validity for user: {username}...")
                self.auth_token = saved_tokens[username]
                self.headers["Authorization"] = f"Bearer {self.auth_token}"
                
                # Test if the token is still valid
                if self.test_connection():
                    print("Saved token is valid, authentication successful!")
                    return True
                else:
                    print("Saved token is no longer valid, proceeding with browser login...")
        
        # Continue with regular PKCE authentication flow if no valid token was found
        # Generate PKCE code verifier and challenge
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        
        # Build authorization URL
        auth_params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": (
                "openid profile email offline_access "
                "https://auth.trackman.com/dr/cloud "
                "https://auth.trackman.com/authorization "
                "https://auth.trackman.com/proamevent"
            ),  # Vereinfachter Scope
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }

        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(auth_params)}"
                
        # Open browser window with auth URL
        print("Opening browser for authentication, please log in:")
        token = open_in_serum(auth_url, username, password)

        if not token:
            print("Failed to get access token")
            return False
        
        if "Bearer" in token:
            token = token.split(" ")[1]
        
        # Store the token
        self.auth_token = token
        
        # Set the Authorization header
        self.headers["Authorization"] = f"Bearer {self.auth_token}"
        # Save the token for future use
        save_token(self.auth_token, username)
        
        print("Authentication successful!\n")
        return True
    
    def get_access_token(self, client_id, username, password):
        """
        Exchange user credentials for an OAuth2 access token using the Resource Owner Password grant.
        """
        # Use proper form encoding for the data
        form_data = {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
            "scope": "openid dr/play offline_access"
        }
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        try:
            response = requests.post(
                "https://login.trackmangolf.com/connect/token", 
                data=form_data,  # requests will encode this properly for form submission
                headers=headers
            )
            
            # Add detailed response info for debugging
            print(f"Auth response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Auth error: {response.text[:500]}")
                return None
                
            response.raise_for_status()
            token_data = response.json()
            
            if "access_token" not in token_data:
                print("No access token in response")
                print(f"Response contains: {list(token_data.keys())}")
                return None
                
            return token_data["access_token"]
            
        except requests.exceptions.RequestException as e:
            print(f"Authentication request error: {e}")
            return None
        except ValueError as e:
            print(f"Invalid response format: {e}")
            return None
    
    def test_connection(self):
        """Test the API connection with a simple query"""
        query = """
        query {
          __schema {
            queryType {
              name
            }
          }
        }
        """
        
        response = self.execute_query(query)
        if response and response.get("data"):
            return True
        return False
    
    def explore_schema(self):
        """Explore the GraphQL schema to see available fields"""
        query = """
        query {
          __schema {
            queryType {
              fields {
                name
                description
              }
            }
          }
        }
        """
        
        response = self.execute_query(query)
        if response and response.get("data", {}).get("__schema"):
            fields = response.get("data", {}).get("__schema", {}).get("queryType", {}).get("fields", [])
            print("\nAvailable query fields:")
            for field in fields:
                print(f"- {field.get('name')}: {field.get('description')}")
        return response
    
    def get_type_fields(self, type_name):
        """Discover fields available on a specific GraphQL type"""
        query = """
        query {
          __type(name: "%s") {
            name
            fields {
              name
              type {
                name
                kind
              }
            }
          }
        }
        """ % type_name
        
        response = self.execute_query(query)
        if response and response.get("data", {}).get("__type"):
            fields = response.get("data", {}).get("__type", {}).get("fields", [])
            print(f"\n{type_name} fields:")
            for field in fields:
                print(f"- {field.get('name')}: {field.get('type', {}).get('name')}")
            return fields
        return []
    
    def get_activity_fields(self):
        """Get the available fields on PlayerActivity type"""
        return self.get_type_fields("PlayerActivity")
    
    def get_activity_list(self, limit=30, skip=0):
        """Retrieve a list of activities"""
        query = """
        query {
          me {
            activities{
              items {
                id
                time
                kind
                isHidden
              }
              totalCount
            }
          }
        }
        """ 
        
        response = self.execute_query(query)
        return response.get("data", {}).get("me", {}).get("activities", {}).get("items", [])
    
    def get_range_practice_shots(self, activity_id, ball_type="PREMIUM"):
        """Retrieve shot data for a specific range practice activity
        
        Args:
            activity_id: The activity ID to retrieve shots for
            ball_type: Either "PREMIUM" or "RANGE" to determine measurement type
        """
        # Set the measurement type based on ball type
        measurement_type = "SITE_MEASUREMENT" if ball_type == "RANGE" else "PRO_BALL_MEASUREMENT"
        
        query = """
        query GetActivityShots($id: ID!, $measurementType: RangeMeasurementTypes!) {
          node(id: $id) {
            ... on RangePracticeActivity {
              id
              kind
              time
              strokes {
                bayName
                time
                club
                measurement(measurementType: $measurementType) {
                  ballSpeed
                  ballSpin
                  ballVelocity
                  carry
                  carryActual
                  carrySide
                  carrySideActual
                  curve
                  curveActual
                  curveTotal
                  curveTotalActual
                  distanceFromPin
                  distanceFromPinActual
                  distanceFromPinTotal
                  distanceFromPinTotalActual
                  isValidMeasurement
                  kind
                  landingAngle
                  landingPossitionCarry
                  landingPossitionCarryActual
                  landingPossitionTotal
                  lastData
                  launchAngle
                  launchDirection
                  maxHeight
                  messageId
                  spinAxis
                  targetDistance
                  time
                  total
                  totalActual
                  totalSide
                  totalSideActual
                  windVelocity
                  ballSpinEffective
                  reducedAccuracy
                }
              }
            }
          }
        }
        """
        
        variables = {
            "id": activity_id,
            "measurementType": measurement_type
        }
        
        response = self.execute_query(query, variables)
        data = response.get("data", {}).get("node", {})
        
        # For compatibility with existing code that expects a 'shots' field
        if data and "strokes" in data:
            data["shots"] = data.get("strokes", [])
            
  
        # Convert ballSpeed from m/s to km/h if present
        for shot in data.get("shots", []):
            measurement = shot.get("measurement")
            if measurement is None:
                # Create empty dictionary if measurement is None
                shot["measurement"] = {}
                measurement = shot["measurement"]
                
            if "ballSpeed" in measurement and measurement["ballSpeed"] is not None:
                try:
                    mph = float(measurement["ballSpeed"])
                    measurement["ballSpeed"] = round(mph * 3.6, 2)
                except (ValueError, TypeError):
                    pass
            if "ballSpinEffective" in measurement and measurement["ballSpinEffective"] is None:
                try:
                    measurement["ballSpinEffective"] = "None"
                except (ValueError, TypeError):
                    pass
            
            if "reducedAccuracy" in measurement and measurement["reducedAccuracy"] not in ("", []):
                measurement["reducedAccuracy"] = "Yes"
            else:
                measurement["reducedAccuracy"] = "No"
                
            for key, value in measurement.items():
                if isinstance(value, (int, float)):
                    measurement[key] = round(value, 1)
        
        return data
    
    def get_range_data(self):
        """Fetch general range data from TrackMan API"""
        query = """
        query {
          range {
            facilities {
              id
              name
              bays {
                id
                name
                number
              }
            }
            currentBay {
              id
              number
              name
            }
            availableBays {
              id
              number
              name
              status
            }
          }
        }
        """
        
        response = self.execute_query(query)
        return response.get("data", {}).get("range", {})
    
    def execute_query(self, query, variables=None):
        """Execute a GraphQL query against the TrackMan API"""
        if not self.auth_token:
            print("Not authenticated. Please login first.")
            return None
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            # Add detailed response info for debugging
            #print(f"API response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Response body: {response.text[:500]}")
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return None

    def save_shots_to_csv(self, shots_data, filename=None, ball_type="PREMIUM", username=None):
        """Save shot data to a CSV file"""
        if not shots_data or not shots_data.get("shots"):
            print("No shot data to save")
            return
        
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
        
        # Write to file
        try:
            with open(filename, 'w') as f:
                f.write("\n".join(rows))
            print(f"Saved {len(shots)} shots to {filename}")
            return True
        except Exception as e:
            print(f"Error saving file: {e}")
            return False

    def save_combined_shots_to_csv(self, all_shot_data, ball_type="PREMIUM", username=None):
        """Save shot data from multiple sessions to separate CSV files
        
        Args:
            all_shot_data: List of session data objects containing shots
            ball_type: Either "PREMIUM" or "RANGE" to determine file suffix
            username: Optional username to include in directory path
        """
        if not all_shot_data:
            print("No shot data to save")
            return
        
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
        
        # Ball type suffix for filename
        ball_suffix = "_range" if ball_type == "RANGE" else "_pro"
        
        # Keep the same measurement fields
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

        # Add shot-level fields (without session fields since each file is for one session)
        header = ["Shot Number", "Club", "Bay"] + measurement_fields
        
        # Track processing stats
        sessions_saved = 0
        total_shots = 0
        
        # Process each session separately
        for session_data in all_shot_data:
            shots = session_data.get("shots", [])
            if not shots:
                continue
                
            # Get session info from first shot
            session_num = shots[0].get("session_number", "0")
            session_time = shots[0].get("session_time", "")
            session_date = ""
            
            # Parse the date for the filename
            if session_time:
                try:
                    dt = datetime.fromisoformat(session_time.replace('Z', '+00:00'))
                    session_date = dt.strftime("%Y%m%d")
                except:
                    pass
            
            # Create filename with date and session number
            if session_date:
                filename = f"{ball_dir}/trackman_{session_date}_session{session_num}{ball_suffix}.csv"
            else:
                filename = f"{ball_dir}/trackman_session{session_num}{ball_suffix}.csv"
            
            # Prepare rows for this session
            rows = [",".join(header)]
            
            # Sort shots by time
            shots.sort(key=lambda x: x.get("time", ""))
            
            # Process each shot
            for idx, shot in enumerate(shots, 1):
                data = shot.get("measurement", {})
                club = shot.get("club", "")
                if club is None:
                    club = "Unknown"
                row = [
                    str(idx),
                    club,
                    shot.get("bayName", "")
                ]
                
                # Add measurement fields
                for field in measurement_fields:
                    value = data.get(field, "")
                    if isinstance(value, bool):
                        value = str(value)
                    if value is None:
                        value = "None"
                    else:
                        row.append(str(value))
                try:    
                    rows.append(",".join(row))
                except Exception as e:
                    print(f"Error processing row: {row} with error: {e}")
                    continue
            
            # Write this session to its own file
            with open(filename, 'w') as f:
                f.write("\n".join(rows))
            
            sessions_saved += 1
            total_shots += len(shots)
            print(f"Session {session_num} with {len(shots)} shots saved to {filename}")
        
        print(f"\nSaved {sessions_saved} sessions with {total_shots} total shots to separate files in {data_dir}")

def main():
    # Add this at the beginning of main
    # Check for command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--logout":
        username = None
        if len(sys.argv) > 2:
            username = sys.argv[2]
        invalidate_token(username)
        print(f"Logged out {'all users' if username is None else username}. You'll need to authenticate again on next run.")
        return

    # Check for available tokens
    available_tokens = check_saved_tokens()
    selected_username = None
    selected_token = None
    
    if available_tokens:
        print("\nAvailable users with saved tokens:")
        usernames = list(available_tokens.keys())
        for i, username in enumerate(usernames, 1):
            print(f"{i}. {username}")
        print(f"{len(usernames)+1}. Use a different account (new login)")
        print(f"{len(usernames)+2}. Logout specific user")
        print(f"{len(usernames)+3}. Logout all users")
        
        try:
            choice = int(input("\nSelect an option: "))
            if 1 <= choice <= len(usernames):
                selected_username = usernames[choice-1]
                selected_token = available_tokens[selected_username]
                print(f"Using saved token for {selected_username}")
            elif choice == len(usernames)+1:
                # New login will happen below
                pass
            elif choice == len(usernames)+2:
                # Logout specific user
                user_idx = int(input("Select user number to logout: "))
                if 1 <= user_idx <= len(usernames):
                    invalidate_token(usernames[user_idx-1])
                return
            elif choice == len(usernames)+3:
                # Logout all users
                invalidate_token()
                return
            else:
                print("Invalid selection")
                return
        except ValueError:
            print("Invalid input, please enter a number")
            return
    
    
    api = TrackManAPI()
    
    # If we have a selected token, use it directly
    if selected_token:
        api.auth_token = selected_token
        api.headers["Authorization"] = f"Bearer {selected_token}"
        
        # Test if the token is still valid
        if api.test_connection():
            print("Saved token is valid, authentication successful!")
        else:
            print("Saved token is no longer valid, proceeding with browser login...")
            selected_token = None
            selected_username = None
    
    # Login if needed
    if not selected_token:
        if not api.login(None, None):
            print("Authentication failed")
            return
        # After successful login, prompt for username to save
        if api.auth_token:
            save_username = input("Enter username/email to save token for: ").strip()
            if save_username:
                save_token(api.auth_token, save_username)
    
    # Test connection
    if not api.test_connection():
        print("Failed to connect to the API")
        return
    
    # Get user's activities
    print("Fetching recent activities...")
    activities = api.get_activity_list(limit=10)
    
    if not activities:
        print("No activities found")
        return
    
    # Filter for only RANGE_PRACTICE activities
    activities = [activity for activity in activities if activity.get("kind") == "RANGE_PRACTICE"]
    
    if not activities:
        print("No range practice activities found")
        return
    
    # DON'T sort - keep original order (newest first)
    # But create a mapping where oldest gets session 1
    total_activities = len(activities)
    
    # Create a mapping: activity index -> session number (reverse numbering)
    # Index 0 (newest) gets session number = total_activities
    # Index 1 gets session number = total_activities - 1
    # ...
    # Index (total-1) (oldest) gets session number = 1
    session_number_map = {i: total_activities - i for i in range(total_activities)}
    
    # Display activities in original order (newest first) but show correct session numbers
    print(f"\nRange practice activities ({len(activities)}):")
    for i, activity in enumerate(activities):
        activity_time = activity.get("time", "Unknown date")
        session_num = session_number_map[i]  # Reverse numbering
        print(f"{i+1}. RANGE_PRACTICE - {activity_time[:10]} (Session #{session_num})")
    
    # Rest of code uses session_number_map[idx] instead of idx+1
    
    # Let user select an activity, 'all', or 'missing'
    selection_input = input("\nSelect an activity (enter number, 'all', or 'missing' for missing sessions): ")
    
    if selection_input.lower() != "missing":
        # Ask for ball type AFTER session selection
        ball_type = input("\nActual data(range) or calculated? (premium/range/both): ").strip().upper()
        if ball_type not in ["RANGE", "PREMIUM", "BOTH"]:
            print("Invalid ball type. Defaulting to PREMIUM balls.")
            ball_type = "PREMIUM"
    else:
        ball_type = "BOTH"
    
    if selection_input.lower() == "missing":
        # Find which sessions are already saved
        existing_pro_sessions, existing_range_sessions = get_existing_sessions(selected_username)
        
        print("\nChecking for missing sessions...")
        
        # Process missing sessions for selected ball type(s)
        missing_activities = []
        
        for idx, activity in enumerate(activities):
            # Convert activity time to date string for comparison
            activity_time = activity.get("time", "")
            activity_date = ""
            
            if activity_time:
                try:
                    dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                    activity_date = dt.strftime("%Y%m%d")
                except:
                    continue
            
            session_num = str(idx + 1)
            
            # Check if this session is missing for the selected ball type(s)
            is_missing = False
            
            if ball_type == "PREMIUM" and (activity_date, session_num) not in existing_pro_sessions:
                is_missing = True
            elif ball_type == "RANGE" and (activity_date, session_num) not in existing_range_sessions:
                is_missing = True
            elif ball_type == "BOTH" and ((activity_date, session_num) not in existing_pro_sessions or 
                                          (activity_date, session_num) not in existing_range_sessions):
                is_missing = True
            
            if is_missing:
                missing_activities.append((idx, activity))
        
        # Process missing activities
        if not missing_activities:
            print("All sessions are already saved. No missing sessions found.")
            return
        
        print(f"Found {len(missing_activities)} missing sessions:")
        for idx, activity in missing_activities:
            activity_time = activity.get("time", "Unknown date")
            kind = activity.get("kind", "Unknown type")
            
            # Determine which ball types are missing for this session
            activity_date = ""
            if activity_time:
                try:
                    dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                    activity_date = dt.strftime("%Y%m%d")
                except:
                    pass
            
            session_num = str(idx + 1)
            
            # Check which ball types are missing
            missing_balls = []
            if (activity_date, session_num) not in existing_pro_sessions:
                missing_balls.append("PREMIUM")
            if (activity_date, session_num) not in existing_range_sessions:
                missing_balls.append("RANGE")
            
            # Format the missing ball types
            missing_ball_str = "/".join(missing_balls)
            
            # Print with ball type information
            print(f"  - {kind} - {activity_time[:10]} (Missing: {missing_ball_str})")
        
        # Ask to save missing sessions
        save_option = input("\nDownload and save missing sessions? (y/n): ")
        if save_option.lower() != 'y':
            return
            
        # Process missing sessions
        if ball_type == "BOTH":
            all_shot_data_pro = []
            all_shot_data_range = []
            
            for idx, activity in missing_activities:
                print(f"Processing activity {idx+1}/{len(missing_activities)}...")
                
                activity_date = ""
                activity_time = activity.get("time", "")
                
                if activity_time:
                    try:
                        dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
                        activity_date = dt.strftime("%Y%m%d")
                    except:
                        pass
                
                session_num = str(idx + 1)
                
                # Process PREMIUM balls if needed
                if (activity_date, session_num) not in existing_pro_sessions:
                    shot_data_pro = api.get_range_practice_shots(activity.get('id'), "PREMIUM")
                    if shot_data_pro and shot_data_pro.get("shots"):
                        shots = shot_data_pro.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_pro.append(shot_data_pro)
                        print(f"  - Downloaded {len(shots)} PREMIUM ball shots")
                
                # Process RANGE balls if needed
                if (activity_date, session_num) not in existing_range_sessions:
                    shot_data_range = api.get_range_practice_shots(activity.get('id'), "RANGE")
                    if shot_data_range and shot_data_range.get("shots"):
                        shots = shot_data_range.get("shots", [])
                        for shot in shots:
                            shot["session_number"] = idx + 1
                            shot["session_time"] = activity.get("time")
                            shot["session_kind"] = activity.get("kind")
                        all_shot_data_range.append(shot_data_range)
                        print(f"  - Downloaded {len(shots)} RANGE ball shots")
            
            # Save the data
            if all_shot_data_pro:
                api.save_combined_shots_to_csv(all_shot_data_pro, ball_type="PREMIUM", username=selected_username)
            if all_shot_data_range:
                api.save_combined_shots_to_csv(all_shot_data_range, ball_type="RANGE", username=selected_username)
            
        else:
            # Process missing sessions for a single ball type
            all_shot_data = []
            
            for idx, activity in missing_activities:
                print(f"Processing activity {idx+1}/{len(missing_activities)}...")
                
                # Process shots
                shot_data = api.get_range_practice_shots(activity.get('id'), ball_type)
                
                if shot_data:
                    # Add session number to each shot
                    shots = shot_data.get("shots", [])
                    for shot in shots:
                        shot["session_number"] = idx + 1
                        shot["session_time"] = activity.get("time")
                        shot["session_kind"] = activity.get("kind")
                    
                    all_shot_data.append(shot_data)
                    print(f"  - Downloaded {len(shots)} {ball_type} ball shots")
            
            # Save the data
            if all_shot_data:
                api.save_combined_shots_to_csv(all_shot_data, ball_type=ball_type, username=selected_username)
    
    elif selection_input.lower() == "all":
        if ball_type == "BOTH":
            # Process both PREMIUM and RANGE balls
            all_shot_data_pro = []
            all_shot_data_range = []
            
            # Process activities in chronological order
            for idx, activity in enumerate(activities):
                print(f"Processing activity {idx+1}/{len(activities)}...")
                
                # Session number is now idx+1 (chronological order)
                session_number = idx + 1
                
                # Process PREMIUM balls
                shot_data_pro = api.get_range_practice_shots(activity.get('id'), "PREMIUM")
                if shot_data_pro and shot_data_pro.get("shots"):
                    shots = shot_data_pro.get("shots", [])
                    for shot in shots:
                        shot["session_number"] = session_number
                        shot["session_time"] = activity.get("time")
                        shot["session_kind"] = activity.get("kind")
                    all_shot_data_pro.append(shot_data_pro)
                
                # Process RANGE balls
                shot_data_range = api.get_range_practice_shots(activity.get('id'), "RANGE")
                if shot_data_range and shot_data_range.get("shots"):
                    shots = shot_data_range.get("shots", [])
                    for shot in shots:
                        shot["session_number"] = session_number
                        shot["session_time"] = activity.get("time")
                        shot["session_kind"] = activity.get("kind")
                    all_shot_data_range.append(shot_data_range)
            
            # Add this part to save the data:
            save_option = input("Save all shot data to CSV files? (y/n): ")
            if save_option.lower() == 'y':
                # Save both types
                api.save_combined_shots_to_csv(all_shot_data_pro, ball_type="PREMIUM", username=selected_username)
                api.save_combined_shots_to_csv(all_shot_data_range, ball_type="RANGE", username=selected_username)
        else:
            # Original code for single ball type
            # Process all activities
            all_shot_data = []
            
            for idx, activity in enumerate(activities):
                print(f"Processing activity {idx+1}/{len(activities)}...")
                
                # Process shots
                shot_data = api.get_range_practice_shots(activity.get('id'), ball_type)
                
                if shot_data:
                    # Add session number to each shot
                    shots = shot_data.get("shots", [])
                    for shot in shots:
                        shot["session_number"] = idx + 1
                        shot["session_time"] = activity.get("time")
                        shot["session_kind"] = activity.get("kind")
                    
                    all_shot_data.append(shot_data)
                else:
                    print("Failed to retrieve shot data")
            
            # Save combined data to a single CSV
            save_option = input("Save all shot data to a single CSV? (y/n): ")
            if save_option.lower() == 'y':
                # Use the new method to save combined data
                api.save_combined_shots_to_csv(all_shot_data, ball_type=ball_type, username=selected_username)
    else:
        # Process single selected activity
        try:
            selection = int(selection_input) - 1
            if selection < 0 or selection >= len(activities):
                print("Invalid selection")
                return
            
            selected_activity = activities[selection]
            
            # Session number is now selection + 1 (chronological order)
            session_number = selection + 1
            
            if ball_type == "BOTH":
                # Process both PREMIUM and RANGE balls for the selected activity
                print(f"Processing activity for both ball types...")
                
                # Get premium ball data
                shot_data_pro = api.get_range_practice_shots(selected_activity.get('id'), "PREMIUM")
                pro_shots = shot_data_pro.get("shots", []) if shot_data_pro else []
                
                # Add session info to premium shots
                for shot in pro_shots:
                    shot["session_number"] = session_number  # Use chronological number
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                # Get range ball data
                shot_data_range = api.get_range_practice_shots(selected_activity.get('id'), "RANGE")
                range_shots = shot_data_range.get("shots", []) if shot_data_range else []
                
                # Add session info to range shots
                for shot in range_shots:
                    shot["session_number"] = session_number  # Use chronological number
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                print(f"\nRetrieved {len(pro_shots)} premium shots and {len(range_shots)} range shots")
                
                # Save to CSV
                save_option = input("Save shot data to CSV? (y/n): ")
                if save_option.lower() == 'y':
                    if pro_shots:
                        api.save_shots_to_csv(shot_data_pro, ball_type="PREMIUM", username=selected_username)
                    if range_shots:
                        api.save_shots_to_csv(shot_data_range, ball_type="RANGE", username=selected_username)
            else:
                # Original code for single ball type
                print(f"Processing activity...")
                
                # Get shot data for the selected activity
                shot_data = api.get_range_practice_shots(selected_activity.get('id'), ball_type)
                
                if not shot_data:
                    print("Failed to retrieve shot data")
                    return
                
                # Add session number AND session time to each shot
                shots = shot_data.get("shots", [])
                for shot in shots:
                    shot["session_number"] = session_number  # Use chronological number
                    shot["session_time"] = selected_activity.get("time")
                    shot["session_kind"] = selected_activity.get("kind")
                
                print(f"\nRetrieved {len(shots)} shots")
                
                # Save to CSV
                save_option = input("Save shot data to CSV? (y/n): ")
                if save_option.lower() == 'y':
                    api.save_shots_to_csv(shot_data, ball_type=ball_type, username=selected_username)
        except ValueError:
            print("Invalid input. Please enter a number or 'all'")
            return