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

# Import Claude chat functionality
try:
    from chat import chat_simple, chat_with_gmail_context, ask_claude
    CLAUDE_AVAILABLE = True
    logger.info("Claude chat module loaded successfully")
except Exception as e:
    CLAUDE_AVAILABLE = False
    logger.warning(f"Claude chat module not available: {e}")

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
                "time_saved": 0,
                "domains_unsubscribed": {}
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
    
    # Ensure user exists in stats
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        }
    
    # Get user stats and handle set-to-list migration for JSON serialization
    stats = user_stats[user_id].copy()
    
    if "domains_unsubscribed" in stats:
        for domain, data in stats["domains_unsubscribed"].items():
            emails = data.get("emails", [])
            if isinstance(emails, set):
                # Convert set to list for JSON serialization
                stats["domains_unsubscribed"][domain]["emails"] = list(emails)
    
    logger.info(f"Returning stats for user {user_id}: {stats}")
    return jsonify(stats)

@app.route('/api/activities', methods=['GET'])
@auth_required
def get_activities():
    """Get the user's recent activities."""
    user_id = g.get('user_id')
    
    # Ensure user exists in activities
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    activities = user_activities[user_id]
    logger.info(f"Returning {len(activities)} activities for user {user_id}")
    return jsonify(activities)

@app.route('/api/unsubscribed-services', methods=['GET'])
@auth_required
def get_unsubscribed_services():
    """Get the list of unsubscribed services/domains."""
    user_id = g.get('user_id')
    
    # Ensure user stats exist and have domains_unsubscribed field
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        }
    elif "domains_unsubscribed" not in user_stats[user_id]:
        user_stats[user_id]["domains_unsubscribed"] = {}
    
    # Get domain statistics
    domains_data = user_stats.get(user_id, {}).get("domains_unsubscribed", {})
    
    # Convert to list format for frontend
    services = []
    for domain, data in domains_data.items():
        # Handle migration: convert set to list for JSON serialization
        emails = data.get("emails", [])
        if isinstance(emails, set):
            emails_list = list(emails)
            # Update the stored data to use list format for future calls
            user_stats[user_id]["domains_unsubscribed"][domain]["emails"] = emails_list
        else:
            emails_list = emails
        
        services.append({
            "domain": domain,
            "sender_name": data.get("sender_name", domain),
            "emails": emails_list,
            "count": data.get("count", 0),
            "last_unsubscribed": datetime.now().isoformat()  # You might want to track this separately
        })
    
    # Sort by count (most unsubscribed first)
    services.sort(key=lambda x: x["count"], reverse=True)
    
    return jsonify(services)

