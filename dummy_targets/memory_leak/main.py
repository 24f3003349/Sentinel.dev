"""Intentionally memory-unsafe export endpoint used only by the Sentinel demo."""
import asyncio

from fastapi import FastAPI

app = FastAPI(title="Sentinel memory-pressure target")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/export")
async def export_data(size_mb: int = 1) -> dict[str, int | str]:
    # Deliberately loads all chunks into RAM rather than streaming them.
    chunks = [bytearray(1024 * 1024) for _ in range(size_mb)]
    # Keep the allocation alive long enough for Sentinel telemetry to observe it.
    if size_mb > 64:
        await asyncio.sleep(2)
    return {"status": "success", "bytes": sum(len(chunk) for chunk in chunks)}
