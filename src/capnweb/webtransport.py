"""WebTransport implementation for Cap'n Web.

This module provides WebTransport server and client using aioquic.
WebTransport offers high-performance bidirectional communication over HTTP/3/QUIC.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlparse

from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.h3.connection import H3Connection

try:
    from aioquic.asyncio import QuicConnectionProtocol, connect, serve
    from aioquic.h3.connection import H3Connection
    from aioquic.h3.events import (
        DataReceived,
        H3Event,
        HeadersReceived,
        WebTransportStreamDataReceived,
    )
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.events import StreamDataReceived

    WEBTRANSPORT_AVAILABLE = True
except ImportError:
    WEBTRANSPORT_AVAILABLE = False

if TYPE_CHECKING:
    from aioquic.quic.events import QuicEvent

logger = logging.getLogger(__name__)


class WebTransportClientProtocol(QuicConnectionProtocol):
    """QUIC client protocol for WebTransport."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._http: H3Connection | None = None
        self._receive_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream_id: int | None = None
        self._session_id: int | None = None

    def quic_event_received(self, event: QuicEvent) -> None:
        """Handle QUIC events.

        Args:
            event: QUIC event from the connection
        """
        if self._http is None:
            self._http = H3Connection(self._quic)

        # Process through H3
        for h3_event in self._http.handle_event(event):
            self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        """Handle HTTP/3 events.

        Args:
            event: HTTP/3 event
        """
        if isinstance(event, HeadersReceived):
            # WebTransport session established
            logger.debug(
                f"WebTransport session established on stream {event.stream_id}"
            )
            self._session_id = event.stream_id

        elif isinstance(event, (DataReceived, WebTransportStreamDataReceived)):
            # Received data on a stream
            logger.debug(
                f"Received {len(event.data)} bytes on stream {event.stream_id}"
            )
            self._receive_queue.put_nowait(event.data)

    async def send_data(self, data: bytes) -> None:
        """Send data on a WebTransport stream.

        Args:
            data: Data to send
        """
        if self._http is None:
            self._http = H3Connection(self._quic)

        # Create bidirectional stream if needed
        if self._stream_id is None:
            self._stream_id = self._quic.get_next_available_stream_id(
                is_unidirectional=False
            )

        # Send data
        self._http._quic.send_stream_data(self._stream_id, data, end_stream=False)
        self.transmit()

    async def receive_data(self, timeout: float | None = None) -> bytes:
        """Receive data from WebTransport stream.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Received data

        Raises:
            asyncio.TimeoutError: If timeout expires
        """
        if timeout:
            return await asyncio.wait_for(self._receive_queue.get(), timeout=timeout)
        return await self._receive_queue.get()


