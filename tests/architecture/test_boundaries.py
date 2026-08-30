import ast
import importlib
import inspect
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import get_type_hints

import seed.crypto as crypto
import seed.errors as errors
import seed.retry as retry
import seed.retry_reference as retry_reference


def test_seed_has_no_reverse_business_dependency() -> None:
    root = Path(__file__).parents[2] / "src" / "seed"
    forbidden_imports = {"mud", "fastapi"}
    forbidden_names = {"Tenant", "Repository", "Migration", "Bootstrap", "PermissionPolicy"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) and node.names
        }
        imports.update(
            node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        )
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
        assert imports.isdisjoint(forbidden_imports), path
        assert names.isdisjoint(forbidden_names), path


def test_only_frozen_modules_exist() -> None:
    root = Path(__file__).parents[2] / "src" / "seed"
    assert {path.name for path in root.glob("*.py")} == {
        "__init__.py",
        "_crypto_aead.py",
        "_crypto_digest.py",
        "_crypto_digest_models.py",
        "_crypto_digest_validation.py",
        "_crypto_models.py",
        "_crypto_nonce.py",
        "_crypto_validation.py",
        "_errors_models.py",
        "_errors_seal.py",
        "_errors_validation.py",
        "_retry_reference_codec.py",
        "_retry_reference_models.py",
        "_retry_reference_snapshot.py",
        "_retry_reference_time.py",
        "_retry_reference_validation.py",
        "config.py",
        "context.py",
        "crypto.py",
        "errors.py",
        "secrets.py",
        "oceanbase.py",
        "retry.py",
        "retry_reference.py",
    }


def test_public_symbols_match_frozen_surface() -> None:
    expected = {
        "seed.config": {"SettingsLoader", "SettingsSource", "RedactedSettingsSummary", "ConfigLoadError"},
        "seed.context": {"RequestContext", "ContextToken", "ContextScope", "ContextError"},
        "seed.secrets": {"SecretReference", "SecretProvider", "SecretLease", "SecretBuffer", "SecretProviderError"},
        "seed.oceanbase": {
            "OceanBaseRuntime",
            "OceanBaseSettings",
            "OceanBaseSessionScope",
            "DialectCapabilities",
            "DependencyHealth",
            "OceanBaseRuntimeError",
        },
        "seed.errors": {
            "DetailsReferenceVerifier",
            "ErrorContractError",
            "ErrorEnvelope",
            "MachineErrorCode",
            "VerifiedDetailsReference",
            "compose_error_envelope",
            "serialize_error_envelope",
            "verify_details_reference",
        },
        "seed.retry": {
            "DependencyFailure",
            "DependencyFailureKind",
            "RetryContractError",
            "RetryReferenceVerifier",
            "VerifiedRetryReference",
            "classify_dependency_failure",
            "dependency_failure_to_error",
            "verify_retry_reference",
        },
        "seed.crypto": {
            "CryptoContractError",
            "KeyProvider",
            "AeadKeyRing",
            "AeadCipher",
            "load_aead_key_ring",
            "create_aead_cipher",
            "ReferenceDigestKeyRing",
            "ReferenceDigester",
            "ReferenceDigestContractError",
            "load_reference_digest_key_ring",
            "create_reference_digester",
        },
        "seed.retry_reference": {
            "RetryReferenceFoundationError",
            "RetryReferencePayloadVerifier",
            "RetryReferenceCodec",
            "RetryReferenceSnapshot",
            "create_retry_reference_codec",
            "freeze_retry_reference_snapshot",
        },
    }
    for module_name, symbols in expected.items():
        assert set(importlib.import_module(module_name).__all__) == symbols


def test_retry_contract_dependency_direction_and_no_second_constructor() -> None:
    root = Path(__file__).parents[2] / "src" / "seed"
    contract_files = {
        name: (root / name).read_text()
        for name in ("_errors_models.py", "_errors_seal.py", "_errors_validation.py", "errors.py", "retry.py")
    }
    errors_source = contract_files["errors.py"]
    retry_source = (root / "retry.py").read_text()
    errors_tree = ast.parse(errors_source)
    retry_tree = ast.parse(retry_source)
    assert "seed.retry" not in errors_source
    assert "_compose_" not in errors_source
    assert "capability" not in errors_source
    assert (
        sum(
            isinstance(node, ast.FunctionDef) and node.name == "compose_error_envelope"
            for node in ast.walk(errors_tree)
        )
        == 1
    )
    assert not any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in {"RetryReferenceVerifier", "VerifiedRetryReference", "verify_retry_reference"}
        for node in ast.walk(retry_tree)
    )
    all_trees = {name: ast.parse(source) for name, source in contract_files.items()}
    assert (
        sum(
            isinstance(node, ast.FunctionDef) and node.name == "compose_error_envelope"
            for tree in all_trees.values()
            for node in ast.walk(tree)
        )
        == 1
    )
    assert (
        sum(
            isinstance(node, ast.FunctionDef) and node.name == "serialize_error_envelope"
            for tree in all_trees.values()
            for node in ast.walk(tree)
        )
        == 1
    )
    internal_trees = {name: tree for name, tree in all_trees.items() if name.startswith("_errors_")}
    assert not any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and any(term in node.name for term in ("compose", "factory", "mint", "capability"))
        for tree in internal_trees.values()
        for node in ast.walk(tree)
    )
    for tree in internal_trees.values():
        imported_modules = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not any(module.endswith("retry") for module in imported_modules)


