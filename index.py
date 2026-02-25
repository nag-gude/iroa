"""Vercel entry point: export the FastAPI app for serverless deployment."""
from iroa.api.main import app

__all__ = ["app"]
