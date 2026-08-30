import ast
import inspect
import subprocess
import sys
from pathlib import Path

import seed
import seed.crypto as crypto

ROOT = Path(__file__).parents[2]
DIGEST_FILES = (
    ROOT / "src/seed/_crypto_digest.py",
    ROOT / "src/seed/_crypto_digest_models.py",
    ROOT / "src/seed/_crypto_digest_validation.py",
)


def test_digest_dependency_direction_and_stdlib_only_algorithm() -> None:
    forbidden_imports = {"cryptography", "fastapi", "sqlalchemy", "mud", "retry_reference"}
    for path in (ROOT / "src/seed/crypto.py", *DIGEST_FILES):
        tree = ast.parse(path.read_text())
        imports = {
            node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) and node.names
        }
        imports.update(
            node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        )
        assert imports.isdisjoint(forbidden_imports), path
    algorithm_source = DIGEST_FILES[0].read_text()
    assert "import hmac" in algorithm_source and "import hashlib" in algorithm_source
    assert "compare_digest" in algorithm_source


def test_digest_contract_has_one_public_facade_and_no_business_semantics() -> None:
    public_names = {
        "ReferenceDigestKeyRing",
        "ReferenceDigester",
        "ReferenceDigestContractError",
        "load_reference_digest_key_ring",
        "create_reference_digester",
    }
    assert public_names <= set(crypto.__all__)
    assert public_names.isdisjoint(seed.__all__)
    forbidden = ("wecom", "tenant", "realm", "appinstance", "credential", "database", "http", "audit")
    source = "\n".join(path.read_text().lower() for path in DIGEST_FILES)
    assert not any(term in source for term in forbidden)
    assert not any(name.startswith("_") and name in crypto.__all__ for name in crypto.__all__)


def test_digest_public_signatures_are_frozen() -> None:
    assert list(inspect.signature(crypto.load_reference_digest_key_ring).parameters) == [
        "provider",
        "active_key_id",
        "previous_key_ids",
    ]
    assert list(inspect.signature(crypto.create_reference_digester).parameters) == ["ring"]
    assert list(inspect.signature(crypto.ReferenceDigester.digest).parameters) == ["self", "reference", "domain"]
    digest_domain = inspect.signature(crypto.ReferenceDigester.digest).parameters["domain"]
    assert digest_domain.kind is inspect.Parameter.KEYWORD_ONLY
    assert list(inspect.signature(crypto.ReferenceDigester.matches).parameters) == [
        "self",
        "reference",
        "candidate",
        "domain",
    ]
    matches_domain = inspect.signature(crypto.ReferenceDigester.matches).parameters["domain"]
    assert matches_domain.kind is inspect.Parameter.KEYWORD_ONLY


def test_reference_digest_typecheck_fixtures() -> None:
    valid = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "tests/typecheck/reference_digest_valid.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr
    invalid = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "tests/typecheck/reference_digest_raw_rejected.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = invalid.stdout + invalid.stderr
    assert invalid.returncode != 0
    assert "Found 8 errors" in output, output