class WebTransportServerProtocol(QuicConnectionProtocol):
    """QUIC server protocol for WebTransport."""

    def __init__(self, *args: Any, handler: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._http: H3Connection | None = None
        self._handler = handler
        self._sessions: dict[int, asyncio.Queue[bytes]] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        """Handle QUIC events.

        Args:
            event: QUIC event from the connection
        """
        if self._http is None:
            self._http = H3Connection(self._quic, enable_webtransport=True)

        # Process through H3
        for h3_event in self._http.handle_event(event):
            self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        """Handle HTTP/3 events.

        Args:
            event: HTTP/3 event
        """
        if isinstance(event, HeadersReceived):
            # New WebTransport session request
            logger.info(f"WebTransport session request on stream {event.stream_id}")

            # Accept the WebTransport session
            if self._http:
                self._http.send_headers(
                    stream_id=event.stream_id,
                    headers=[
                        (b":status", b"200"),
                        (b"sec-webtransport-http3-draft", b"draft02"),
                    ],
                )
                self.transmit()

            # Create queue for this session
            self._sessions[event.stream_id] = asyncio.Queue()

            # Notify handler if available
            if self._handler:
                asyncio.create_task(self._handler(self, event.stream_id))

        elif isinstance(event, (DataReceived, WebTransportStreamDataReceived)):
            # Data received on stream
            logger.debug(
                f"Received {len(event.data)} bytes on stream {event.stream_id}"
            )

            # Find the session this stream belongs to
            # For simplicity, we'll use the stream_id directly
            # In a real implementation, we'd track which streams belong to which session
            if event.stream_id in self._sessions:
                self._sessions[event.stream_id].put_nowait(event.data)

    async def send_data(self, stream_id: int, data: bytes) -> None:
        """Send data on a WebTransport stream.

        Args:
            stream_id: Stream ID to send on
            data: Data to send
        """
        if self._http:
            self._http._quic.send_stream_data(stream_id, data, end_stream=False)
            self.transmit()

    async def receive_data(self, stream_id: int, timeout: float | None = None) -> bytes:
        """Receive data from a WebTransport stream.

        Args:
            stream_id: Stream ID to receive from
            timeout: Optional timeout in seconds

        Returns:
            Received data

        Raises:
            asyncio.TimeoutError: If timeout expires
            KeyError: If stream doesn't exist
        """
        if stream_id not in self._sessions:
            msg = f"Stream {stream_id} not found"
            raise KeyError(msg)

        queue = self._sessions[stream_id]
        if timeout:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        return await queue.get()


class WebTransportClient:
    """WebTransport client for Cap'n Web.

    Example:
        ```python
        async with WebTransportClient("https://localhost:4433/rpc/wt") as client:
            await client.send(b"hello")
            response = await client.receive()
        ```
    """

    def __init__(
        self,
        url: str,
        cert_path: str | None = None,
        verify_mode: bool = False,
    ) -> None:
        """Initialize WebTransport client.

        Args:
            url: WebTransport URL (must use https://)
            cert_path: Path to CA certificate for verification
            verify_mode: Whether to verify server certificate (default: False for development)
        """
        if not WEBTRANSPORT_AVAILABLE:
            msg = "WebTransport requires aioquic: pip install aioquic"
            raise RuntimeError(msg)

        self.url = url
        self.cert_path = cert_path
        self.verify_mode = verify_mode
        self._protocol: WebTransportClientProtocol | None = None
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager."""
        await self.close()

    async def connect(self) -> None:
        """Establish WebTransport connection."""
        # Parse URL
        parsed = urlparse(self.url)
        if parsed.scheme != "https":
            msg = "WebTransport requires HTTPS URL"
            raise ValueError(msg)

        host = parsed.hostname or "localhost"
        port = parsed.port or 4433

        # Create QUIC configuration
        configuration = QuicConfiguration(
            is_client=True,
            alpn_protocols=["h3"],
        )

        if not self.verify_mode:
            configuration.verify_mode = False
        elif self.cert_path:
            configuration.load_verify_locations(self.cert_path)

        # Connect
        logger.info("Connecting to %s:%s", host, port)

        # Store protocol for later use
        async def run_client() -> None:
            async with connect(
                host,
                port,
                configuration=configuration,
                create_protocol=WebTransportClientProtocol,
            ) as protocol:
                self._protocol = protocol
                # Keep connection alive
                await asyncio.Event().wait()

        self._task = asyncio.create_task(run_client())

        # Wait a bit for connection to establish
        await asyncio.sleep(0.2)

    async def send(self, data: bytes) -> None:
        """Send data over WebTransport.

        Args:
            data: Data to send

        Raises:
            RuntimeError: If not connected
        """
        if not self._protocol:
            msg = "Not connected"
            raise RuntimeError(msg)

        await self._protocol.send_data(data)

    async def receive(self, timeout: float | None = None) -> bytes:
        """Receive data from WebTransport.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Received data

        Raises:
            RuntimeError: If not connected
            asyncio.TimeoutError: If timeout expires
        """
        if not self._protocol:
            msg = "Not connected"
            raise RuntimeError(msg)

        return await self._protocol.receive_data(timeout=timeout)

    async def send_and_receive(
        self, data: bytes, timeout: float | None = None
    ) -> bytes:
        """Send data and wait for response.

        Args:
            data: Data to send
            timeout: Optional timeout in seconds

        Returns:
            Response data
        """
        await self.send(data)
        return await self.receive(timeout=timeout)

    async def close(self) -> None:
        """Close the WebTransport connection."""
        if self._protocol:
            self._protocol._quic.close()
            self._protocol = None

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None


class WebTransportServer:
    """WebTransport server for Cap'n Web.

    Example:
        ```python
        async def handler(protocol, stream_id):
            data = await protocol.receive_data(stream_id)
            await protocol.send_data(stream_id, b"response")

        server = WebTransportServer("localhost", 4433, cert_path, key_path, handler)
        await server.serve()
        ```
    """

    def __init__(
        self,
        host: str,
        port: int,
        cert_path: str | Path,
        key_path: str | Path,
        handler: Any = None,
    ) -> None:
        """Initialize WebTransport server.

        Args:
            host: Host to bind to
            port: Port to bind to
            cert_path: Path to SSL certificate
            key_path: Path to SSL private key
            handler: Async handler function(protocol, stream_id)
        """
        if not WEBTRANSPORT_AVAILABLE:
            msg = "WebTransport requires aioquic: pip install aioquic"
            raise RuntimeError(msg)

        self.host = host
        self.port = port
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.handler = handler
        self._server: Any = None  # QuicServer from aioquic

    async def serve(self) -> None:
        """Start serving WebTransport connections.

        This method runs forever until the server is closed.
        """
        # Create QUIC configuration
        configuration = QuicConfiguration(
            is_client=False,
            alpn_protocols=["h3"],
        )

        # Load certificate and key
        configuration.load_cert_chain(str(self.cert_path), str(self.key_path))

        # Create protocol factory
        def create_protocol(*args: Any, **kwargs: Any) -> WebTransportServerProtocol:
            return WebTransportServerProtocol(*args, handler=self.handler, **kwargs)

        # Start server
        logger.info("Starting WebTransport server on %s:%s", self.host, self.port)

        self._server = await serve(
            self.host,
            self.port,
            configuration=configuration,
            create_protocol=create_protocol,
        )

        # Wait forever (server runs in background)
        await asyncio.Event().wait()

    async def close(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
