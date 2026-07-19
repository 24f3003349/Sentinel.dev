"""Required Graphify integration, read through its local graph.json output.

Graphify is the sole mapper. It creates an on-device NetworkX node-link graph
under ``graphify-out/graph.json`` and does not require Neo4j or any service.
Sentinel only normalizes that upstream graph into its small agent contract.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import networkx as nx

from sentinel.schemas import GraphEdge, GraphNode, KnowledgeGraph


def _run_graphify(target: Path) -> Path:
    """Build a fresh graph using the upstream Graphify Python module."""
    # Code-only is deliberate: Graphify's local AST extractor needs no LLM/API
    # key, while docs/images semantic extraction is outside Sentinel's CI scope.
    args = [
        sys.executable, "-m", "graphify", "extract", str(target), "--force",
        "--code-only", "--no-cluster",
    ]
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "Graphify is required. Install the declared graphifyy dependency and retry. "
            f"Upstream extractor failed: {exc}"
        ) from exc
    output = target / "graphify-out" / "graph.json"
    if not output.is_file():
        raise RuntimeError("Graphify completed without graphify-out/graph.json; refusing to use a substitute map.")
    return output


def build_graph(target: Path, focus: str = "book") -> KnowledgeGraph:
    target = target.resolve()
    payload = json.loads(_run_graphify(target).read_text(encoding="utf-8"))
    raw_nodes = payload.get("nodes", [])
    raw_edges = payload.get("edges", payload.get("links", []))
    nodes = [
        GraphNode(
            id=str(item["id"]),
            kind=str(item.get("kind", item.get("type", item.get("file_type", "symbol")))),
            file=str(item.get("source_file", item.get("file", ""))),
            line=int(item.get("line", item.get("line_start", 0)) or 0),
            label=str(item.get("label", item["id"])),
        )
        for item in raw_nodes
    ]
    edges = [
        GraphEdge(
            source=str(item["source"]), target=str(item["target"]), relation=str(item.get("relation", "references"))
        )
        for item in raw_edges
    ]
    result = KnowledgeGraph(provider="graphify", nodes=nodes, edges=edges)
    result.blast_radius = _blast_radius(result, focus)
    return result


def _blast_radius(graph: KnowledgeGraph, focus: str) -> list[str]:
    directed = nx.DiGraph()
    directed.add_edges_from((edge.source, edge.target) for edge in graph.edges)
    anchors = [node.id for node in graph.nodes if focus.lower() in node.label.lower()]
    affected: set[str] = set(anchors)
    for anchor in anchors:
        if anchor in directed:
            affected.update(nx.ancestors(directed, anchor))
            affected.update(nx.descendants(directed, anchor))
    return sorted(affected)


def graph_as_dict(graph: KnowledgeGraph) -> dict:
    return graph.model_dump(mode="json")
