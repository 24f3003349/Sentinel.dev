from pathlib import Path

import pytest

from . import main


@pytest.mark.asyncio
async def test_happy_path_single_customer(monkeypatch) -> None:
    database = Path(__file__).with_name("test-tickets.db")
    database.unlink(missing_ok=True)
    monkeypatch.setattr(main, "DB_FILE", database)
    try:
        main.init_db()
        result = await main.book_ticket()
        assert result["status"] == "success"
    finally:
        # Windows can retain SQLite's file handle until interpreter shutdown.
        # The file is ignored and is removed before the next test run.
        pass
