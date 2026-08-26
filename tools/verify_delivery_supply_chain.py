"""Verify a maia-seed Delivery with GitHub OIDC attestations and Build Once state."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag

REPOSITORY = "xiajingan/maia-seed"
SIGNER_WORKFLOW = "github.com/xiajingan/maia-seed/.github/workflows/attest-library-candidate.yml"
PROVENANCE_PREDICATE = "https://slsa.dev/provenance/v1"
SBOM_PREDICATE = "https://spdx.dev/Document/v2.3"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def evidence_digests(value: str, scheme: str) -> tuple[str, str]:
    prefix = f"{scheme}://"
    if not value.startswith(prefix):
        raise ValueError(f"invalid {scheme} evidence URI")
    parts = value.rsplit("/", 2)
    if len(parts) != 3 or not parts[1].startswith("sha256:") or not parts[2].startswith("sha256:"):
        raise ValueError(f"invalid {scheme} evidence identity")
    return parts[1], parts[2]


def run_gh(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["gh", *args], cwd=cwd, check=False, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or result.stdout[-1000:] or "GitHub attestation verification failed")
    return result.stdout


def verify_attestation(artifact: Path, predicate: str, expected_bundle_digest: str, source_ref: str) -> None:
    common = (
        str(artifact),
        "--repo",
        REPOSITORY,
        "--signer-workflow",
        SIGNER_WORKFLOW,
        "--source-ref",
        source_ref,
        "--predicate-type",
        predicate,
    )
    payload = json.loads(run_gh("attestation", "verify", *common, "--format", "json"))
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"expected exactly one verified attestation for {predicate}")
    with tempfile.TemporaryDirectory(prefix="maia-seed-attestation-") as directory:
        root = Path(directory)
        run_gh("attestation", "download", *common[:1], "--repo", REPOSITORY, "--predicate-type", predicate, cwd=root)
        bundles = list(root.glob("*.jsonl")) + list(root.glob("*.json"))
        if len(bundles) != 1:
            raise ValueError(f"expected exactly one attestation bundle for {predicate}")
        actual = "sha256:" + sha256_bytes(bundles[0].read_bytes())
        if actual != expected_bundle_digest:
            raise ValueError(f"attestation bundle digest mismatch for {predicate}")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def build_state_identity(value: str) -> tuple[str, str, str]:
    prefix = "build://maia-seed/library-packages/"
    if not value.startswith(prefix):
        raise ValueError("invalid build evidence URI")
    parts = value[len(prefix) :].split("/")
    if len(parts) != 3 or not parts[0].startswith("sprint-"):
        raise ValueError("invalid build evidence path")
    if not parts[1].startswith("sha256:") or not parts[2].startswith("sha256:"):
        raise ValueError("invalid build evidence identity")
    return parts[0], parts[1], parts[2]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = load_json(args.manifest.resolve())
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or not isinstance(artifacts[0], dict):
        raise ValueError("exactly one Delivery artifact is required")
    item = artifacts[0]
    if item.get("type") != "dependency-package" or item.get("package") != "maia-seed":
        raise ValueError("unexpected Delivery artifact")
    expected = "sha256:" + str(item.get("sha256", "")).removeprefix("sha256:")
    source_url, fragment = urldefrag(str(item.get("ref", "")))
    if fragment != "sha256=" + expected.removeprefix("sha256:"):
        raise ValueError("artifact ref is not bound to its SHA-256")
    required_url = f"https://github.com/{REPOSITORY}/releases/download/v{item.get('version')}/"
    if not source_url.startswith(required_url):
        raise ValueError("artifact ref is outside the trusted GitHub Release")

    signature_subject, signature_bundle = evidence_digests(str(item.get("signature", "")), "signature")
    sbom_subject, sbom_bundle = evidence_digests(str(item.get("sbom", "")), "sbom")
    sprint, build_subject, build_state_digest = build_state_identity(str(item.get("build_once_evidence", "")))
    if {signature_subject, sbom_subject, build_subject} != {expected}:
        raise ValueError("supply-chain evidence is not bound to the artifact")

    project = Path.cwd().resolve()
    package_state_path = project / ".harness/state/library-packages" / f"{sprint}.json"
    package_state = load_json(package_state_path)
    if (
        package_state.get("package") != item.get("package")
        or package_state.get("version") != item.get("version")
        or package_state.get("sha256") != expected
        or package_state.get("source_commit") != manifest.get("source_commit")
        or "sha256:" + sha256_bytes(package_state_path.read_bytes()) != build_state_digest
    ):
        raise ValueError("Build Once state does not match Delivery")
    quality_digest = item.get("quality_evidence_sha256")
    if quality_digest is not None:
        quality_path = Path(str(package_state.get("quality_evidence", "")))
        if (
            package_state.get("quality_evidence_sha256") != quality_digest
            or not quality_path.is_file()
            or "sha256:" + sha256_bytes(quality_path.read_bytes()) != quality_digest
        ):
            raise ValueError("Library quality evidence does not match Delivery")

    source_ref = "refs/heads/library/" + sprint.removeprefix("sprint-")

    with tempfile.TemporaryDirectory(prefix="maia-seed-release-") as directory:
        downloaded = Path(directory) / Path(source_url).name
        with urllib.request.urlopen(source_url, timeout=120) as response:
            downloaded.write_bytes(response.read())
        if "sha256:" + sha256_bytes(downloaded.read_bytes()) != expected:
            raise ValueError("downloaded Release artifact digest mismatch")
        verify_attestation(downloaded, PROVENANCE_PREDICATE, signature_bundle, source_ref)
        verify_attestation(downloaded, SBOM_PREDICATE, sbom_bundle, source_ref)

    identities = [{"type": str(item["type"]), "ref": str(item["ref"]), "digest": expected}]
    print(
        json.dumps(
            {
                "manifest_digest": manifest.get("manifest_digest"),
                "artifacts": identities,
                "signature": True,
                "sbom": True,
                "build_once": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
