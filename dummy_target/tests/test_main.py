from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from domain import BookingService


@pytest.mark.asyncio
async def test_one_customer_can_book_the_only_ticket() -> None:
    """This deliberately happy-path test passes despite the production race."""
    service = BookingService({"concert-2026": 1})
    result = await service.book("concert-2026")
    assert result == {"confirmed": True}
    assert service.inventory["concert-2026"] == 0
