"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";

type GraphRecord = { id: string; label: string; kind: string; file?: string; line?: number };
type GraphEdge = { source: string; target: string; relation?: string };
type Report = {
  sandbox?: { status?: string; stdout?: string; stderr?: string; telemetry?: { cpu_percent: number; memory_bytes: number }[] };
  graph?: { nodes?: GraphRecord[]; edges?: GraphEdge[] };
  verification?: { status?: string };
  chaos?: { title?: string };
  status?: string;
};
type Tone = "module" | "function" | "risk" | "test" | "context" | "dependency";
type GraphNodeData = { label: string; meta: string; tone: Tone };

const RISK_WORDS = /book|export|validate|race|redos|memory/i;
const SEMANTIC_RELATIONS = new Set(["contains", "calls", "rationale_for", "imports_from", "references"]);

function toneFor(node: GraphRecord): Tone {
  const label = node.label.toLowerCase();
  if (RISK_WORDS.test(node.label) && !label.endsWith(".py")) return "risk";
  if (node.kind === "rationale") return "context";
  if (label.includes("test") || node.file?.startsWith("test_")) return "test";
  if (node.label.endsWith(".py")) return "module";
  if (node.label === "FastAPI") return "dependency";
  return "function";
}

function rankFor(node: GraphRecord, tone: Tone): number {
  if (tone === "context") return 0;
  if (tone === "module" || tone === "dependency") return 1;
  if (tone === "risk" || tone === "function") return 2;
  return 3;
}

function SentinelNode({ data }: NodeProps) {
  const node = data as GraphNodeData;
  return (
    <div className={`sentinel-node tone-${node.tone}`}>
      <Handle type="target" position={Position.Left} className="sentinel-handle" />
      <span className="node-kicker">{node.meta}</span>
      <strong>{node.label}</strong>
      <Handle type="source" position={Position.Right} className="sentinel-handle" />
    </div>
  );
}

const nodeTypes = { sentinel: SentinelNode };

function TerminalPanel({ report }: { report: Report | null }) {
  const host = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  useEffect(() => {
    if (host.current && !terminal.current) {
      terminal.current = new Terminal({ convertEol: true, rows: 12, theme: { background: "#020504", foreground: "#8cfcc1" } });
      terminal.current.open(host.current);
    }
    const lines = report?.sandbox
      ? `[MAP] ${report.chaos?.title ?? "Graphify report loaded"}\r\n[ARENA] ${report.sandbox.status?.toUpperCase()}\r\n${report.sandbox.stdout ?? ""}${report.sandbox.stderr ?? ""}\r\n[VERIFY] ${report.verification?.status ?? "awaiting patch"}`
      : "[SYSTEM] Run Sentinel to stream a fresh local report ...";
    terminal.current?.clear();
    terminal.current?.write(lines);
  }, [report]);
  return <div className="terminal-host" ref={host} aria-label="Sentinel execution terminal" />;
}

function graphFrom(report: Report | null): { nodes: Node[]; edges: Edge[] } {
  const raw = (report?.graph?.nodes ?? []).slice(0, 14);
  const counters = [0, 0, 0, 0];
  const columns = [28, 230, 468, 740];
  const nodes = raw.map((record) => {
    const tone = toneFor(record);
    const rank = rankFor(record, tone);
    const slot = counters[rank]++;
    const y = rank === 2 ? 32 + slot * 78 : 48 + slot * 114;
    const meta = record.file ? `${record.file}${record.line ? ` · ${record.line}` : ""}` : record.kind;
    return {
      id: record.id,
      type: "sentinel",
      data: { label: record.label, meta, tone },
      position: { x: columns[rank], y },
      draggable: false,
      selectable: false,
    } satisfies Node;
  });
  const known = new Set(nodes.map((node) => node.id));
  const edges = (report?.graph?.edges ?? [])
    .filter((edge) => known.has(edge.source) && known.has(edge.target) && SEMANTIC_RELATIONS.has(edge.relation ?? ""))
    .map((edge, index) => {
      const risky = nodes.find((node) => node.id === edge.source || node.id === edge.target)?.data as GraphNodeData | undefined;
      const color = risky?.tone === "risk" ? "#ff7078" : edge.relation === "calls" ? "#6bdbff" : "#4c8f76";
      return {
        id: `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: edge.relation === "calls",
        style: { stroke: color, strokeWidth: edge.relation === "calls" ? 2 : 1.25, opacity: 0.8 },
        markerEnd: { type: MarkerType.ArrowClosed, color },
      } satisfies Edge;
    });
  return { nodes, edges };
}

function WarRoom() {
  const [defcon, setDefcon] = useState(5);
  const [report, setReport] = useState<Report | null>(null);
  useEffect(() => {
    const load = () => fetch("/api/report", { cache: "no-store" }).then((response) => response.json()).then(setReport).catch(() => setReport(null));
    load();
    const timer = window.setInterval(load, 2500);
    return () => window.clearInterval(timer);
  }, []);
  const graph = useMemo(() => graphFrom(report), [report]);
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (graph.nodes.length) {
      const frame = window.requestAnimationFrame(() => fitView({ padding: 0.16, maxZoom: 1.05 }));
      return () => window.cancelAnimationFrame(frame);
    }
  }, [fitView, graph.edges.length, graph.nodes.length]);
  const telemetry = report?.sandbox?.telemetry ?? [];
  const peakMemory = Math.max(0, ...telemetry.map((sample) => sample.memory_bytes)) / 1024 / 1024;
  const peakCpu = Math.max(0, ...telemetry.map((sample) => sample.cpu_percent));
  const status = report?.verification?.status ?? report?.sandbox?.status ?? report?.status ?? "waiting";
  return <main>
    <header><div><span className="eyebrow">SENTINEL.DEV / GRAPHIFY / CHAOS CI</span><h1>War Room</h1></div><span className={`status ${status}`}>● {status.toUpperCase()}</span></header>
    <section className="metrics"><div><span>PEAK MEMORY</span><b>{peakMemory.toFixed(1)} MiB</b></div><div><span>PEAK CPU</span><b>{peakCpu.toFixed(1)}%</b></div><div><span>ACTIVE PROBE</span><b>{report?.chaos?.title ?? "Awaiting run"}</b></div></section>
    <section className="grid">
      <article className="card controls-card"><span className="eyebrow">CHAOS INTENSITY</span><h2>DEFCON {defcon}</h2><input aria-label="Chaos intensity" type="range" min="1" max="5" value={defcon} onChange={(event) => setDefcon(+event.target.value)} /><p>Sentinel keeps this probe bounded. The graph highlights the risky handler in red, source modules in green, and test coverage in violet.</p></article>
      <article className="card graph"><div className="graph-heading"><div><span className="eyebrow">LIVE BLAST RADIUS</span><p>Graphify dependency flow · red = attacked handler</p></div><span className="legend"><i className="legend-risk" /> at risk</span></div><ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.16, maxZoom: 1.05 }} minZoom={0.45} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} elementsSelectable={false} proOptions={{ hideAttribution: true }}><Background color="#1a3f34" gap={22} size={1} /><Controls showInteractive={false} /></ReactFlow></article>
      <article className="card terminal"><span className="eyebrow">GLADIATOR TERMINAL</span><TerminalPanel report={report} /></article>
    </section>
    <footer>Graphify maps local code only. Docker executes the probe locally; no source is uploaded.</footer>
  </main>;
}

export default function Page() { return <ReactFlowProvider><WarRoom /></ReactFlowProvider>; }
