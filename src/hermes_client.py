"""Hermes client — sends messages to Hermes Agent via CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HermesClientError(Exception):
    """Hermes client error."""


class HermesClient:
    """Client that sends messages to Hermes Agent via `hermes chat -q`."""

    def __init__(
        self,
        hermes_bin: str = "hermes",
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        self._hermes_bin = hermes_bin
        self._model = model
        self._timeout = timeout

    async def send_message(
        self,
        message: str,
        chat_id: str,
        user_id: str,
        user_name: str,
        reply_to: Optional[str] = None,
        raw_update: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send a message to Hermes Agent and return the response.

        Returns dict with 'message' (agent response text) on success.
        """
        # Build context for the agent
        context = f"[MAX chat_id={chat_id}, user={user_name} (id={user_id})]"
        if reply_to:
            context += f" [reply_to={reply_to}]"

        full_message = f"{context}\n\n{message}"

        cmd = [self._hermes_bin, "chat", "-q", full_message, "-Q", "--source", "max-bridge"]

        if self._model:
            cmd.extend(["-m", self._model])

        logger.info("Sending to Hermes: chat_id=%s, user=%s, msg_len=%d", chat_id, user_name, len(message))
        logger.debug("Hermes command: %s", " ".join(shlex.quote(c) for c in cmd))

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
                raise HermesClientError(f"Hermes exited with code {proc.returncode}: {stderr_text[:200]}")

            if stderr_text:
                logger.debug("Hermes stderr: %s", stderr_text[:300])

            # Parse response — hermes chat -Q outputs the agent response
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
        """Extract agent response from hermes chat output."""
        if not stdout:
            return ""

        # hermes chat -Q outputs the response directly
        # Try to find JSON output first
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

        # Fallback: return the full stdout
        return stdout
