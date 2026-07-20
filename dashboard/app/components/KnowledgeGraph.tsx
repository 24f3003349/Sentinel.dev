"use client";

import { useState } from "react";
import { type GraphPoint, type ProjectView } from "../data/projects";

export interface KnowledgeGraphProps { readonly project: ProjectView; }

function connected(edge: readonly [string, string], nodeId: string | null) { return nodeId !== null && (edge[0] === nodeId || edge[1] === nodeId); }
function edgeRisk(edge: readonly [string, string], nodes: Map<string, GraphPoint>) { return edge.some((id) => nodes.get(id)?.tone === "risk"); }

export function KnowledgeGraph({ project }: KnowledgeGraphProps) {
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const byId = new Map(project.nodes.map((node) => [node.id, node]));
  return <section className="knowledge-panel" aria-label={`${project.label} knowledge graph`}>
    <div className="section-heading"><div><p className="kicker">Graphify knowledge graph</p><h2>{project.label}</h2></div><p className="graph-summary">{project.summary}</p></div>
    <div className={`graph-canvas ${activeNode ? "has-active-node" : ""}`}>
      <svg className="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {project.edges.map(([sourceId, targetId]) => {
          const source = byId.get(sourceId); const target = byId.get(targetId); if (!source || !target) return null;
          const classes = ["graph-edge", edgeRisk([sourceId, targetId], byId) ? "graph-edge--risk" : "", connected([sourceId, targetId], activeNode) ? "graph-edge--active" : ""].filter(Boolean).join(" ");
          return <line className={classes} key={`${sourceId}-${targetId}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
        })}
      </svg>
      {project.nodes.map((node) => <button key={node.id} onMouseEnter={() => setActiveNode(node.id)} onMouseLeave={() => setActiveNode(null)} onFocus={() => setActiveNode(node.id)} onBlur={() => setActiveNode(null)} className={`graph-dot graph-dot--${node.tone} ${node.major ? "graph-dot--major" : ""} ${activeNode === node.id ? "is-active" : ""}`} style={{ left: `${node.x}%`, top: `${node.y}%` }} aria-label={`${node.label}: ${node.detail}`}><span className="graph-tooltip"><b>{node.label}</b><em>{node.detail}</em></span></button>)}
      <span className="graph-watermark">GRAPHIFY / LOCAL CONTEXT</span>
    </div>
    <div className="graph-legend" aria-label="Graph legend"><span><i className="module" /> module root</span><span><i className="risk" /> risk path</span><span><i className="test" /> local test</span><span className="legend-hint">hover a node to trace relations</span></div>
  </section>;
}
