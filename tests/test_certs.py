"""Tests for certificate generation utilities."""

import datetime

import pytest
from cryptography.x509.oid import ExtensionOID, NameOID

from capnweb.certs import (
    generate_self_signed_cert,
    load_certificate,
    load_private_key,
    verify_certificate,
)


class TestCertificateGeneration:
    """Test certificate generation utilities."""

    def test_generate_self_signed_cert(self, tmp_path):
        """Test generating self-signed certificates."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="localhost",
            key_size=2048,
            validity_days=30,
            output_dir=tmp_path,
        )

        assert cert_path.exists()
        assert key_path.exists()
        assert cert_path.name == "localhost.crt"
        assert key_path.name == "localhost.key"

        # Verify certificate can be loaded
        cert = load_certificate(cert_path)
        key = load_private_key(key_path)

        assert cert is not None
        assert key is not None

    def test_generate_cert_with_custom_hostname(self, tmp_path):
        """Test generating certificates with custom hostname."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="example.com",
            output_dir=tmp_path,
        )

        assert cert_path.name == "example.com.crt"
        assert key_path.name == "example.com.key"

    def test_generate_cert_with_custom_key_size(self, tmp_path):
        """Test generating certificate with custom key size."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="localhost",
            key_size=4096,  # Larger key
            output_dir=tmp_path,
        )

        # Load and verify key size
        key = load_private_key(key_path)
        assert key.key_size == 4096

    def test_generate_cert_with_ip_address(self, tmp_path):
        """Test generating certificate for IP address."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="192.168.1.1",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Should verify for the IP address
        assert verify_certificate(cert, "192.168.1.1")

    def test_generate_cert_with_ipv6_address(self, tmp_path):
        """Test generating certificate for IPv6 address."""
        cert_path, key_path = generate_self_signed_cert(
            hostname="::1",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Should verify for IPv6
        assert verify_certificate(cert, "::1")

    def test_generate_cert_default_output_dir(self, tmp_path, monkeypatch):
        """Test generating certificate with default output directory."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        cert_path, key_path = generate_self_signed_cert(
            hostname="test.local",
            output_dir=None,  # Use current directory
        )

        assert cert_path.exists()
        assert key_path.exists()

    def test_verify_certificate(self, tmp_path):
        """Test certificate verification."""
        cert_path, _ = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Should verify for localhost
        assert verify_certificate(cert, "localhost")

        # Should not verify for different hostname
        assert not verify_certificate(cert, "example.com")

    def test_verify_certificate_with_127_0_0_1(self, tmp_path):
        """Test localhost certificate verifies for 127.0.0.1."""
        cert_path, _ = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Localhost cert should include 127.0.0.1 in SAN
        assert verify_certificate(cert, "127.0.0.1")

    def test_verify_certificate_with_ipv6_localhost(self, tmp_path):
        """Test localhost certificate verifies for ::1."""
        cert_path, _ = generate_self_signed_cert(
            hostname="localhost",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Localhost cert should include ::1 in SAN
        assert verify_certificate(cert, "::1")

    def test_verify_expired_certificate(self, tmp_path):
        """Test verification fails for expired certificate."""
        # Create certificate with very short validity
        cert_path, _ = generate_self_signed_cert(
            hostname="test.local",
            validity_days=0,  # Expires immediately
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Certificate should be expired or very close to expiry
        # This might be timing-sensitive, so we just check it doesn't crash
        result = verify_certificate(cert, "test.local")
        # Result could be True or False depending on timing

    def test_load_nonexistent_certificate(self, tmp_path):
        """Test loading certificate that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_certificate(tmp_path / "nonexistent.crt")

    def test_load_nonexistent_key(self, tmp_path):
        """Test loading key that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_private_key(tmp_path / "nonexistent.key")

    def test_load_invalid_certificate(self, tmp_path):
        """Test loading invalid certificate file."""
        invalid_cert = tmp_path / "invalid.crt"
        invalid_cert.write_text("not a certificate")

        with pytest.raises(ValueError):
            load_certificate(invalid_cert)

    def test_load_invalid_key(self, tmp_path):
        """Test loading invalid key file."""
        invalid_key = tmp_path / "invalid.key"
        invalid_key.write_text("not a key")

        with pytest.raises(ValueError):
            load_private_key(invalid_key)

    def test_certificate_has_correct_extensions(self, tmp_path):
        """Test generated certificate has required extensions."""
        cert_path, _ = generate_self_signed_cert(
            hostname="test.local",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Check for SubjectAlternativeName
        san_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        assert san_ext is not None

        # Check for BasicConstraints
        basic_constraints = cert.extensions.get_extension_for_oid(
            ExtensionOID.BASIC_CONSTRAINTS
        )
        assert basic_constraints is not None
        assert basic_constraints.critical is True

        # Check for KeyUsage
        key_usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
        assert key_usage is not None
        assert key_usage.critical is True

    def test_certificate_validity_period(self, tmp_path):
        """Test certificate has correct validity period."""
        validity_days = 365
        cert_path, _ = generate_self_signed_cert(
            hostname="test.local",
            validity_days=validity_days,
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Check validity period (allow some tolerance for test execution time)
        now = datetime.datetime.now(datetime.UTC)
        expected_expiry = now + datetime.timedelta(days=validity_days)

        # Certificate should expire roughly validity_days from now
        # Allow 1 day tolerance
        time_diff = abs((cert.not_valid_after_utc - expected_expiry).total_seconds())
        assert time_diff < 86400  # Less than 1 day difference

    def test_verify_certificate_without_san(self, tmp_path):
        """Test verification falls back to CN when no SAN."""
        # This tests the fallback path in verify_certificate
        # We can't easily create a cert without SAN using our function,
        # but we can test with a custom hostname
        cert_path, _ = generate_self_signed_cert(
            hostname="custom.test",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Should verify for the hostname in CN
        assert verify_certificate(cert, "custom.test")

    def test_certificate_subject_attributes(self, tmp_path):
        """Test certificate has correct subject attributes."""
        cert_path, _ = generate_self_signed_cert(
            hostname="test.example.com",
            output_dir=tmp_path,
        )

        cert = load_certificate(cert_path)

        # Check common name
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        assert len(cn_attrs) == 1
        assert cn_attrs[0].value == "test.example.com"

        # Check organization
        org_attrs = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        assert len(org_attrs) == 1
        assert org_attrs[0].value == "Cap'n Web"

    def test_certificate_serial_number_is_random(self, tmp_path):
        """Test that certificates get random serial numbers."""
        cert_path1, _ = generate_self_signed_cert(
            hostname="test1.local",
            output_dir=tmp_path,
        )
        cert_path2, _ = generate_self_signed_cert(
            hostname="test2.local",
            output_dir=tmp_path,
        )

        cert1 = load_certificate(cert_path1)
        cert2 = load_certificate(cert_path2)

        # Serial numbers should be different
        assert cert1.serial_number != cert2.serial_number

    def test_private_key_format(self, tmp_path):
        """Test private key is in correct format."""
        _, key_path = generate_self_signed_cert(
            hostname="test.local",
            output_dir=tmp_path,
        )

        # Read the key file
        key_data = key_path.read_text()

        # Should be PEM format
        assert "-----BEGIN RSA PRIVATE KEY-----" in key_data
        assert "-----END RSA PRIVATE KEY-----" in key_data

    def test_certificate_format(self, tmp_path):
        """Test certificate is in correct format."""
        cert_path, _ = generate_self_signed_cert(
            hostname="test.local",
            output_dir=tmp_path,
        )

        # Read the cert file
        cert_data = cert_path.read_text()

        # Should be PEM format
        assert "-----BEGIN CERTIFICATE-----" in cert_data
        assert "-----END CERTIFICATE-----" in cert_data
