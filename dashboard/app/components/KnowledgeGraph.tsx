"use client";

import { type ProjectView } from "../data/projects";

export interface KnowledgeGraphProps { readonly project: ProjectView; }

const toneClass = (tone: string) => `graph-dot graph-dot--${tone}`;

export function KnowledgeGraph({ project }: KnowledgeGraphProps) {
  const byId = new Map(project.nodes.map((node) => [node.id, node]));
  return (
    <section className="knowledge-panel" aria-label={`${project.label} knowledge graph`}>
      <div className="section-heading">
        <div><p className="kicker">Graphify knowledge graph</p><h2>{project.label}</h2></div>
        <p className="graph-summary">{project.summary}</p>
      </div>
      <div className="graph-canvas">
        <svg className="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {project.edges.map(([sourceId, targetId]) => {
            const source = byId.get(sourceId); const target = byId.get(targetId);
            if (!source || !target) return null;
            return <line key={`${sourceId}-${targetId}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
          })}
        </svg>
        {project.nodes.map((node) => (
          <button key={node.id} className={toneClass(node.tone)} style={{ left: `${node.x}%`, top: `${node.y}%` }} aria-label={`${node.label}: ${node.detail}`}>
            <span className="graph-tooltip"><b>{node.label}</b><em>{node.detail}</em></span>
          </button>
        ))}
        <span className="graph-watermark">GRAPHIFY / LOCAL CONTEXT</span>
      </div>
      <div className="graph-legend" aria-label="Graph legend"><span><i className="module" /> module</span><span><i className="risk" /> risk path</span><span><i className="test" /> local test</span></div>
    </section>
  );
}
