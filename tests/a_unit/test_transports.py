"""Tests for transport implementations."""

import pytest

from capnweb.transport.transports import (
    HttpBatchTransport,
    WebSocketTransport,
    create_transport,
)


class TestTransportFactory:
    """Tests for transport factory function."""

    def test_create_http_transport(self):
        """Test creating HTTP batch transport."""
        transport = create_transport("http://localhost:8080/rpc/batch")
        assert isinstance(transport, HttpBatchTransport)
        assert transport.url == "http://localhost:8080/rpc/batch"

    def test_create_https_transport(self):
        """Test creating HTTPS batch transport."""
        transport = create_transport("https://example.com/rpc/batch")
        assert isinstance(transport, HttpBatchTransport)

    def test_create_websocket_transport(self):
        """Test creating WebSocket transport."""
        transport = create_transport("ws://localhost:8080/rpc/ws")
        assert isinstance(transport, WebSocketTransport)
        assert transport.url == "ws://localhost:8080/rpc/ws"

    def test_create_wss_transport(self):
        """Test creating secure WebSocket transport."""
        transport = create_transport("wss://example.com/rpc/ws")
        assert isinstance(transport, WebSocketTransport)

    def test_create_transport_with_timeout(self):
        """Test creating transport with custom timeout."""
        transport = create_transport("http://localhost:8080/rpc", timeout=60.0)
        assert isinstance(transport, HttpBatchTransport)
        assert transport.timeout == 60.0

    def test_create_transport_invalid_scheme(self):
        """Test that invalid URL scheme raises error."""
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            create_transport("ftp://example.com/rpc")


class TestHttpBatchTransport:
    """Tests for HTTP batch transport."""

    def test_initialization(self):
        """Test HTTP batch transport initialization."""
        transport = HttpBatchTransport("http://localhost:8080/rpc/batch", timeout=45.0)
        assert transport.url == "http://localhost:8080/rpc/batch"
        assert transport.timeout == 45.0

    @pytest.mark.asyncio
    async def test_send_without_open_raises_error(self):
        """Test that sending without opening transport raises error."""
        transport = HttpBatchTransport("http://localhost:8080/rpc/batch")
        with pytest.raises(RuntimeError, match="Transport not open"):
            await transport.send(b"test data")

    @pytest.mark.asyncio
    async def test_receive_without_send_raises_error(self):
        """Test that receiving without sending raises error."""
        transport = HttpBatchTransport("http://localhost:8080/rpc/batch")
        async with transport:
            with pytest.raises(RuntimeError, match="No data to send"):
                await transport.receive()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test that transport works as async context manager."""
        transport = HttpBatchTransport("http://localhost:8080/rpc/batch")
        async with transport:
            assert transport._session is not None

        # After exit, session should be closed
        assert transport._session is None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing transport."""
        transport = HttpBatchTransport("http://localhost:8080/rpc/batch")
        async with transport:
            pass

        # Should be able to call close() multiple times safely
        await transport.close()
        await transport.close()


class TestWebSocketTransport:
    """Tests for WebSocket transport."""

    def test_initialization(self):
        """Test WebSocket transport initialization."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        assert transport.url == "ws://localhost:8080/rpc/ws"

    @pytest.mark.asyncio
    async def test_send_without_connection_raises_error(self):
        """Test that sending without connection raises error."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        with pytest.raises(RuntimeError, match="WebSocket not connected"):
            await transport.send(b"test data")

    @pytest.mark.asyncio
    async def test_receive_without_connection_raises_error(self):
        """Test that receiving without connection raises error."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")
        with pytest.raises(RuntimeError, match="WebSocket not connected"):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing WebSocket transport."""
        transport = WebSocketTransport("ws://localhost:8080/rpc/ws")

        # Should be able to call close() even if never connected
        await transport.close()
        await transport.close()
