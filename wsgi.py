"""
WSGI entry point untuk server produksi (gunicorn / uWSGI).

Contoh: gunicorn --bind 0.0.0.0:8000 wsgi:app
"""

from app import app  # noqa: F401

if __name__ == "__main__":
    app.run()
