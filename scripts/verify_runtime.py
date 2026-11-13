# SPDX-License-Identifier: Apache-2.0
"""Capture read-only baseline runtime evidence after dedicated service tests."""
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Same wording as the README quick start, so recorded results stay comparable.
QUESTION = "Which destination can Galaxium Travels customers visit? Cite your sources."
LUNAR_SOURCE = "galaxium:company-overview#lunar-excursions"
# Baseline data has no training facts, so a grounded answer must say the evidence is missing.
ABSENT_QUESTION = "Which training does Lunar Excursions require before departure? Cite your sources."
MISSING_EVIDENCE = re.compile(
    r"no (information|evidence|mention|data|details)|not (mention|specif|contain|found|available|provide|include)"
    r"|does(n't| not) (mention|specify|say|state|contain|provide|include)|missing|cannot find|could not find",
    re.IGNORECASE)


def capture(command, timeout=60):
    try:
        environment = os.environ.copy()
        if command[0] == "ollama":
            from local_graphrag.config import Settings
            environment["OLLAMA_HOST"] = Settings.load().ollama
        result = subprocess.run(command, cwd=ROOT, env=environment,
                                capture_output=True, text=True, timeout=timeout)
        return {"command": command, "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        return {"command": command, "returncode": -1, "error": str(error)}


def main():
    now = datetime.now(timezone.utc)
    cli = [sys.executable, "-m", "local_graphrag"]
    steps = []
    for command in (["git", "rev-parse", "HEAD"], ["git", "status", "--short"],
                    ["ollama", "--version"], ["ollama", "list"],
                    [sys.executable, "-m", "pip", "freeze"], cli + ["doctor"]):
        steps.append(capture(command))
        if steps[-1]["returncode"]:
            break
    if all(step["returncode"] == 0 for step in steps):
        steps.append(capture(cli + ["search", QUESTION], timeout=180))
    if all(step["returncode"] == 0 for step in steps):
        steps.append(capture(cli + ["ask", "--trace", QUESTION], timeout=360))
    if all(step["returncode"] == 0 for step in steps):
        steps.append(capture(cli + ["ask", "--trace", ABSENT_QUESTION], timeout=360))
    checks = {}
    search = next((s for s in steps if s["command"] == cli + ["search", QUESTION]), None)
    if search and search["returncode"] == 0:
        try:
            rows = json.loads(search["stdout"])
            checks["retrieved_lunar_fact"] = any(
                fact.get("relation") == "VISITS" and fact.get("object") == "Moon"
                and fact.get("document_id") == "lunar-itinerary"
                for row in rows for fact in row.get("graph", []))
        except (ValueError, TypeError, AttributeError):
            checks["retrieved_lunar_fact"] = False
    answer = next((s for s in steps if s["command"] == cli + ["ask", "--trace", QUESTION]), None)
    if answer and answer["returncode"] == 0:
        try:
            traced = json.loads(answer["stdout"])
        except ValueError:
            traced = {"answer": "", "tool_calls": []}
        tools = [call.get("tool") for call in traced.get("tool_calls", [])]
        checks["answer_has_expected_citation"] = all(
            token in traced.get("answer", "") for token in
            ("Moon", "lunar-itinerary", LUNAR_SOURCE))
        # The prompt asks for search first, then graph expansion; the model may skip it.
        checks["agent_searched_then_expanded_graph"] = (
            "search_documents" in tools and "graph_context" in tools
            and tools.index("search_documents") < tools.index("graph_context"))
    absent = next((s for s in steps if s["command"] == cli + ["ask", "--trace", ABSENT_QUESTION]), None)
    if absent and absent["returncode"] == 0:
        try:
            text = json.loads(absent["stdout"]).get("answer", "")
        except ValueError:
            text = ""
        # Heuristic phrase match; read the answer to confirm it invents no training.
        checks["answer_reports_missing_evidence"] = bool(MISSING_EVIDENCE.search(text))
    passed = (all(s["returncode"] == 0 for s in steps)
              and len(checks) == 4 and all(checks.values()))
    directory = ROOT / ".runtime" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / (now.strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    output.write_text(json.dumps({"time_utc": now.isoformat(), "platform": platform.platform(),
                                  "python": sys.version, "steps": steps, "checks": checks,
                                  "passed": passed, "human_answer_review": "pending"}, indent=2) + "\n")
    print(f"{'PASS' if passed else 'FAIL'}: {output}; review answer evidence manually")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
