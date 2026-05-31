"""
Comprehensive tests for secret redaction in diagnostics.

Tests redaction of sensitive keys and values in logs and diagnostics.
"""

from swirrl.core.diagnostics import (
    SECRET_KEY_PARTS,
    SECRET_VALUE_PATTERNS,
    _is_sensitive_key,
    _is_sensitive_value,
    redact,
)


class TestSensitiveKeyDetection:
    """Test detection of sensitive key names."""

    def test_detect_api_key(self):
        """Test detection of api_key."""
        assert _is_sensitive_key("api_key") is True
        assert _is_sensitive_key("API_KEY") is True
        assert _is_sensitive_key("my_api_key") is True

    def test_detect_password(self):
        """Test detection of password."""
        assert _is_sensitive_key("password") is True
        assert _is_sensitive_key("user_password") is True
        assert _is_sensitive_key("PASSWORD") is True

    def test_detect_token(self):
        """Test detection of token."""
        assert _is_sensitive_key("token") is True
        assert _is_sensitive_key("access_token") is True
        assert _is_sensitive_key("refresh_token") is True
        assert _is_sensitive_key("bearer_token") is True

    def test_detect_secret(self):
        """Test detection of secret."""
        assert _is_sensitive_key("secret") is True
        assert _is_sensitive_key("client_secret") is True
        assert _is_sensitive_key("SECRET_KEY") is True

    def test_detect_private_key(self):
        """Test detection of private_key."""
        assert _is_sensitive_key("private_key") is True
        assert _is_sensitive_key("PRIVATE_KEY") is True

    def test_detect_session(self):
        """Test detection of session."""
        assert _is_sensitive_key("session") is True
        assert _is_sensitive_key("session_id") is True
        assert _is_sensitive_key("SESSION_TOKEN") is True

    def test_detect_cookie(self):
        """Test detection of cookie."""
        assert _is_sensitive_key("cookie") is True
        assert _is_sensitive_key("auth_cookie") is True

    def test_detect_jwt(self):
        """Test detection of jwt."""
        assert _is_sensitive_key("jwt") is True
        assert _is_sensitive_key("jwt_token") is True

    def test_detect_csrf(self):
        """Test detection of csrf."""
        assert _is_sensitive_key("csrf") is True
        assert _is_sensitive_key("csrf_token") is True

    def test_non_sensitive_keys(self):
        """Test that non-sensitive keys are not detected."""
        assert _is_sensitive_key("username") is False
        assert _is_sensitive_key("email") is False
        assert _is_sensitive_key("id") is False
        assert _is_sensitive_key("name") is False


class TestSensitiveValueDetection:
    """Test detection of sensitive values."""

    def test_detect_bearer_token(self):
        """Test detection of Bearer tokens."""
        assert _is_sensitive_value("Bearer abc123def456") is True
        assert _is_sensitive_value("bearer xyz789") is True

    def test_detect_basic_auth(self):
        """Test detection of Basic auth."""
        assert _is_sensitive_value("Basic YWxhZGRpbjpvcGVuc2VzYW1l") is True
        assert _is_sensitive_value("basic dXNlcjpwYXNz") is True

    def test_detect_jwt_token(self):
        """Test detection of JWT tokens."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        assert _is_sensitive_value(jwt) is True

    def test_detect_aws_key(self):
        """Test detection of AWS access keys."""
        assert _is_sensitive_value("AKIAIOSFODNN7EXAMPLE") is True

    def test_detect_password_in_string(self):
        """Test detection of password= patterns."""
        assert _is_sensitive_value("password=secret123") is True
        assert _is_sensitive_value("PASSWORD: mypass") is True

    def test_short_strings_not_sensitive(self):
        """Test that short strings are not flagged."""
        assert _is_sensitive_value("short") is False
        assert _is_sensitive_value("abc") is False
        assert _is_sensitive_value("1234567") is False

    def test_non_string_values_not_sensitive(self):
        """Test that non-string values return False."""
        assert _is_sensitive_value(123) is False
        assert _is_sensitive_value(None) is False
        assert _is_sensitive_value([]) is False


class TestRedactDictionaries:
    """Test redacting dictionaries."""

    def test_redact_simple_dict(self):
        """Test redacting simple dictionary."""
        data = {
            "username": "alice",
            "password": "secret123",
        }

        redacted = redact(data)

        assert redacted["username"] == "alice"
        assert redacted["password"] == "********"

    def test_redact_nested_dict(self):
        """Test redacting nested dictionary."""
        data = {
            "user": {
                "name": "alice",
                "credentials": {
                    "api_key": "secret_key_123",
                    "token": "bearer_token_456",
                },
            }
        }

        redacted = redact(data)

        assert redacted["user"]["name"] == "alice"
        assert redacted["user"]["credentials"]["api_key"] == "********"
        assert redacted["user"]["credentials"]["token"] == "********"

    def test_redact_multiple_sensitive_keys(self):
        """Test redacting multiple sensitive keys."""
        data = {
            "api_key": "key1",
            "access_token": "token1",
            "password": "pass1",
            "secret": "secret1",
            "username": "user1",
        }

        redacted = redact(data)

        assert redacted["api_key"] == "********"
        assert redacted["access_token"] == "********"
        assert redacted["password"] == "********"
        assert redacted["secret"] == "********"
        assert redacted["username"] == "user1"


class TestRedactLists:
    """Test redacting lists."""

    def test_redact_list_of_dicts(self):
        """Test redacting list of dictionaries."""
        data = [
            {"name": "alice", "password": "pass1"},
            {"name": "bob", "api_key": "key1"},
        ]

        redacted = redact(data)

        assert redacted[0]["name"] == "alice"
        assert redacted[0]["password"] == "********"
        assert redacted[1]["name"] == "bob"
        assert redacted[1]["api_key"] == "********"

    def test_redact_nested_lists(self):
        """Test redacting nested lists."""
        data = {
            "users": [
                {"name": "alice", "token": "token1"},
                {"name": "bob", "secret": "secret1"},
            ]
        }

        redacted = redact(data)

        assert redacted["users"][0]["token"] == "********"
        assert redacted["users"][1]["secret"] == "********"


class TestRedactTuples:
    """Test redacting tuples."""

    def test_redact_tuple(self):
        """Test redacting tuple."""
        data = (
            {"password": "secret"},
            {"api_key": "key123"},
        )

        redacted = redact(data)

        assert isinstance(redacted, tuple)
        assert redacted[0]["password"] == "********"
        assert redacted[1]["api_key"] == "********"


class TestRedactValues:
    """Test redacting sensitive values (not just keys)."""

    def test_redact_values_disabled_by_default(self):
        """Test that value redaction is disabled by default."""
        data = {
            "data": "Bearer abc123def456ghi789",
        }

        redacted = redact(data, redact_values=False)

        # Value should not be redacted (key is not sensitive)
        assert "Bearer" in redacted["data"]

    def test_redact_values_when_enabled(self):
        """Test that value redaction works when enabled."""
        data = {
            "data": "Bearer abc123def456ghi789",
        }

        redacted = redact(data, redact_values=True)

        # Value should be redacted
        assert redacted["data"] == "********"

    def test_redact_jwt_value(self):
        """Test redacting JWT token value."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        data = {"token_data": jwt}

        redacted = redact(data, redact_values=True)

        assert redacted["token_data"] == "********"


