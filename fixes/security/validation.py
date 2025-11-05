"""
Request Validation Schemas
Validates and sanitizes all API inputs using Marshmallow
"""

from marshmallow import Schema, fields, validates, validates_schema, ValidationError, EXCLUDE
import re
from typing import Dict, Any


class EmailSearchSchema(Schema):
    """Schema for email search parameters"""

    search_query = fields.String(
        required=True,
        validate=lambda x: len(x) > 0 and len(x) <= 500,
        error_messages={
            "required": "Search query is required",
            "validator_failed": "Search query must be between 1 and 500 characters"
        }
    )

    max_emails = fields.Integer(
        required=True,
        validate=lambda x: 1 <= x <= 200,
        error_messages={
            "required": "max_emails is required",
            "validator_failed": "max_emails must be between 1 and 200"
        }
    )

    @validates('search_query')
    def validate_search_query(self, value):
        """Validate search query for safety"""
        # Prevent injection attempts
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'onerror=',
            r'onclick=',
            r'\x00',  # Null byte
        ]

        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(f"Search query contains forbidden pattern: {pattern}")

        return value

    class Meta:
        unknown = EXCLUDE  # Ignore unknown fields


class PreviewRequestSchema(EmailSearchSchema):
    """Schema for preview request (extends EmailSearchSchema)"""
    pass


class ApplyActionsSchema(Schema):
    """Schema for applying unsubscribe actions"""

    items = fields.List(
        fields.Dict(),
        required=True,
        validate=lambda x: len(x) > 0 and len(x) <= 200,
        error_messages={
            "required": "items list is required",
            "validator_failed": "items must contain between 1 and 200 entries"
        }
    )

    create_auto_archive_filter = fields.Boolean(
        missing=False
    )

    @validates('items')
    def validate_items(self, value):
        """Validate items structure"""
        for idx, item in enumerate(value):
            if 'id' not in item:
                raise ValidationError(f"Item {idx}: 'id' field is required")
            if 'action' not in item:
                raise ValidationError(f"Item {idx}: 'action' field is required")

            # Validate action type
            valid_actions = ['one_click_unsub', 'label_archive']
            if item['action'] not in valid_actions:
                raise ValidationError(f"Item {idx}: action must be one of {valid_actions}")

            # Validate message ID format (Gmail message IDs are typically hex strings)
            msg_id = item['id']
            if not isinstance(msg_id, str) or len(msg_id) < 10 or len(msg_id) > 100:
                raise ValidationError(f"Item {idx}: invalid message ID format")

        return value

    class Meta:
        unknown = EXCLUDE


class UndoOperationSchema(Schema):
    """Schema for undo operation request"""

    operation_id = fields.String(
        required=True,
        validate=lambda x: len(x) == 36,  # UUID v4 format
        error_messages={
            "required": "operation_id is required",
            "validator_failed": "operation_id must be a valid UUID"
        }
    )

    @validates('operation_id')
    def validate_operation_id(self, value):
        """Validate UUID format"""
        # UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, value, re.IGNORECASE):
            raise ValidationError("Invalid UUID format")
        return value

    class Meta:
        unknown = EXCLUDE


class ChatMessageSchema(Schema):
    """Schema for chat messages"""

    message = fields.String(
        required=True,
        validate=lambda x: len(x) > 0 and len(x) <= 5000,
        error_messages={
            "required": "message is required",
            "validator_failed": "message must be between 1 and 5000 characters"
        }
    )

    history = fields.List(
        fields.Dict(),
        missing=list,
        validate=lambda x: len(x) <= 50,
        error_messages={
            "validator_failed": "history can contain at most 50 messages"
        }
    )

    gmail_context = fields.Dict(
        missing=dict
    )

    user_context = fields.Dict(
        missing=dict
    )

    @validates('message')
    def validate_message(self, value):
        """Validate message content"""
        # Prevent prompt injection attempts
        suspicious_patterns = [
            r'ignore previous instructions',
            r'disregard',
            r'system:',
            r'<system>',
            r'pretend you are',
        ]

        value_lower = value.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError("Message contains potentially malicious content")

        return value

    @validates('history')
    def validate_history(self, value):
        """Validate history structure"""
        for idx, msg in enumerate(value):
            if 'role' not in msg or 'content' not in msg:
                raise ValidationError(f"History item {idx}: must contain 'role' and 'content' fields")

            if msg['role'] not in ['user', 'assistant']:
                raise ValidationError(f"History item {idx}: role must be 'user' or 'assistant'")

        return value

    class Meta:
        unknown = EXCLUDE


