"""Intentionally vulnerable booking domain used only by the Sentinel demonstration."""
from __future__ import annotations

import asyncio


class BookingService:
    def __init__(self, initial_inventory: dict[str, int]) -> None:
        self.inventory = dict(initial_inventory)

    async def book(self, ticket_id: str) -> dict[str, bool]:
        available = self.inventory.get(ticket_id, 0)
        if available <= 0:
            return {"confirmed": False}
        # Intentional check-then-act race: all concurrent callers can read 1 here.
        await asyncio.sleep(0.005)
        self.inventory[ticket_id] = available - 1
        return {"confirmed": True}
