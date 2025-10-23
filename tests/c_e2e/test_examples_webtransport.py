"""End-to-end tests for the WebTransport examples."""

import asyncio
import sys
from pathlib import Path

import pytest

# Add examples directory to path to locate the scripts
examples_dir = Path(__file__).parent.parent.parent / "examples"
sys.path.insert(0, str(examples_dir))

# --- Fixtures for Standalone WebTransport Example ---


@pytest.fixture(scope="module")
async def webtransport_certs():
    """Generate certificates for the standalone webtransport example."""
    cert_script_path = examples_dir / "webtransport" / "generate_certs.py"
    proc = await asyncio.create_subprocess_exec(sys.executable, str(cert_script_path))
    await proc.wait()
    assert proc.returncode == 0, "Certificate generation script failed"
    return
    # No cleanup needed for certs


@pytest.fixture
async def webtransport_server(webtransport_certs):
    """Starts the standalone webtransport server as a subprocess."""
    server_path = examples_dir / "webtransport" / "server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.sleep(3)
    yield process
    process.terminate()
    await process.wait()


# --- Fixtures for Integrated WebTransport Example ---


@pytest.fixture(scope="module")
async def webtransport_integrated_certs():
    """Generate certificates for the integrated webtransport example."""
    cert_script_path = examples_dir / "webtransport-integrated" / "generate_certs.py"
    proc = await asyncio.create_subprocess_exec(sys.executable, str(cert_script_path))
    await proc.wait()
    assert proc.returncode == 0, "Certificate generation script failed"
    return


@pytest.fixture
async def webtransport_integrated_server(webtransport_integrated_certs):
    """Starts the integrated webtransport server as a subprocess."""
    server_path = examples_dir / "webtransport-integrated" / "server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.sleep(3)
    yield process
    process.terminate()
    await process.wait()


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="WebTransport has protocol issues with self-signed certs in test environment"
)
async def test_webtransport_standalone_example(webtransport_server):
    """Tests the standalone WebTransport example."""
    client_path = examples_dir / "webtransport" / "client.py"
    client_process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(client_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            client_process.communicate(), timeout=20
        )
    except TimeoutError:
        client_process.kill()
        stdout, stderr = await client_process.communicate()
        pytest.fail("Client process timed out.")

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    print("--- Standalone Client STDOUT ---")
    print(stdout_str)
    print("--- Standalone Client STDERR ---")
    print(stderr_str)

    assert client_process.returncode == 0, "Client process should exit cleanly"
    assert "✅ Demo completed successfully!" in stdout_str
    assert "Hello, WebTransport!" in stdout_str


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="WebTransport has protocol issues with self-signed certs in test environment"
)
async def test_webtransport_integrated_example(webtransport_integrated_server):
    """Tests the integrated WebTransport example."""
    client_path = examples_dir / "webtransport-integrated" / "client.py"
    client_process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(client_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            client_process.communicate(), timeout=20
        )
    except TimeoutError:
        client_process.kill()
        stdout, stderr = await client_process.communicate()
        pytest.fail("Client process timed out.")

    stdout_str = stdout.decode()
    stderr_str = stderr.decode()

    print("--- Integrated Client STDOUT ---")
    print(stdout_str)
    print("--- Integrated Client STDERR ---")
    print(stderr_str)

    assert client_process.returncode == 0, "Client process should exit cleanly"
    assert "✅ Demo completed successfully!" in stdout_str
    assert "5 + 3 = 8" in stdout_str
    assert "25 × 4 = 100" in stdout_str
