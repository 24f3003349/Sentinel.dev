import pytest

from .main import export_data


@pytest.mark.asyncio
async def test_happy_path_small_export() -> None:
    assert (await export_data(size_mb=1))["bytes"] == 1024 * 1024
