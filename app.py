"""WSGI entrypoint for Vercel. Uses the same protected IVAS app as Render.

Do not reinstate the legacy cookie-based /sms OTP endpoint here.
"""
from safe_app import app

__all__ = ["app"]
