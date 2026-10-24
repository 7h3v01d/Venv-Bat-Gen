# SPDX-License-Identifier: Apache-2.0
# Copyright 2025-2026 Leon Priest (7h3v01d)
"""
Tests for the low-level string-safety helpers in core.py:
bat_escape, _sh_escape, _b64_encode, MODULE_RE, SCRIPT_RE, and the v3.5
runner-arg model (parse_runner_args / runner_args_problem / arg-vector
emitters).

These are the foundation every template generator relies on to avoid
producing a broken or exploitable .bat/.sh file when project names, entry
points, or runner args contain unusual characters.
"""

from __future__ import annotations

import base64
import typing

import pytest

from venv_bat_gen.core import (
    MODULE_RE,
    SCRIPT_RE,
    _b64_encode,
    _bat_arg_vector,
    _ps1_array_literal,
    _sh_array_literal,
    _sh_escape,
    bat_escape,
    parse_runner_args,
    runner_args_problem,
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


class TestScriptRegex:
    def test_simple_name_matches(self):
        assert SCRIPT_RE.match("uvicorn")

    def test_hyphenated_name_matches(self):
        assert SCRIPT_RE.match("adp-server")

    def test_dotted_name_matches(self):
        assert SCRIPT_RE.match("my.tool-cli")

    def test_path_separator_rejected(self):
        assert not SCRIPT_RE.match("Scripts/evil")
        assert not SCRIPT_RE.match("..\\evil")

    def test_leading_hyphen_rejected(self):
        assert not SCRIPT_RE.match("-rf")

    def test_space_rejected(self):
        assert not SCRIPT_RE.match("two words")

    def test_empty_rejected(self):
        assert not SCRIPT_RE.match("")


class TestParseRunnerArgs:
    def test_empty_string_gives_empty_list(self):
        assert parse_runner_args("") == []
        assert parse_runner_args("   ") == []

    def test_plain_tokens_split_on_whitespace(self):
        assert parse_runner_args("app.main:app --port 8000") == \
            ["app.main:app", "--port", "8000"]

    def test_double_quoted_token_kept_whole(self):
        # THE core v3.4 failure: spaced args were impossible in every shell.
        assert parse_runner_args('--name "My App"') == ["--name", "My App"]

    def test_single_quoted_token_kept_whole(self):
        assert parse_runner_args("--name 'My App'") == ["--name", "My App"]

    def test_unbalanced_quote_raises(self):
        with pytest.raises(ValueError):
            parse_runner_args('--name "My App')


class TestRunnerArgsProblem:
    def test_plain_args_ok(self):
        assert runner_args_problem("app.main:app --host 0.0.0.0 --port 8000") is None

    def test_quoted_spaced_arg_ok(self):
        # Regression: v3.4 rejected any double quote outright.
        assert runner_args_problem('--config "conf dir/app.json"') is None

    def test_cmd_metachars_inside_token_ok(self):
        # & | < > ^ ! are safe once emitted inside quoted tokens with no
        # delayed expansion — v3.4 banned them wholesale.
        assert runner_args_problem("--filter a&b --level 100!") is None

    def test_unbalanced_quotes_rejected(self):
        assert runner_args_problem('--name "My App') is not None

    def test_embedded_literal_double_quote_rejected(self):
        # shlex-escaped literal quote inside a token: cmd cannot represent it.
        assert runner_args_problem('--say \\"hi\\"') is not None

    def test_newline_inside_quoted_token_rejected(self):
        # An unquoted newline is just whitespace to shlex; only a quoted one
        # can survive into a token — and that is unrepresentable in .bat.
        assert runner_args_problem('--a "b\nc"') is not None


class TestArgVectorEmitters:
    ARGS: typing.ClassVar[list[str]] = [
        "app.main:app", "--name", "My App", "--pct", "100%", "--filter", "a&b",
    ]

    def test_bat_vector_quotes_every_token_and_doubles_percent(self):
        vec = _bat_arg_vector(self.ARGS)
        assert '"My App"' in vec
        assert '"100%%"' in vec          # % doubled for batch parsing
        assert '"a&b"' in vec            # & literal inside quotes
        # every token individually quoted
        assert vec.count('"') == 2 * len(self.ARGS)

    def test_sh_array_single_quotes_and_escapes_embedded_quote(self):
        vec = _sh_array_literal(["it's", "My App"])
        assert vec == "('it'\\''s' 'My App')"

    def test_sh_array_empty(self):
        assert _sh_array_literal([]) == "()"

    def test_ps1_array_doubles_single_quotes(self):
        vec = _ps1_array_literal(["it's", "My App"])
        assert vec == "@('it''s', 'My App')"

    def test_ps1_array_empty(self):
        assert _ps1_array_literal([]) == "@()"
