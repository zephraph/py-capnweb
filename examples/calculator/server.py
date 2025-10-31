import asyncio

from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class Calculator(RpcTarget):
    """Calculator service using automatic method dispatch.

    Methods are automatically exposed as RPC endpoints.
    No need for manual call() implementation with match/case.
    """

    async def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    async def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b


async def main() -> None:
    config = ServerConfig(host="127.0.0.1", port=8080)
    server = Server(config)

    # Register the main capability
    server.register_capability(0, Calculator())

    await server.start()

    print("Calculator server listening on http://127.0.0.1:8080/rpc/batch")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
