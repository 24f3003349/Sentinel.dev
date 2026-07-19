import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

DB_FILE = Path(os.getenv("SENTINEL_DB_PATH", "/tmp/tickets.db"))


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, stock INTEGER NOT NULL)")
        connection.execute("INSERT OR REPLACE INTO inventory (id, stock) VALUES (1, 1)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sentinel race-condition target", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/book")
async def book_ticket() -> dict[str, int | str]:
    with sqlite3.connect(DB_FILE, timeout=1) as connection:
        cursor = connection.execute(
            "UPDATE inventory SET stock = stock - 1 WHERE id = 1 AND stock > 0"
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=400, detail="Sold out")
        remaining = connection.execute("SELECT stock FROM inventory WHERE id = 1").fetchone()[0]
        return {"status": "success", "remaining_stock": remaining}
