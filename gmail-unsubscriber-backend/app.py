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
from werkzeug.middleware.proxy_fix import ProxyFix
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database functionality
from database import initialize_database, get_db_manager

# Set insecure transport for OAuth in development only
# WARNING: This should NEVER be enabled in production!
if os.environ.get('ENVIRONMENT') == 'development' or (
    os.environ.get('ENVIRONMENT') is None and 
    os.environ.get('FRONTEND_URL', '').startswith('http://localhost')
):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    print("WARNING: Running in development mode with OAUTHLIB_INSECURE_TRANSPORT enabled.")
    print("This allows OAuth over HTTP but should NEVER be used in production!")

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

# Log insecure transport warning if enabled
if os.environ.get('OAUTHLIB_INSECURE_TRANSPORT') == '1':
    logger.warning("OAUTHLIB_INSECURE_TRANSPORT is enabled - OAuth will work over HTTP.")
    logger.warning("This is for development only and must NOT be used in production!")

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

# Add ProxyFix middleware to handle X-Forwarded headers properly
# This helps with proxy/load balancer scenarios like Railway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Configure Flask session for OAuth state management
# Different settings for development vs production
is_production = os.environ.get('ENVIRONMENT') == 'production'
is_https = not (os.environ.get('FRONTEND_URL', '').startswith('http://localhost') or 
               os.environ.get('ENVIRONMENT') == 'development')

app.config.update(
    SESSION_COOKIE_SECURE=is_https,  # Only secure in HTTPS environments
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None' if is_production else 'Lax',  # 'None' for cross-origin in production
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    SESSION_COOKIE_DOMAIN=None,  # Don't set for localhost development
    SESSION_COOKIE_NAME='gmail_unsubscriber_session',  # Custom session name
    SESSION_COOKIE_PATH='/'  # Ensure cookie is available for all paths
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
    # Railway deployment URLs
    'https://gmailunsubscriber-production.up.railway.app',
    'https://gmail-unsubscriber-backend.up.railway.app',
    # Regex pattern for all Railway subdomains
    r'^https://.*\.railway\.app$',
]

# Add localhost origins for development
if os.environ.get('ENVIRONMENT') == 'development':
    allowed_origins.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',  # Common React dev server port
        'http://127.0.0.1:3000',
        'http://[::1]:8000',  # IPv6 localhost
        'http://[::]:8000',  # IPv6 all interfaces
        r'^http://\[.*\]:8000$',  # Regex for any IPv6 address on port 8000
    ])
    oauth_logger.debug(f"Development mode: Added localhost origins to CORS")

CORS(app, 
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "OPTIONS"],
     expose_headers=["Set-Cookie"],
     max_age=600  # Cache preflight requests for 10 minutes
)

# Gmail API settings
SCOPES = [
    'openid',  # Google automatically adds this when requesting userinfo.email
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/userinfo.email'
]
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

user_stats = {}
user_activities = {}
oauth_states = set()

# Initialize database and load existing data
try:
    db_success = initialize_database()
    if db_success:
        db_manager = get_db_manager()
        if db_manager:
            # Load existing data from database
            loaded_stats = db_manager.load_user_stats()
            loaded_activities = db_manager.load_user_activities()
            
            # Merge with in-memory data (database takes precedence)
            user_stats.update(loaded_stats)
            user_activities.update(loaded_activities)
            
            logger.info(f"Loaded data for {len(loaded_stats)} users with stats and {len(loaded_activities)} users with activities")
        else:
            logger.warning("Database manager not available after initialization")
    else:
        logger.error("Database initialization failed - running in memory-only mode")
except Exception as e:
    logger.error(f"Database setup failed: {e} - running in memory-only mode")

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

