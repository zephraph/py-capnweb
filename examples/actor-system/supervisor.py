"""Supervisor actor that creates and manages worker actors.

This demonstrates dynamic capability creation and registration.
The supervisor can spawn new workers and return capabilities to them.

Run:
    python examples/actor-system/supervisor.py
"""

import asyncio
from typing import Any

from capnweb.error import RpcError
from capnweb.hooks import TargetStubHook
from capnweb.server import Server, ServerConfig
from capnweb.stubs import RpcStub
from capnweb.types import RpcTarget

from worker import Worker


class Supervisor(RpcTarget):
    """A supervisor actor that can create and manage other actors (Workers).

    This demonstrates dynamic capability creation and registration.
    """

    def __init__(self, server: Server):
        # The supervisor needs a reference to its own server
        # to register new capabilities (workers).
        self._server = server
        self._workers: dict[str, Worker] = {}
        # Export IDs > 0 are used for dynamically created capabilities.
        # ID 0 is reserved for the main capability (the supervisor itself).
        self._next_export_id = 1

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle messages sent to the supervisor."""
        match method:
            case "spawn_worker":
                name = args[0]
                if name in self._workers:
                    msg = f"Worker with name '{name}' already exists"
                    raise RpcError.bad_request(msg)

                # 1. Create the new worker actor instance.
                worker = Worker(name)

                # 2. Register the new worker with the server, getting a new export ID.
                export_id = self._next_export_id
                self._server.register_capability(export_id, worker)
                self._next_export_id += 1
                self._workers[name] = worker

                print(f"Supervisor spawned worker '{name}' with export ID {export_id}")

                # 3. Create a stub wrapping the worker so the serializer can export it.
                #    The server's serializer will convert this RpcStub to an export reference.
                #    Return the stub directly - client will get an RpcStub on their side.
                hook = TargetStubHook(worker)
                worker_stub = RpcStub(hook)
                return worker_stub

            case "list_workers":
                return list(self._workers.keys())
            case _:
                msg = f"Supervisor method '{method}' not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "worker_count":
                return len(self._workers)
            case _:
                msg = f"Supervisor property '{property}' not found"
                raise RpcError.not_found(msg)


async def main() -> None:
    """Run the supervisor server."""
    port = 8080
    config = ServerConfig(host="127.0.0.1", port=port)
    server = Server(config)

    # The supervisor needs a reference to the server to register new workers.
    supervisor = Supervisor(server)
    server.register_capability(0, supervisor)

    await server.start()
    print(f"Supervisor listening on http://127.0.0.1:{port}/rpc/batch")
    print("Press Ctrl+C to stop")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down supervisor...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
