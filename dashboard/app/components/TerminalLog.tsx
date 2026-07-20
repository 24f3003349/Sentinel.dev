"use client";

export type TerminalReport = Readonly<{ sandbox?: { status?: string; stdout?: string; stderr?: string }; verification?: { status?: string }; chaos?: { title?: string } }>;
export interface TerminalLogProps { readonly report: TerminalReport | null; readonly probe: string; }

export function TerminalLog({ report, probe }: TerminalLogProps) {
  const sandbox = report?.sandbox;
  return <section className="terminal-panel" aria-label="Gladiator execution log">
    <div className="terminal-heading"><div><p className="kicker">Gladiator</p><h2>Last arena session</h2></div><span className="live-pulse">LOCAL ARENA</span></div>
    <div className="terminal-body">
      <p><span className="log-time">00:00.000</span><span className="log-info">[LOCAL TESTS]</span> happy path passed</p>
      <p><span className="log-time">00:00.184</span><span className="log-info">[MAP]</span> Graphify context assembled</p>
      <p><span className="log-time">00:00.311</span><span className="log-dim">[PROBE]</span> {report?.chaos?.title ?? probe}</p>
      {sandbox ? <><p><span className="log-time">00:01.927</span><span className={sandbox.status === "passed" ? "log-ok" : "log-risk"}>[ARENA]</span> {(sandbox.status ?? "unknown").toUpperCase()}</p><pre>{sandbox.stdout || sandbox.stderr || "No sandbox output recorded."}</pre><p><span className="log-time">00:02.104</span><span className={report?.verification?.status === "passed" ? "log-ok" : "log-dim"}>[VERIFY]</span> {(report?.verification?.status ?? "awaiting remediation").toUpperCase()}</p></> : <p className="log-dim"><span className="log-time">--:--.---</span> Run Sentinel to stream a fresh local report.</p>}
    </div>
  </section>;
}