def test_retry_contract_aliases_signatures_and_root_exports() -> None:
    import seed

    assert seed.__all__ == [
        "config",
        "context",
        "crypto",
        "errors",
        "oceanbase",
        "retry",
        "retry_reference",
        "secrets",
    ]
    assert retry.RetryReferenceVerifier is errors.DetailsReferenceVerifier
    assert retry.VerifiedRetryReference is errors.VerifiedDetailsReference
    assert retry.verify_retry_reference is errors.verify_details_reference
    hints = get_type_hints(errors.compose_error_envelope)
    assert hints["details_ref"] == errors.VerifiedDetailsReference | None
    assert list(inspect.signature(retry.dependency_failure_to_error).parameters) == [
        "failure",
        "user_message",
        "recovery",
        "correlation_id",
    ]


def test_crypto_and_foundation_dependency_direction_and_no_duplicate_contracts() -> None:
    root = Path(__file__).parents[2] / "src" / "seed"
    sources = {path.name: path.read_text() for path in root.glob("*.py")}
    crypto_files = {
        name: source for name, source in sources.items() if name == "crypto.py" or name.startswith("_crypto_")
    }
    foundation_files = {
        name: source
        for name, source in sources.items()
        if name == "retry_reference.py" or name.startswith("_retry_reference_")
    }
    assert all("retry_reference" not in source and "from .retry" not in source for source in crypto_files.values())
    assert "from .crypto import AeadCipher" in sources["retry_reference.py"]
    assert (
        "from .retry import VerifiedRetryReference, verify_retry_reference" in sources["_retry_reference_snapshot.py"]
    )
    forbidden = {"VerifiedDetailsReference", "DependencyFailure", "ErrorEnvelope", "compose_error_envelope"}
    for source in (*crypto_files.values(), *foundation_files.values()):
        tree = ast.parse(source)
        definitions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
        assert definitions.isdisjoint(forbidden)


def test_new_public_signatures_and_no_public_test_seams() -> None:
    assert list(inspect.signature(crypto.load_aead_key_ring).parameters) == [
        "provider",
        "active_key_id",
        "previous_key_ids",
    ]
    assert list(inspect.signature(crypto.AeadCipher.seal).parameters) == ["self", "plaintext", "aad"]
    assert list(inspect.signature(retry_reference.create_retry_reference_codec).parameters) == [
        "cipher",
        "namespace",
        "ttl_seconds",
        "skew_seconds",
    ]
    assert list(inspect.signature(retry_reference.freeze_retry_reference_snapshot).parameters) == ["codec", "entries"]
    public = (crypto, retry_reference)
    forbidden = ("random", "nonce", "counter", "clock", "test", "mint", "seal_factory")
    for module in public:
        for name in module.__all__:
            assert not any(term in name.lower() for term in forbidden)
            value = getattr(module, name)
            if callable(value):
                assert not any(
                    term in parameter.lower() for parameter in inspect.signature(value).parameters for term in forbidden
                )


def test_package_version_security_extra_and_typed_data() -> None:
    root = Path(__file__).parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    assert project["project"]["version"] == "0.3.0"
    assert "cryptography>=44,<51" in project["project"]["optional-dependencies"]["security"]
    assert all("cryptography" not in dependency for dependency in project["project"]["dependencies"])
    assert "py.typed" in project["tool"]["setuptools"]["package-data"]["seed"]


def test_retry_reference_typecheck_fixtures() -> None:
    root = Path(__file__).parents[2]
    valid = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "tests/typecheck/retry_reference_valid.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr
    invalid = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "tests/typecheck/retry_reference_raw_rejected.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert invalid.returncode != 0
    output = invalid.stdout + invalid.stderr
    assert "incompatible type" in output.lower() and "Found 6 errors" in output
