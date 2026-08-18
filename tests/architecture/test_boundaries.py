import ast
import importlib
from pathlib import Path


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
        "config.py",
        "context.py",
        "secrets.py",
        "oceanbase.py",
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
    }
    for module_name, symbols in expected.items():
        assert set(importlib.import_module(module_name).__all__) == symbols
