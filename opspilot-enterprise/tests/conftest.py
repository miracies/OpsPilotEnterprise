"""Test helpers for loading service apps from specific paths."""
import importlib
import importlib.util
import sys
import os


def load_service_app(service_path: str):
    """Load a FastAPI app from a specific service directory by manipulating sys.path.
    
    Returns the FastAPI app instance.
    """
    abs_path = os.path.abspath(service_path)
    
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]
    
    sys.path.insert(0, abs_path)
    try:
        import app.main
        importlib.reload(app.main)
        return app.main.app
    finally:
        if abs_path in sys.path:
            sys.path.remove(abs_path)
