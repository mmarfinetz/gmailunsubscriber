"""
Gmail Unsubscriber Backend API
This Flask application provides the backend API for the Gmail Unsubscriber frontend.
It handles Gmail authentication, email scanning, and unsubscription processing.
"""

import os
import json
import base64
import re
import time
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, redirect, session, url_for
from flask_cors import CORS
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=5)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'

# Enable CORS with restricted origins
frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:8000')
CORS(app, 
     origins=[frontend_url, 'https://gmail-unsubscriber-frontend-ftrl3114t-mmarfinetzs-projects.vercel.app', 'https://gmail-unsubscriber-frontend-cghhingxm-mmarfinetzs-projects.vercel.app'],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

# Gmail API settings
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

# Store user credentials in memory (for demo purposes)
# In production, use a proper database
user_credentials = {}
user_stats = {}
user_activities = {}

# Authentication configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID', ''),
        "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        "redirect_uris": [os.environ.get('REDIRECT_URI', 'http://localhost:5000/oauth2callback')]
    }
}

# Don't save credentials to file in production
if os.environ.get('ENVIRONMENT') == 'development':
    with open('client_secrets.json', 'w') as f:
        json.dump(CLIENT_CONFIG, f)

# Helper function to check if user is authenticated
def is_authenticated(user_id):
    if user_id not in user_credentials:
        return False
    
    creds = Credentials.from_authorized_user_info(user_credentials[user_id], SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                user_credentials[user_id] = json.loads(creds.to_json())
                return True
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                return False
        return False
    
    return True

# Authentication required decorator
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        
        if not user_id or not is_authenticated(user_id):
            return jsonify({"error": "Authentication required"}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

# Routes
@app.route('/api/auth/login', methods=['GET'])
def login():
    """Initiate the OAuth2 authorization flow."""
    # Create flow instance
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
    )
    
    # Generate URL for request to Google's OAuth 2.0 server
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Store the state in the session
    session['state'] = state
    
    # Redirect the user to Google's OAuth 2.0 server
    return jsonify({"auth_url": authorization_url})

@app.route('/oauth2callback')
def oauth2callback():
    """Handle the OAuth2 callback from Google."""
    # Specify the state when creating the flow in the callback
    state = request.args.get('state', '')
    
    if state != session.get('state', ''):
        return jsonify({"error": "Invalid state parameter"}), 401
    
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        state=state,
        redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
    )
    
    # Use the authorization server's response to fetch the OAuth 2.0 tokens
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    # Store credentials in the session
    credentials = flow.credentials
    user_info = get_user_info(credentials)
    user_id = user_info['email']
    
    # Store in our server-side storage
    user_credentials[user_id] = json.loads(credentials.to_json())
    
    # Initialize user stats and activities
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0
        }
    
    if user_id not in user_activities:
        user_activities[user_id] = [{
            "type": "info",
            "message": "Successfully connected Gmail account",
            "time": datetime.now().isoformat()
        }]
    
    # Store user ID in session
    session['user_id'] = user_id
    
    # Redirect to frontend
    frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend-ftrl3114t-mmarfinetzs-projects.vercel.app')
    return redirect(f"{frontend_url}?auth=success&email={user_id}")

@app.route('/api/auth/logout', methods=['POST'])
@auth_required
def logout():
    """Log out the user by clearing their session."""
    user_id = session.get('user_id')
    
    if user_id in user_credentials:
        del user_credentials[user_id]
    
    session.clear()
    
    return jsonify({"success": True, "message": "Logged out successfully"})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check if the user is authenticated."""
    user_id = session.get('user_id')
    
    if user_id and is_authenticated(user_id):
        return jsonify({
            "authenticated": True,
            "email": user_id
        })
    
    return jsonify({"authenticated": False})

@app.route('/api/stats', methods=['GET'])
@auth_required
def get_stats():
    """Get the user's unsubscription statistics."""
    user_id = session.get('user_id')
    
    return jsonify(user_stats.get(user_id, {
        "total_scanned": 0,
        "total_unsubscribed": 0,
        "time_saved": 0
    }))

@app.route('/api/activities', methods=['GET'])
@auth_required
def get_activities():
    """Get the user's recent activities."""
    user_id = session.get('user_id')
    
    return jsonify(user_activities.get(user_id, []))

