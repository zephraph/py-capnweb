"""Integrated WebTransport client example.

This demonstrates the Cap'n Web Client using WebTransport URL.
The Client auto-detects WebTransport based on the URL.

Run:
    python examples/webtransport-integrated/client.py
"""

from __future__ import annotations

import asyncio
import traceback

from capnweb.client import Client, ClientConfig


async def main() -> None:
    """Run the WebTransport client demo."""
    # WebTransport URL - Client auto-detects transport
    url = "https://localhost:4433/rpc/wt"

    print("--- WebTransport Calculator Demo (Integrated) ---")
    print(f"Connecting to {url}...")
    print()

    config = ClientConfig(url=url)

    try:
        async with Client(config) as client:
            print("✅ Connected via WebTransport!\n")

            # Test calculations
            print("1. Basic arithmetic:")
            result1 = await client.call(0, "add", [5, 3])
            print(f"   5 + 3 = {result1}")

            result2 = await client.call(0, "subtract", [10, 4])
            print(f"   10 - 4 = {result2}")

            result3 = await client.call(0, "multiply", [7, 6])
            print(f"   7 × 6 = {result3}")

            result4 = await client.call(0, "divide", [20, 4])
            print(f"   20 ÷ 4 = {result4}")

            # Concurrent requests (demonstrating multiplexing)
            print("\n2. Concurrent requests (WebTransport multiplexing):")
            tasks = [
                client.call(0, "add", [100, 50]),
                client.call(0, "subtract", [200, 75]),
                client.call(0, "multiply", [25, 4]),
            ]
            results: list[int] = list(await asyncio.gather(*tasks))  # type: ignore[arg-type]
            print(f"   100 + 50 = {results[0]}")
            print(f"   200 - 75 = {results[1]}")
            print(f"   25 × 4 = {results[2]}")

            print("\n✅ Demo completed successfully!")
            print()
            print("Benefits of WebTransport:")
            print(
                "  - Multiplexed streams (concurrent requests without head-of-line blocking)"
            )
            print("  - Better performance over lossy networks (QUIC protocol)")
            print("  - 0-RTT reconnection support")
            print("  - Built on HTTP/3")

    except ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        print()
        print("Make sure the server is running:")
        print("  python examples/webtransport-integrated/server.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
