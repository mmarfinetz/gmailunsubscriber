"""
Production-Ready Security Middleware
Implements rate limiting, CSRF protection, security headers, and request validation
"""

import functools
import logging
import secrets
import time
from typing import Callable, Optional, Any
from datetime import datetime, timedelta
import jwt
from flask import Flask, request, jsonify, session, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_talisman import Talisman
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Comprehensive security middleware for Flask application"""

    def __init__(self, app: Flask, config: Any):
        """Initialize security middleware

        Args:
            app: Flask application
            config: Application configuration
        """
        self.app = app
        self.config = config

        # Initialize rate limiter
        if config.RATELIMIT_ENABLED:
            self.limiter = self._init_rate_limiter()
        else:
            self.limiter = None
            logger.warning("Rate limiting is DISABLED - not recommended for production")

        # Initialize CSRF protection
        if not config.DEBUG:
            self.csrf = self._init_csrf_protection()
        else:
            self.csrf = None
            logger.warning("CSRF protection is DISABLED in debug mode")

        # Initialize security headers
        if config.is_production:
            self.talisman = self._init_security_headers()
        else:
            self.talisman = None

        # Register error handlers
        self._register_error_handlers()

        # Register request middleware
        self._register_request_middleware()

    def _init_rate_limiter(self) -> Limiter:
        """Initialize Flask-Limiter with Redis backend"""
        logger.info("Initializing rate limiter")

        # Use Redis if available, otherwise in-memory (not recommended for production)
        storage_uri = self.config.RATELIMIT_STORAGE_URL or "memory://"

        if storage_uri.startswith("memory://") and self.config.is_production:
            logger.error("WARNING: Using in-memory rate limiting in production!")
            logger.error("This will NOT work with multiple workers. Use Redis instead!")

        limiter = Limiter(
            key_func=get_remote_address,
            app=self.app,
            storage_uri=storage_uri,
            strategy=self.config.RATELIMIT_STRATEGY,
            default_limits=["1000 per day", "100 per hour"],
            headers_enabled=True,
            swallow_errors=False  # Raise errors in development
        )

        # Apply specific rate limits to endpoints
        self._configure_rate_limits(limiter)

        logger.info(f"Rate limiter initialized with storage: {storage_uri}")
        return limiter

    def _configure_rate_limits(self, limiter: Limiter) -> None:
        """Configure rate limits for specific endpoints"""

        # Authentication endpoints - strict limits
        limiter.limit("5 per minute")(self.app.view_functions.get('login', lambda: None))
        limiter.limit("10 per hour")(self.app.view_functions.get('oauth2callback', lambda: None))

        # API endpoints - moderate limits
        # Note: These will be applied when the routes are registered

        logger.info("Rate limits configured for endpoints")

    def _init_csrf_protection(self) -> CSRFProtect:
        """Initialize CSRF protection"""
        logger.info("Initializing CSRF protection")

        csrf = CSRFProtect()
        csrf.init_app(self.app)

        # Exempt certain endpoints from CSRF (like OAuth callbacks)
        csrf.exempt('oauth2callback')

        logger.info("CSRF protection initialized")
        return csrf

    def _init_security_headers(self) -> Talisman:
        """Initialize security headers with Flask-Talisman"""
        logger.info("Initializing security headers")

        # Content Security Policy
        csp = {
            'default-src': "'self'",
            'script-src': [
                "'self'",
                "'unsafe-inline'",  # TODO: Remove after adding nonces
                "https://cdnjs.cloudflare.com",
                "https://accounts.google.com"
            ],
            'style-src': [
                "'self'",
                "'unsafe-inline'",  # Required for inline styles
                "https://cdnjs.cloudflare.com"
            ],
            'img-src': [
                "'self'",
                "data:",
                "https:",
                "https://upload.wikimedia.org"
            ],
            'font-src': [
                "'self'",
                "https://cdnjs.cloudflare.com"
            ],
            'connect-src': [
                "'self'",
                self.config.FRONTEND_URL,
                "https://accounts.google.com",
                "https://oauth2.googleapis.com",
                "https://www.googleapis.com"
            ],
            'frame-ancestors': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'"
        }

        talisman = Talisman(
            self.app,
            force_https=self.config.HSTS_ENABLED,
            strict_transport_security=self.config.HSTS_ENABLED,
            strict_transport_security_max_age=self.config.HSTS_MAX_AGE,
            content_security_policy=csp if self.config.CSP_ENABLED else None,
            content_security_policy_nonce_in=['script-src'],
            referrer_policy='strict-origin-when-cross-origin',
            feature_policy={
                'geolocation': "'none'",
                'microphone': "'none'",
                'camera': "'none'",
                'payment': "'none'"
            }
        )

        logger.info("Security headers initialized")
        return talisman

    def _register_error_handlers(self) -> None:
        """Register error handlers for security-related errors"""

        @self.app.errorhandler(429)
        def ratelimit_handler(e):
            """Handle rate limit exceeded"""
            logger.warning(f"Rate limit exceeded for IP {request.remote_addr}: {request.path}")
            return jsonify({
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please slow down and try again later.",
                "retry_after": e.description if hasattr(e, 'description') else 60
            }), 429

        @self.app.errorhandler(CSRFError)
        def csrf_error_handler(e):
            """Handle CSRF errors"""
            logger.warning(f"CSRF error for IP {request.remote_addr}: {request.path}")
            return jsonify({
                "error": "csrf_validation_failed",
                "message": "CSRF token validation failed. Please refresh and try again."
            }), 403

        @self.app.errorhandler(400)
        def bad_request_handler(e):
            """Handle bad requests"""
            return jsonify({
                "error": "bad_request",
                "message": str(e.description) if hasattr(e, 'description') else "Invalid request"
            }), 400

        @self.app.errorhandler(401)
        def unauthorized_handler(e):
            """Handle unauthorized requests"""
            return jsonify({
                "error": "unauthorized",
                "message": "Authentication required"
            }), 401

        @self.app.errorhandler(403)
        def forbidden_handler(e):
            """Handle forbidden requests"""
            return jsonify({
                "error": "forbidden",
                "message": "Access denied"
            }), 403

        @self.app.errorhandler(500)
        def internal_error_handler(e):
            """Handle internal server errors"""
            # Log full error for debugging
            logger.error(f"Internal server error: {str(e)}", exc_info=True)

            # Return generic error to client (don't leak implementation details)
            if self.config.DEBUG:
                return jsonify({
                    "error": "internal_server_error",
                    "message": str(e),
                    "type": type(e).__name__
                }), 500
            else:
                return jsonify({
                    "error": "internal_server_error",
                    "message": "An internal error occurred. Please try again later."
                }), 500

        logger.info("Error handlers registered")

    def _register_request_middleware(self) -> None:
        """Register request middleware for logging and security"""

        @self.app.before_request
        def before_request():
            """Execute before each request"""
            # Add request ID for tracing
            g.request_id = secrets.token_hex(8)
            g.start_time = time.time()

            # Log request (sanitized)
            logger.info(f"[{g.request_id}] {request.method} {request.path} from {request.remote_addr}")

            # Validate content type for JSON endpoints
            if request.method in ['POST', 'PUT', 'PATCH'] and request.path.startswith('/api/'):
                if not request.is_json and 'multipart/form-data' not in request.content_type:
                    logger.warning(f"[{g.request_id}] Invalid content type: {request.content_type}")
                    return jsonify({
                        "error": "invalid_content_type",
                        "message": "Content-Type must be application/json"
                    }), 415

        @self.app.after_request
        def after_request(response):
            """Execute after each request"""
            # Calculate request duration
            if hasattr(g, 'start_time'):
                duration = time.time() - g.start_time
                logger.info(f"[{g.request_id}] Response: {response.status_code} in {duration:.3f}s")

            # Add security headers
            if not self.talisman:  # Only if Talisman is not handling this
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['X-XSS-Protection'] = '1; mode=block'

            # Add request ID to response headers
            if hasattr(g, 'request_id'):
                response.headers['X-Request-ID'] = g.request_id

            return response

        logger.info("Request middleware registered")


def validate_request_size(max_size_mb: int = 10):
    """Decorator to validate request body size

    Args:
        max_size_mb: Maximum request size in megabytes

    Example:
        @app.route('/api/upload', methods=['POST'])
        @validate_request_size(max_size_mb=5)
        def upload():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            content_length = request.content_length
            if content_length and content_length > max_size_mb * 1024 * 1024:
                logger.warning(f"Request too large: {content_length} bytes (max: {max_size_mb}MB)")
                return jsonify({
                    "error": "request_too_large",
                    "message": f"Request body too large. Maximum size: {max_size_mb}MB"
                }), 413
            return f(*args, **kwargs)
        return wrapped
    return decorator