def get_redirect_uri(request):
    """Determine the correct redirect URI based on the request origin."""
    # Hardcode for production to avoid any detection issues
    if os.environ.get('ENVIRONMENT') == 'production':
        return 'https://gmailunsubscriber-production.up.railway.app/oauth2callback'
    
    # Existing logic for dev (dynamic detection)
    host = request.headers.get('Host', 'localhost:5000')
    scheme = 'https' if request.is_secure else 'http'
    
    # Handle X-Forwarded headers for proxy/load balancer scenarios
    forwarded_proto = request.headers.get('X-Forwarded-Proto')
    if forwarded_proto:
        scheme = forwarded_proto
    
    forwarded_host = request.headers.get('X-Forwarded-Host')
    if forwarded_host:
        host = forwarded_host
    
    # For local development, always use localhost:5000 for consistency
    # This ensures the OAuth callback matches regardless of how the frontend is accessed
    if host in ['[::1]:5000', '[::]:5000', '127.0.0.1:5000'] or 'localhost' in host:
        host = 'localhost:5000'
    
    # Construct the redirect URI
    redirect_uri = f"{scheme}://{host}/oauth2callback"
    
    oauth_logger.debug(f"Determined redirect URI: {redirect_uri}")
    oauth_logger.debug(f"Request headers - Host: {request.headers.get('Host')}, X-Forwarded-Host: {forwarded_host}, X-Forwarded-Proto: {forwarded_proto}")
    oauth_logger.debug(f"Environment: {os.environ.get('ENVIRONMENT', 'NOT SET')}")
    
    return redirect_uri

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

@app.route('/api/session/debug', methods=['GET'])
def debug_session():
    """Debug endpoint to check session status."""
    session_info = {
        "session_contents": dict(session),
        "session_cookie_config": {
            "domain": app.config.get('SESSION_COOKIE_DOMAIN'),
            "secure": app.config.get('SESSION_COOKIE_SECURE'),
            "httponly": app.config.get('SESSION_COOKIE_HTTPONLY'),
            "samesite": app.config.get('SESSION_COOKIE_SAMESITE'),
            "lifetime": str(app.config.get('PERMANENT_SESSION_LIFETIME'))
        },
        "environment_info": {
            "is_production": is_production,
            "is_https": is_https,
            "frontend_url": os.environ.get('FRONTEND_URL', 'NOT SET'),
            "environment": os.environ.get('ENVIRONMENT', 'NOT SET')
        },
        "request_info": {
            "host": request.host,
            "origin": request.headers.get('Origin'),
            "cookies": list(request.cookies.keys()),
            "has_session_cookie": 'session' in request.cookies,
            "session_cookie_name": app.config.get('SESSION_COOKIE_NAME')
        },
        "stored_state": {
            "oauth2_state": session.get('oauth2_state', 'Not found'),
            "oauth2_state_timestamp": session.get('oauth2_state_timestamp', 'Not found'),
            "oauth_redirect_uri": session.get('oauth_redirect_uri', 'Not found'),
            "fallback_states_count": len(oauth_states)
        }
    }
    
    oauth_logger.debug(f"Session debug info: {json.dumps(session_info, indent=2)}")
    return jsonify(session_info)

