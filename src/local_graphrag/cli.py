# SPDX-License-Identifier: Apache-2.0
import argparse
import asyncio
import json


def main():
    parser = argparse.ArgumentParser(description="Local GraphRAG example")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate curated documents without services")
    validate.add_argument("--data", default="data/documents")
    validate.add_argument("--ontology", help="Validate against this ontology file; does not change the graph")
    diff = commands.add_parser("ontology-diff", help="Compare two ontology files; no services needed")
    diff.add_argument("old")
    diff.add_argument("new")
    prepare = commands.add_parser("prepare", help="Map the supplied company Markdown to curated JSON; no services needed")
    prepare.add_argument("--source", default="data/input-documents/galaxium-travels-company_overview.md")
    prepare.add_argument("--output", default="data/documents")
    prepare.add_argument("--ontology", help="Label and validate output for this ontology file (default v1)")
    ingest = commands.add_parser("ingest", help="Plan changes against the graph's active ontology; writes require --apply")
    ingest.add_argument("--data", default="data/documents")
    ingest.add_argument("--apply", action="store_true")
    ingest.add_argument("--skip-if-migrated", action="store_true",
                        help="Do nothing if the graph is on a newer ontology than the data (used by start.sh)")
    migrate = commands.add_parser("migrate", help="Plan moving stored documents to an approved ontology; writes require --apply")
    migrate.add_argument("--ontology", required=True)
    migrate.add_argument("--apply", action="store_true")
    commands.add_parser("inspect", help="Show the active ontology, document revisions and facts")
    commands.add_parser("serve", help="Run the read-only MCP server at the configured MCP_URL")
    ask = commands.add_parser("ask", help="Answer with the local agent")
    ask.add_argument("question")
    ask.add_argument("--trace", action="store_true",
                     help="Print JSON with model, prompt version, tool calls and answer")
    search = commands.add_parser("search", help="Test retrieval independently of the agent")
    search.add_argument("question")
    commands.add_parser("doctor", help="Check Neo4j, Ollama models and MCP discovery")
    args = parser.parse_args()
    from .data import load_documents, load_ontology
    if args.command == "prepare":
        from .prepare import write_documents
        ontology = load_ontology(args.ontology) if args.ontology else None
        documents = write_documents(args.source, args.output, ontology)
        print(f"Prepared {len(documents)} documents in {args.output}; graph unchanged")
        return
    if args.command == "ontology-diff":
        from .data import ontology_diff
        print(json.dumps(ontology_diff(load_ontology(args.old), load_ontology(args.new)), indent=2))
        return
    if args.command == "validate":
        try:
            ontology = load_ontology(args.ontology) if args.ontology else None
            count = len(load_documents(args.data, ontology))
        except (ValueError, OSError) as error:
            raise SystemExit(f"Rejected under {args.ontology or 'built-in v1'}: {error}")
        print(f"Validated {count} documents")
        if ontology:
            print(f"Validation only: ontology {ontology['version']} ({ontology['status']}); "
                  "the importer follows the graph's active ontology (graphrag inspect)")
        return
    from .config import Settings
    settings = Settings.load()
    if args.command == "serve":
        from .server import serve
        serve()
        return
    if args.command == "ask":
        from .agent import ask
        result = asyncio.run(ask(settings, args.question, args.trace))
        print(json.dumps(result, indent=2) if args.trace else result)
        return
    from .store import Store
    store = Store(settings)
    try:
        if args.command == "ingest":
            active = store.active_ontology()
            try:
                docs = load_documents(args.data, active)
            except ValueError as error:
                if args.skip_if_migrated and "Unsupported ontology version" in str(error) and active["version"] != "1":
                    print(f"Graph is on ontology {active['version']}; skipped importing {args.data}. "
                          "Reset with ./scripts/stop.sh --delete-data")
                    return
                raise SystemExit(f"Rejected under active ontology {active['version']}: {error}")
            if args.apply:
                store.schema()
                result = store.apply(docs)
            else:
                result = store.plan(docs)
        elif args.command == "migrate":
            try:
                target = load_ontology(args.ontology)
                result = store.migrate(target) if args.apply else store.migration_plan(target)
            except ValueError as error:
                raise SystemExit(f"Migration refused: {error}")
        elif args.command == "inspect":
            result = store.inspect()
        elif args.command == "search":
            result = [{**row, "graph": store.context(row["document_id"])}
                      for row in store.search(args.question)]
        else:
            from urllib.request import urlopen
            from fastmcp import Client
            store.driver.verify_connectivity()
            with urlopen(settings.ollama + "/api/tags", timeout=10) as response:
                models = {m["name"] for m in json.load(response)["models"]}
            missing = [m for m in (settings.chat_model, settings.embed_model)
                       if m not in models and f"{m}:latest" not in models]
            if missing:
                raise RuntimeError(f"Missing local Ollama models: {missing}")
            store.vector("Local embedding health check")
            async def check_mcp():
                async with Client(settings.mcp_url) as client:
                    return [t.name for t in await client.list_tools()]
            result = {"neo4j": "reachable", "models": sorted(models),
                      "mcp_tools": asyncio.run(check_mcp())}
        print(json.dumps(result, indent=2))
    finally:
        store.close()
