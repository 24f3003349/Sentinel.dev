"""Intentionally vulnerable SQLite ticket API used only by the Sentinel demo."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Sentinel race-condition target")
DB_FILE = Path(os.getenv("SENTINEL_DB_PATH", "/tmp/tickets.db"))


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, stock INTEGER NOT NULL)")
        connection.execute("INSERT OR REPLACE INTO inventory (id, stock) VALUES (1, 1)")


@app.on_event("startup")
def initialise() -> None:
    init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/book")
async def book_ticket() -> dict[str, int | str]:
    """Vulnerable check-then-act update: concurrent buyers can both succeed."""
    with sqlite3.connect(DB_FILE, timeout=1) as connection:
        stock = connection.execute("SELECT stock FROM inventory WHERE id = 1").fetchone()[0]
        if stock <= 0:
            raise HTTPException(status_code=400, detail="Sold out")
        await asyncio.sleep(0.04)
        connection.execute("UPDATE inventory SET stock = ? WHERE id = 1", (stock - 1,))
        return {"status": "success", "remaining_stock": stock - 1}
