import pickle

import pytest

from seed.secrets import SecretProvider, SecretProviderError, SecretReference


def test_reference_parser_rejects_inline_and_plaintext() -> None:
    with pytest.raises(SecretProviderError):
        SecretReference.parse("plaintext://secret", "ref")
    with pytest.raises(SecretProviderError):
        SecretReference.parse("secret", "ref")


async def test_env_rotation_leases_and_cleanup(monkeypatch) -> None:
    provider = SecretProvider(allowed_env=frozenset({"APP_SECRET"}), file_roots=())
    reference = SecretReference.parse("env://APP_SECRET", "app-secret")
    monkeypatch.setenv("APP_SECRET", "first")
    lease = await provider.open(reference, "test-purpose")
    buffer = lease.borrow()
    assert bytes(buffer.reveal()) == b"first"
    monkeypatch.setenv("APP_SECRET", "second")
    rotated = await provider.open(reference, "test-purpose")
    assert bytes(rotated.borrow().reveal()) == b"second"
    lease.close()
    lease.close()
    with pytest.raises(SecretProviderError, match="lease_closed"):
        lease.borrow()
    with pytest.raises(SecretProviderError, match="buffer_closed"):
        buffer.reveal()
    rotated.close()


async def test_file_root_permissions_and_traversal(tmp_path) -> None:
    root = tmp_path / "secrets"
    root.mkdir()
    secret = root / "value"
    secret.write_bytes(b"value")
    secret.chmod(0o600)
    provider = SecretProvider(allowed_env=frozenset(), file_roots=(root,))
    lease = await provider.open(SecretReference.parse(f"file://{secret}", "file-secret"), "purpose")
    assert bytes(lease.borrow().reveal()) == b"value"
    lease.close()
    outside = tmp_path / "outside"
    outside.write_text("no")
    outside.chmod(0o600)
    with pytest.raises(SecretProviderError, match="reference_not_allowed"):
        await provider.open(SecretReference.parse(f"file://{outside}", "outside"), "purpose")
    secret.chmod(0o644)
    with pytest.raises(SecretProviderError, match="insecure_file"):
        await provider.open(SecretReference.parse(f"file://{secret}", "file-secret"), "purpose")


async def test_provider_errors_are_safe(monkeypatch) -> None:
    provider = SecretProvider(allowed_env=frozenset({"MISSING"}), file_roots=())
    monkeypatch.delenv("MISSING", raising=False)
    with pytest.raises(SecretProviderError, match="provider_unavailable"):
        await provider.open(SecretReference.parse("env://MISSING", "safe-id"), "purpose")
    with pytest.raises(SecretProviderError, match="reference_not_allowed"):
        await provider.open(SecretReference.parse("env://OTHER", "safe-id"), "purpose")
    with pytest.raises(SecretProviderError, match="invalid_purpose"):
        await provider.open(SecretReference.parse("env://MISSING", "safe-id"), "bad\npurpose")


async def test_repr_and_pickle_never_expose_value(monkeypatch) -> None:
    monkeypatch.setenv("CANARY", "top-secret-canary")
    provider = SecretProvider(allowed_env=frozenset({"CANARY"}), file_roots=())
    lease = await provider.open(SecretReference.parse("env://CANARY", "canary-ref"), "test")
    buffer = lease.borrow()
    assert "top-secret-canary" not in repr(lease) + repr(buffer)
    with pytest.raises(TypeError):
        pickle.dumps(lease)
    with pytest.raises(TypeError):
        pickle.dumps(buffer)
    lease.close()
