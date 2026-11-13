# SPDX-License-Identifier: Apache-2.0
"""Print declared license metadata for every exact package in requirements.lock.

Run with the project's installed environment. This is a metadata inventory,
not an SPDX SBOM or a determination of license compatibility.
"""
import json
from importlib.metadata import distribution
from pathlib import Path


def inventory():
    root = Path(__file__).resolve().parents[1]
    packages = []
    for line in (root / "requirements.lock").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        installed = distribution(name)
        if installed.version != version:
            raise ValueError(f"{name}: expected {version}, installed {installed.version}")
        metadata = installed.metadata
        packages.append({
            "name": name, "version": version,
            "license_expression": metadata.get("License-Expression"),
            "legacy_license": metadata.get("License"),
            "license_classifiers": [c for c in metadata.get_all("Classifier", [])
                                    if c.startswith("License ::")],
            "license_files": metadata.get_all("License-File", []),
            "project_urls": metadata.get_all("Project-URL", []),
        })
    return {"source": "installed distribution metadata matched to requirements.lock",
            "scope": "Python dependencies only; declarations require review",
            "packages": packages}


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
