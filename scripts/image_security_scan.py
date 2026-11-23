#!/usr/bin/env python3
"""Generate the CycloneDX SBOM and a vulnerability summary of a CADRO image with Trivy.

Trivy runs in a container and reads the image through the Docker socket, so only Docker
is needed on the host.

usage: python scripts/image_security_scan.py [--image cadro-bench:eval] [--out docs/governance/sbom]
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

TRIVY_IMAGE = "aquasec/trivy:0.76.2"


def run_trivy(image: str, out_dir: Path, *args: str) -> None:
    command = [
        "docker", "run", "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{out_dir.resolve()}:/out",
        TRIVY_IMAGE, "image", "--quiet", *args, image,
    ]
    subprocess.run(command, check=True)  # nosec B603 - fixed docker command, image name is a CLI argument


def summarize(report: Path) -> str:
    data = json.loads(report.read_text(encoding="utf-8"))
    totals: collections.Counter[str] = collections.Counter()
    fixable: collections.Counter[str] = collections.Counter()
    lines = [f"image: {data.get('ArtifactName')}  os: {data.get('Metadata', {}).get('OS')}"]
    for result in data.get("Results", []):
        counts: collections.Counter[str] = collections.Counter()
        for vuln in result.get("Vulnerabilities") or []:
            counts[vuln["Severity"]] += 1
            totals[vuln["Severity"]] += 1
            if vuln.get("FixedVersion"):
                fixable[vuln["Severity"]] += 1
        lines.append(f"  {result.get('Class')}/{result.get('Type')}: {dict(counts)}")
    lines.append(f"total: {dict(totals)}")
    lines.append(f"with a fix available: {dict(fixable)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="cadro-bench:eval")
    parser.add_argument("--out", default="docs/governance/sbom", type=Path)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    run_trivy(args.image, args.out, "--format", "cyclonedx", "--output", "/out/cadro-bench.cdx.json")
    run_trivy(args.image, args.out, "--scanners", "vuln", "--format", "json", "--output", "/out/vulnerabilities.json")
    summary = summarize(args.out / "vulnerabilities.json")
    (args.out / "vulnerability-summary.txt").write_text(summary + "\n", encoding="utf-8")
    (args.out / "vulnerabilities.json").unlink()  # large raw report; regenerate when needed
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
