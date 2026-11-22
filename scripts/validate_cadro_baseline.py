"""Validate the pinned CADRO baseline and local lockfile metadata.

This check is deliberately provider-independent. Verifying a release against an
already-provisioned Bench and resolving package licenses/SBOM belongs to later
release gates, not to a static manifest syntax check.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REF_PATTERN = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._/-]*$")
SUPPORTED_CHANNELS = {"development", "stable", "patch"}
INTEGRITY_PATTERN = re.compile(r"^  integrity (sha(?:256|384|512))-([A-Za-z0-9+/]+={0,2})$", re.MULTILINE)
DIGEST_LENGTHS: dict[str, int] = {"sha256": 32, "sha384": 48, "sha512": 64}


class BaselineValidationError(ValueError):
    """Raised when a required baseline record cannot support reproducibility."""


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineValidationError(message)


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    expect(isinstance(value, dict), f"{path.name}: top-level value must be an object")
    return value


def validate_repository_pinned(record: dict, category: str) -> None:
    name = record.get("name")
    expect(isinstance(name, str) and bool(name), f"{category}: name is required")
    expect(record.get("repository", "").startswith("https://github.com/"), f"{name}: HTTPS GitHub source required")
    expect(SHA_PATTERN.fullmatch(record.get("commit", "")) is not None, f"{name}: use a full lowercase commit SHA")
    expect(REF_PATTERN.fullmatch(record.get("ref", "")) is not None, f"{name}: source ref is missing or unsafe")
    expect(isinstance(record.get("purpose"), str) and record["purpose"], f"{name}: purpose is required")


def parse_yarn_lock(path: Path) -> dict[str, str]:
    """Resolve each Yarn v1 selector to its locked version and check registry integrity."""
    content = path.read_text(encoding="utf-8")
    expect("# yarn lockfile v1" in content[:512], f"{path}: Yarn v1 lockfile required")
    entries: dict[str, str] = {}
    for block in re.split(r"(?=^[^\s#][^\n]*:$)", content, flags=re.MULTILINE):
        if not block or block.startswith("#"):
            continue
        selector_line, *_ = block.split("\n", 1)
        if not selector_line.endswith(":"):
            raise BaselineValidationError(f"{path}: malformed lockfile block")
        # Yarn puts one pair of quotes around a combined selector list.
        # Strip outer quotes first, then each comma-separated selector individually.
        selectors = [s.strip('"') for s in selector_line.removesuffix(":").strip("\"'").split(", ")]
        version = re.search(r'^  version "([^"\s]+)"$', block, re.MULTILINE)
        expect(version is not None, f"{path}: missing resolved version for {selector_line}")
        local = any("@link:" in selector or "@file:" in selector for selector in selectors)
        if not local:
            expect(re.search(r'^  resolved "[^"]+"$', block, re.MULTILINE) is not None, f"{path}: missing resolved URL: {selector_line}")
            integrity_match = INTEGRITY_PATTERN.search(block)
            expect(integrity_match is not None, f"{path}: missing strong integrity: {selector_line}")
            algorithm = integrity_match.group(1)
            encoded = integrity_match.group(2)
            import base64

            try:
                digest = base64.b64decode(encoded, validate=True)
            except (ValueError, base64.binascii.Error) as error:
                raise BaselineValidationError(f"{path}: malformed integrity: {selector_line}") from error
            expect(len(digest) == DIGEST_LENGTHS.get(algorithm, -1), f"{path}: wrong integrity length: {selector_line}")
        for selector in selectors:
            # npm aliases retain their own selector; semver ranges also match directly.
            canonical_selector = selector.replace("@npm:", "@")
            expect(selector not in entries, f"{path}: duplicate selector {selector}")
            entries[selector] = version.group(1)
            entries.setdefault(canonical_selector, version.group(1))
    return entries


def validate_local_project(manifest: Path) -> None:
    project_root = manifest.parent
    package = read_json(project_root / "package.json")
    lockfile = parse_yarn_lock(manifest)
    for group in ("dependencies", "devDependencies", "optionalDependencies", "resolutions"):
        dependencies = package.get(group, {})
        expect(isinstance(dependencies, dict), f"{project_root}: {group} must be an object")
        for name, specifier in dependencies.items():
            expect(isinstance(specifier, str) and bool(specifier), f"{project_root}: dependency {name} needs a range")
            # Yarn v1 combines compatible selectors into one quoted, comma-separated entry.
            # Check both the exact selector and the name+range pair individually, because
            # parse_yarn_lock stores every component of a combined entry.
            selector = f"{name}@{specifier}"
            npm_selector = f"{name}@npm:{specifier}"
            found = selector in lockfile or npm_selector in lockfile
            expect(found, f"{project_root}: lockfile lacks {selector}")
            if specifier.startswith(("git", "http:", "https:")):
                expect(
                    re.search(r"[0-9a-f]{40}", specifier) is not None,
                    f"{project_root}: external dependency {name} requires a full commit SHA",
                )


def validate_python_manifest(path: Path, version_source: Path) -> None:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    expect(project.get("name") == "erpnext", "Keep ERPNext technical package identity in Phase 0")
    expect(project.get("requires-python") == ">=3.14", "Record intentional Python runtime changes explicitly")
    dependencies = project.get("dependencies", [])
    expect("holidays~=0.87" in dependencies, "holiday dependency must be revalidated intentionally")
    expect("plaid-python~=7.2.1" in dependencies, "Plaid dependency must be revalidated intentionally")
    version = ast.literal_eval(
        re.search(r"^__version__\s*=.*$", version_source.read_text(encoding="utf-8"), re.MULTILINE).group(0).split("=", 1)[1].strip()
    )
    expect(version == "17.0.0-dev", "Phase 0 baseline stays on the measured development version")


def validate_release_config(project: dict[str, object]) -> None:
    """Check source-controlled release inputs without requiring Frappe at runtime."""
    bench = project.get("tool", {}).get("bench", {})
    framework = bench.get("frappe-dependencies", {}).get("frappe")
    if framework != ">=17.0.0-dev,<18.0.0":
        raise BaselineValidationError("Review the Frappe major-version window with the release line")
    assets = bench.get("assets", {})
    if assets.get("build_dir") != "./banking" or assets.get("out_dir") != "../erpnext/public/banking":
        raise BaselineValidationError("Banking asset output paths differ from the baseline")


def assert_local_ancestry(source_commit: str) -> None:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 1:
        raise BaselineValidationError("HEAD does not contain the declared upstream baseline")
    if completed.returncode != 0:
        raise BaselineValidationError(f"Local Git baseline cannot be verified: {completed.stderr.strip()}")


def validate(path: Path | None = None, verify_ancestry: bool = True, document: dict | None = None) -> None:
    """Validate either a manifest path or a deep-copied fixture against local sources."""
    if document is None:
        expect(path is not None, "A manifest path or fixture document is required")
        document = read_json(path)
    _validate_document(document, verify_ancestry)


def _validate_document(document: dict, verify_ancestry: bool) -> None:
    expect(document.get("schema_version") == 1, "Unsupported schema_version")
    baseline = document.get("baseline")
    expect(isinstance(baseline, dict), "baseline must be an object")
    expect(SHA_PATTERN.fullmatch(baseline.get("source_commit", "")) is not None, "baseline.source_commit must be a full SHA")
    expect(REF_PATTERN.fullmatch(baseline.get("source_branch", "")) is not None, "baseline.source_branch is invalid")
    expect(baseline.get("release_status") == "evaluation-only", "Only an evaluation baseline may use this Phase 0 schema")
    expect(baseline.get("production_approved") is False, "Phase 0 cannot declare production approval")

    components = document.get("components")
    expect(isinstance(components, list) and len(components) >= 1, "components must contain at least one record")
    names = []
    for component in components:
        validate_repository_pinned(component, "components")
        expect(component.get("channel") in SUPPORTED_CHANNELS, f'{component["name"]}: invalid channel')
        expect(component.get("production_approved") is False, f'{component["name"]}: no Phase 0 production approval')
        names.append(component["name"])
    expect(len(names) == len(set(names)), "components must have unique names")
    expect("erpnext" in names and "frappe" in names, "Both ERPNext and Frappe pins are required")
    erpnext = next(item for item in components if item["name"] == "erpnext")
    expect(erpnext["repository"] == "https://github.com/frappe/erpnext", "ERPNext must use canonical upstream")
    expect(erpnext["commit"] == baseline["source_commit"], "source_commit must equal ERPNext evaluation commit")

    references = document.get("references")
    expect(isinstance(references, list), "references must be an array")
    for reference in references:
        validate_repository_pinned(reference, "references")

    integration_tests = document.get("integration_tests")
    expect(isinstance(integration_tests, list), "integration_tests must be an array")
    for record in integration_tests:
        manifest = REPOSITORY_ROOT / record["manifest"]
        declared_in = REPOSITORY_ROOT / record["declared_in"]
        expect(manifest.is_file(), f"Missing manifest: {manifest.relative_to(REPOSITORY_ROOT)}")
        expect(declared_in.is_file(), f"Missing declaration: {declared_in.relative_to(REPOSITORY_ROOT)}")
        if manifest.name == "yarn.lock":
            expect(record.get("locked_dependencies") is True, f"{manifest}: lockfile must be marked as locked")
            validate_local_project(manifest)

    root_package = read_json(REPOSITORY_ROOT / "package.json")
    root_version = (REPOSITORY_ROOT / "erpnext" / "__init__.py").read_text(encoding="utf-8")
    expect('__version__ = "17.0.0-dev"' in root_version, "Manifest did not expect the current development version")
    expect(root_package.get("name") == "erpnext", "Keep the technical ERPNext package identity in Phase 0")
    validate_python_manifest(REPOSITORY_ROOT / "pyproject.toml", REPOSITORY_ROOT / "erpnext" / "__init__.py")
    validate_release_config(tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")))
    if verify_ancestry:
        assert_local_ancestry(baseline["source_commit"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=REPOSITORY_ROOT / "cadro.baseline.json")
    parser.add_argument("--skip-ancestry", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    try:
        validate(arguments.manifest, verify_ancestry=not arguments.skip_ancestry)
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, BaselineValidationError, KeyError) as error:
        raise SystemExit(f"CADRO baseline check failed: {error}") from error
    print(f"CADRO evaluation baseline inputs are valid: {arguments.manifest}")
    print("Production approval still requires integrated Bench tests, SBOM and legal review.")
