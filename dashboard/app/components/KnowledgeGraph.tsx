"use client";

import { useMemo, useState } from "react";

export type EvidenceGraph = Readonly<{ provider?: string; nodes?: { id: string; label: string; kind: string; file?: string; line?: number }[]; edges?: { source: string; target: string; relation?: string }[]; blast_radius?: string[] }>;
export interface KnowledgeGraphProps { readonly graph?: EvidenceGraph; readonly targetLabel: string; }
type Point = { id: string; label: string; detail: string; tone: "module" | "blast" | "test" | "function"; x: number; y: number; major?: boolean };

function layout(graph?: EvidenceGraph): { points: Point[]; edges: { source: string; target: string; relation: string }[] } {
  const nodes = graph?.nodes ?? []; const present = new Set(nodes.map((node) => node.id));
  const edges = (graph?.edges ?? []).filter((edge) => present.has(edge.source) && present.has(edge.target)).map((edge) => ({ ...edge, relation: edge.relation ?? "related" }));
  if (!nodes.length) return { points: [], edges };
  const root = nodes.find((node) => node.label === "main.py") ?? nodes[0];
  const direct = [...new Set(edges.filter((edge) => edge.source === root.id || edge.target === root.id).map((edge) => edge.source === root.id ? edge.target : edge.source))];
  const blast = new Set(graph?.blast_radius ?? []);
  const pointFor = (node: typeof nodes[number], index: number): Point => {
    if (node.id === root.id) return { id: node.id, label: node.label, detail: `${node.file || "local graph"}${node.line ? ` · L${node.line}` : ""}`, tone: "module", x: 50, y: 48, major: true };
    const primary = direct.indexOf(node.id); const ring = primary >= 0 ? 1 : 2; const count = ring === 1 ? Math.max(1, direct.length) : Math.max(1, nodes.length - direct.length - 1); const position = ring === 1 ? primary : Math.max(0, index - 1 - direct.length); const angle = (-Math.PI / 2) + (position / count) * Math.PI * 2 + (ring === 2 ? .27 : 0);
    const radiusX = ring === 1 ? 17 : 28; const radiusY = ring === 1 ? 23 : 34;
    const tone = blast.has(node.id) ? "blast" : (node.file?.startsWith("test_") || node.label.includes("test_") ? "test" : (node.label.endsWith(".py") ? "module" : "function"));
    return { id: node.id, label: node.label, detail: `${node.file || node.kind}${node.line ? ` · L${node.line}` : ""}`, tone, x: 50 + Math.cos(angle) * radiusX, y: 48 + Math.sin(angle) * radiusY };
  };
  return { points: nodes.map(pointFor), edges };
}

export function KnowledgeGraph({ graph, targetLabel }: KnowledgeGraphProps) {
  const [activeNode, setActiveNode] = useState<string | null>(null); const { points, edges } = useMemo(() => layout(graph), [graph]); const byId = new Map(points.map((node) => [node.id, node]));
  if (!points.length) return <section className="knowledge-panel"><div className="section-heading"><div><p className="kicker">Graphify knowledge graph</p><h2>No scan evidence yet</h2></div></div><div className="graph-empty">Run Sentinel against {targetLabel} to populate this graph from Graphify output.</div></section>;
  return <section className="knowledge-panel" aria-label={`${targetLabel} Graphify knowledge graph`}><div className="section-heading"><div><p className="kicker">Graphify knowledge graph</p><h2>{targetLabel}</h2></div><p className="graph-summary">{points.length} nodes · {edges.length} verified relationships · provider: {graph?.provider ?? "unknown"}</p></div><div className={`graph-canvas ${activeNode ? "has-active-node" : ""}`}><svg className="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{edges.map((edge) => { const source = byId.get(edge.source); const target = byId.get(edge.target); if (!source || !target) return null; const active = activeNode === edge.source || activeNode === edge.target; const blast = source.tone === "blast" || target.tone === "blast"; return <line className={`graph-edge ${blast ? "graph-edge--risk" : ""} ${active ? "graph-edge--active" : ""}`} key={`${edge.source}-${edge.target}-${edge.relation}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />; })}</svg>{points.map((node) => <button key={node.id} onMouseEnter={() => setActiveNode(node.id)} onMouseLeave={() => setActiveNode(null)} onFocus={() => setActiveNode(node.id)} onBlur={() => setActiveNode(null)} className={`graph-dot graph-dot--${node.tone} ${node.major ? "graph-dot--major" : ""} ${activeNode === node.id ? "is-active" : ""}`} style={{ left: `${node.x}%`, top: `${node.y}%` }} aria-label={`${node.label}: ${node.detail}`}><span className="graph-tooltip"><b>{node.label}</b><em>{node.detail}</em></span></button>)}<span className="graph-watermark">GRAPHIFY / REPORT EVIDENCE</span></div><div className="graph-legend"><span><i className="module" /> module</span><span><i className="risk" /> Graphify blast radius</span><span><i className="test" /> local test</span><span className="legend-hint">hover a node to trace verified relations</span></div></section>;
}
