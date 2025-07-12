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

from flask import Flask, request, jsonify, redirect, g, session
import jwt
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

# Import Claude chat functionality
try:
    from chat import chat_simple, chat_with_gmail_context, ask_claude
    CLAUDE_AVAILABLE = True
    logger.info("Claude chat module loaded successfully")
except Exception as e:
    CLAUDE_AVAILABLE = False
    logger.warning(f"Claude chat module not available: {e}")

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

# Create OAuth debug logger
oauth_logger = logging.getLogger('oauth_debug')
oauth_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
oauth_logger.addHandler(handler)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configure Flask session for OAuth state management
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True for HTTPS in production
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',  # Critical for OAuth redirects
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_COOKIE_DOMAIN=None  # Don't set for localhost development
)

# Enable CORS with restricted origins
frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')

# Define allowed origins for CORS
allowed_origins = [
    frontend_url,
    # Vercel deployment URLs (for backward compatibility)
    'https://gmail-unsubscriber-frontend.vercel.app',
    'https://gmail-unsubscriber-frontend-ftrl3114t-mmarfinetzs-projects.vercel.app',
    'https://gmail-unsubscriber-frontend-cghhingxm-mmarfinetzs-projects.vercel.app',
]

# Add localhost origins for development
if os.environ.get('ENVIRONMENT') == 'development':
    allowed_origins.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',  # Common React dev server port
        'http://127.0.0.1:3000'
    ])
    oauth_logger.debug(f"Development mode: Added localhost origins to CORS")

# Add Railway domain patterns if environment is production
if os.environ.get('ENVIRONMENT') == 'production':
    # Allow Railway domains (*.railway.app)
    allowed_origins.extend([
        'https://*.railway.app',
        # Add specific Railway domains if needed
    ])

