"""Intentionally ReDoS-prone validation endpoint used only by the Sentinel demo."""
import re

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Sentinel ReDoS target")
EMAIL_REGEX = re.compile(r"^(a+)+$")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/validate")
async def validate_input(payload: dict[str, str]) -> dict[str, str]:
    if not EMAIL_REGEX.fullmatch(payload.get("text", "")):
        raise HTTPException(status_code=400, detail="Invalid format")
    return {"status": "valid"}
