"""Integrated WebTransport server example.

This demonstrates the Cap'n Web Server with WebTransport support enabled.
The server serves both HTTP batch and WebTransport simultaneously.

Run:
    python examples/webtransport-integrated/server.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class Calculator(RpcTarget):
    """Simple calculator RPC target."""

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "add":
                if len(args) != 2:
                    raise RpcError.bad_request("add requires 2 arguments")
                return args[0] + args[1]

            case "subtract":
                if len(args) != 2:
                    raise RpcError.bad_request("subtract requires 2 arguments")
                return args[0] - args[1]

            case "multiply":
                if len(args) != 2:
                    raise RpcError.bad_request("multiply requires 2 arguments")
                return args[0] * args[1]

            case "divide":
                if len(args) != 2:
                    raise RpcError.bad_request("divide requires 2 arguments")
                if args[1] == 0:
                    raise RpcError.bad_request("Cannot divide by zero")
                return args[0] / args[1]

            case _:
                raise RpcError.not_found(f"Method '{method}' not found")

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        raise RpcError.not_found(f"Property '{property}' not found")


async def main() -> None:
    """Run the integrated server with WebTransport support."""
    # Get certificate paths
    example_dir = Path(__file__).parent
    cert_path = example_dir / "localhost.crt"
    key_path = example_dir / "localhost.key"

    # Check if certificates exist
    if not cert_path.exists() or not key_path.exists():
        print("ERROR: SSL certificates not found!")
        print()
        print("Please generate certificates first:")
        print("  python examples/webtransport-integrated/generate_certs.py")
        print()
        print("Expected files:")
        print(f"  {cert_path}")
        print(f"  {key_path}")
        return

    # Create server config with WebTransport enabled
    config = ServerConfig(
        host="localhost",
        port=8080,
        enable_webtransport=True,
        webtransport_port=4433,
        webtransport_cert_path=str(cert_path),
        webtransport_key_path=str(key_path),
    )

    # Create and start server
    server = Server(config)

    # Register calculator at export ID 0
    server.register_capability(0, Calculator())

    try:
        async with server:
            print()
            print("Server is running:")
            print(f"  HTTP:         http://localhost:{config.port}/rpc/batch")
            print(
                f"  WebTransport: https://localhost:{config.webtransport_port}/rpc/wt"
            )
            print()
            print("Press Ctrl+C to stop")

            # Keep running
            await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    asyncio.run(main())
