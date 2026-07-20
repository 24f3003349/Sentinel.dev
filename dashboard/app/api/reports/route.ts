import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export async function GET() {
  const directory = resolve(process.cwd(), "..", "reports");
  if (!existsSync(directory)) return NextResponse.json({ reports: {} });
  const reports: Record<string, unknown> = {};
  for (const file of readdirSync(directory).filter((name) => name.endsWith(".json") && name !== "latest.json")) {
    try { reports[file.replace(/\.json$/, "")] = JSON.parse(readFileSync(resolve(directory, file), "utf8")); } catch { /* Ignore malformed historical report. */ }
  }
  if (!Object.keys(reports).length && existsSync(resolve(directory, "latest.json"))) {
    try { const latest = JSON.parse(readFileSync(resolve(directory, "latest.json"), "utf8")); reports[String(latest.target ?? "latest").split(/[\\/]/).pop() ?? "latest"] = latest; } catch { /* Return empty evidence set. */ }
  }
  return NextResponse.json({ reports });
}
