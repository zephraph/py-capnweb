"""End-to-end test for the calculator example."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add examples directory to path to locate the scripts
examples_dir = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(examples_dir))


@pytest.fixture
async def calculator_server():
    """Starts the calculator server as a subprocess."""
    server_path = examples_dir / "calculator" / "server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for the server to be ready
    await asyncio.sleep(3)

    yield process

    # Cleanup
    process.terminate()
    await process.wait()


@pytest.mark.asyncio
async def test_calculator_example(calculator_server):
    """
    Tests the calculator example by running the server and client in separate
    processes and verifying the client's output.
    """
    client_path = examples_dir / "calculator" / "client.py"
    # Use unbuffered output to ensure prints are captured before termination
    env = {"PYTHONUNBUFFERED": "1"}
    client_process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",  # Force unbuffered output
        str(client_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    # Let the client run for a few seconds to produce output
    await asyncio.sleep(3)
    client_process.terminate()

    # Capture and verify output
    stdout, stderr = await client_process.communicate()
    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    print("--- Client STDOUT ---")
    print(stdout_str)
    print("--- Client STDERR ---")
    print(stderr_str)

    assert not stderr_str, "Client process should not have errors"
    assert " + " in stdout_str, "Client should be printing additions"
    assert " = " in stdout_str, "Client should be printing results"
