# SPDX-License-Identifier: Apache-2.0
"""Reviewed mapping for the supplied company overview, not a general extractor."""
import hashlib
import json
import re
from pathlib import Path

from .data import V1, validate

SERVICES = {
    "Orbital Flights": "orbital-flights",
    "Lunar Excursions": "lunar-excursions",
    "Space Hotel Stays": "space-hotel-stays",
    "Lunar Photography Tours": "lunar-photography-tours",
}
SOURCE = "galaxium:company-overview"


def prepare_documents(source, ontology=None):
    version = (ontology or V1)["version"]
    text = Path(source).read_text(encoding="utf-8")
    if "## Galaxium Travels - Company Overview" not in text:
        raise ValueError("Expected the supplied Galaxium Travels company overview")
    match = re.search(r"^## Primary Services\s*\n(.*?)^## Future Plans\s*$", text,
                      re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError("Expected Primary Services followed by Future Plans")
    section = match.group(1).strip()
    blocks = re.split(r"(?m)(?=^- [^\n]+ \d+\.\s*$)", section)
    services = {}
    for block in blocks:
        if not block.strip():
            continue
        heading = re.match(r"- (.+?) \d+\.\s*\n", block)
        if not heading or heading[1] not in SERVICES or heading[1] in services:
            raise ValueError("Unrecognized or duplicate service heading; review the mapping")
        services[heading[1]] = block.strip()
    lunar = services.get("Lunar Excursions", "")
    if "Moon surface exploration" not in lunar:
        raise ValueError("This mapping requires the lunar Moon evidence; review changed semantics")
    company = {"id": "galaxium", "name": "Galaxium Travels", "type": "Company"}
    entities = [{"id": SERVICES[name], "name": name, "type": "Service"} for name in services]
    names = "\n".join(f"- {name}" for name in services)
    # Include the full primary-services excerpt so detail edits also change its fingerprint.
    overview = {
        "id": "company-overview", "title": "Galaxium Travels primary services",
        "source": SOURCE + "#primary-services", "ontology_version": version,
        "source_version": hashlib.sha256(section.encode()).hexdigest(),
        "text": "Galaxium Travels offers these primary services:\n" + names + "\n\nSource excerpt:\n" + section,
        "entities": [company, *entities],
        "facts": [{"subject": "galaxium", "relation": "OFFERS", "object": e["id"]} for e in entities],
    }
    itinerary = {
        "id": "lunar-itinerary", "title": "Galaxium Travels lunar service",
        # A narrower anchor than the company document, so citations show which block supports the fact.
        "source": SOURCE + "#lunar-excursions", "ontology_version": version,
        "source_version": hashlib.sha256(lunar.encode()).hexdigest(),
        "text": "Galaxium Travels Lunar Excursions:\n" + lunar,
        "entities": [{"id": "lunar-excursions", "name": "Lunar Excursions", "type": "Service"},
                     {"id": "moon", "name": "Moon", "type": "Destination"}],
        "facts": [{"subject": "lunar-excursions", "relation": "VISITS", "object": "moon"}],
    }
    return [validate(overview, ontology), validate(itinerary, ontology)]


def write_documents(source, output, ontology=None):
    documents = prepare_documents(source, ontology)
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, document in zip(("company.json", "lunar.json"), documents):
        (directory / filename).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return documents
