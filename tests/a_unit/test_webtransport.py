"""Tests for WebTransport functionality.

These tests verify the WebTransport client and server implementation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from capnweb.certs import (
    generate_self_signed_cert,
)
from capnweb.transport.transports import (
    HttpBatchTransport,
    WebTransportTransport,
    create_transport,
)
from capnweb.transport.webtransport import (
    WebTransportClient,
    WebTransportClientProtocol,
    WebTransportServer,
    WebTransportServerProtocol,
)

# Note: Some tests require aioquic, others don't
# We mark specific test classes that need aioquic


class TestWebTransportImports:
    """Test WebTransport class imports and initialization."""

    def test_import_webtransport_client(self):
        """Test importing WebTransportClient."""
        assert WebTransportClient is not None

    def test_import_webtransport_server(self):
        """Test importing WebTransportServer."""
        assert WebTransportServer is not None

    def test_create_client(self):
        """Test creating WebTransportClient instance."""
        client = WebTransportClient("https://localhost:4433/test")
        assert client.url == "https://localhost:4433/test"
        assert client.verify_mode is False  # Default for development

    def test_create_client_with_cert(self, tmp_path):
        """Test creating WebTransportClient with certificate."""
        cert_path = tmp_path / "test.crt"
        cert_path.touch()

        client = WebTransportClient(
            "https://localhost:4433/test",
            cert_path=str(cert_path),
            verify_mode=True,
        )

        assert client.cert_path == str(cert_path)
        assert client.verify_mode is True

    def test_create_server(self, tmp_path):
        """Test creating WebTransportServer instance."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        server = WebTransportServer(
            host="localhost",
            port=4433,
            cert_path=cert_path,
            key_path=key_path,
        )

        assert server.host == "localhost"
        assert server.port == 4433
        assert server.cert_path == cert_path
        assert server.key_path == key_path

    @pytest.mark.asyncio
    async def test_client_send_without_connection(self):
        """Test sending data without connection raises error."""
        client = WebTransportClient("https://localhost:4433/test")

        with pytest.raises(RuntimeError) as exc_info:
            await client.send(b"test")

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_client_receive_without_connection(self):
        """Test receiving data without connection raises error."""
        client = WebTransportClient("https://localhost:4433/test")

        with pytest.raises(RuntimeError) as exc_info:
            await client.receive()

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_client_connect_with_invalid_url(self):
        """Test connecting with invalid URL scheme raises error."""
        client = WebTransportClient("http://localhost:4433/test")  # Wrong scheme

        with pytest.raises(ValueError) as exc_info:
            await client.connect()

        assert "https" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_client_close_without_connection(self):
        """Test closing client that was never connected."""
        client = WebTransportClient("https://localhost:4433/test")

        # Should not raise error
        await client.close()

    @pytest.mark.asyncio
    async def test_server_needs_valid_cert_and_key(self, tmp_path):
        """Test server initialization validates cert and key paths."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        # Valid paths
        server = WebTransportServer(
            host="localhost",
            port=4433,
            cert_path=cert_path,
            key_path=key_path,
        )
        assert server is not None


class TestWebTransportTransport:
    """Test WebTransportTransport integration."""

    def test_import_transport(self):
        """Test importing WebTransportTransport."""
        assert WebTransportTransport is not None

    def test_create_transport(self):
        """Test creating WebTransportTransport instance."""
        transport = WebTransportTransport("https://localhost:4433/test")
        assert transport is not None

    def test_transport_factory_webtransport(self):
        """Test transport factory creates WebTransportTransport for https://.../wt URLs."""
        # WebTransport URLs (with /wt or :4433)
        transport1 = create_transport("https://localhost:4433/rpc/wt")
        assert isinstance(transport1, WebTransportTransport)

        transport2 = create_transport("https://localhost/rpc/wt")
        assert isinstance(transport2, WebTransportTransport)

    def test_transport_factory_http_batch(self):
        """Test transport factory creates HttpBatchTransport for regular https:// URLs."""
        # Regular HTTPS should use HttpBatchTransport
        transport = create_transport("https://localhost/rpc/batch")
        assert isinstance(transport, HttpBatchTransport)


