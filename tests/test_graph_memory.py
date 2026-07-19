from sentinel.graph_memory import _blast_radius
from sentinel.schemas import GraphEdge, GraphNode, KnowledgeGraph


def test_graphify_normalized_graph_keeps_callers_and_callees() -> None:
    graph = KnowledgeGraph(
        provider="graphify",
        nodes=[GraphNode(id="checkout", kind="function", file="main.py", line=1, label="checkout"), GraphNode(id="book", kind="function", file="domain.py", line=9, label="book")],
        edges=[GraphEdge(source="checkout", target="book")],
    )
    assert _blast_radius(graph, "book") == ["book", "checkout"]
