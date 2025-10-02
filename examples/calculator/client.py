# ruff: noqa: S311

import asyncio
import random

from capnweb.client import Client, ClientConfig


async def main() -> None:
    config = ClientConfig(url="http://localhost:8080/rpc/batch")
    client = Client(config)

    try:
        # Make an RPC call
        while True:
            x = random.randint(0, 100)
            y = random.randint(0, 100)
            result = await client.call(0, "add", [x, y])
            print(f"{x} + {y} = {result}")
            await asyncio.sleep(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
