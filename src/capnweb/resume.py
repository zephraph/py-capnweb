"""Resume token support for Cap'n Web protocol.

Resume tokens allow sessions to be resumed after reconnection,
preserving capability references and avoiding the need to re-authenticate
or re-establish capabilities.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ResumeToken:
    """Resume token for session restoration.

    Contains all necessary information to restore a client session:
    - Session ID for server-side lookup
    - Capability mappings (import/export IDs)
    - Creation timestamp for expiration
    - Optional custom data
    """

    session_id: str
    capabilities: dict[int, int]  # Map of import_id -> export_id
    created_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp
    metadata: dict[str, Any] | None = None

    def to_json(self) -> str:
        """Serialize resume token to JSON string.

        Returns:
            JSON string representation of the token
        """
        data: dict[str, Any] = {
            "session_id": self.session_id,
            "capabilities": self.capabilities,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return json.dumps(data)

    @staticmethod
    def from_json(token_str: str) -> ResumeToken:
        """Parse resume token from JSON string.

        Args:
            token_str: JSON string representation

        Returns:
            Parsed ResumeToken

        Raises:
            ValueError: If token format is invalid
        """
        try:
            data = json.loads(token_str)
            # Convert string keys back to integers for capabilities dict
            capabilities = {int(k): v for k, v in data["capabilities"].items()}
            return ResumeToken(
                session_id=data["session_id"],
                capabilities=capabilities,
                created_at=data["created_at"],
                expires_at=data["expires_at"],
                metadata=data.get("metadata"),
            )
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            msg = f"Invalid resume token format: {e}"
            raise ValueError(msg) from e

    def is_expired(self) -> bool:
        """Check if the token has expired.

        Returns:
            True if token is expired, False otherwise
        """
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the token is valid (not expired and properly formed).

        Returns:
            True if token is valid, False otherwise
        """
        if self.is_expired():
            return False
        if not self.session_id:
            return False
        return not self.created_at > self.expires_at


class ResumeTokenManager:
    """Manages resume tokens and session state."""

    def __init__(self, default_ttl: float = 3600.0) -> None:
        """Initialize resume token manager.

        Args:
            default_ttl: Default time-to-live for tokens in seconds (default: 1 hour)
        """
        self.default_ttl = default_ttl
        # Session ID -> (export_table_snapshot, import_table_snapshot)
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_token(
        self,
        imports: dict[int, Any],
        exports: dict[int, Any],
        ttl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ResumeToken:
        """Create a new resume token.

        Args:
            imports: Current import table state (import_id -> (value, ref_count))
            exports: Current export table state (export_id -> (target, ref_count))
            ttl: Time-to-live in seconds (None = use default)
            metadata: Optional custom metadata

        Returns:
            New ResumeToken
        """
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        expires_at = now + (ttl or self.default_ttl)

        # Create capability mapping (import_id -> export_id)
        # This allows the client to restore references
        # In a real implementation, we'd need to map to corresponding export IDs
        capabilities = {import_id: import_id for import_id in imports}

        # Store session state for server-side restoration
        # This allows same-server restoration to be more efficient
        self._sessions[session_id] = {
            "imports": imports.copy(),
            "exports": exports.copy(),
            "created_at": now,
            "expires_at": expires_at,
        }

        return ResumeToken(
            session_id=session_id,
            capabilities=capabilities,
            created_at=now,
            expires_at=expires_at,
            metadata=metadata,
        )

    def validate_token(self, token: ResumeToken) -> bool:
        """Validate a resume token.

        Args:
            token: Token to validate

        Returns:
            True if token is valid and session exists, False otherwise
        """
        if not token.is_valid():
            return False

        # Check if session exists
        if token.session_id not in self._sessions:
            return False

        # Check if session is expired
        session = self._sessions[token.session_id]
        if time.time() > session["expires_at"]:
            # Clean up expired session
            del self._sessions[token.session_id]
            return False

        return True

    def restore_session(
        self, token: ResumeToken
    ) -> tuple[dict[int, Any], dict[int, Any], bool] | None:
        """Restore session state from a resume token.

        Args:
            token: Token to restore from

        Returns:
            Tuple of (imports, exports, session_found) if successful, None if token is invalid
            - session_found is True if the session was found in this manager

        Note:
            If the session doesn't exist in this manager (e.g., different server instance),
            this returns empty tables with session_found=False.
            For distributed systems, use a shared session store.
        """
        # Basic token validation (not expired, well-formed)
        if not token.is_valid():
            return None

        # If session exists in this manager, return stored state
        if token.session_id in self._sessions:
            session = self._sessions[token.session_id]
            return (session["imports"].copy(), session["exports"].copy(), True)

        # Otherwise return empty state (session may exist elsewhere, or be truly invalid)
        # In production, you'd check a shared session store here
        return ({}, {}, False)

    def invalidate_token(self, session_id: str) -> None:
        """Invalidate a resume token by session ID.

        Args:
            session_id: Session ID to invalidate
        """
        self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed
        """
        now = time.time()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now > session["expires_at"]
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
