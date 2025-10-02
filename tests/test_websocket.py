"""Tests for WebSocket transport functionality."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from capnweb import RpcTarget
from capnweb.transports import WebSocketTransport, create_transport


class EchoTarget(RpcTarget):
    """Test target that echoes back arguments."""

    async def call(self, method: str, args: list[Any]) -> Any:
        """Echo back the arguments."""
        match method:
            case "echo":
                return args[0] if args else None
            case "reverse":
                return args[0][::-1] if args and isinstance(args[0], str) else None
            case _:
                return f"Called {method} with {args}"

    async def get_property(self, property: str) -> Any:
        """Get a property."""
        return f"Property: {property}"


@pytest.mark.asyncio
class TestWebSocketTransport:
    """Test WebSocket transport implementation."""

    async def test_create_websocket_transport(self) -> None:
        """Test creating WebSocketTransport instance."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        assert transport.url == "ws://localhost:8080/rpc/ws"
        assert transport._session is None  # Not connected yet
        assert transport._ws is None

    async def test_transport_factory_creates_websocket(self) -> None:
        """Test transport factory creates WebSocketTransport for ws:// URLs."""
        transport = create_transport("ws://localhost:8080/rpc/ws")
        assert isinstance(transport, WebSocketTransport)

        transport2 = create_transport("wss://localhost:8080/rpc/ws")
        assert isinstance(transport2, WebSocketTransport)

    async def test_send_without_connection_raises_error(self) -> None:
        """Test sending data without connection raises RuntimeError."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        with pytest.raises(RuntimeError) as exc_info:
            await transport.send(b"test")

        assert "not connected" in str(exc_info.value).lower()

    async def test_receive_without_connection_raises_error(self) -> None:
        """Test receiving data without connection raises RuntimeError."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        with pytest.raises(RuntimeError) as exc_info:
            await transport.receive()

        assert "not connected" in str(exc_info.value).lower()

    async def test_send_and_receive_with_mock(self) -> None:
        """Test send_and_receive with mocked WebSocket."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        # Mock the WebSocket connection
        mock_ws = AsyncMock()
        mock_ws.send_bytes = AsyncMock()

        # Create a mock message
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.BINARY
        mock_msg.data = b"response"
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        # Test send_and_receive
        result = await transport.send_and_receive(b"test")

        assert result == b"response"
        mock_ws.send_bytes.assert_called_once_with(b"test")
        mock_ws.receive.assert_called_once()

    async def test_receive_text_message(self) -> None:
        """Test receiving TEXT type message converts to bytes."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.data = "text response"
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        result = await transport.receive()
        assert result == b"text response"

    async def test_receive_close_message_raises_error(self) -> None:
        """Test receiving CLOSE message raises ConnectionError."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.CLOSE
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        with pytest.raises(ConnectionError) as exc_info:
            await transport.receive()

        assert "closed" in str(exc_info.value).lower()

    async def test_receive_error_message_raises_error(self) -> None:
        """Test receiving ERROR message raises ConnectionError."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        mock_ws = AsyncMock()
        mock_ws.exception = Mock(return_value=RuntimeError("Test error"))
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.ERROR
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        with pytest.raises(ConnectionError) as exc_info:
            await transport.receive()

        assert "error" in str(exc_info.value).lower()

    async def test_receive_unexpected_message_type_raises_error(self) -> None:
        """Test receiving unexpected message type raises ValueError."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.PING  # Unexpected type
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        with pytest.raises(ValueError) as exc_info:
            await transport.receive()

        assert "unexpected" in str(exc_info.value).lower()

    async def test_close_without_connection(self) -> None:
        """Test closing transport that was never connected."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        # Should not raise error
        await transport.close()

    async def test_close_with_connection(self) -> None:
        """Test closing active WebSocket connection."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        # Mock connected state
        mock_ws = AsyncMock()
        mock_session = AsyncMock()

        transport._ws = mock_ws
        transport._session = mock_session

        await transport.close()

        mock_ws.close.assert_called_once()
        mock_session.close.assert_called_once()
        assert transport._ws is None
        assert transport._session is None

    async def test_context_manager_mock(self) -> None:
        """Test using WebSocketTransport as async context manager with mocks."""
        # We can't test real WebSocket without a server, but we can test the pattern
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_ws = AsyncMock()
            mock_session.ws_connect = AsyncMock(return_value=mock_ws)
            mock_session_class.return_value = mock_session

            async with WebSocketTransport("ws://localhost:8080/rpc/ws") as transport:
                assert transport._session is not None
                assert transport._ws is not None

            # After exiting context, should be closed
            mock_ws.close.assert_called()
            mock_session.close.assert_called()


@pytest.mark.asyncio
class TestWebSocketIntegration:
    """Integration tests for WebSocket transport with real server.

    Note: These tests use HTTP batch for the server but demonstrate
    how WebSocket client would work. Full WebSocket server support
    requires implementing the WebSocket endpoint in Server.
    """

    async def test_websocket_url_parsing(self) -> None:
        """Test WebSocket URL is correctly parsed."""
        # Test that ws:// and wss:// URLs create WebSocket transport
        ws_transport = create_transport("ws://example.com/rpc/ws")
        assert isinstance(ws_transport, WebSocketTransport)

        wss_transport = create_transport("wss://example.com/rpc/ws")
        assert isinstance(wss_transport, WebSocketTransport)

    async def test_connection_error_handling(self) -> None:
        """Test error handling when WebSocket server is not available."""
        transport = WebSocketTransport("ws://localhost:19999/nonexistent")

        # Attempting to connect to non-existent server should fail
        try:
            async with transport:
                pass  # Should not reach here
        except (OSError, aiohttp.ClientError, RuntimeError):
            # Expected - connection refused or similar error
            pass

    async def test_multiple_messages(self) -> None:
        """Test sending multiple messages over WebSocket."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        # Mock WebSocket for multiple messages
        mock_ws = AsyncMock()
        mock_ws.send_bytes = AsyncMock()

        # Queue of responses
        responses = [
            Mock(type=aiohttp.WSMsgType.BINARY, data=b"response1"),
            Mock(type=aiohttp.WSMsgType.BINARY, data=b"response2"),
            Mock(type=aiohttp.WSMsgType.BINARY, data=b"response3"),
        ]
        mock_ws.receive = AsyncMock(side_effect=responses)

        transport._ws = mock_ws

        # Send multiple messages
        result1 = await transport.send_and_receive(b"msg1")
        result2 = await transport.send_and_receive(b"msg2")
        result3 = await transport.send_and_receive(b"msg3")

        assert result1 == b"response1"
        assert result2 == b"response2"
        assert result3 == b"response3"

        assert mock_ws.send_bytes.call_count == 3


