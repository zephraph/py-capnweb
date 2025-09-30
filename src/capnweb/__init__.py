"""Cap'n Web Protocol - Python Implementation

This module provides a Python implementation of the Cap'n Web protocol,
a capability-based RPC system with promise pipelining.
"""

from capnweb.client import Client, ClientConfig
from capnweb.error import ErrorCode, RpcError
from capnweb.ids import ExportId, IdAllocator, ImportId
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

__version__ = "0.1.0"

__all__ = [
    # Client
    "Client",
    "ClientConfig",
    # Server
    "Server",
    "ServerConfig",
    # Core types
    "RpcTarget",
    "ImportId",
    "ExportId",
    "IdAllocator",
    # Errors
    "RpcError",
    "ErrorCode",
]