@app.route('/api/auth/login', methods=['GET'])
def login():
    """Initiate the OAuth2 authorization flow."""
    oauth_logger.debug("=== OAuth Login Started ===")
    oauth_logger.debug(f"Request headers: {dict(request.headers)}")
    oauth_logger.debug(f"Request cookies: {dict(request.cookies)}")
    oauth_logger.debug(f"Session before login: {dict(session)}")
    oauth_logger.debug(f"Session cookie domain: {app.config.get('SESSION_COOKIE_DOMAIN')}")
    oauth_logger.debug(f"Session cookie secure: {app.config.get('SESSION_COOKIE_SECURE')}")
    oauth_logger.debug(f"Session cookie samesite: {app.config.get('SESSION_COOKIE_SAMESITE')}")
    
    # Determine the redirect URI dynamically
    redirect_uri = get_redirect_uri(request)
    
    # Store the redirect URI in session for callback validation
    session['oauth_redirect_uri'] = redirect_uri
    
    # Create flow instance with dynamic redirect URI
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    oauth_logger.debug(f"OAuth redirect URI: {redirect_uri}")
    
    # Generate URL for request to Google's OAuth 2.0 server
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Store state in Flask session instead of in-memory set
    session['oauth2_state'] = state
    session['oauth2_state_timestamp'] = datetime.now().isoformat()
    session.permanent = True  # Make session permanent for better persistence
    session.modified = True
    
    # Also store state in a backup location for fallback (optional)
    oauth_states.add(state)  # Keep in-memory backup for Railway restarts
    
    oauth_logger.debug(f"Generated OAuth state: {state}")
    oauth_logger.debug(f"Stored state in session: {session.get('oauth2_state')}")
    oauth_logger.debug(f"Session after storing state: {dict(session)}")
    oauth_logger.debug(f"Session ID (if available): {request.cookies.get('session', 'No session cookie')}")
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
        oauth_logger.debug(f"Request headers: {dict(request.headers)}")
        oauth_logger.debug(f"Request cookies: {dict(request.cookies)}")
        oauth_logger.debug(f"Session before state check: {dict(session)}")
        oauth_logger.debug(f"Session ID (if available): {request.cookies.get('session', 'No session cookie')}")
        
        # Enhanced state validation
        received_state = request.args.get('state')
        stored_state = session.get('oauth2_state')
        
        oauth_logger.debug(f"Received state: {received_state}")
        oauth_logger.debug(f"Stored state: {stored_state}")
        
        if not received_state:
            oauth_logger.error("Missing state parameter in callback")
            frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
            return redirect(f"{frontend_url}?auth=error&error=missing_state")
        
        # Enhanced state validation with fallback mechanism
        if not stored_state:
            oauth_logger.warning("No stored state in session - checking fallback")
            
            # Check fallback in-memory storage (for Railway restarts)
            if received_state in oauth_states:
                oauth_logger.info("Found state in fallback storage, proceeding with OAuth")
                oauth_states.discard(received_state)  # Remove from fallback
            else:
                oauth_logger.error("No stored state in session or fallback - possible session loss")
                frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
                return redirect(f"{frontend_url}?auth=error&error=no_stored_state")
        else:
            # Primary validation: check against session state
            if not secrets.compare_digest(received_state, stored_state):
                oauth_logger.error("State mismatch - possible CSRF attack")
                oauth_logger.error(f"Expected: {stored_state[:20]}...")
                oauth_logger.error(f"Received: {received_state[:20]}...")
                frontend_url = os.environ.get('FRONTEND_URL', 'https://gmail-unsubscriber-frontend.vercel.app')
                return redirect(f"{frontend_url}?auth=error&error=state_mismatch")
            
            # Remove from fallback storage if it exists
            oauth_states.discard(received_state)
        
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
        
        # Get the redirect URI from session or determine it dynamically
        redirect_uri = session.get('oauth_redirect_uri') or get_redirect_uri(request)
        oauth_logger.debug(f"Using redirect URI for callback: {redirect_uri}")
        
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            state=received_state,
            redirect_uri=redirect_uri
        )
        oauth_logger.info("OAuth flow created successfully")
        
        # Use the authorization server's response to fetch the OAuth 2.0 tokens
        authorization_response = request.url
        oauth_logger.info(f"Authorization response URL: {authorization_response}")
        
        oauth_logger.info("Fetching OAuth tokens")
        try:
            flow.fetch_token(authorization_response=authorization_response)
            oauth_logger.info("OAuth tokens fetched successfully")
        except Warning as w:
            # Handle scope mismatch warning (Google adds 'openid' automatically)
            oauth_logger.warning(f"OAuth scope warning (non-fatal): {str(w)}")
            oauth_logger.info("Continuing with authentication despite scope warning")
        
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
            save_stats_to_db(user_id)
        
        if user_id not in user_activities:
            activity = {
                "type": "info",
                "message": "Successfully connected Gmail account",
                "time": datetime.now().isoformat()
            }
            user_activities[user_id] = [activity]
            oauth_logger.info(f"Initialized activities for user: {user_id}")
            save_activity_to_db(user_id, activity)
        
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
        
        # Add specific handling for common OAuth errors
        error_message = str(e).lower()
        if 'redirect_uri_mismatch' in error_message:
            oauth_logger.error("REDIRECT_URI_MISMATCH ERROR DETECTED!")
            oauth_logger.error(f"Used redirect URI: {redirect_uri}")
            oauth_logger.error("Please ensure this URI is added to your Google Cloud Console:")
            oauth_logger.error("1. Go to https://console.cloud.google.com/")
            oauth_logger.error("2. Navigate to APIs & Services → Credentials")
            oauth_logger.error("3. Edit your OAuth 2.0 Client ID")
            oauth_logger.error(f"4. Add '{redirect_uri}' to Authorized redirect URIs")
        
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

