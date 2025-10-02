import asyncio
from typing import Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class Calculator(RpcTarget):
    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "add":
                return args[0] + args[1]
            case "subtract":
                return args[0] - args[1]
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        msg = "Property access not implemented"
        raise RpcError.not_found(msg)


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
