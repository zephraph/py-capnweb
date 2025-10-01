"""Tests for promise pipelining functionality."""

import asyncio
from typing import Any

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.pipeline import PipelinePromise
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class UserService(RpcTarget):
    """Test service for user-related operations."""

    def __init__(self) -> None:
        self.users = {
            "token-123": {"id": 1, "name": "Alice"},
            "token-456": {"id": 2, "name": "Bob"},
        }
        self.profiles = {
            1: {"id": 1, "bio": "Software engineer"},
            2: {"id": 2, "bio": "Product manager"},
        }
        self.notifications = {
            1: ["You have 3 new messages", "System update available"],
            2: ["Meeting in 10 minutes"],
        }

    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "authenticate":
                token = args[0]
                user = self.users.get(token)
                if not user:
                    msg = f"Invalid token: {token}"
                    raise RpcError.not_found(msg)
                return user

            case "getUserProfile":
                user_id = args[0]
                profile = self.profiles.get(user_id)
                if not profile:
                    msg = f"Profile not found for user {user_id}"
                    raise RpcError.not_found(msg)
                return profile

            case "getNotifications":
                user_id = args[0]
                notifications = self.notifications.get(user_id, [])
                return notifications

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:  # noqa: ARG002
        msg = "Property access not implemented"
        raise RpcError.not_found(msg)


class TestPipelineBatch:
    """Tests for PipelineBatch class."""

    async def test_basic_pipeline(self) -> None:
        """Test basic pipelining without dependencies."""
        config = ServerConfig(host="127.0.0.1", port=18100)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18100/rpc/batch")
            async with Client(client_config) as client:
                # Create a pipeline batch
                batch = client.pipeline()

                # Make calls that don't depend on each other
                user1 = batch.call(0, "authenticate", ["token-123"])
                user2 = batch.call(0, "authenticate", ["token-456"])

                # Await both
                u1, u2 = await asyncio.gather(user1, user2)

                assert u1["id"] == 1
                assert u1["name"] == "Alice"
                assert u2["id"] == 2
                assert u2["name"] == "Bob"

        finally:
            await server.stop()

    async def test_pipeline_with_property_access(self) -> None:
        """Test pipelining with property access (not yet fully implemented)."""
        config = ServerConfig(host="127.0.0.1", port=18101)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18101/rpc/batch")
            async with Client(client_config) as client:
                # Create a pipeline batch
                batch = client.pipeline()

                # Make dependent calls - add all before awaiting
                user = batch.call(0, "authenticate", ["token-123"])

                # Access property on promise
                # Note: This creates a PipelinePromise but execution is sequential for now
                user_id_promise = user.id  # noqa: F841

                # Await the user
                u = await user

                # Create a new batch for the second call
                batch2 = client.pipeline()
                profile = batch2.call(0, "getUserProfile", [u["id"]])
                p = await profile

                assert u["id"] == 1
                assert p["bio"] == "Software engineer"

        finally:
            await server.stop()

    async def test_pipeline_error_handling(self) -> None:
        """Test error handling in pipelined calls."""
        config = ServerConfig(host="127.0.0.1", port=18102)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18102/rpc/batch")
            async with Client(client_config) as client:
                batch = client.pipeline()

                # Make a call that will fail
                invalid_user = batch.call(0, "authenticate", ["invalid-token"])

                with pytest.raises(RpcError) as exc_info:
                    await invalid_user

                assert exc_info.value.code.value == "not_found"

        finally:
            await server.stop()

    async def test_multiple_awaits_same_promise(self) -> None:
        """Test that awaiting the same promise multiple times works."""
        config = ServerConfig(host="127.0.0.1", port=18103)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18103/rpc/batch")
            async with Client(client_config) as client:
                batch = client.pipeline()
                user = batch.call(0, "authenticate", ["token-123"])

                # Await the same promise twice
                u1 = await user
                u2 = await user

                assert u1 == u2
                assert u1["id"] == 1

        finally:
            await server.stop()

    async def test_pipeline_with_asyncio_gather(self) -> None:
        """Test pipelining with asyncio.gather."""
        config = ServerConfig(host="127.0.0.1", port=18104)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18104/rpc/batch")
            async with Client(client_config) as client:
                # First batch for authentication
                batch1 = client.pipeline()
                user = batch1.call(0, "authenticate", ["token-123"])
                u = await user

                # Second batch for profile and notifications
                batch2 = client.pipeline()
                profile = batch2.call(0, "getUserProfile", [u["id"]])
                notifications = batch2.call(0, "getNotifications", [u["id"]])

                # Gather results from the second batch
                p, n = await asyncio.gather(profile, notifications)

                assert p["bio"] == "Software engineer"
                assert len(n) == 2
                assert n[0] == "You have 3 new messages"

        finally:
            await server.stop()


class TestPipelinePromise:
    """Tests for PipelinePromise class."""

    async def test_promise_property_access(self) -> None:
        """Test property access on pipeline promises."""
        config = ServerConfig(host="127.0.0.1", port=18105)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18105/rpc/batch")
            async with Client(client_config) as client:
                batch = client.pipeline()
                user = batch.call(0, "authenticate", ["token-123"])

                # Access property - creates a PipelinePromise
                user_id = user.id
                user_name = user.name

                # These are PipelinePromise objects

                assert isinstance(user_id, PipelinePromise)
                assert isinstance(user_name, PipelinePromise)

        finally:
            await server.stop()

    async def test_promise_chained_property_access(self) -> None:
        """Test chained property access on promises."""
        config = ServerConfig(host="127.0.0.1", port=18106)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18106/rpc/batch")
            async with Client(client_config) as client:
                batch = client.pipeline()
                user = batch.call(0, "authenticate", ["token-123"])

                # Chained property access
                # This creates pipeline references but doesn't execute yet
                prop1 = user.profile
                prop2 = prop1.settings

                assert isinstance(prop2, PipelinePromise)

        finally:
            await server.stop()


class TestPipelineIntegration:
    """Integration tests for pipelining."""

    async def test_realistic_workflow(self) -> None:
        """Test a realistic pipelined workflow."""
        config = ServerConfig(host="127.0.0.1", port=18107)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18107/rpc/batch")
            async with Client(client_config) as client:
                # Step 1: Authenticate
                batch1 = client.pipeline()
                user = batch1.call(0, "authenticate", ["token-123"])
                u = await user

                # Step 2: Fetch profile and notifications in one batch
                batch2 = client.pipeline()
                profile = batch2.call(0, "getUserProfile", [u["id"]])
                notifications = batch2.call(0, "getNotifications", [u["id"]])

                p, n = await asyncio.gather(profile, notifications)

                # Verify results
                assert u["name"] == "Alice"
                assert p["bio"] == "Software engineer"
                assert "You have 3 new messages" in n

        finally:
            await server.stop()

    async def test_mixed_pipeline_and_regular_calls(self) -> None:
        """Test mixing pipelined and regular calls."""
        config = ServerConfig(host="127.0.0.1", port=18108)
        server = Server(config)
        server.register_capability(0, UserService())

        await server.start()

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18108/rpc/batch")
            async with Client(client_config) as client:
                # Regular call
                user1 = await client.call(0, "authenticate", ["token-123"])

                # Pipelined calls
                batch = client.pipeline()
                profile = batch.call(0, "getUserProfile", [user1["id"]])
                notifications = batch.call(0, "getNotifications", [user1["id"]])

                p, n = await asyncio.gather(profile, notifications)

                assert user1["id"] == 1
                assert p["id"] == 1
                assert isinstance(n, list)

        finally:
            await server.stop()