@app.route('/api/unsubscribe/start', methods=['POST'])
@auth_required
def start_unsubscription():
    """Start the unsubscription process."""
    user_id = g.get('user_id')
    data = request.json
    
    # Get parameters with defaults
    search_query = data.get('search_query', '"unsubscribe" OR "email preferences" OR "opt-out" OR "subscription preferences"')
    max_emails = data.get('max_emails', 50)
    
    # Ensure user stats and activities exist
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        }
    
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    logger.info(f"Starting unsubscription process for user {user_id} with query: {search_query}, max_emails: {max_emails}")
    
    # Add activity
    add_activity(user_id, "info", f"Started unsubscription process with query: {search_query}")
    
    # Start the process in a background thread (in a real app)
    # For demo purposes, we'll do it synchronously
    try:
        process_unsubscriptions(user_id, search_query, max_emails, g.credentials)
        
        # Return the updated stats along with success message
        stats = user_stats.get(user_id, {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        })
        
        # Ensure domains_unsubscribed emails are lists not sets for JSON serialization
        if "domains_unsubscribed" in stats:
            for domain, data in stats["domains_unsubscribed"].items():
                emails = data.get("emails", [])
                if isinstance(emails, set):
                    stats["domains_unsubscribed"][domain]["emails"] = list(emails)
        
        return jsonify({
            "success": True, 
            "message": "Unsubscription process completed",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error in unsubscription process: {e}")
        add_activity(user_id, "error", f"Error in unsubscription process: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/unsubscribe/status', methods=['GET'])
@auth_required
def get_unsubscription_status():
    """Get the status of the unsubscription process."""
    user_id = g.get('user_id')
    
    # Ensure user exists in both stats and activities
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        }
    
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    # Get user stats and handle set-to-list migration for JSON serialization
    stats = user_stats[user_id].copy()
    if "domains_unsubscribed" in stats:
        for domain, data in stats["domains_unsubscribed"].items():
            emails = data.get("emails", [])
            if isinstance(emails, set):
                # Convert set to list for JSON serialization
                stats["domains_unsubscribed"][domain]["emails"] = list(emails)
    
    activities = user_activities[user_id]
    
    logger.info(f"Returning status for user {user_id}: stats={stats}, activities_count={len(activities)}")
    
    return jsonify({
        "stats": stats,
        "activities": activities
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

def add_activity(user_id, activity_type, message, metadata=None):
    """Add an activity to the user's activity log."""
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    activity = {
        "type": activity_type,
        "message": message,
        "time": datetime.now().isoformat()
    }
    
    # Add metadata if provided
    if metadata:
        activity["metadata"] = metadata
    
    user_activities[user_id].insert(0, activity)
    
    # Limit to 50 most recent activities
    if len(user_activities[user_id]) > 50:
        user_activities[user_id] = user_activities[user_id][:50]
    
    logger.info(f"Added activity for user {user_id}: [{activity_type}] {message}")
    return activity

def ensure_unsubscribed_label(service):
    """Ensure the UNSUBSCRIBED label exists in Gmail."""
    try:
        # Try to get existing labels
        labels_result = service.users().labels().list(userId='me').execute()
        labels = labels_result.get('labels', [])
        
        # Check if UNSUBSCRIBED label already exists
        for label in labels:
            if label['name'] == 'UNSUBSCRIBED':
                logger.info(f"Label 'UNSUBSCRIBED' already exists")
                return label['id']
        
        # Create the label if it doesn't exist
        label_object = {
            'name': 'UNSUBSCRIBED',
            'messageListVisibility': 'show',
            'labelListVisibility': 'labelShow'
        }
        
        created_label = service.users().labels().create(userId='me', body=label_object).execute()
        logger.info(f"Created UNSUBSCRIBED label with ID: {created_label['id']}")
        return created_label['id']
        
    except Exception as e:
        logger.error(f"Error ensuring UNSUBSCRIBED label exists: {e}")
        return None

def process_unsubscriptions(user_id, query, max_emails, creds_data):
    """Process unsubscriptions for the user."""
    # Ensure user stats and activities are initialized
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}
        }
        logger.info(f"Initialized stats for user {user_id} in process_unsubscriptions")
    
    if user_id not in user_activities:
        user_activities[user_id] = []
        logger.info(f"Initialized activities for user {user_id} in process_unsubscriptions")
    
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    if not creds.valid and creds.refresh_token:
        try:
            creds.refresh(Request())
            creds_data.update(json.loads(creds.to_json()))
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            raise
    service = build(API_SERVICE_NAME, API_VERSION, credentials=creds, cache_discovery=False)
    
    # Ensure UNSUBSCRIBED label exists
    unsubscribed_label_id = ensure_unsubscribed_label(service)
    if unsubscribed_label_id:
        logger.info(f"UNSUBSCRIBED label ready with ID: {unsubscribed_label_id}")
    
    # Search for emails
    add_activity(user_id, "info", "🔍 Searching for subscription emails...")
    messages = search_emails(service, query, max_emails)
    
    if not messages:
        add_activity(user_id, "warning", "⚠️ No subscription emails found matching the search criteria")
        return
    
    add_activity(user_id, "info", f"📧 Found {len(messages)} subscription emails - starting unsubscription process")
    
    # Track progress counters
    successful_unsubscriptions = 0
    failed_unsubscriptions = 0
    emails_scanned = 0
    
    # Process each email
    for i, msg in enumerate(messages):
        try:
            emails_scanned += 1
            
            # Update progress every 10 emails or at the end
            if i == 0:
                add_activity(user_id, "info", f"🔄 Starting to process {len(messages)} emails...")
            elif (i + 1) % 10 == 0 or i == len(messages) - 1:
                progress_percentage = int(((i + 1) / len(messages)) * 100)
                add_activity(user_id, "info", f"📊 Progress: {i + 1}/{len(messages)} emails processed ({progress_percentage}% complete)")
            
            logger.info(f"Processing email {i+1}/{len(messages)}: {msg['id']}")
            
            # Get email content and metadata
            email_data = get_email(service, msg['id'])
            email_html = email_data.get("content", "")
            metadata = email_data.get("metadata", {})
            
            # Update scanned count immediately
            user_stats[user_id]["total_scanned"] = emails_scanned
            
            # Extract unsubscribe links
            unsub_links = extract_unsub_links(email_html)
            
            if not unsub_links:
                sender_info = metadata.get("sender_name", "Unknown sender")
                add_activity(user_id, "warning", f"⚠️ No unsubscribe links found in email from {sender_info}")
                failed_unsubscriptions += 1
                continue
            
            # Try to unsubscribe
            unsubscribed = False
            
            for link in unsub_links:
                if execute_unsub(link):
                    unsubscribed = True
                    break
            
            if unsubscribed:
                successful_unsubscriptions += 1
                user_stats[user_id]["total_unsubscribed"] = successful_unsubscriptions
                user_stats[user_id]["time_saved"] = successful_unsubscriptions * 2  # 2 minutes per unsubscription
                
                # Track domain statistics
                domain = metadata.get("domain", "unknown")
                if domain and domain != "unknown":
                    if domain not in user_stats[user_id]["domains_unsubscribed"]:
                        user_stats[user_id]["domains_unsubscribed"][domain] = {
                            "count": 0,
                            "sender_name": metadata.get("sender_name", domain),
                            "emails": []
                        }
                    user_stats[user_id]["domains_unsubscribed"][domain]["count"] += 1
                    sender_email = metadata.get("sender_email")
                    if sender_email and sender_email not in user_stats[user_id]["domains_unsubscribed"][domain]["emails"]:
                        user_stats[user_id]["domains_unsubscribed"][domain]["emails"].append(sender_email)
                
                # Add label to email if we have the label ID
                if unsubscribed_label_id:
                    try:
                        service.users().messages().modify(
                            userId='me',
                            id=msg['id'],
                            body={'removeLabelIds': ['INBOX'], 'addLabelIds': [unsubscribed_label_id]}
                        ).execute()
                        logger.info(f"Successfully labeled email {msg['id']} as UNSUBSCRIBED")
                    except Exception as label_error:
                        logger.warning(f"Failed to add UNSUBSCRIBED label to email {msg['id']}: {label_error}")
                
                sender_info = metadata.get("sender_name", "Unknown sender")
                sender_email = metadata.get("sender_email", "")
                display_name = f"{sender_info}" + (f" ({sender_email})" if sender_email and sender_email != sender_info else "")
                add_activity(user_id, "success", f"✅ Successfully unsubscribed from {display_name}")
            else:
                failed_unsubscriptions += 1
                sender_info = metadata.get("sender_name", "Unknown sender")
                sender_email = metadata.get("sender_email", "")
                display_name = f"{sender_info}" + (f" ({sender_email})" if sender_email and sender_email != sender_info else "")
                add_activity(user_id, "error", f"❌ Failed to unsubscribe from {display_name} - no working unsubscribe link found")
            
            # Rate limiting - be respectful to email servers
            time.sleep(2)
            
        except Exception as e:
            failed_unsubscriptions += 1
            logger.error(f"Error processing email {msg['id']}: {e}")
            add_activity(user_id, "error", f"❌ Error processing email: {str(e)}")
    
    # Final summary
    time_saved = user_stats[user_id]['time_saved']
    
    summary_message = f"🎉 Unsubscription process completed! "
    summary_message += f"Scanned {emails_scanned} emails, "
    summary_message += f"successfully unsubscribed from {successful_unsubscriptions} services"
    if failed_unsubscriptions > 0:
        summary_message += f" ({failed_unsubscriptions} failed)"
    summary_message += f", saving you {time_saved} minutes of future email management time."
    
    add_activity(user_id, "success", summary_message)
    
    logger.info(f"Completed unsubscription process for user {user_id}: {successful_unsubscriptions} successful, {failed_unsubscriptions} failed, {emails_scanned} total scanned")

def search_emails(service, query, max_results=50):
    """Search Gmail for emails matching the query."""
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        logger.info(f"Found {len(messages)} emails matching query: {query}")
        return messages
    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        return []

def get_email(service, msg_id):
    """Get the HTML content and metadata of an email with enhanced error handling."""
    try:
        logger.debug(f"Fetching email content for message ID: {msg_id}")
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        if not message:
            logger.warning(f"No message returned for ID: {msg_id}")
            return {"content": "", "metadata": {}}
        
        # Extract metadata from headers
        metadata = extract_email_metadata(message)
        
        payload = message.get('payload', {})
        if not payload:
            logger.warning(f"No payload found for message ID: {msg_id}")
            return {"content": "", "metadata": metadata}
        
        # Try to get HTML content
        html_content = extract_html_content(payload, msg_id)
        
        # If no HTML content found, try to get plain text
        if not html_content:
            logger.debug(f"No HTML content found for {msg_id}, trying plain text")
            html_content = extract_text_content(payload, msg_id)
        
        logger.debug(f"Extracted {len(html_content)} characters from email {msg_id}")
        return {"content": html_content, "metadata": metadata}
        
    except Exception as e:
        logger.error(f"Error getting email {msg_id}: {type(e).__name__} - {str(e)}")
        # Don't re-raise the exception, return empty content to allow processing to continue
        return {"content": "", "metadata": {}}

def extract_html_content(payload, msg_id):
    """Extract HTML content from email payload."""
    try:
        parts = payload.get('parts', [])
        
        if parts:
            # Multi-part message
            for part in parts:
                if part.get('mimeType') == 'text/html':
                    if 'data' in part.get('body', {}):
                        data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        return data
                # Check nested parts (for complex multipart messages)
                elif part.get('parts'):
                    nested_content = extract_html_content(part, msg_id)
                    if nested_content:
                        return nested_content
        else:
            # Single part message
            if payload.get('mimeType') == 'text/html':
                if 'data' in payload.get('body', {}):
                    data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    return data
        
        return ""
        
    except Exception as e:
        logger.error(f"Error extracting HTML content from {msg_id}: {str(e)}")
        return ""

def extract_text_content(payload, msg_id):
    """Extract plain text content from email payload as fallback."""
    try:
        parts = payload.get('parts', [])
        
        if parts:
            # Multi-part message
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part.get('body', {}):
                        data = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        return data
                # Check nested parts
                elif part.get('parts'):
                    nested_content = extract_text_content(part, msg_id)
                    if nested_content:
                        return nested_content
        else:
            # Single part message
            if payload.get('mimeType') == 'text/plain':
                if 'data' in payload.get('body', {}):
                    data = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    return data
        
        return ""
        
    except Exception as e:
        logger.error(f"Error extracting text content from {msg_id}: {str(e)}")
        return ""

def extract_email_metadata(message):
    """Extract metadata from email headers."""
    try:
        metadata = {
            "sender": "",
            "sender_name": "",
            "sender_email": "",
            "domain": "",
            "subject": "",
            "date": ""
        }
        
        # Get headers from the email
        headers = message.get('payload', {}).get('headers', [])
        
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            
            if name == 'from':
                metadata['sender'] = value
                # Parse sender name and email
                # Format can be: "Name <email@domain.com>" or just "email@domain.com"
                import re
                match = re.match(r'^"?([^"<]*)"?\s*<?([^>]+)>?$', value.strip())
                if match:
                    sender_name = match.group(1).strip()
                    sender_email = match.group(2).strip()
                    metadata['sender_name'] = sender_name if sender_name else sender_email.split('@')[0]
                    metadata['sender_email'] = sender_email
                    # Extract domain
                    if '@' in sender_email:
                        metadata['domain'] = sender_email.split('@')[1].lower()
                else:
                    # Fallback: treat entire value as email
                    metadata['sender_email'] = value.strip()
                    if '@' in value:
                        metadata['domain'] = value.split('@')[1].lower()
                        metadata['sender_name'] = value.split('@')[0]
                    
            elif name == 'subject':
                metadata['subject'] = value
                
            elif name == 'date':
                metadata['date'] = value
        
        # Clean up sender name - remove quotes, extra spaces
        metadata['sender_name'] = metadata['sender_name'].strip('"\'').strip()
        
        # If no sender name, use the domain as a fallback
        if not metadata['sender_name'] and metadata['domain']:
            # Make domain more readable: amazon.com -> Amazon
            domain_parts = metadata['domain'].split('.')
            if domain_parts:
                metadata['sender_name'] = domain_parts[0].capitalize()
        
        logger.debug(f"Extracted metadata: {metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting email metadata: {type(e).__name__} - {str(e)}")
        return {
            "sender": "",
            "sender_name": "",
            "sender_email": "",
            "domain": "",
            "subject": "",
            "date": ""
        }

def extract_unsub_links(html):
    """Extract unsubscribe links from HTML content."""
    if not html:
        return []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        pattern = re.compile(r'unsubscribe|opt[-\s]?out|email preferences|manage preferences', re.I)
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text(strip=True)
            
            # Check if the link text or href contains unsubscribe-related keywords
            if pattern.search(link_text) or pattern.search(href):
                # Make sure it's a valid URL
                if href.startswith(('http://', 'https://')):
                    links.append(href)
        
        logger.debug(f"Found {len(links)} unsubscribe links in email")
        return links
    except Exception as e:
        logger.error(f"Error extracting unsubscribe links: {e}")
        return []

def execute_unsub(link):
    """Execute an unsubscription by visiting the link."""
    try:
        logger.info(f"Attempting to unsubscribe via: {link}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(link, timeout=10, headers=headers, allow_redirects=True)
        
        if response.status_code == 200:
            logger.info(f'Successful GET unsubscribe: {link}')
            return True
        else:
            logger.warning(f'Non-200 status for unsubscribe: {link}, status: {response.status_code}')
            return False
            
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