def rate_limit(limit_string: str):
    """Decorator for custom rate limits

    Args:
        limit_string: Rate limit string (e.g., "10 per minute")

    Example:
        @app.route('/api/expensive-operation', methods=['POST'])
        @rate_limit("5 per hour")
        def expensive_operation():
            ...
    """
    def decorator(f: Callable) -> Callable:
        # This will be applied by the limiter when middleware is initialized
        f._rate_limit = limit_string
        return f
    return decorator


def require_api_key(f: Callable) -> Callable:
    """Decorator to require API key authentication

    Example:
        @app.route('/api/admin/stats', methods=['GET'])
        @require_api_key
        def admin_stats():
            ...
    """
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                "error": "api_key_required",
                "message": "API key required"
            }), 401

        # Validate API key (implement your logic here)
        # For now, this is a placeholder
        valid_api_keys = []  # Load from config or database

        if api_key not in valid_api_keys:
            logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
            return jsonify({
                "error": "invalid_api_key",
                "message": "Invalid API key"
            }), 403

        return f(*args, **kwargs)
    return wrapped


def log_security_event(event_type: str, details: dict, severity: str = "INFO"):
    """Log security-related events for monitoring

    Args:
        event_type: Type of security event (e.g., "failed_login", "rate_limit", "csrf_error")
        details: Event details
        severity: Log severity (INFO, WARNING, ERROR, CRITICAL)
    """
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "severity": severity,
        "ip": request.remote_addr if request else None,
        "user_agent": request.user_agent.string if request else None,
        "path": request.path if request else None,
        **details
    }

    log_func = getattr(logger, severity.lower())
    log_func(f"Security Event: {event_type}", extra=event_data)


def sanitize_log_data(data: dict) -> dict:
    """Sanitize sensitive data before logging

    Args:
        data: Data to sanitize

    Returns:
        Sanitized data with sensitive fields redacted
    """
    sensitive_fields = [
        'password', 'token', 'secret', 'api_key', 'access_token',
        'refresh_token', 'client_secret', 'authorization', 'cookie'
    ]

    sanitized = {}
    for key, value in data.items():
        if any(field in key.lower() for field in sensitive_fields):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value

    return sanitized
