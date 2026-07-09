"""
Tests for the low-level string-safety helpers in core.py:
bat_escape, _sh_escape, _b64_encode, MODULE_RE, RUNNER_ARGS_UNSAFE_RE.

These are the foundation every template generator relies on to avoid
producing a broken or exploitable .bat/.sh file when project names, entry
points, or runner args contain unusual characters.
"""

from __future__ import annotations

import base64

from venv_bat_gen.core import (
    MODULE_RE,
    RUNNER_ARGS_UNSAFE_RE,
    _b64_encode,
    _sh_escape,
    bat_escape,
)


class TestBatEscape:
    def test_plain_string_unchanged(self):
        assert bat_escape("MyProject") == "MyProject"

    def test_strips_double_quotes(self):
        assert bat_escape('My "Cool" App') == "My Cool App"

    def test_doubles_percent_signs(self):
        assert bat_escape("100%") == "100%%"

    def test_percent_and_quote_combined(self):
        assert bat_escape('50% "done"') == "50%% done"

    def test_empty_string(self):
        assert bat_escape("") == ""


class TestShEscape:
    def test_plain_string_unchanged(self):
        assert _sh_escape("MyProject") == "MyProject"

    def test_escapes_double_quotes(self):
        assert _sh_escape('say "hi"') == r'say \"hi\"'

    def test_escapes_backslashes(self):
        assert _sh_escape(r"C:\path") == r"C:\\path"

    def test_escapes_dollar_sign(self):
        assert _sh_escape("$HOME") == r"\$HOME"

    def test_escapes_backtick(self):
        assert _sh_escape("`whoami`") == r"\`whoami\`"

    def test_backslash_escaped_before_other_chars_prevents_double_escaping(self):
        # If '$' were escaped before '\', the backslash inserted for '$'
        # would itself get re-escaped, corrupting the output.
        result = _sh_escape(r"\$")
        assert result == r"\\\$"


class TestB64Encode:
    def test_round_trips_with_default_crlf(self):
        text = "line1\nline2\n"
        encoded = _b64_encode(text)
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "line1\r\nline2\r\n"

    def test_lf_line_endings_preserved_when_requested(self):
        text = "line1\nline2\n"
        encoded = _b64_encode(text, line_endings="\n")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "line1\nline2\n"

    def test_output_is_valid_base64(self):
        encoded = _b64_encode("hello world")
        # Should not raise
        base64.b64decode(encoded)

    def test_unicode_content_encoded_as_utf8(self):
        encoded = _b64_encode("café ☕")
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "café ☕"


class TestModuleRegex:
    def test_simple_name_matches(self):
        assert MODULE_RE.match("mypackage")

    def test_dotted_path_matches(self):
        assert MODULE_RE.match("mypackage.submodule.cli")

    def test_leading_digit_rejected(self):
        assert not MODULE_RE.match("123package")

    def test_hyphen_rejected(self):
        assert not MODULE_RE.match("my-package")

    def test_empty_string_rejected(self):
        assert not MODULE_RE.match("")

    def test_trailing_dot_rejected(self):
        assert not MODULE_RE.match("mypackage.")

    def test_shell_injection_attempt_rejected(self):
        assert not MODULE_RE.match("os; rm -rf /")


class TestRunnerArgsUnsafeRegex:
    def test_plain_args_are_safe(self):
        assert not RUNNER_ARGS_UNSAFE_RE.search("app.main:app --host 0.0.0.0 --port 8000")

    def test_ampersand_flagged(self):
        assert RUNNER_ARGS_UNSAFE_RE.search("run.bat & del *.*")

    def test_pipe_flagged(self):
        assert RUNNER_ARGS_UNSAFE_RE.search("app | more")

    def test_redirect_flagged(self):
        assert RUNNER_ARGS_UNSAFE_RE.search("app > out.txt")

    def test_caret_flagged(self):
        assert RUNNER_ARGS_UNSAFE_RE.search("app ^& other")

    def test_double_quote_flagged(self):
        assert RUNNER_ARGS_UNSAFE_RE.search('app "arg"')