class TestRedactPaths:
    """Test redacting Path objects."""

    def test_redact_path_object(self):
        """Test that Path objects are converted to strings."""
        from pathlib import Path

        data = {
            "file_path": Path("/home/user/file.txt"),
            "password": "secret",
        }

        redacted = redact(data)

        assert isinstance(redacted["file_path"], str)
        assert redacted["password"] == "********"


class TestRedactComplexStructures:
    """Test redacting complex nested structures."""

    def test_redact_deeply_nested_structure(self):
        """Test redacting deeply nested structure."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "api_key": "secret_key",
                            "data": "public_data",
                        }
                    }
                }
            }
        }

        redacted = redact(data)

        assert redacted["level1"]["level2"]["level3"]["level4"]["api_key"] == "********"
        assert redacted["level1"]["level2"]["level3"]["level4"]["data"] == "public_data"

    def test_redact_mixed_structure(self):
        """Test redacting mixed structure with dicts, lists, and tuples."""
        data = {
            "users": [
                {
                    "name": "alice",
                    "credentials": ("password", "secret123"),
                    "tokens": ["token1", "token2"],
                },
            ],
            "config": {
                "api_key": "key123",
                "settings": ["setting1", "setting2"],
            },
        }

        redacted = redact(data)

        assert redacted["users"][0]["name"] == "alice"
        assert redacted["config"]["api_key"] == "********"


class TestSecretKeyParts:
    """Test SECRET_KEY_PARTS constant."""

    def test_secret_key_parts_includes_common_patterns(self):
        """Test that SECRET_KEY_PARTS includes common sensitive patterns."""
        assert "api_key" in SECRET_KEY_PARTS
        assert "password" in SECRET_KEY_PARTS
        assert "token" in SECRET_KEY_PARTS
        assert "secret" in SECRET_KEY_PARTS
        assert "private_key" in SECRET_KEY_PARTS
        assert "session" in SECRET_KEY_PARTS
        assert "cookie" in SECRET_KEY_PARTS
        assert "jwt" in SECRET_KEY_PARTS
        assert "refresh_token" in SECRET_KEY_PARTS
        assert "csrf" in SECRET_KEY_PARTS


class TestSecretValuePatterns:
    """Test SECRET_VALUE_PATTERNS constant."""

    def test_secret_value_patterns_is_list(self):
        """Test that SECRET_VALUE_PATTERNS is a list."""
        assert isinstance(SECRET_VALUE_PATTERNS, list)
        assert len(SECRET_VALUE_PATTERNS) > 0

    def test_patterns_are_compiled_regex(self):
        """Test that patterns are compiled regex objects."""
        import re

        for pattern in SECRET_VALUE_PATTERNS:
            assert isinstance(pattern, re.Pattern)


class TestRedactionEdgeCases:
    """Test edge cases in redaction."""

    def test_redact_empty_dict(self):
        """Test redacting empty dictionary."""
        data = {}
        redacted = redact(data)
        assert redacted == {}

    def test_redact_empty_list(self):
        """Test redacting empty list."""
        data = []
        redacted = redact(data)
        assert redacted == []

    def test_redact_none_value(self):
        """Test redacting None value."""
        data = {"key": None}
        redacted = redact(data)
        assert redacted["key"] is None

    def test_redact_numeric_values(self):
        """Test that numeric values are preserved."""
        data = {
            "count": 42,
            "price": 19.99,
            "api_key": "secret",
        }

        redacted = redact(data)

        assert redacted["count"] == 42
        assert redacted["price"] == 19.99
        assert redacted["api_key"] == "********"

    def test_redact_boolean_values(self):
        """Test that boolean values are preserved."""
        data = {
            "enabled": True,
            "disabled": False,
            "password": "secret",
        }

        redacted = redact(data)

        assert redacted["enabled"] is True
        assert redacted["disabled"] is False
        assert redacted["password"] == "********"
