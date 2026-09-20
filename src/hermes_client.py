"""Hermes client — sends messages to Hermes Agent via CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Response markers from Hermes chat -Q output
_SESSION_LINE_PREFIXES = (
    "Session: ",
    "Session ID: ",
    "Session saved as: ",
    "---",  # separator lines
)


class HermesClientError(Exception):
    """Hermes client error."""


class HermesClient:
    """Client that sends messages to Hermes Agent via `hermes chat -q`.

    Supports role instructions (system prompt) and quiet mode
    that strips tool previews, banners, and session info.
    """

    def __init__(
        self,
        hermes_bin: str = "hermes",
        model: Optional[str] = None,
        timeout: int = 120,
        system_prompt: str = "",
    ):
        self._hermes_bin = hermes_bin
        self._model = model
        self._timeout = timeout
        self._system_prompt = system_prompt

    async def close(self) -> None:
        """Close client (no-op for CLI-based client)."""
        pass

    async def send_message(
        self,
        message: str,
        chat_id: str,
        user_id: str,
        user_name: str,
        reply_to: Optional[str] = None,
        raw_update: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a message to Hermes Agent and return the response.

        Supports optional `system_prompt` via kwargs for per-message
        role instructions. Falls back to self._system_prompt (set at init).
        """
        # Build full message with system prompt and user context
        parts: list[str] = []

        # Use per-message system_prompt if provided, otherwise use init-time one
        system_prompt = kwargs.pop("system_prompt", None) or self._system_prompt

        if system_prompt:
            parts.append(f"[Системные инструкции]\n{system_prompt}\n[/Системные инструкции]")

        context = f"[MAX chat_id={chat_id}, user={user_name} (id={user_id})]"
        if reply_to:
            context += f" [reply_to={reply_to}]"
        parts.append(context)
        parts.append(message)

        full_message = "\n\n".join(parts)

        cmd = [
            self._hermes_bin, "chat", "-q", full_message, "-Q",
            "--source", "max-bridge",
            "--ignore-rules",
            "--max-turns", "3",
        ]

        if self._model:
            cmd.extend(["-m", self._model])

        logger.info(
            "Sending to Hermes: chat_id=%s, user=%s, msg_len=%d, system_prompt=%s",
            chat_id, user_name, len(message), bool(self._system_prompt),
        )
        logger.debug("Hermes command: %s", " ".join(shlex.quote(c) for c in cmd))
        logger.debug("Full message: %r", full_message[:500])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise HermesClientError(f"Hermes timed out after {self._timeout}s")

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                logger.error("Hermes exit code %d: %s", proc.returncode, stderr_text[:500])
                raise HermesClientError(
                    f"Hermes exited with code {proc.returncode}: {stderr_text[:200]}"
                )

            if stderr_text:
                logger.debug("Hermes stderr: %s", stderr_text[:300])

            # Extract clean response text
            agent_response = self._extract_response(stdout_text)

            logger.info("Hermes response: %d chars", len(agent_response))

            return {
                "message": agent_response,
                "chat_id": chat_id,
                "user_id": user_id,
                "platform": "max",
            }

        except HermesClientError:
            raise
        except Exception as e:
            logger.error("Hermes client error: %s", e)
            raise HermesClientError(str(e)) from e

    @staticmethod
    def _extract_response(stdout: str) -> str:
        """Extract agent response from hermes chat output.

        In -Q (quiet) mode, Hermes outputs only the final response
        and optionally a session line. We strip session/metadata lines.
        """
        if not stdout:
            return ""

        # Try JSON output first (for structured format)
        for line in stdout.split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if "message" in data:
                        return data["message"]
                    if "response" in data:
                        return data["response"]
                    if "text" in data:
                        return data["text"]
                except json.JSONDecodeError:
                    pass

        # Strip session/metadata lines from the end
        lines = stdout.split("\n")
        clean_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in _SESSION_LINE_PREFIXES):
                continue
            clean_lines.append(line)

        result = "\n".join(clean_lines).strip()

        # Fallback: if nothing left, return original
        return result if result else stdout