from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from typing import Any


class InteractivePromptError(ValueError):
    """Raised when an interactive prompt cannot be shown safely."""


class PromptUI:
    def require_tty(self, hint: str) -> None:
        stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
        stderr_tty = bool(getattr(sys.stderr, "isatty", lambda: False)())
        if not stdin_tty or not stderr_tty:
            raise InteractivePromptError(hint)

    @staticmethod
    def _inquirer():
        try:
            from InquirerPy import inquirer
        except ImportError as exc:  # pragma: no cover - installed package declares the dependency
            raise InteractivePromptError(
                "Interactive prompts require InquirerPy; reinstall the Smart Search package"
            ) from exc
        return inquirer

    @staticmethod
    def _execute(factory: Callable[[], Any]) -> Any:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                return factory().execute()
        except EOFError as exc:
            raise InteractivePromptError(
                "Interactive input ended unexpectedly; use explicit non-interactive options"
            ) from exc

    def select(self, message: str, choices: list[dict[str, Any]], *, default: Any = None) -> Any:
        inquirer = self._inquirer()
        return self._execute(
            lambda: inquirer.select(
                message=message,
                choices=choices,
                default=default,
                qmark="",
                pointer=">",
            )
        )

    def checkbox(
        self,
        message: str,
        choices: list[dict[str, Any]],
        *,
        enabled: list[Any] | None = None,
        required: bool = False,
    ) -> list[Any]:
        selected = set(enabled or [])
        normalized = [dict(choice, enabled=choice.get("value") in selected) for choice in choices]
        inquirer = self._inquirer()
        return list(
            self._execute(
                lambda: inquirer.checkbox(
                    message=message,
                    choices=normalized,
                    instruction="(Up/Down move, Space select, Enter confirm)",
                    qmark="",
                    pointer=">",
                    enabled_symbol="[x]",
                    disabled_symbol="[ ]",
                    validate=(lambda result: bool(result)) if required else None,
                    invalid_message="Select at least one option",
                )
            )
        )

    def confirm(self, message: str, *, default: bool = False) -> bool:
        inquirer = self._inquirer()
        return bool(self._execute(lambda: inquirer.confirm(message=message, default=default, qmark="")))

    def text(self, message: str, *, default: str = "", required: bool = False) -> str:
        inquirer = self._inquirer()
        return str(
            self._execute(
                lambda: inquirer.text(
                    message=message,
                    default=default,
                    qmark="",
                    validate=(lambda value: bool(value.strip())) if required else None,
                    invalid_message="A value is required",
                )
            )
        ).strip()

    def secret(self, message: str, *, required: bool = False) -> str:
        inquirer = self._inquirer()
        return str(
            self._execute(
                lambda: inquirer.secret(
                    message=message,
                    qmark="",
                    validate=(lambda value: bool(value.strip())) if required else None,
                    invalid_message="A value is required",
                )
            )
        ).strip()


prompt_ui = PromptUI()
