"""
Backward-compatible entrypoint.

Prefer:
  uvicorn app.main:socket_app --reload --port 8001 --app-dir backend

This module re-exports the modular application so existing scripts keep working:
  uvicorn server:socket_app --reload --port 8001
"""
from app.main import app, socket_app, sio

__all__ = ["app", "socket_app", "sio"]