@pytest.mark.asyncio
class TestWebSocketEdgeCases:
    """Test edge cases and error conditions for WebSocket transport."""

    async def test_send_empty_data(self) -> None:
        """Test sending empty bytes."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        mock_ws = AsyncMock()
        transport._ws = mock_ws

        await transport.send(b"")
        mock_ws.send_bytes.assert_called_once_with(b"")

    async def test_receive_empty_binary(self) -> None:
        """Test receiving empty binary message."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.BINARY
        mock_msg.data = b""
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        result = await transport.receive()
        assert result == b""

    async def test_receive_empty_text(self) -> None:
        """Test receiving empty text message."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        mock_ws = AsyncMock()
        mock_msg = Mock()
        mock_msg.type = aiohttp.WSMsgType.TEXT
        mock_msg.data = ""
        mock_ws.receive = AsyncMock(return_value=mock_msg)

        transport._ws = mock_ws

        result = await transport.receive()
        assert result == b""

    async def test_concurrent_operations(self) -> None:
        """Test concurrent send/receive operations."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        mock_ws = AsyncMock()

        # Set up responses
        responses = [
            Mock(type=aiohttp.WSMsgType.BINARY, data=f"response{i}".encode())
            for i in range(5)
        ]
        mock_ws.receive = AsyncMock(side_effect=responses)
        mock_ws.send_bytes = AsyncMock()

        transport._ws = mock_ws

        # Send multiple messages concurrently
        tasks = [transport.send_and_receive(f"msg{i}".encode()) for i in range(5)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result == f"response{i}".encode()
