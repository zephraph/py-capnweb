"""Worker actor implementation.

This file defines a simple, stateful worker actor that maintains a count
and knows its own name and process ID.
"""

import os
from typing import Any

from capnweb.error import RpcError
from capnweb.types import RpcTarget


class Worker(RpcTarget):
    """A simple, stateful worker actor.

    It maintains a name, a private counter, and knows its process ID.
    """

    def __init__(self, name: str):
        self._name = name
        self._count = 0
        self._pid = os.getpid()
        print(f"  [Worker '{self._name}' created in PID {self._pid}]")

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle messages sent to this worker."""
        match method:
            case "increment":
                self._count += 1
                return self._count
            case "get_count":
                return self._count
            case _:
                msg = f"Worker method '{method}' not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Allow access to read-only properties."""
        match property:
            case "name":
                return self._name
            case "pid":
                return self._pid
            case _:
                msg = f"Worker property '{property}' not found"
                raise RpcError.not_found(msg)
