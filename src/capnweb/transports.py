"""Transport implementations for Cap'n Web protocol.

This module provides concrete implementations of the Transport protocol
for different communication methods (HTTP batch, WebSocket, WebTransport).
"""

from __future__ import annotations

from typing import Any, Self

import aiohttp

# Optional WebTransport support
try:
    from capnweb.webtransport import WebTransportClient

    WEBTRANSPORT_AVAILABLE = True
except ImportError:
    WEBTRANSPORT_AVAILABLE = False


class HttpBatchTransport:
    """HTTP batch transport implementation.

    Sends and receives batches of RPC messages over HTTP POST requests.
    Each request contains a newline-delimited JSON batch.
    """

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        """Initialize the HTTP batch transport.

        Args:
            url: The URL endpoint for batch RPC (e.g., "http://localhost:8080/rpc/batch")
            timeout: Request timeout in seconds
        """
        self.url = url
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def send(self, data: bytes) -> None:
        """Send a batch request.

        Args:
            data: Newline-delimited JSON batch data

        Raises:
            RuntimeError: If transport is not open
            aiohttp.ClientError: If request fails
        """
        if not self._session:
            msg = "Transport not open - use async context manager"
            raise RuntimeError(msg)

        # For HTTP batch, we don't actually send immediately
        # Instead, we store the data to be sent with receive()
        # This is because HTTP is request-response based
        self._pending_data = data

    async def receive(self) -> bytes:
        """Send request and receive response.

        Returns:
            Response batch data

        Raises:
            RuntimeError: If transport is not open or no data to send
            aiohttp.ClientError: If request fails
        """
        if not self._session:
            msg = "Transport not open"
            raise RuntimeError(msg)

        if not hasattr(self, "_pending_data"):
            msg = "No data to send - call send() first"
            raise RuntimeError(msg)

        data = self._pending_data
        delattr(self, "_pending_data")

        async with self._session.post(
            self.url,
            data=data,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as response:
            response.raise_for_status()
            return await response.read()

    async def close(self) -> None:
        """Close the transport connection."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send_and_receive(self, data: bytes) -> bytes:
        """Convenience method to send and receive in one call.

        Args:
            data: Data to send

        Returns:
            Response data
        """
        await self.send(data)
        return await self.receive()


class WebSocketTransport:
    """WebSocket transport implementation.

    Provides bidirectional streaming RPC over WebSocket connections.
    """

    def __init__(self, url: str) -> None:
        """Initialize the WebSocket transport.

        Args:
            url: The WebSocket URL (e.g., "ws://localhost:8080/rpc/ws")
        """
        self.url = url
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url)
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def send(self, data: bytes) -> None:
        """Send data over WebSocket.

        Args:
            data: Data to send

        Raises:
            RuntimeError: If transport is not connected
        """
        if not self._ws:
            msg = "WebSocket not connected"
            raise RuntimeError(msg)

        await self._ws.send_bytes(data)

    async def receive(self) -> bytes:
        """Receive data from WebSocket.

        Returns:
            Received data

        Raises:
            RuntimeError: If transport is not connected
            ConnectionError: If WebSocket is closed
        """
        if not self._ws:
            msg = "WebSocket not connected"
            raise RuntimeError(msg)

        msg = await self._ws.receive()

        if msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data.encode("utf-8")
        if msg.type == aiohttp.WSMsgType.CLOSE:
            msg = "WebSocket closed"
            raise ConnectionError(msg)
        if msg.type == aiohttp.WSMsgType.ERROR:
            msg = f"WebSocket error: {self._ws.exception()}"
            raise ConnectionError(msg)
        msg = f"Unexpected message type: {msg.type}"
        raise ValueError(msg)

    async def send_and_receive(self, data: bytes) -> bytes:
        """Send data and receive response (convenience method).

        Args:
            data: Data to send

        Returns:
            Response data
        """
        await self.send(data)
        return await self.receive()

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None


class WebTransportTransport:
    """WebTransport transport implementation.

    Provides high-performance bidirectional streaming over HTTP/3 using QUIC.

    Features:
    - Multiplexed streams over a single QUIC connection
    - 0-RTT reconnection support
    - Better performance than WebSocket
    - Built-in congestion control

    Note: Requires aioquic to be installed (pip install aioquic)
    """

    def __init__(
        self,
        url: str,
        cert_path: str | None = None,
        verify_mode: bool = False,
    ) -> None:
        """Initialize the WebTransport transport.

        Args:
            url: The WebTransport URL (e.g., "https://localhost:4433/rpc/wt")
            cert_path: Path to CA certificate for verification (None to skip)
            verify_mode: Whether to verify server certificate (default: False)
        """
        if not WEBTRANSPORT_AVAILABLE:
            msg = "WebTransport requires aioquic library: pip install aioquic"
            raise RuntimeError(msg)

        self._client = WebTransportClient(url, cert_path, verify_mode)

    async def __aenter__(self) -> Self:
        """Async context manager entry - establishes WebTransport connection."""
        await self._client.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit - closes connection."""
        await self.close()

    async def send(self, data: bytes) -> None:
        """Send data over WebTransport stream.

        Args:
            data: Data to send

        Raises:
            RuntimeError: If not connected
        """
        await self._client.send(data)

    async def receive(self) -> bytes:
        """Receive data from WebTransport stream.

        Returns:
            Received data

        Raises:
            RuntimeError: If not connected
            ConnectionError: If connection is closed
        """
        return await self._client.receive()

    async def send_and_receive(self, data: bytes) -> bytes:
        """Send data and receive response.

        Args:
            data: Data to send

        Returns:
            Response data
        """
        return await self._client.send_and_receive(data)

    async def close(self) -> None:
        """Close the WebTransport connection."""
        await self._client.close()


def create_transport(
    url: str, **kwargs: Any
) -> HttpBatchTransport | WebSocketTransport | WebTransportTransport:
    """Factory function to create appropriate transport based on URL.

    Args:
        url: The endpoint URL
        **kwargs: Additional transport-specific options

    Returns:
        Appropriate transport implementation

    Examples:
        >>> transport = create_transport("http://localhost:8080/rpc/batch")
        >>> transport = create_transport("ws://localhost:8080/rpc/ws")
        >>> transport = create_transport("https://localhost:4433/rpc/wt")
    """
    if url.startswith(("ws://", "wss://")):
        return WebSocketTransport(url)
    if url.startswith("http://"):
        timeout = kwargs.get("timeout", 30.0)
        return HttpBatchTransport(url, timeout=timeout)
    if url.startswith("https://"):
        # For HTTPS, check if it's WebTransport or HTTP batch
        # WebTransport URLs typically have a /wt path or use port 4433
        if "/wt" in url or ":4433" in url:
            cert_path = kwargs.get("cert_path")
            verify_mode = kwargs.get("verify_mode", True)
            return WebTransportTransport(
                url, cert_path=cert_path, verify_mode=verify_mode
            )
        # Otherwise, treat as HTTP batch
        timeout = kwargs.get("timeout", 30.0)
        return HttpBatchTransport(url, timeout=timeout)
    msg = f"Unsupported URL scheme: {url}"
    raise ValueError(msg)
