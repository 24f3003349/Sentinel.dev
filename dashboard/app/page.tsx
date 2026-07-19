"use client";
import { useState } from "react";

const logs = ["[MAP] 11 nodes indexed — blast radius constrained", "[CHAOS] concurrent inventory invariant probe armed", "[ARENA] INVARIANT_VIOLATION: oversold ticket inventory", "[HEAL] branch sentinel/fix-race-condition committed"];

export default function WarRoom() {
  const [defcon, setDefcon] = useState(5);
  return <main>
    <header><div><span className="eyebrow">SENTINEL.DEV / CI SURVIVABILITY</span><h1>War Room</h1></div><span className="status">● PATCH READY</span></header>
    <section className="grid">
      <article className="card"><span className="eyebrow">CHAOS INTENSITY</span><h2>DEFCON {defcon}</h2><input aria-label="Chaos intensity" type="range" min="1" max="5" value={defcon} onChange={e => setDefcon(+e.target.value)} /><p>Bounded concurrency: {defcon * 25} simulated checkouts</p></article>
      <article className="card"><span className="eyebrow">BLAST RADIUS</span><div className="graph"><b className="node red">checkout</b><i>calls</i><b className="node red">book</b><i>mutates</i><b className="node green">inventory lock</b></div></article>
      <article className="card terminal"><span className="eyebrow">GLADIATOR TERMINAL</span>{logs.map(log => <p key={log}>{log}</p>)}</article>
    </section>
    <footer>Local-first demo • Docker telemetry when available • Git branch remediation</footer>
  </main>;
}
