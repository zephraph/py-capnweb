"""Generate self-signed certificates for WebTransport development.

This script creates SSL certificates suitable for testing WebTransport.
DO NOT use these certificates in production - use properly CA-signed certificates.

Run:
    python examples/webtransport/generate_certs.py
"""

from pathlib import Path

from capnweb.certs import generate_self_signed_cert


def main() -> None:
    """Generate self-signed certificates for localhost."""
    # Generate in the webtransport example directory
    output_dir = Path(__file__).parent

    print("Generating self-signed certificates for WebTransport...")
    print(f"Output directory: {output_dir}")

    cert_path, key_path = generate_self_signed_cert(
        hostname="localhost",
        key_size=2048,
        validity_days=365,
        output_dir=output_dir,
    )

    print(f"✅ Certificate generated: {cert_path}")
    print(f"✅ Private key generated: {key_path}")
    print()
    print("These certificates are for development only.")
    print("For production, use properly CA-signed certificates.")
    print()
    print("Next steps:")
    print("  1. Start the server: python examples/webtransport/server.py")
    print("  2. Run the client:  python examples/webtransport/client.py")


if __name__ == "__main__":
    main()
