import ast
import importlib
import inspect
from pathlib import Path
from typing import get_type_hints

import seed.errors as errors
import seed.retry as retry


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
        "_errors_models.py",
        "_errors_seal.py",
        "_errors_validation.py",
        "config.py",
        "context.py",
        "errors.py",
        "secrets.py",
        "oceanbase.py",
        "retry.py",
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

    assert seed.__all__ == ["config", "context", "errors", "oceanbase", "retry", "secrets"]
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
