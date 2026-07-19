"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Background, Controls, Edge, Node, ReactFlow, ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";

type Report = { sandbox?: { status?: string; stdout?: string; stderr?: string; telemetry?: { cpu_percent: number; memory_bytes: number }[] }; graph?: { nodes?: { id: string; label: string; kind: string }[]; edges?: { source: string; target: string }[] }; verification?: { status?: string }; chaos?: { title?: string }; status?: string; message?: string };

function TerminalPanel({ report }: { report: Report | null }) {
  const host = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  useEffect(() => {
    if (host.current && !terminal.current) {
      terminal.current = new Terminal({ convertEol: true, rows: 12, theme: { background: "#020504", foreground: "#8cfcc1" } });
      terminal.current.open(host.current);
    }
    const lines = report?.sandbox ? `[MAP] ${report.chaos?.title ?? "Graphify report loaded"}\r\n[ARENA] ${report.sandbox.status?.toUpperCase()}\r\n${report.sandbox.stdout ?? ""}${report.sandbox.stderr ?? ""}\r\n[VERIFY] ${report.verification?.status ?? "awaiting patch"}` : "[SYSTEM] Waiting for reports/latest.json ...";
    terminal.current?.clear();
    terminal.current?.write(lines);
  }, [report]);
  return <div className="terminal-host" ref={host} aria-label="Sentinel execution terminal" />;
}

function WarRoom() {
  const [defcon, setDefcon] = useState(5);
  const [report, setReport] = useState<Report | null>(null);
  useEffect(() => {
    const load = () => fetch("/api/report", { cache: "no-store" }).then((r) => r.json()).then(setReport).catch(() => setReport(null));
    load(); const timer = window.setInterval(load, 2500); return () => window.clearInterval(timer);
  }, []);
  const graph = useMemo(() => {
    const nodes: Node[] = (report?.graph?.nodes ?? []).slice(0, 12).map((node, index) => ({ id: node.id, data: { label: node.label }, position: { x: (index % 4) * 185, y: Math.floor(index / 4) * 110 }, className: node.label.toLowerCase().includes("book") ? "risk-node" : "graph-node" }));
    const ids = new Set(nodes.map((node) => node.id));
    const edges: Edge[] = (report?.graph?.edges ?? []).filter((edge) => ids.has(edge.source) && ids.has(edge.target)).slice(0, 18).map((edge, index) => ({ id: `${edge.source}-${edge.target}-${index}`, source: edge.source, target: edge.target, animated: true }));
    return { nodes, edges };
  }, [report]);
  const telemetry = report?.sandbox?.telemetry ?? [];
  const peakMemory = Math.max(0, ...telemetry.map((sample) => sample.memory_bytes)) / 1024 / 1024;
  const peakCpu = Math.max(0, ...telemetry.map((sample) => sample.cpu_percent));
  const status = report?.verification?.status ?? report?.sandbox?.status ?? report?.status ?? "waiting";
  return <main>
    <header><div><span className="eyebrow">SENTINEL.DEV / GRAPHIFY / CHAOS CI</span><h1>War Room</h1></div><span className={`status ${status}`}>● {status.toUpperCase()}</span></header>
    <section className="metrics"><div><span>PEAK MEMORY</span><b>{peakMemory.toFixed(1)} MiB</b></div><div><span>PEAK CPU</span><b>{peakCpu.toFixed(1)}%</b></div><div><span>ACTIVE PROBE</span><b>{report?.chaos?.title ?? "Awaiting run"}</b></div></section>
    <section className="grid"><article className="card"><span className="eyebrow">CHAOS INTENSITY</span><h2>DEFCON {defcon}</h2><input aria-label="Chaos intensity" type="range" min="1" max="5" value={defcon} onChange={(event) => setDefcon(+event.target.value)} /><p>CLI uses DEFCON to set the bounded probe intensity. Run <code>sentinel attack --defcon {defcon}</code>.</p></article><article className="card graph"><span className="eyebrow">LIVE BLAST RADIUS</span><ReactFlow nodes={graph.nodes} edges={graph.edges} fitView><Background /><Controls /></ReactFlow></article><article className="card terminal"><span className="eyebrow">GLADIATOR TERMINAL</span><TerminalPanel report={report} /></article></section>
    <footer>Report refreshes every 2.5 seconds from the local Sentinel API route. Docker data remains local.</footer>
  </main>;
}

export default function Page() { return <ReactFlowProvider><WarRoom /></ReactFlowProvider>; }
