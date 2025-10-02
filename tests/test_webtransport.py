"""Tests for WebTransport functionality.

These tests verify the WebTransport client and server implementation.
"""

from __future__ import annotations

import pytest

# Check if WebTransport is available
try:
    from capnweb.webtransport import (
        WEBTRANSPORT_AVAILABLE,
        WebTransportClient,
        WebTransportServer,
    )
except ImportError:
    WEBTRANSPORT_AVAILABLE = False

from capnweb.certs import (
    generate_self_signed_cert,
    load_certificate,
    load_private_key,
    verify_certificate,
)
from capnweb.transports import (
    HttpBatchTransport,
    WebTransportTransport,
    create_transport,
)

pytestmark = pytest.mark.skipif(
    not WEBTRANSPORT_AVAILABLE,
    reason="WebTransport requires aioquic library",
)


class TestCertificateGeneration:
    """Test certificate generation utilities."""

    def test_generate_self_signed_cert(self, tmp_path):
        """Test generating self-signed certificates."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="localhost",
            key_size=2048,
            validity_days=30,
            output_dir=tmp_path,
        )

        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.name == "localhost.crt"
        assert key_path.name == "localhost.key"

        # Verify certificate can be loaded
        cert = load_certificate(cert_path)
        key = load_private_key(key_path)

        assert cert is not None
        assert key is not None

    def test_generate_cert_with_custom_hostname(self, tmp_path):
        """Test generating certificates with custom hostname."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="example.com",
            output_dir=tmp_path,
        )

        assert cert_path.name == "example.com.crt"
        assert key_path.name == "example.com.key"

    def test_verify_certificate(self, tmp_path):
        """Test certificate verification."""
        cert_path, _ = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Should verify for localhost
        assert verify_certificate(cert, "localhost")

        # Should not verify for different hostname
        assert not verify_certificate(cert, "example.com")


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