CORS(app, 
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

# Gmail API settings
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

user_stats = {}
user_activities = {}
oauth_states = set()

# Authentication configuration
CLIENT_CONFIG = {
    "web": {
        "client_id": os.environ.get('GOOGLE_CLIENT_ID', ''),
        "project_id": os.environ.get('GOOGLE_PROJECT_ID', ''),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        "redirect_uris": [os.environ.get('REDIRECT_URI', 'https://gmailunsubscriber-production.up.railway.app/oauth2callback')]
    }
}

# Don't save credentials to file in production
if os.environ.get('ENVIRONMENT') == 'development':
    with open('client_secrets.json', 'w') as f:
        json.dump(CLIENT_CONFIG, f)

def decode_token(token):
    """Decode a JWT token and return its payload or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        return payload
    except Exception as e:
        logger.error(f"Invalid token: {e}")
        return None

def is_authenticated(token):
    """Validate token and refresh Gmail credentials if needed."""
    payload = decode_token(token)
    if not payload:
        return None

    creds_data = payload.get("credentials")
    if not creds_data:
        return None

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                payload["credentials"] = json.loads(creds.to_json())
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                return None
        else:
            return None

    return payload

# Authentication required decorator
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
        else:
            token = request.args.get('token')

        payload = is_authenticated(token)
        if not payload:
            return jsonify({"error": "Authentication required"}), 401

        g.user_id = payload.get('user_id')
        g.credentials = payload.get('credentials')
        return f(*args, **kwargs)

    return decorated_function

# Routes
@app.route('/')
def health_check():
    """Health check endpoint for Railway."""
    return jsonify({
        "status": "healthy",
        "service": "gmail-unsubscriber-backend",
        "timestamp": datetime.now().isoformat()
    })

@app.before_request
def log_oauth_debug():
    """Debug logging for OAuth-related requests."""
    if request.path.startswith(('/oauth', '/api/auth')):
        oauth_logger.debug(f"=== {request.method} {request.path} ===")
        oauth_logger.debug(f"Request args: {dict(request.args)}")
        oauth_logger.debug(f"Session contents: {dict(session)}")
        oauth_logger.debug(f"Session ID: {session.sid if hasattr(session, 'sid') else 'No SID'}")
        oauth_logger.debug(f"Session is new: {session.new if hasattr(session, 'new') else 'Unknown'}")

@app.route('/api/auth/login', methods=['GET'])
def login():
    """Initiate the OAuth2 authorization flow."""
    oauth_logger.debug("=== OAuth Login Started ===")
    
    # Create flow instance
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
    )
    
    oauth_logger.debug(f"OAuth redirect URI: {CLIENT_CONFIG['web']['redirect_uris'][0]}")
    
    # Generate URL for request to Google's OAuth 2.0 server
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Store state in Flask session instead of in-memory set
    session['oauth2_state'] = state
    session['oauth2_state_timestamp'] = datetime.now().isoformat()
    session.modified = True
    
    oauth_logger.debug(f"Generated OAuth state: {state}")
    oauth_logger.debug(f"Stored state in session: {session.get('oauth2_state')}")
    oauth_logger.debug(f"Authorization URL: {authorization_url}")
    oauth_logger.debug("=== OAuth Login Completed ===")

    # Return the authorization URL to the frontend
    return jsonify({"auth_url": authorization_url})

@app.route('/oauth2callback')
def oauth2callback():
    """Handle the OAuth2 callback from Google."""
    try:
        oauth_logger.debug("=== OAuth Callback Started ===")
        oauth_logger.debug(f"Request URL: {request.url}")
        oauth_logger.debug(f"Request args: {dict(request.args)}")
        oauth_logger.debug(f"Session before state check: {dict(session)}")
        
        # Enhanced state validation
        received_state = request.args.get('state')
        stored_state = session.get('oauth2_state')
        
        oauth_logger.debug(f"Received state: {received_state}")
        oauth_logger.debug(f"Stored state: {stored_state}")
        
        if not received_state:
            oauth_logger.error("Missing state parameter in callback")
            frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
            return redirect(f"{frontend_url}?auth=error&error=missing_state")
        
        # Validate state for all environments now that we use sessions
        if not stored_state:
            oauth_logger.error("No stored state in session - possible session loss")
            frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
            return redirect(f"{frontend_url}?auth=error&error=no_stored_state")
        
        if not secrets.compare_digest(received_state, stored_state):
            oauth_logger.error("State mismatch - possible CSRF attack")
            oauth_logger.error(f"Expected: {stored_state[:20]}...")
            oauth_logger.error(f"Received: {received_state[:20]}...")
            frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
            return redirect(f"{frontend_url}?auth=error&error=state_mismatch")
        
        # Clear state from session
        session.pop('oauth2_state', None)
        session.pop('oauth2_state_timestamp', None)
        session.modified = True
        
        oauth_logger.debug("State validation passed")
        
        # Check for OAuth error
        error = request.args.get('error')
        if error:
            oauth_logger.error(f"OAuth error from Google: {error}")
            frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
            return redirect(f"{frontend_url}?auth=error&error={error}")
        
        oauth_logger.info("Creating OAuth flow")
        # Log CLIENT_CONFIG without sensitive data
        safe_config = {
            "web": {
                "client_id": CLIENT_CONFIG['web']['client_id'][:20] + "...",
                "project_id": CLIENT_CONFIG['web']['project_id'],
                "redirect_uris": CLIENT_CONFIG['web']['redirect_uris']
            }
        }
        oauth_logger.info(f"CLIENT_CONFIG (redacted): {safe_config}")
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=received_state,
            redirect_uri=CLIENT_CONFIG['web']['redirect_uris'][0]
        )
        oauth_logger.info("OAuth flow created successfully")
        
        # Use the authorization server's response to fetch the OAuth 2.0 tokens
        authorization_response = request.url
        oauth_logger.info(f"Authorization response URL: {authorization_response}")
        
        oauth_logger.info("Fetching OAuth tokens")
        flow.fetch_token(authorization_response=authorization_response)
        oauth_logger.info("OAuth tokens fetched successfully")
        
        credentials = flow.credentials
        oauth_logger.info("Getting user info")
        user_info = get_user_info(credentials)
        oauth_logger.info(f"User info retrieved: {user_info}")
        
        user_id = user_info['email']
        oauth_logger.info(f"User ID: {user_id}")

        oauth_logger.info("Converting credentials to JSON")
        creds_dict = json.loads(credentials.to_json())
        oauth_logger.info("Credentials converted successfully")
        
        # Initialize user stats and activities
        if user_id not in user_stats:
            user_stats[user_id] = {
                "total_scanned": 0,
                "total_unsubscribed": 0,
                "time_saved": 0
            }
            oauth_logger.info(f"Initialized stats for user: {user_id}")
        
        if user_id not in user_activities:
            user_activities[user_id] = [{
                "type": "info",
                "message": "Successfully connected Gmail account",
                "time": datetime.now().isoformat()
            }]
            oauth_logger.info(f"Initialized activities for user: {user_id}")
        
        # Create JWT token containing the credentials
        oauth_logger.info("Creating JWT token")
        token = jwt.encode({
            "user_id": user_id,
            "credentials": creds_dict,
            "exp": datetime.now().replace(tzinfo=None) + timedelta(days=5)
        }, app.secret_key, algorithm="HS256")
        oauth_logger.info("JWT token created successfully")

        # Redirect to frontend with token
        frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
        redirect_url = f"{frontend_url}?auth=success&email={user_id}&token={token}"
        
        oauth_logger.debug(f"Final session contents: {dict(session)}")
        oauth_logger.debug("=== OAuth Callback Completed ===")
        oauth_logger.info(f"Redirecting to: {redirect_url}")
        
        return redirect(redirect_url)
        
    except Exception as e:
        oauth_logger.error(f"OAuth callback error: {str(e)}")
        oauth_logger.error(f"Error type: {type(e).__name__}")
        import traceback
        oauth_logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Add environment variable debugging
        oauth_logger.error(f"Environment check: CLIENT_ID exists: {bool(os.environ.get('GOOGLE_CLIENT_ID'))}")
        oauth_logger.error(f"Environment check: CLIENT_SECRET exists: {bool(os.environ.get('GOOGLE_CLIENT_SECRET'))}")
        oauth_logger.error(f"Environment check: PROJECT_ID exists: {bool(os.environ.get('GOOGLE_PROJECT_ID'))}")
        oauth_logger.error(f"Environment check: SECRET_KEY exists: {bool(os.environ.get('SECRET_KEY'))}")
        oauth_logger.error(f"Environment check: REDIRECT_URI: {os.environ.get('REDIRECT_URI', 'NOT SET')}")
        oauth_logger.error(f"Environment check: ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'NOT SET')}")
        oauth_logger.error(f"Environment check: FRONTEND_URL: {os.environ.get('FRONTEND_URL', 'NOT SET')}")
        
        # Include error type in redirect for debugging
        error_type = type(e).__name__
        frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
        
        # Return JSON error response for API calls or redirect for web requests
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                "error": "OAuth callback failed",
                "error_type": error_type,
                "message": str(e)
            }), 500
        else:
            return redirect(f"{frontend_url}?auth=error&error=callback_failed&details={error_type}")

@app.route('/api/auth/logout', methods=['POST'])
@auth_required
def logout():
    """Client-side logout. No server state is stored."""
    return jsonify({"success": True, "message": "Logged out"})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check if the request contains a valid auth token."""
    auth_header = request.headers.get('Authorization', '')
    token = None
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()

    payload = is_authenticated(token)
    if payload:
        return jsonify({
            "authenticated": True,
            "email": payload.get('user_id')
        })

    return jsonify({"authenticated": False})

@app.route('/api/debug/env', methods=['GET'])
def debug_env():
    """Debug endpoint to check environment variables."""
    return jsonify({
        "has_client_id": bool(os.environ.get('GOOGLE_CLIENT_ID')),
        "has_client_secret": bool(os.environ.get('GOOGLE_CLIENT_SECRET')),
        "has_project_id": bool(os.environ.get('GOOGLE_PROJECT_ID')),
        "has_secret_key": bool(os.environ.get('SECRET_KEY')),
        "redirect_uri": os.environ.get('REDIRECT_URI', 'NOT SET'),
        "frontend_url": os.environ.get('FRONTEND_URL', 'NOT SET'),
        "environment": os.environ.get('ENVIRONMENT', 'NOT SET'),
        "client_id_length": len(os.environ.get('GOOGLE_CLIENT_ID', '')),
        "project_id": os.environ.get('GOOGLE_PROJECT_ID', 'NOT SET')
    })

@app.route('/api/stats', methods=['GET'])
@auth_required
def get_stats():
    """Get the user's unsubscription statistics."""
    user_id = g.get('user_id')
    
    return jsonify(user_stats.get(user_id, {
        "total_scanned": 0,
        "total_unsubscribed": 0,
        "time_saved": 0
    }))

@app.route('/api/activities', methods=['GET'])
@auth_required
def get_activities():
    """Get the user's recent activities."""
    user_id = g.get('user_id')
    
    return jsonify(user_activities.get(user_id, []))

@app.route('/api/unsubscribe/start', methods=['POST'])
@auth_required
def start_unsubscription():
    """Start the unsubscription process."""
    user_id = g.get('user_id')
    data = request.json
    
    search_query = data.get('search_query', '"unsubscribe" OR "email preferences" OR "opt-out" OR "subscription preferences"')
    max_emails = data.get('max_emails', 50)
    
    # Add activity
    add_activity(user_id, "info", f"Started unsubscription process with query: {search_query}")
    
    # Start the process in a background thread (in a real app)
    # For demo purposes, we'll do it synchronously
    try:
        process_unsubscriptions(user_id, search_query, max_emails, g.credentials)
        return jsonify({"success": True, "message": "Unsubscription process completed"})
    except Exception as e:
        logger.error(f"Error in unsubscription process: {e}")
        add_activity(user_id, "error", f"Error in unsubscription process: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/unsubscribe/status', methods=['GET'])
@auth_required
def get_unsubscription_status():
    """Get the status of the unsubscription process."""
    user_id = g.get('user_id')
    
    # In a real app, this would check the status of the background process
    # For demo purposes, we'll just return the stats
    return jsonify({
        "stats": user_stats.get(user_id, {}),
        "activities": user_activities.get(user_id, [])
    })

# Claude AI Chat Endpoints
@app.route('/api/chat/status', methods=['GET'])
def chat_status():
    """Check if Claude chat functionality is available."""
    return jsonify({
        "available": CLAUDE_AVAILABLE,
        "service": "claude-chat",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/chat/simple', methods=['POST'])
@auth_required
def chat_simple_endpoint():
    """Simple chat interface with Claude using cached prompts."""
    if not CLAUDE_AVAILABLE:
        return jsonify({"error": "Claude chat not available"}), 503
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Get user context for logging
        user_id = g.user_id
        logger.info(f"Claude chat request from user {user_id}: {message[:100]}...")
        
        # Call Claude with caching
        response = chat_simple(message)
        
        # Log the response
        logger.info(f"Claude response length: {len(response)} characters")
        
        return jsonify({
            "response": response,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except ValueError as e:
        logger.error(f"Configuration error in Claude chat: {e}")
        return jsonify({"error": "Chat service configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in Claude chat: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/chat/gmail-context', methods=['POST'])
@auth_required  
def chat_with_gmail_context_endpoint():
    """Chat with Claude including Gmail unsubscriber context."""
    if not CLAUDE_AVAILABLE:
        return jsonify({"error": "Claude chat not available"}), 503
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        user_id = g.user_id
        
        # Build context from current user session
        gmail_context = {
            "stats": user_stats.get(user_id, {}),
            "recent_activities": user_activities.get(user_id, [])[-3:],
            "service": "gmail-unsubscriber"
        }
        
        user_context = {
            "user_id": user_id,
            "authenticated": True,
            "timestamp": datetime.now().isoformat()
        }
        
        # Include any additional context from request
        if data.get('gmail_context'):
            gmail_context.update(data['gmail_context'])
        
        if data.get('user_context'):
            user_context.update(data['user_context'])
        
        logger.info(f"Claude context chat from user {user_id}: {message[:100]}...")
        
        # Call Claude with context
        response = chat_with_gmail_context(message, gmail_context, user_context)
        
        return jsonify({
            "response": response,
            "user_id": user_id,
            "context_included": {
                "gmail_stats": bool(gmail_context.get("stats")),
                "recent_activities": len(gmail_context.get("recent_activities", [])),
                "user_authenticated": user_context.get("authenticated", False)
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except ValueError as e:
        logger.error(f"Configuration error in Claude context chat: {e}")
        return jsonify({"error": "Chat service configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in Claude context chat: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/chat/conversation', methods=['POST'])
@auth_required
def chat_conversation_endpoint():
    """Multi-turn conversation with Claude maintaining history and caching."""
    if not CLAUDE_AVAILABLE:
        return jsonify({"error": "Claude chat not available"}), 503
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        history = data.get('history', [])
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Validate history format
        if history and not isinstance(history, list):
            return jsonify({"error": "History must be a list of message objects"}), 400
        
        user_id = g.user_id
        logger.info(f"Claude conversation from user {user_id} with {len(history)} history items")
        
        # Call Claude with conversation history for optimal caching
        response = ask_claude(message, history)
        
        # Extract text response
        response_text = response.content[0].text if response.content else ""
        
        # Log cache usage for monitoring
        usage = response.usage
        cache_info = {
            "cache_read_tokens": getattr(usage, 'cache_read_input_tokens', 0),
            "cache_write_tokens": getattr(usage, 'cache_creation_input_tokens', 0),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens
        }
        
        logger.info(f"Cache usage: {cache_info}")
        
        return jsonify({
            "response": response_text,
            "user_id": user_id,
            "conversation_length": len(history) + 1,
            "cache_info": cache_info,
            "timestamp": datetime.now().isoformat()
        })
        
    except ValueError as e:
        logger.error(f"Configuration error in Claude conversation: {e}")
        return jsonify({"error": "Chat service configuration error"}), 500
    except Exception as e:
        logger.error(f"Error in Claude conversation: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Helper functions
def get_user_info(credentials):
    """Get the user's email address from their Google account."""
    try:
        # Use the Google OAuth2 API to get user info
        from google.auth.transport.requests import Request as AuthRequest
        import requests as req
        
        # Get access token from credentials
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(AuthRequest())
        
        # Make direct request to Google's userinfo endpoint
        headers = {'Authorization': f'Bearer {credentials.token}'}
        response = req.get('https://www.googleapis.com/oauth2/v2/userinfo', headers=headers)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to get user info: {response.status_code} - {response.text}")
        
        user_info = response.json()
        if 'email' not in user_info:
            raise ValueError("No email found in user info")
        
        logger.info(f"Successfully retrieved user info for: {user_info.get('email')}")
        return user_info
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        oauth_logger.error(f"Error type: {type(e).__name__}")
        import traceback
        oauth_logger.error(f"Traceback: {traceback.format_exc()}")
        raise

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

def process_unsubscriptions(user_id, query, max_emails, creds_data):
    """Process unsubscriptions for the user."""
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    if not creds.valid and creds.refresh_token:
        try:
            creds.refresh(Request())
            creds_data.update(json.loads(creds.to_json()))
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            raise
    service = build(API_SERVICE_NAME, API_VERSION, credentials=creds, cache_discovery=False)
    
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

# Check if environment variables are set on startup
if not os.environ.get('GOOGLE_CLIENT_ID') or not os.environ.get('GOOGLE_CLIENT_SECRET'):
    logger.warning("Google OAuth credentials not set. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")

if __name__ == '__main__':
    # Run the Flask app
    debug_mode = os.environ.get('ENVIRONMENT') == 'development'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
