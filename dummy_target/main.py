"""Tiny FastAPI façade for the crash-test booking domain."""
from fastapi import FastAPI
from pydantic import BaseModel

from domain import BookingService

app = FastAPI(title="Ticket Booking API — Sentinel demo")
service = BookingService({"concert-2026": 1})


class BookingRequest(BaseModel):
    ticket_id: str = "concert-2026"


@app.post("/checkout")
async def checkout(request: BookingRequest) -> dict[str, bool]:
    return await service.book(request.ticket_id)
