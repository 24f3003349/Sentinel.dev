"use client";

import { useEffect, useMemo, useState } from "react";
import { KnowledgeGraph } from "./components/KnowledgeGraph";
import { TerminalLog, type TerminalReport } from "./components/TerminalLog";
import { projectFor, projects, type ProjectId } from "./data/projects";

type Report = TerminalReport & { target?: string; status?: string; sandbox?: TerminalReport["sandbox"] & { telemetry?: { cpu_percent: number; memory_bytes: number }[] } };

const targetFrom = (report: Report | null): ProjectId => {
  const target = report?.target ?? "";
  if (target.includes("memory_leak")) return "memory_leak";
  if (target.includes("redos_attack")) return "redos_attack";
  return "race_condition";
};

function Metric({ label, value, detail, children }: Readonly<{ label: string; value: string; detail: string; children?: React.ReactNode }>) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small>{children}</div>;
}

export default function Page() {
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState<ProjectId>("race_condition");
  useEffect(() => {
    const load = () => fetch("/api/report", { cache: "no-store" }).then((response) => response.json()).then((next: Report) => { setReport(next); setSelected(targetFrom(next)); }).catch(() => setReport(null));
    load(); const timer = window.setInterval(load, 2500); return () => window.clearInterval(timer);
  }, []);
  const project = projectFor(selected);
  const telemetry = report?.sandbox?.telemetry ?? [];
  const memory = Math.max(0, ...telemetry.map((sample) => sample.memory_bytes)) / 1024 / 1024;
  const cpu = Math.max(0, ...telemetry.map((sample) => sample.cpu_percent));
  const state = report?.verification?.status ?? report?.sandbox?.status ?? report?.status ?? "waiting";
  const isStable = state === "passed" || state === "waiting";
  return <main className="war-room">
    <header className="topbar"><p className="wordmark">SENTINEL.DEV <span>/</span> WAR ROOM</p><nav className="project-tabs" aria-label="Select a local target">{projects.map((item) => <button key={item.id} onClick={() => setSelected(item.id)} className={selected === item.id ? "active" : ""}><i />{item.label}</button>)}</nav><span className={`system-status ${isStable ? "stable" : "gated"}`}>{isStable ? "SYSTEM: STABLE" : "CI GATED"}</span></header>
    <section className="hero"><div><p className="kicker">Deployment survivability / local code graph</p><h1>See the failure<br /><em>before production does.</em></h1></div><p className="hero-copy">Graphify maps the dependency surface. Sentinel then probes the boundary ordinary local tests leave behind.</p></section>
    <section className="telemetry" aria-label="Arena telemetry">
      <Metric label="Peak memory" value={`${memory.toFixed(1)} MiB`} detail={`${((memory / 256) * 100).toFixed(1)}% of 256 MiB arena`} />
      <Metric label="CPU core load" value={`${cpu.toFixed(1)}%`} detail="10 sample capacity"><span className="micro-bars">{Array.from({ length: 10 }, (_, index) => <i key={index} className={index < Math.ceil(cpu / 10) ? "on" : ""} />)}</span></Metric>
      <Metric label="DEFCON risk intensity" value="5 / 5" detail="bounded defensive probe" />
      <Metric label="Active swarm probe" value={project.probe} detail="localhost only" />
    </section>
    <KnowledgeGraph project={project} />
    <TerminalLog report={report} probe={project.probe} />
    <footer><span>Graphify maps local source only.</span><span>Docker arena has no host mounts or external network.</span><span>Report refreshes every 2.5 seconds.</span></footer>
  </main>;
}