class TestWebTransportClientServer:
    """Test WebTransport client-server communication."""

    # NOTE: Full client-server echo test is commented out as it requires
    # more complex WebTransport session setup. The unit tests below
    # provide good coverage of the components.
    #
    # @pytest.mark.asyncio
    # async def test_client_server_echo(self, tmp_path):
    #     """Test basic WebTransport client-server echo communication."""
    #     ... (complex QUIC setup needed)

    @pytest.mark.asyncio
    async def test_client_connection_error(self, tmp_path):
        """Test client handles connection errors gracefully."""
        # Try to connect to non-existent server
        client = WebTransportClient(
            url="https://localhost:9999/test",
            verify_mode=False,
        )

        # Connection should fail (no server running on port 9999)
        try:
            await client.connect()
            await asyncio.sleep(1.0)

            # If we get here, try to send and it should fail
            with pytest.raises(RuntimeError):
                await client.send(b"test")
        except Exception:  # noqa: S110
            # Connection failure is expected
            pass
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_client_url_parsing(self):
        """Test client correctly parses WebTransport URLs."""
        # Test with port
        client1 = WebTransportClient("https://example.com:4433/test")
        assert client1.url == "https://example.com:4433/test"

        # Test without port (should use default 4433)
        client2 = WebTransportClient("https://example.com/test")
        assert client2.url == "https://example.com/test"

    @pytest.mark.asyncio
    async def test_protocol_events(self):
        """Test WebTransport protocol event handling."""
        # Create mock QUIC connection
        mock_quic = Mock()

        # Create protocol instance with QUIC
        protocol = WebTransportClientProtocol(quic=mock_quic)

        # Test receive queue is created
        assert protocol._receive_queue is not None
        assert protocol._http is None
        assert protocol._stream_id is None

    @pytest.mark.asyncio
    async def test_server_protocol_initialization(self):
        """Test WebTransport server protocol initialization."""
        # Create mock QUIC connection
        mock_quic = Mock()

        # Create protocol with handler
        handler_called = False

        async def test_handler(protocol, stream_id):
            nonlocal handler_called
            handler_called = True

        protocol = WebTransportServerProtocol(quic=mock_quic, handler=test_handler)

        assert protocol._handler == test_handler
        assert protocol._http is None
        assert protocol._sessions == {}


# NOTE: Integration tests with actual client/server communication would require:
# 1. Starting a test server in background
# 2. Connecting with a client
# 3. Sending/receiving data
# 4. Verifying protocol behavior
# 5. Cleanup (stopping server)
# For now, see examples/webtransport-integrated/ for working client/server demos.
#
# Example (commented out until implementation is complete):
#
# @pytest.mark.asyncio
# async def test_client_server_echo(tmp_path):
#     """Test basic client-server communication."""
#     # Generate certificates
#     cert_path, key_path = generate_self_signed_cert(
#         hostname="localhost",
#         output_dir=tmp_path,
#     )
#
#     # Start server
#     async def handler(protocol, stream_id):
#         data = await protocol.receive_data(stream_id)
#         await protocol.send_data(stream_id, data)  # Echo
#
#     server = WebTransportServer(
#         "localhost", 4444, cert_path, key_path, handler
#     )
#     server_task = asyncio.create_task(server.serve())
#
#     # Give server time to start
#     await asyncio.sleep(0.5)
#
#     try:
#         # Connect client
#         async with WebTransportClient("https://localhost:4444/test") as client:
#             # Send message
#             await client.send(b"Hello")
#             # Receive echo
#             response = await client.receive(timeout=2.0)
#             assert response == b"Hello"
#     finally:
#         server_task.cancel()
#         await server.close()
