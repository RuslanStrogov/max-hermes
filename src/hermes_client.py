"""Hermes client — sends messages to Hermes Agent via CLI with session persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HermesClientError(Exception):
    """Raised when Hermes CLI returns a non-zero exit or an error message."""


class HermesClient:
    """Sends messages to Hermes Agent CLI and captures responses."""

    # Systemd unit has ProtectHome=read-only, so we must store sessions
    # inside a ReadWritePaths-whitelisted subdirectory.
    SESSION_STORE_PATH = Path.home() / ".hermes" / "sessions" / "max-bridge.json"
    # Prefixes used by Hermes CLI on stdout that should be stripped from response
    _SESSION_LINE_PREFIXES = {
        "Session:",
        "---",
        "Duration:",
        "Messages:",
        "Resume this session",
        "  hermes --resume",
        # Box-drawing characters from the non-quiet output
        "╭─",
        "╰─",
        "│",
        "Query:",
        "Initializing agent",
        "────────────────────────",
    }

    def __init__(
        self,
        hermes_bin: str = "hermes",
        timeout: int = 300,
        model: Optional[str] = None,
        system_prompt: str = "",
    ):
        self._hermes_bin = hermes_bin
        self._timeout = timeout
        self._model = model
        self._system_prompt = system_prompt

        # session_id → chat_id mapping, loaded from disk
        self._sessions: dict[str, str] = {}
        self._load_sessions()

    async def close(self) -> None:
        """No-op — HermesClient has no persistent connections to close."""
        pass

    # ───────── session persistence ──────────────────────────────────────

    def _load_sessions(self) -> None:
        """Load session_id → chat_id mapping from disk."""
        if not self.SESSION_STORE_PATH.exists():
            self._sessions = {}
            return
        try:
            data = json.loads(self.SESSION_STORE_PATH.read_text())
            self._sessions = data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load session store: %s", exc)
            self._sessions = {}

    def _save_sessions(self) -> None:
        """Persist session_id → chat_id mapping to disk (best-effort)."""
        try:
            self.SESSION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.SESSION_STORE_PATH.with_suffix(".tmp.json")
            tmp.write_text(json.dumps(self._sessions, indent=2, ensure_ascii=False))
            tmp.replace(self.SESSION_STORE_PATH)
        except OSError as exc:
            logger.warning(
                "Failed to persist sessions (non-fatal): %s", exc
            )

    def _get_session_id(self, chat_id: str) -> Optional[str]:
        """Return saved session_id for this chat, or None."""
        return self._sessions.get(str(chat_id))

    def _set_session_id(self, chat_id: str, session_id: str) -> None:
        """Associate a Hermes session_id with a MAX chat_id and save."""
        self._sessions[str(chat_id)] = session_id
        self._save_sessions()

    # ───────── response parsing ─────────────────────────────────────────

    @staticmethod
    def _parse_session_id_from_stderr(stderr: str) -> Optional[str]:
        """Extract 'session_id: XXXX' from Hermes stderr output.

        Hermes prints the session ID to stderr on every invocation, even
        in quiet mode.  Both fresh and resumed sessions include it.
        """
        m = re.search(r"session_id:\s+(\S+)", stderr)
        return m.group(1) if m else None

    @staticmethod
    def _extract_response(output: str) -> str:
        """Strip Hermes CLI framing lines and return the actual response text."""
        lines = output.split("\n")
        clean: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Skip empty lines, session/metadata lines, and box-drawing
            if not stripped:
                continue
            if any(stripped.startswith(p) for p in HermesClient._SESSION_LINE_PREFIXES):
                continue
            clean.append(line)
        return "\n".join(clean).strip()

    # ───────── core: send to Hermes ──────────────────────────────────────

    async def send_message(
        self,
        message: str,
        chat_id: str,
        user_name: str = "",
        attachments: Optional[list[dict[str, Any]]] = None,
        reply_to: Optional[str] = None,
    ) -> str:
        """Send a message to Hermes and return the response text.

        Manages session persistence transparently:
        * First message from a chat → creates a new Hermes session and
          stores the session_id so subsequent messages continue the
          conversation.
        * Subsequent messages → resume the saved session via ``--resume``.
        """
        # ── build system prompt block ────────────────────────────────
        parts: list[str] = []
        if self._system_prompt:
            parts.append("[Системные инструкции]")
            parts.append(self._system_prompt)
            parts.append("[/Системные инструкции]")

        # ── attachment context ───────────────────────────────────────
        if attachments:
            parts.append("[Прикреплённые файлы]")
            for att in attachments:
                if isinstance(att, dict):
                    att_type = att.get("type", "unknown")
                    att_token = att.get("payload", {}).get("token", "?")
                    parts.append(f"  - {att_type}: token={att_token}")
            parts.append("[/Прикреплённые файлы]")

        parts.append(message)
        full_message = "\n".join(parts)

        # ── decide whether to continue a session ─────────────────────
        session_id = self._get_session_id(chat_id)
        cmd = [
            self._hermes_bin,
            "chat",
            "-q",
            full_message,
            "-Q",  # quiet — suppress banner / tool previews
            "--source",
            "max-bridge",
            "--ignore-rules",
            "--max-turns",
            "20",
        ]

        if session_id:
            cmd.extend(["--resume", session_id])

        if self._model:
            cmd.extend(["-m", self._model])

        logger.info(
            "Sending to Hermes: chat_id=%s, user=%s, msg_len=%d, "
            "system_prompt=%s, session=%s",
            chat_id,
            user_name or "?",
            len(message),
            bool(self._system_prompt),
            session_id or "new",
        )

        # ── execute ──────────────────────────────────────────────────
        # shell_quote the whole command for logging only
        logger.debug("Hermes command: %s", shlex.join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HermesClientError(
                f"Hermes timed out after {self._timeout}s"
            )

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        # ── parse session ID from stderr (available on every call) ───
        new_session_id = self._parse_session_id_from_stderr(stderr_text)
        if new_session_id:
            if new_session_id != session_id:
                self._set_session_id(chat_id, new_session_id)
                logger.info(
                    "Saved session %s for chat %s",
                    new_session_id,
                    chat_id,
                )
        else:
            logger.warning(
                "No session_id in Hermes stderr for chat %s:\n%s",
                chat_id,
                stderr_text[:500],
            )

        # ── check for errors ──────────────────────────────────────────
        if proc.returncode != 0:
            error_text = stdout_text or stderr_text or ""
            # If saved session was lost (prune / DB corruption), retry fresh
            if session_id and "Session not found" in error_text:
                logger.warning(
                    "Session %s for chat %s no longer exists — creating new",
                    session_id,
                    chat_id,
                )
                del self._sessions[str(chat_id)]
                self._save_sessions()
                # Recurse once (will create a new session)
                return await self.send_message(
                    message=message,
                    chat_id=chat_id,
                    user_name=user_name,
                    attachments=attachments,
                    reply_to=reply_to,
                )
            raise HermesClientError(f"Hermes error: {error_text[:1000]}")

        if not stdout_text.strip():
            logger.warning(
                "Hermes returned empty response for chat %s. "
                "stderr: %s",
                chat_id,
                stderr_text[:500],
            )

        response = self._extract_response(stdout_text)
        logger.info(
            "Hermes response: %d chars (session=%s)",
            len(response),
            new_session_id or "?",
        )
        return response