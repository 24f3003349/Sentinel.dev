import { existsSync, readFileSync } from "node:fs";
import { NextResponse } from "next/server";
import { resolve } from "node:path";

export const dynamic = "force-dynamic";

export async function GET() {
  const file = process.env.SENTINEL_REPORT_PATH ?? resolve(process.cwd(), "..", "reports", "latest.json");
  if (!existsSync(file)) {
    return NextResponse.json({ status: "waiting", message: "Run Sentinel to populate reports/latest.json." });
  }
  try {
    return NextResponse.json(JSON.parse(readFileSync(file, "utf8")));
  } catch {
    return NextResponse.json({ status: "invalid", message: "Sentinel report is not valid JSON." }, { status: 500 });
  }
}