@app.route('/api/auth/debug', methods=['GET'])
def auth_debug():
    """Debug endpoint to show OAuth configuration."""
    redirect_uri = get_redirect_uri(request)
    
    return jsonify({
        "current_redirect_uri": redirect_uri,
        "is_production": os.environ.get('ENVIRONMENT') == 'production',
        "hardcoded_production_uri": 'https://gmailunsubscriber-production.up.railway.app/oauth2callback',
        "request_host": request.headers.get('Host'),
        "request_scheme": 'https' if request.is_secure else 'http',
        "x_forwarded_host": request.headers.get('X-Forwarded-Host'),
        "x_forwarded_proto": request.headers.get('X-Forwarded-Proto'),
        "configured_client_id": CLIENT_CONFIG['web']['client_id'][:20] + "..." if CLIENT_CONFIG['web']['client_id'] else None,
        "environment": os.environ.get('ENVIRONMENT', 'NOT SET'),
        "frontend_url": os.environ.get('FRONTEND_URL', 'NOT SET'),
        "proxy_fix_enabled": True,
        "instructions": {
            "message": "Add the 'current_redirect_uri' to your Google Cloud Console",
            "steps": [
                "1. Go to https://console.cloud.google.com/",
                "2. Navigate to APIs & Services → Credentials",
                "3. Edit your OAuth 2.0 Client ID",
                f"4. Add '{redirect_uri}' to Authorized redirect URIs",
                "5. Save the changes"
            ]
        }
    })

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

@app.route('/api/unsubscribed-services', methods=['GET'])
@auth_required
def get_unsubscribed_services():
    """Get the list of unsubscribed services/domains."""
    user_id = g.get('user_id')
    
    # Get domain statistics
    domains_data = user_stats.get(user_id, {}).get("domains_unsubscribed", {})
    
    # Convert to list format for frontend
    services = []
    for domain, data in domains_data.items():
        # Convert set to list for JSON serialization
        emails_list = list(data.get("emails", []))
        
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

