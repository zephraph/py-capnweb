"""WebTransport server example with calculator RPC.

This demonstrates a WebTransport/HTTP/3 server using Cap'n Web.

Features:
- HTTP/3/QUIC transport (faster than WebSocket)
- TLS 1.3 encryption
- Multiplexed bidirectional streams
- Calculator RPC target

Run:
    python examples/webtransport/server.py
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from capnweb.error import RpcError
from capnweb.types import RpcTarget
from capnweb.webtransport import WebTransportServer

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)


class Calculator(RpcTarget):
    """Simple calculator RPC target."""

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "add":
                if len(args) != 2:
                    msg = "add requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] + args[1]

            case "subtract":
                if len(args) != 2:
                    msg = "subtract requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] - args[1]

            case "multiply":
                if len(args) != 2:
                    msg = "multiply requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] * args[1]

            case "divide":
                if len(args) != 2:
                    msg = "divide requires 2 arguments"
                    raise RpcError.bad_request(msg)
                if args[1] == 0:
                    msg = "Cannot divide by zero"
                    raise RpcError.bad_request(msg)
                return args[0] / args[1]

            case _:
                msg = f"Method '{method}' not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        msg = f"Property '{property}' not found"
        raise RpcError.not_found(msg)


async def handle_session(protocol: Any, stream_id: int) -> None:
    """Handle a WebTransport session.

    Args:
        protocol: The WebTransport protocol instance
        stream_id: The stream ID for this session
    """
    logger.info("New session on stream %s", stream_id)

    Calculator()

    try:
        while True:
            # Receive request data
            data = await protocol.receive_data(stream_id, timeout=60.0)

            if not data:
                logger.info("Session %s closed by client", stream_id)
                break

            logger.debug(f"Received {len(data)} bytes on stream {stream_id}")

            # Parse NDJSON request
            # In a real implementation, we'd use the full RPC protocol
            # For this example, we'll do simple echo for now
            # TODO: Integrate with full Cap'n Web RPC protocol

            # Echo response (placeholder)
            response = data

            # Send response
            await protocol.send_data(stream_id, response)
            logger.debug(f"Sent {len(response)} bytes on stream {stream_id}")

    except TimeoutError:
        logger.info("Session %s timed out", stream_id)
    except Exception as e:
        logger.error("Error in session %s: %s", stream_id, e)
    finally:
        logger.info("Session %s ended", stream_id)


async def main() -> None:
    """Run the WebTransport server."""
    # Get certificate paths
    example_dir = Path(__file__).parent
    cert_path = example_dir / "localhost.crt"
    key_path = example_dir / "localhost.key"

    # Check if certificates exist
    if not cert_path.exists() or not key_path.exists():
        print("ERROR: SSL certificates not found!")
        print()
        print("Please generate certificates first:")
        print("  python examples/webtransport/generate_certs.py")
        print()
        print("Expected files:")
        print(f"  {cert_path}")
        print(f"  {key_path}")
        return

    # Create server
    host = "localhost"
    port = 4433

    print(f"Server listening on https://{host}:{port}/rpc/wt")
    print("Press Ctrl+C to stop")

    server = WebTransportServer(
        host=host,
        port=port,
        cert_path=cert_path,
        key_path=key_path,
        handler=handle_session,
    )

    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