@app.route('/api/unsubscribe/start', methods=['POST'])
@auth_required
def start_unsubscription():
    """Start the unsubscription process."""
    user_id = session.get('user_id')
    data = request.json
    
    search_query = data.get('search_query', '"unsubscribe" OR "email preferences" OR "opt-out" OR "subscription preferences"')
    max_emails = data.get('max_emails', 50)
    
    # Add activity
    add_activity(user_id, "info", f"Started unsubscription process with query: {search_query}")
    
    # Start the process in a background thread (in a real app)
    # For demo purposes, we'll do it synchronously
    try:
        process_unsubscriptions(user_id, search_query, max_emails)
        return jsonify({"success": True, "message": "Unsubscription process completed"})
    except Exception as e:
        logger.error(f"Error in unsubscription process: {e}")
        add_activity(user_id, "error", f"Error in unsubscription process: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/unsubscribe/status', methods=['GET'])
@auth_required
def get_unsubscription_status():
    """Get the status of the unsubscription process."""
    user_id = session.get('user_id')
    
    # In a real app, this would check the status of the background process
    # For demo purposes, we'll just return the stats
    return jsonify({
        "stats": user_stats.get(user_id, {}),
        "activities": user_activities.get(user_id, [])
    })

# Helper functions
def get_user_info(credentials):
    """Get the user's email address from their Google account."""
    service = build('oauth2', 'v2', credentials=credentials)
    user_info = service.userinfo().get().execute()
    return user_info

def add_activity(user_id, activity_type, message):
    """Add an activity to the user's activity log."""
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    activity = {
        "type": activity_type,
        "message": message,
        "time": datetime.now().isoformat()
    }
    
    user_activities[user_id].insert(0, activity)
    
    # Limit to 50 most recent activities
    if len(user_activities[user_id]) > 50:
        user_activities[user_id] = user_activities[user_id][:50]
    
    return activity

def process_unsubscriptions(user_id, query, max_emails):
    """Process unsubscriptions for the user."""
    if not is_authenticated(user_id):
        raise Exception("User not authenticated")
    
    creds = Credentials.from_authorized_user_info(user_credentials[user_id], SCOPES)
    service = build(API_SERVICE_NAME, API_VERSION, credentials=creds)
    
    # Search for emails
    add_activity(user_id, "info", "Searching for subscription emails...")
    messages = search_emails(service, query, max_emails)
    
    if not messages:
        add_activity(user_id, "warning", "No subscription emails found")
        return
    
    add_activity(user_id, "info", f"Found {len(messages)} subscription emails")
    
    # Process each email
    for i, msg in enumerate(messages):
        try:
            # Update progress
            progress_percentage = int((i / len(messages)) * 100)
            
            # Get email content
            email_html = get_email(service, msg['id'])
            
            # Extract unsubscribe links
            unsub_links = extract_unsub_links(email_html)
            
            if not unsub_links:
                add_activity(user_id, "warning", f"No unsubscribe links found in email {i+1}/{len(messages)}")
                user_stats[user_id]["total_scanned"] += 1
                continue
            
            # Try to unsubscribe
            unsubscribed = False
            
            for link in unsub_links:
                if execute_unsub(link):
                    unsubscribed = True
                    break
            
            # Update stats and labels
            user_stats[user_id]["total_scanned"] += 1
            
            if unsubscribed:
                user_stats[user_id]["total_unsubscribed"] += 1
                user_stats[user_id]["time_saved"] += 2  # Assume 2 minutes saved per unsubscription
                
                # Add label to email
                service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={'removeLabelIds': ['INBOX'], 'addLabelIds': ['UNSUBSCRIBED']}
                ).execute()
                
                add_activity(user_id, "success", f"Successfully unsubscribed from email {i+1}/{len(messages)}")
            else:
                add_activity(user_id, "error", f"Failed to unsubscribe from email {i+1}/{len(messages)}")
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error processing email {msg['id']}: {e}")
            add_activity(user_id, "error", f"Error processing email: {str(e)}")
    
    add_activity(user_id, "success", f"Completed unsubscription process. Unsubscribed from {user_stats[user_id]['total_unsubscribed']} emails.")

def search_emails(service, query, max_results=50):
    """Search Gmail for emails matching the query."""
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])
    return messages

def get_email(service, msg_id):
    """Get the HTML content of an email."""
    message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    payload = message['payload']
    parts = payload.get('parts', [])
    data = ""
    
    if parts:
        for part in parts:
            if part['mimeType'] == 'text/html':
                if 'data' in part['body']:
                    data = base64.urlsafe_b64decode(part['body']['data']).decode()
                    break
    else:
        if 'data' in payload['body']:
            data = base64.urlsafe_b64decode(payload['body']['data']).decode()
    
    return data

def extract_unsub_links(html):
    """Extract unsubscribe links from HTML content."""
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    pattern = re.compile(r'unsubscribe|opt[-\s]?out|email preferences', re.I)
    
    for link in soup.find_all('a', href=True):
        if pattern.search(link.text) or pattern.search(link['href']):
            links.append(link['href'])
    
    return links

def execute_unsub(link):
    """Execute an unsubscription by visiting the link."""
    try:
        response = requests.get(link, timeout=10)
        if response.status_code == 200:
            logger.info(f'Successful GET unsubscribe: {link}')
            return True
        else:
            logger.warning(f'Non-200 status for unsubscribe: {link}, status: {response.status_code}')
    except Exception as e:
        logger.error(f'GET request failed for {link}: {e}')
    
    return False

if __name__ == '__main__':
    # Check if environment variables are set
    if not os.environ.get('GOOGLE_CLIENT_ID') or not os.environ.get('GOOGLE_CLIENT_SECRET'):
        logger.warning("Google OAuth credentials not set. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
    
    # Run the Flask app
    debug_mode = os.environ.get('ENVIRONMENT') == 'development'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