@app.route('/api/database/stats', methods=['GET'])
def get_database_stats():
    """Get database statistics for monitoring."""
    try:
        db_manager = get_db_manager()
        if db_manager:
            db_stats = db_manager.get_database_stats()
            return jsonify({
                "database_available": True,
                "stats": db_stats,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "database_available": False,
                "message": "Database manager not available",
                "timestamp": datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return jsonify({
            "database_available": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

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
        # Log credentials object for debugging
        oauth_logger.debug(f"Credentials type: {type(credentials)}")
        oauth_logger.debug(f"Credentials valid: {credentials.valid}")
        oauth_logger.debug(f"Credentials expired: {credentials.expired}")
        oauth_logger.debug(f"Has refresh token: {bool(credentials.refresh_token)}")
        
        # Refresh credentials if needed
        from google.auth.transport.requests import Request as AuthRequest
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                oauth_logger.info("Refreshing expired credentials")
                credentials.refresh(AuthRequest())
        
        # Log token information for debugging
        oauth_logger.debug(f"Token value: {getattr(credentials, 'token', 'NO TOKEN ATTR')[:20]}..." if hasattr(credentials, 'token') and credentials.token else "NO TOKEN")
        oauth_logger.debug(f"Token expiry: {getattr(credentials, 'expiry', 'NO EXPIRY')}")
        oauth_logger.debug(f"Scopes: {getattr(credentials, 'scopes', 'NO SCOPES')}")
        
        # Option 1: Use the OAuth2 API service (recommended approach)
        try:
            oauth_logger.info("Attempting to get user info using OAuth2 service")
            # Create the OAuth2 service with explicit authorization
            from googleapiclient import discovery
            import google_auth_httplib2
            authorized_http = google_auth_httplib2.AuthorizedHttp(credentials)
            oauth2_service = discovery.build('oauth2', 'v2', http=authorized_http)
            user_info = oauth2_service.userinfo().get().execute()
            
            if 'email' not in user_info:
                raise ValueError("No email found in user info")
            
            logger.info(f"Successfully retrieved user info for: {user_info.get('email')}")
            return user_info
            
        except Exception as service_error:
            oauth_logger.error(f"OAuth2 service approach failed: {service_error}")
            
            # Option 2: Fallback to manual request with proper token access
            oauth_logger.info("Falling back to manual HTTP request")
            import requests as req
            
            # Try different ways to access the token
            access_token = None
            if hasattr(credentials, 'token') and credentials.token:
                access_token = credentials.token
                oauth_logger.debug("Using credentials.token")
            elif hasattr(credentials, 'access_token') and credentials.access_token:
                access_token = credentials.access_token
                oauth_logger.debug("Using credentials.access_token")
            elif hasattr(credentials, '_token') and credentials._token:
                access_token = credentials._token
                oauth_logger.debug("Using credentials._token")
            else:
                # Log available attributes for debugging
                oauth_logger.error(f"Available credential attributes: {dir(credentials)}")
                raise ValueError("Could not find access token in credentials object")
            
            headers = {'Authorization': f'Bearer {access_token}'}
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
    
    # Save to database
    save_activity_to_db(user_id, activity)
    
    return activity

def save_stats_to_db(user_id):
    """Save user statistics to database."""
    try:
        db_manager = get_db_manager()
        if db_manager and user_id in user_stats:
            success = db_manager.save_single_user_stats(user_id, user_stats[user_id])
            if not success:
                logger.warning(f"Failed to save stats to database for user: {user_id}")
        else:
            logger.debug("Database manager not available or user not found for stats save")
    except Exception as e:
        logger.error(f"Error saving stats to database for user {user_id}: {e}")

def save_activity_to_db(user_id, activity):
    """Save a single activity to database."""
    try:
        db_manager = get_db_manager()
        if db_manager:
            success = db_manager.save_single_user_activity(user_id, activity)
            if not success:
                logger.warning(f"Failed to save activity to database for user: {user_id}")
        else:
            logger.debug("Database manager not available for activity save")
    except Exception as e:
        logger.error(f"Error saving activity to database for user {user_id}: {e}")

def save_all_data_to_db():
    """Save all user data to database. Used for bulk operations."""
    try:
        db_manager = get_db_manager()
        if db_manager:
            stats_success = db_manager.save_user_stats(user_stats)
            activities_success = db_manager.save_user_activities(user_activities)
            
            if stats_success and activities_success:
                logger.info("Successfully saved all data to database")
            else:
                logger.warning("Partial failure saving data to database")
        else:
            logger.debug("Database manager not available for bulk save")
    except Exception as e:
        logger.error(f"Error saving all data to database: {e}")

def ensure_label_exists(service, label_name):
    """Ensure a Gmail label exists, create it if it doesn't."""
    try:
        # List all labels
        labels = service.users().labels().list(userId='me').execute()
        
        # Check if label already exists
        for label in labels.get('labels', []):
            if label['name'] == label_name:
                logger.info(f"Label '{label_name}' already exists")
                return label['id']
        
        # Create the label if it doesn't exist
        logger.info(f"Creating label '{label_name}'")
        label_object = {
            'name': label_name,
            'messageListVisibility': 'show',
            'labelListVisibility': 'labelShow'
        }
        
        created_label = service.users().labels().create(
            userId='me',
            body=label_object
        ).execute()
        
        logger.info(f"Successfully created label '{label_name}' with ID: {created_label['id']}")
        return created_label['id']
        
    except Exception as e:
        logger.error(f"Error ensuring label '{label_name}' exists: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        # Return None if we can't create the label, we'll handle this gracefully
        return None

def process_unsubscriptions(user_id, query, max_emails, creds_data):
    """Process unsubscriptions for the user."""
    
    # Initialize user stats if not exists
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0,
            "domains_unsubscribed": {}  # Track unsubscriptions by domain
        }
        logger.info(f"Initialized stats for user: {user_id}")
    else:
        logger.info(f"Using existing stats for user: {user_id}")
        # Ensure domains_unsubscribed exists for older sessions
        if "domains_unsubscribed" not in user_stats[user_id]:
            user_stats[user_id]["domains_unsubscribed"] = {}
    
    # Initialize user activities if not exists
    if user_id not in user_activities:
        user_activities[user_id] = []
        logger.info(f"Initialized activities for user: {user_id}")
    else:
        logger.info(f"Using existing activities for user: {user_id} (count: {len(user_activities[user_id])})")
    
    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    if not creds.valid and creds.refresh_token:
        try:
            creds.refresh(Request())
            creds_data.update(json.loads(creds.to_json()))
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            raise
    service = build(API_SERVICE_NAME, API_VERSION, credentials=creds)
    
    # Ensure the UNSUBSCRIBED label exists
    add_activity(user_id, "info", "Setting up Gmail labels...")
    unsubscribed_label_id = ensure_label_exists(service, 'UNSUBSCRIBED')
    if unsubscribed_label_id:
        logger.info(f"UNSUBSCRIBED label ready with ID: {unsubscribed_label_id}")
    else:
        logger.warning("Could not create UNSUBSCRIBED label, will skip labeling emails")
    
    # Search for emails
    add_activity(user_id, "info", "Searching for subscription emails...")
    messages = search_emails(service, query, max_emails)
    
    if not messages:
        add_activity(user_id, "warning", "No subscription emails found")
        return
    
    add_activity(user_id, "info", f"Found {len(messages)} subscription emails")
    
    # Process each email with individual error boundaries
    successful_count = 0
    failed_count = 0
    
    for i, msg in enumerate(messages):
        msg_id = msg.get('id', 'unknown')
        
        try:
            logger.info(f"Processing email {i+1}/{len(messages)}: {msg_id}")
            logger.debug(f"user_id: {user_id}")
            logger.debug(f"user_stats keys: {list(user_stats.keys())}")
            logger.debug(f"user_id in user_stats: {user_id in user_stats}")
            
            # Step 1: Get email content (with error boundary)
            email_data = {"content": "", "metadata": {}}
            try:
                email_data = get_email(service, msg_id)
                if not email_data.get("content"):
                    logger.warning(f"No content retrieved for email {msg_id}")
                    metadata = email_data.get("metadata", {})
                    sender_info = metadata.get("sender_name", "Unknown sender")
                    add_activity(user_id, "warning", f"No content found in email {i+1}/{len(messages)} from {sender_info}", metadata)
                    user_stats[user_id]["total_scanned"] += 1
                    save_stats_to_db(user_id)
                    failed_count += 1
                    continue
            except Exception as content_error:
                logger.error(f"Failed to get content for email {msg_id}: {str(content_error)}")
                add_activity(user_id, "error", f"Failed to retrieve email {i+1}/{len(messages)}")
                failed_count += 1
                continue
            
            # Step 2: Extract unsubscribe links (with error boundary)
            unsub_links = []
            metadata = email_data.get("metadata", {})
            sender_info = metadata.get("sender_name", "Unknown sender")
            email_content = email_data.get("content", "")
            
            try:
                unsub_links = extract_unsub_links(email_content)
                if not unsub_links:
                    logger.debug(f"No unsubscribe links found in email {msg_id}")
                    add_activity(user_id, "warning", f"No unsubscribe links found in email {i+1}/{len(messages)} from {sender_info}", metadata)
                    user_stats[user_id]["total_scanned"] += 1
                    save_stats_to_db(user_id)
                    failed_count += 1
                    continue
            except Exception as link_error:
                logger.error(f"Failed to extract links from email {msg_id}: {str(link_error)}")
                add_activity(user_id, "error", f"Failed to extract links from email {i+1}/{len(messages)} from {sender_info}", metadata)
                user_stats[user_id]["total_scanned"] += 1
                save_stats_to_db(user_id)
                failed_count += 1
                continue
            
            # Step 3: Try to unsubscribe (with error boundary)
            unsubscribed = False
            try:
                for link in unsub_links:
                    if execute_unsub(link):
                        unsubscribed = True
                        break
            except Exception as unsub_error:
                logger.error(f"Failed to execute unsubscribe for email {msg_id}: {str(unsub_error)}")
                add_activity(user_id, "error", f"Unsubscribe failed for email {i+1}/{len(messages)} from {sender_info}", metadata)
                user_stats[user_id]["total_scanned"] += 1
                save_stats_to_db(user_id)
                failed_count += 1
                continue
            
            # Step 4: Update stats and labels
            try:
                user_stats[user_id]["total_scanned"] += 1
                save_stats_to_db(user_id)
                logger.debug(f"Updated total_scanned for user {user_id}")
            except Exception as stats_error:
                logger.error(f"Error updating stats for user {user_id}: {str(stats_error)}")
                raise
            
            if unsubscribed:
                try:
                    user_stats[user_id]["total_unsubscribed"] += 1
                    user_stats[user_id]["time_saved"] += 2  # Assume 2 minutes saved per unsubscription
                    
                    # Track domain statistics
                    domain = metadata.get("domain", "unknown")
                    if domain:
                        if domain not in user_stats[user_id]["domains_unsubscribed"]:
                            user_stats[user_id]["domains_unsubscribed"][domain] = {
                                "count": 0,
                                "sender_name": metadata.get("sender_name", domain),
                                "emails": set()
                            }
                        user_stats[user_id]["domains_unsubscribed"][domain]["count"] += 1
                        if metadata.get("sender_email"):
                            user_stats[user_id]["domains_unsubscribed"][domain]["emails"].add(metadata.get("sender_email"))
                    
                    logger.debug(f"Updated unsubscribe stats for user {user_id}")
                    
                    # Save updated stats to database
                    save_stats_to_db(user_id)
                    
                except Exception as unsub_stats_error:
                    logger.error(f"Error updating unsubscribe stats for user {user_id}: {str(unsub_stats_error)}")
                    raise
                
                # Step 5: Add label to email (with error boundary)
                if unsubscribed_label_id:
                    try:
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['INBOX'], 'addLabelIds': [unsubscribed_label_id]}
                        ).execute()
                        logger.info(f"Successfully labeled email {msg_id} as UNSUBSCRIBED")
                    except Exception as label_error:
                        logger.warning(f"Failed to label email {msg_id}: {str(label_error)}")
                        # Continue processing even if labeling fails
                
                add_activity(user_id, "success", f"Successfully unsubscribed from {sender_info} ({metadata.get('sender_email', '')})", metadata)
                successful_count += 1
            else:
                add_activity(user_id, "error", f"Failed to unsubscribe from {sender_info} ({metadata.get('sender_email', '')})", metadata)
                failed_count += 1
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            # This is a catch-all for any unexpected errors
            error_msg = f"Unexpected error processing email {msg_id}"
            error_type = type(e).__name__
            error_details = str(e)
            
            logger.error(f"{error_msg}: {error_type} - {error_details}")
            
            # Add additional debug info for KeyError
            if isinstance(e, KeyError):
                logger.error(f"KeyError details:")
                logger.error(f"  - user_id: {user_id}")
                logger.error(f"  - user_stats keys: {list(user_stats.keys())}")
                logger.error(f"  - user_id in user_stats: {user_id in user_stats}")
                logger.error(f"  - Exception args: {e.args}")
                import traceback
                logger.error(f"  - Traceback: {traceback.format_exc()}")
            
            # Try to get metadata if available
            metadata_info = email_data.get("metadata", {}) if 'email_data' in locals() else {}
            sender_desc = metadata_info.get("sender_name", "") if metadata_info else ""
            if sender_desc:
                add_activity(user_id, "error", f"Unexpected error for email {i+1}/{len(messages)} from {sender_desc}: {error_type}", metadata_info)
            else:
                add_activity(user_id, "error", f"Unexpected error for email {i+1}/{len(messages)}: {error_type}")
            failed_count += 1
            
            # Continue processing other emails
            continue
    
    # Final summary
    total_processed = successful_count + failed_count
    add_activity(user_id, "success", f"Process completed. Processed {total_processed} emails: {successful_count} successful, {failed_count} failed.")

def search_emails(service, query, max_results=50):
    """Search Gmail for emails matching the query."""
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])
    return messages

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
        pattern = re.compile(r'unsubscribe|opt[-\s]?out|email preferences', re.I)
        
        for link in soup.find_all('a', href=True):
            try:
                link_text = link.text or ""
                link_href = link.get('href', '')
                
                if link_href and (pattern.search(link_text) or pattern.search(link_href)):
                    links.append(link_href)
            except Exception as link_error:
                logger.warning(f"Error processing individual link: {str(link_error)}")
                continue
        
        return links
        
    except Exception as e:
        logger.error(f"Error extracting unsubscribe links: {type(e).__name__} - {str(e)}")
        return []

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
    import signal
    import atexit
    
    def cleanup():
        """Save all data to database on shutdown."""
        try:
            logger.info("Saving all data to database on shutdown...")
            save_all_data_to_db()
            logger.info("Data saved successfully on shutdown")
        except Exception as e:
            logger.error(f"Error saving data on shutdown: {e}")
    
    def signal_handler(signum, _):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        cleanup()
        exit(0)
    
    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the Flask app
    debug_mode = os.environ.get('ENVIRONMENT') == 'development'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
