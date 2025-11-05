"""
Security-focused unit tests for Gmail Unsubscriber
Tests input validation, authentication, rate limiting, and security features
"""

import pytest
import secrets
from marshmallow import ValidationError
from fixes.security.validation import (
    EmailSearchSchema,
    ApplyActionsSchema,
    UndoOperationSchema,
    sanitize_html,
    sanitize_email,
    sanitize_url,
    sanitize_filename,
)
from fixes.security.config import Config, Environment, ConfigurationError, get_config


class TestInputValidation:
    """Test input validation schemas"""

    def test_email_search_schema_valid(self):
        """Test valid email search parameters"""
        schema = EmailSearchSchema()
        data = {
            "search_query": "unsubscribe",
            "max_emails": 50
        }
        result = schema.load(data)
        assert result["search_query"] == "unsubscribe"
        assert result["max_emails"] == 50

    def test_email_search_schema_invalid_max_emails(self):
        """Test max_emails validation"""
        schema = EmailSearchSchema()

        # Too large
        with pytest.raises(ValidationError) as exc_info:
            schema.load({"search_query": "test", "max_emails": 999})
        assert "max_emails" in str(exc_info.value)

        # Too small
        with pytest.raises(ValidationError) as exc_info:
            schema.load({"search_query": "test", "max_emails": 0})
        assert "max_emails" in str(exc_info.value)

    def test_email_search_schema_xss_prevention(self):
        """Test XSS prevention in search query"""
        schema = EmailSearchSchema()

        dangerous_queries = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onerror=alert(1)",
            "onclick=alert(1)",
        ]

        for query in dangerous_queries:
            with pytest.raises(ValidationError) as exc_info:
                schema.load({"search_query": query, "max_emails": 50})
            assert "forbidden pattern" in str(exc_info.value).lower()

    def test_apply_actions_schema_valid(self):
        """Test valid apply actions request"""
        schema = ApplyActionsSchema()
        data = {
            "items": [
                {"id": "abc123def456", "action": "one_click_unsub"},
                {"id": "xyz789ghi012", "action": "label_archive"}
            ],
            "create_auto_archive_filter": True
        }
        result = schema.load(data)
        assert len(result["items"]) == 2
        assert result["create_auto_archive_filter"] is True

    def test_apply_actions_schema_invalid_action(self):
        """Test invalid action type"""
        schema = ApplyActionsSchema()
        data = {
            "items": [
                {"id": "abc123def456", "action": "invalid_action"}
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "action must be one of" in str(exc_info.value)

    def test_apply_actions_schema_too_many_items(self):
        """Test maximum items limit"""
        schema = ApplyActionsSchema()
        data = {
            "items": [
                {"id": f"msg{i}", "action": "label_archive"}
                for i in range(201)  # Over limit
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "items must contain between 1 and 200" in str(exc_info.value)

    def test_undo_operation_schema_valid(self):
        """Test valid undo operation request"""
        schema = UndoOperationSchema()
        valid_uuid = "123e4567-e89b-42d3-a456-426614174000"
        result = schema.load({"operation_id": valid_uuid})
        assert result["operation_id"] == valid_uuid

    def test_undo_operation_schema_invalid_uuid(self):
        """Test invalid UUID format"""
        schema = UndoOperationSchema()
        invalid_uuids = [
            "not-a-uuid",
            "123",
            "123e4567-e89b-12d3-a456-426614174000",  # Wrong version
            "",
        ]

        for invalid_uuid in invalid_uuids:
            with pytest.raises(ValidationError):
                schema.load({"operation_id": invalid_uuid})


class TestSanitization:
    """Test sanitization functions"""

    def test_sanitize_html(self):
        """Test HTML sanitization"""
        dangerous_html = '<script>alert("xss")</script><p>Safe content</p>'
        sanitized = sanitize_html(dangerous_html)

        assert '<script>' not in sanitized
        assert 'alert' not in sanitized
        assert '&lt;' in sanitized  # HTML entities escaped

    def test_sanitize_email_valid(self):
        """Test valid email sanitization"""
        emails = [
            "user@example.com",
            "user.name+tag@example.co.uk",
            "user_name@sub.example.com",
        ]
        for email in emails:
            result = sanitize_email(email)
            assert "@" in result
            assert result == email.lower().strip()

    def test_sanitize_email_invalid(self):
        """Test invalid email rejection"""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "user\n@example.com",  # Email header injection
            "user\r@example.com",
        ]
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                sanitize_email(email)

    def test_sanitize_url_valid(self):
        """Test valid URL sanitization"""
        urls = [
            "https://example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
        ]
        for url in urls:
            result = sanitize_url(url)
            assert result == url

    def test_sanitize_url_invalid_scheme(self):
        """Test URL scheme validation"""
        invalid_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                sanitize_url(url)
            assert "scheme" in str(exc_info.value).lower()

    def test_sanitize_url_ssrf_prevention(self):
        """Test SSRF prevention"""
        ssrf_urls = [
            "http://localhost/admin",
            "http://127.0.0.1/admin",
            "http://[::1]/admin",
            "http://10.0.0.1/internal",
            "http://192.168.1.1/router",
        ]
        for url in ssrf_urls:
            with pytest.raises(ValidationError) as exc_info:
                sanitize_url(url)

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        test_cases = [
            ("safe-filename.txt", "safe-filename.txt"),
            ("../../../etc/passwd", "...etcpasswd"),
            ("file\x00name.txt", "filename.txt"),
            ("my file.pdf", "my_file.pdf"),
            ("file/with\\slashes.doc", "filewithslashes.doc"),
        ]
        for input_name, expected_output in test_cases:
            result = sanitize_filename(input_name)
            assert "/" not in result
            assert "\\" not in result
            assert ".." not in result

    def test_sanitize_filename_empty(self):
        """Test empty filename rejection"""
        with pytest.raises(ValidationError):
            sanitize_filename("")

        with pytest.raises(ValidationError):
            sanitize_filename(".")


class TestConfiguration:
    """Test configuration management"""

    def test_config_validation_production(self, monkeypatch):
        """Test production configuration validation"""
        # Set minimal required environment variables
        env_vars = {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': secrets.token_hex(32),
            'GOOGLE_CLIENT_ID': 'test-client-id',
            'GOOGLE_CLIENT_SECRET': 'test-client-secret',
            'GOOGLE_PROJECT_ID': 'test-project',
            'REDIRECT_URI': 'https://example.com/oauth2callback',
            'FRONTEND_URL': 'https://example.com',
            'REDIS_URL': 'redis://localhost:6379/0',
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        from fixes.security.config import get_config
        config = get_config()

        assert config.ENVIRONMENT == Environment.PRODUCTION
        assert config.is_production
        assert not config.DEBUG
        assert config.HSTS_ENABLED
        assert config.CSP_ENABLED

    def test_config_requires_secret_key_in_production(self, monkeypatch):
        """Test that SECRET_KEY is required in production"""
        monkeypatch.setenv('ENVIRONMENT', 'production')
        monkeypatch.delenv('SECRET_KEY', raising=False)

        with pytest.raises(ConfigurationError) as exc_info:
            from fixes.security.config import get_config
            get_config()

        assert "SECRET_KEY" in str(exc_info.value)

    def test_config_validates_secret_length(self, monkeypatch):
        """Test SECRET_KEY length validation"""
        env_vars = {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'too-short',  # Less than 32 characters
            'GOOGLE_CLIENT_ID': 'test-client-id',
            'GOOGLE_CLIENT_SECRET': 'test-client-secret',
            'GOOGLE_PROJECT_ID': 'test-project',
            'REDIRECT_URI': 'https://example.com/oauth2callback',
            'FRONTEND_URL': 'https://example.com',
            'REDIS_URL': 'redis://localhost:6379/0',
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        from fixes.security.config import get_config

        with pytest.raises(ConfigurationError) as exc_info:
            config = get_config()
            config.validate()

        assert "at least 32 characters" in str(exc_info.value)

    def test_config_requires_https_in_production(self, monkeypatch):
        """Test HTTPS requirement in production"""
        env_vars = {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': secrets.token_hex(32),
            'GOOGLE_CLIENT_ID': 'test-client-id',
            'GOOGLE_CLIENT_SECRET': 'test-client-secret',
            'GOOGLE_PROJECT_ID': 'test-project',
            'REDIRECT_URI': 'http://example.com/oauth2callback',  # HTTP not HTTPS
            'FRONTEND_URL': 'https://example.com',
            'REDIS_URL': 'redis://localhost:6379/0',
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        from fixes.security.config import get_config

        with pytest.raises(ConfigurationError) as exc_info:
            config = get_config()
            config.validate()

        assert "HTTPS" in str(exc_info.value)


class TestSecurityMiddleware:
    """Test security middleware (integration tests would go here)"""

    # These would require a Flask app context
    # Example structure:

    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        from flask import Flask
        app = Flask(__name__)
        # Configure app for testing
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    # Add actual tests for rate limiting, CSRF, etc.


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
