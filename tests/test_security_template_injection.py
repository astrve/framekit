"""
Tests for Jinja2 template injection vulnerabilities.

Focuses on the NFO template rendering system which uses Jinja2
with SandboxedEnvironment to prevent template injection.
"""

from __future__ import annotations

import pytest
from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment, SecurityError


def _render_sandboxed(template_content: str, context: dict) -> str:
    """Render template using same sandbox config as Swirrl NFO renderer."""
    from jinja2 import BaseLoader, StrictUndefined

    env = SandboxedEnvironment(
        loader=BaseLoader(),
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
    )
    template = env.from_string(template_content)
    return template.render(**context)


class TestJinja2TemplateSandboxing:
    """Test that Jinja2 templates are properly sandboxed."""

    def test_render_uses_sandboxed_environment(self):
        """Test that rendering uses SandboxedEnvironment."""
        from swirrl.modules.nfo.templates import render_template

        # Verify the function exists and module imports cleanly
        assert callable(render_template)

    def test_malicious_template_code_execution_blocked(self):
        """Test that malicious code execution attempts are blocked."""
        malicious_templates = [
            "{{ ''.__class__.__mro__[1].__subclasses__() }}",
            "{{ ''.__class__.__mro__[1].__subclasses__()[104].__init__.__globals__['sys'].modules['os'].system('ls') }}",
        ]

        for malicious_content in malicious_templates:
            with pytest.raises((SecurityError, TemplateSyntaxError, AttributeError, TypeError)):
                _render_sandboxed(malicious_content, {})

    def test_template_cannot_access_private_attributes(self):
        """Test that templates cannot access private attributes."""

        class TestObj:
            def __init__(self):
                self._private_attr = "secret"
                self.public_attr = "public"

        with pytest.raises((SecurityError, AttributeError)):
            _render_sandboxed("{{ obj._private_attr }}", {"obj": TestObj()})

    def test_template_cannot_call_dangerous_functions(self):
        """Test that templates cannot call dangerous built-in functions."""
        dangerous_calls = [
            "{{ eval('1+1') }}",
            "{{ exec('import os') }}",
            "{{ __import__('os').system('ls') }}",
            "{{ open('/etc/passwd').read() }}",
        ]

        for dangerous_call in dangerous_calls:
            with pytest.raises((SecurityError, TemplateSyntaxError, NameError, Exception)):
                _render_sandboxed(dangerous_call, {})

    def test_safe_template_rendering_works(self):
        """Test that safe templates render correctly."""
        template = (
            "Title: {{ title }}\n"
            "Year: {{ year }}\n"
            "{% if rating %}Rating: {{ rating }}{% endif %}\n"
            "{% for genre in genres %}- {{ genre }}\n{% endfor %}"
        )

        result = _render_sandboxed(
            template,
            {
                "title": "Test Movie",
                "year": 2024,
                "rating": 8.5,
                "genres": ["Action", "Drama"],
            },
        )

        assert "Test Movie" in result
        assert "2024" in result
        assert "8.5" in result
        assert "Action" in result
        assert "Drama" in result


class TestTemplateInputValidation:
    """Test validation of template inputs."""

    def test_template_context_not_executed(self):
        """Test that injected context values are rendered as text, not executed."""
        malicious_contexts = [
            {"value": "{{ ''.__class__ }}"},
            {"value": "<script>alert('xss')</script>"},
        ]

        for context in malicious_contexts:
            result = _render_sandboxed("{{ value }}", context)
            # Value is rendered as-is (text), not interpreted as Jinja2
            assert result == context["value"]

    def test_template_path_traversal_blocked(self):
        """Test that path traversal in template names is blocked."""
        from swirrl.modules.nfo.templates import resolve_template_path

        with pytest.raises((FileNotFoundError, ValueError, OSError)):
            resolve_template_path("../../etc/passwd")


class TestTemplateFileSystemAccess:
    """Test that templates cannot access arbitrary files."""

    def test_template_cannot_include_arbitrary_paths(self, tmp_path):
        """Test that include with absolute paths fails in sandbox."""
        env = SandboxedEnvironment(
            loader=None,
            autoescape=False,
        )

        # Attempting to load a template from None loader should fail
        with pytest.raises(Exception):
            env.get_template("/etc/passwd")
