"""f1manager - safe, scriptable edits to an F1 Manager save database."""
from .db import SaveDatabase
from .save import Change, NotASaveError, SaveSession

__version__ = "0.1.0"

__all__ = ["SaveDatabase", "SaveSession", "Change", "NotASaveError", "__version__"]
