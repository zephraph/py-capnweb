"""WebTransport client example demonstrating RPC over HTTP/3.

This demonstrates a WebTransport/HTTP/3 client using Cap'n Web.

Features:
- HTTP/3/QUIC transport (faster than WebSocket)
- TLS 1.3 encryption
- Multiplexed bidirectional streams
- Calculator RPC calls

Run:
    python examples/webtransport/client.py
"""

from __future__ import annotations

import asyncio
import logging
import traceback

from capnweb.webtransport import WebTransportClient

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the WebTransport client demo."""
    url = "https://localhost:4433/rpc/wt"

    print("--- WebTransport Calculator Demo ---")
    print(f"Connecting to {url}...")

    try:
        async with WebTransportClient(url, verify_mode=False) as client:
            print("✅ Connected!\n")

            # Simple echo test
            print("1. Testing connection with echo:")
            test_msg = b"Hello, WebTransport!"
            await client.send(test_msg)
            response = await client.receive(timeout=5.0)
            print(f"   Sent:     {test_msg.decode()}")
            print(f"   Received: {response.decode()}")

            print("\n2. Testing concurrent requests (multiplexing):")
            # Send multiple messages concurrently
            messages = [
                b"Message 1",
                b"Message 2",
                b"Message 3",
            ]

            # Send all messages
            for msg in messages:
                await client.send(msg)
                print(f"   Sent: {msg.decode()}")

            # Receive all responses
            for _i in range(len(messages)):
                response = await client.receive(timeout=5.0)
                print(f"   Received: {response.decode()}")

            print("\n✅ Demo completed successfully!")

    except TimeoutError:
        print("\n❌ Connection timed out")
        print("   Make sure the server is running:")
        print("   python examples/webtransport/server.py")

    except ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        print("   Make sure the server is running:")
        print("   python examples/webtransport/server.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
