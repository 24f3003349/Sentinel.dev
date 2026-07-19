import pytest

from .main import validate_input


@pytest.mark.asyncio
async def test_happy_path_valid_input() -> None:
    assert await validate_input({"text": "aaaa"}) == {"status": "valid"}
