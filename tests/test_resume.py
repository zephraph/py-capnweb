"""Tests for resume token functionality."""

import time
from typing import Any

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.ids import ExportId
from capnweb.resume import ResumeToken, ResumeTokenManager
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class TestResumeToken:
    """Tests for ResumeToken class."""

    def test_token_creation(self) -> None:
        """Test creating a resume token."""
        token = ResumeToken(
            session_id="test-session",
            capabilities={1: 10, 2: 20},
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )

        assert token.session_id == "test-session"
        assert token.capabilities == {1: 10, 2: 20}
        assert not token.is_expired()
        assert token.is_valid()

    def test_token_serialization(self) -> None:
        """Test token JSON serialization."""
        token = ResumeToken(
            session_id="test-session",
            capabilities={1: 10},
            created_at=1000.0,
            expires_at=2000.0,
            metadata={"user_id": "123"},
        )

        json_str = token.to_json()
        parsed = ResumeToken.from_json(json_str)

        assert parsed.session_id == token.session_id
        assert parsed.capabilities == token.capabilities
        assert parsed.created_at == token.created_at
        assert parsed.expires_at == token.expires_at
        assert parsed.metadata == token.metadata

    def test_token_expiration(self) -> None:
        """Test token expiration."""
        # Already expired
        token = ResumeToken(
            session_id="test",
            capabilities={},
            created_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )

        assert token.is_expired()
        assert not token.is_valid()

    def test_token_validation(self) -> None:
        """Test token validation."""
        # Valid token
        valid_token = ResumeToken(
            session_id="valid",
            capabilities={},
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert valid_token.is_valid()

        # Empty session ID
        invalid_token = ResumeToken(
            session_id="",
            capabilities={},
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert not invalid_token.is_valid()

        # Created after expiration
        backwards_token = ResumeToken(
            session_id="backwards",
            capabilities={},
            created_at=time.time() + 7200,
            expires_at=time.time() + 3600,
        )
        assert not backwards_token.is_valid()

    def test_invalid_json_parsing(self) -> None:
        """Test parsing invalid JSON."""
        with pytest.raises(ValueError):
            ResumeToken.from_json("{invalid json")

        with pytest.raises(ValueError):
            ResumeToken.from_json('{"missing": "fields"}')


class TestResumeTokenManager:
    """Tests for ResumeTokenManager class."""

    def test_create_token(self) -> None:
        """Test creating a token through the manager."""
        manager = ResumeTokenManager(default_ttl=3600.0)

        token = manager.create_token(imports={1: "value1"}, exports={10: "target1"})

        assert token.session_id
        assert not token.is_expired()
        assert token.is_valid()

    def test_validate_token(self) -> None:
        """Test token validation."""
        manager = ResumeTokenManager()

        # Create a valid token
        token = manager.create_token(imports={}, exports={})
        assert manager.validate_token(token)

        # Try to validate non-existent token
        fake_token = ResumeToken(
            session_id="nonexistent",
            capabilities={},
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert not manager.validate_token(fake_token)

    def test_restore_session(self) -> None:
        """Test restoring session from token."""
        manager = ResumeTokenManager()

        # Create token with some state
        imports = {1: "import1", 2: "import2"}
        exports = {10: "export10"}
        token = manager.create_token(imports=imports, exports=exports)

        # Restore session
        result = manager.restore_session(token)
        assert result is not None

        restored_imports, restored_exports, session_found = result
        assert session_found is True
        assert restored_imports == imports
        assert restored_exports == exports

    def test_invalidate_token(self) -> None:
        """Test token invalidation."""
        manager = ResumeTokenManager()

        token = manager.create_token(imports={}, exports={})
        assert manager.validate_token(token)

        # Invalidate token
        manager.invalidate_token(token.session_id)
        assert not manager.validate_token(token)

    def test_cleanup_expired(self) -> None:
        """Test cleanup of expired tokens."""
        manager = ResumeTokenManager(default_ttl=0.1)  # Very short TTL

        # Create tokens
        token1 = manager.create_token(imports={}, exports={})
        token2 = manager.create_token(imports={}, exports={})

        # Wait for expiration
        time.sleep(0.2)

        # Cleanup
        count = manager.cleanup_expired()
        assert count == 2

        # Tokens should no longer be valid
        assert not manager.validate_token(token1)
        assert not manager.validate_token(token2)

    def test_custom_ttl(self) -> None:
        """Test custom TTL for tokens."""
        manager = ResumeTokenManager(default_ttl=7200.0)

        token = manager.create_token(imports={}, exports={}, ttl=1800.0)

        # Should expire in 1800 seconds, not 7200
        expected_expiry = token.created_at + 1800.0
        assert abs(token.expires_at - expected_expiry) < 1.0

    def test_token_with_metadata(self) -> None:
        """Test tokens with custom metadata."""
        manager = ResumeTokenManager()

        metadata = {"user_id": "user123", "role": "admin"}
        token = manager.create_token(imports={}, exports={}, metadata=metadata)

        assert token.metadata == metadata

        # Restore and verify metadata preserved
        result = manager.restore_session(token)
        assert result is not None


class TestServerResumeTokens:
    """Tests for Server resume token methods."""

    def test_server_create_token(self) -> None:
        """Test server can create resume tokens."""
        config = ServerConfig()
        server = Server(config)

        token = server.create_resume_token()

        assert token.session_id
        assert token.is_valid()
        assert not token.is_expired()

    def test_server_create_token_with_metadata(self) -> None:
        """Test server creates token with metadata."""
        config = ServerConfig()
        server = Server(config)

        metadata = {"client_id": "abc123"}
        token = server.create_resume_token(metadata=metadata)

        assert token.metadata == metadata

    def test_server_restore_from_token(self) -> None:
        """Test server can restore from token."""
        config = ServerConfig()
        server = Server(config)

        # Create token
        token = server.create_resume_token()

        # Restore (should succeed for newly created token)
        result = server.restore_from_token(token)
        assert result is True

    def test_server_invalidate_token(self) -> None:
        """Test server can invalidate tokens."""
        config = ServerConfig()
        server = Server(config)

        token = server.create_resume_token()
        session_id = token.session_id

        # Invalidate
        server.invalidate_resume_token(session_id)

        # Should no longer be restorable
        result = server.restore_from_token(token)
        assert result is False

    def test_server_cleanup_expired(self) -> None:
        """Test server cleanup of expired tokens."""
        config = ServerConfig(resume_token_ttl=0.1)
        server = Server(config)

        # Create tokens
        server.create_resume_token()
        server.create_resume_token()

        # Wait for expiration
        time.sleep(0.2)

        # Cleanup
        count = server.cleanup_expired_tokens()
        assert count == 2


class TestClientResumeTokens:
    """Tests for Client resume token methods."""

    def test_client_validate_token(self) -> None:
        """Test client can validate tokens."""
        config = ClientConfig(url="http://localhost:8080/rpc/batch")
        client = Client(config)

        # Valid token
        valid_token = ResumeToken(
            session_id="valid",
            capabilities={},
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
        assert client.validate_resume_token(valid_token)

        # Expired token
        expired_token = ResumeToken(
            session_id="expired",
            capabilities={},
            created_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )
        assert not client.validate_resume_token(expired_token)

    def test_client_get_token_info(self) -> None:
        """Test client can get token information."""
        config = ClientConfig(url="http://localhost:8080/rpc/batch")
        client = Client(config)

        token = ResumeToken(
            session_id="test-session",
            capabilities={1: 10, 2: 20},
            created_at=1000.0,
            expires_at=2000.0,
            metadata={"key": "value"},
        )

        info = client.get_resume_token_info(token)

        assert info["session_id"] == "test-session"
        assert info["created_at"] == 1000.0
        assert info["expires_at"] == 2000.0
        assert info["capability_count"] == 2
        assert info["metadata"] == {"key": "value"}
        assert "is_expired" in info
        assert "is_valid" in info


class TestResumeIntegration:
    """Integration tests for resume token functionality."""

    async def test_session_restoration_with_capability(self) -> None:
        """Test session can be restored with a capability."""

        class Counter(RpcTarget):
            def __init__(self) -> None:
                self.count = 0

            async def call(self, method: str, args: list[Any]) -> Any:
                if method == "increment":
                    self.count += 1
                    return self.count
                if method == "get":
                    return self.count
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

            async def get_property(self, property: str) -> Any:  # noqa: ARG002
                msg = "Property access not implemented"
                raise RpcError.not_found(msg)

        # Create server with capability
        config = ServerConfig()
        server = Server(config)
        counter = Counter()
        server.register_capability(0, counter)

        # Increment counter
        await counter.call("increment", [])
        await counter.call("increment", [])
        count_before = await counter.call("get", [])
        assert count_before == 2

        # Create resume token
        token = server.create_resume_token(metadata={"user": "test"})
        assert token.is_valid()
        assert token.metadata == {"user": "test"}

        # Simulate server restart by clearing tables
        server._imports.clear()
        server._exports.clear()

        # Restore session on same server
        success = server.restore_from_token(token)
        assert success

        # Verify capability was restored

        assert server._exports_typed.contains(ExportId(0))

    async def test_resume_token_with_multiple_capabilities(self) -> None:
        """Test resume token with multiple capabilities."""

        class SimpleCapability(RpcTarget):
            def __init__(self, name: str) -> None:
                self.name = name

            async def call(self, method: str, args: list[Any]) -> Any:
                if method == "getName":
                    return self.name
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

            async def get_property(self, property: str) -> Any:  # noqa: ARG002
                msg = "Property access not implemented"
                raise RpcError.not_found(msg)

        # Create server with multiple capabilities
        config = ServerConfig()
        server = Server(config)
        server.register_capability(0, SimpleCapability("cap1"))
        server.register_capability(1, SimpleCapability("cap2"))
        server.register_capability(2, SimpleCapability("cap3"))

        # Create token
        token = server.create_resume_token()

        # Simulate server restart
        server._imports.clear()
        server._exports.clear()

        # Restore session
        success = server.restore_from_token(token)
        assert success

        # Verify capabilities count
        exports_count = len(server._exports_typed._entries)
        assert exports_count == 3

    def test_resume_token_serialization_roundtrip(self) -> None:
        """Test resume token can be serialized and deserialized."""
        # Create server with state
        config = ServerConfig()
        server = Server(config)

        # Create token
        token1 = server.create_resume_token(metadata={"client_id": "123"})

        # Serialize to JSON
        token_json = token1.to_json()

        # Deserialize
        token2 = ResumeToken.from_json(token_json)

        # Verify they match
        assert token1.session_id == token2.session_id
        assert token1.capabilities == token2.capabilities
        assert token1.created_at == token2.created_at
        assert token1.expires_at == token2.expires_at
        assert token1.metadata == token2.metadata

        # Verify can be restored (on same server to access session state)
        success = server.restore_from_token(token2)
        assert success