class PaginationSchema(Schema):
    """Schema for pagination parameters"""

    page = fields.Integer(
        missing=1,
        validate=lambda x: x >= 1,
        error_messages={
            "validator_failed": "page must be >= 1"
        }
    )

    per_page = fields.Integer(
        missing=50,
        validate=lambda x: 1 <= x <= 100,
        error_messages={
            "validator_failed": "per_page must be between 1 and 100"
        }
    )

    class Meta:
        unknown = EXCLUDE


def validate_request(schema: Schema) -> Any:
    """Decorator to validate request data

    Args:
        schema: Marshmallow schema class

    Example:
        @app.route('/api/unsubscribe/preview', methods=['POST'])
        @validate_request(PreviewRequestSchema())
        def preview_unsubscribe_candidates():
            validated_data = g.validated_data
            ...
    """
    from functools import wraps
    from flask import request, jsonify, g

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                # Parse and validate request data
                data = request.get_json(force=True, silent=True)
                if data is None:
                    return jsonify({
                        "error": "invalid_json",
                        "message": "Request body must be valid JSON"
                    }), 400

                # Validate against schema
                validated_data = schema.load(data)

                # Store validated data in g for use in route
                g.validated_data = validated_data

                return f(*args, **kwargs)

            except ValidationError as e:
                return jsonify({
                    "error": "validation_error",
                    "message": "Request validation failed",
                    "details": e.messages
                }), 400
            except Exception as e:
                return jsonify({
                    "error": "invalid_request",
                    "message": str(e)
                }), 400

        return wrapped
    return decorator


def sanitize_html(text: str) -> str:
    """Sanitize HTML to prevent XSS

    Args:
        text: Raw HTML text

    Returns:
        Sanitized text with dangerous tags removed
    """
    import html

    # Escape HTML entities
    sanitized = html.escape(text)

    # Remove any remaining script tags (defense in depth)
    sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)

    return sanitized


def sanitize_email(email: str) -> str:
    """Validate and sanitize email address

    Args:
        email: Email address

    Returns:
        Sanitized email address

    Raises:
        ValidationError: If email is invalid
    """
    # Simple email validation (not RFC 5322 compliant, but good enough)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email address format")

    # Prevent email header injection
    if '\n' in email or '\r' in email:
        raise ValidationError("Email address contains invalid characters")

    return email.strip().lower()


def sanitize_url(url: str, allowed_schemes: list = None) -> str:
    """Validate and sanitize URL

    Args:
        url: URL to sanitize
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])

    Returns:
        Sanitized URL

    Raises:
        ValidationError: If URL is invalid
    """
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        # Validate scheme
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"URL scheme must be one of {allowed_schemes}")

        # Prevent javascript: and data: schemes
        if parsed.scheme in ['javascript', 'data', 'file']:
            raise ValidationError("URL scheme not allowed")

        # Prevent SSRF to localhost
        if parsed.hostname in ['localhost', '127.0.0.1', '::1', '0.0.0.0']:
            raise ValidationError("URL cannot point to localhost")

        # Prevent SSRF to private IP ranges
        if parsed.hostname:
            # This is a basic check; use ipaddress module for comprehensive validation
            if parsed.hostname.startswith('10.') or parsed.hostname.startswith('192.168.') or parsed.hostname.startswith('172.'):
                raise ValidationError("URL cannot point to private IP address")

        return url

    except Exception as e:
        raise ValidationError(f"Invalid URL: {str(e)}")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path separators
    sanitized = filename.replace('/', '').replace('\\', '').replace('..', '')

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    # Keep only alphanumeric, dash, underscore, and dot
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', sanitized)

    # Limit length
    sanitized = sanitized[:255]

    if not sanitized or sanitized == '.':
        raise ValidationError("Invalid filename")

    return sanitized


# Export schemas for easy importing
__all__ = [
    'EmailSearchSchema',
    'PreviewRequestSchema',
    'ApplyActionsSchema',
    'UndoOperationSchema',
    'ChatMessageSchema',
    'PaginationSchema',
    'validate_request',
    'sanitize_html',
    'sanitize_email',
    'sanitize_url',
    'sanitize_filename',
]
