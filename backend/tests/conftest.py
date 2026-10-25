import os
import sys
from pathlib import Path

# Use in-memory Qdrant and test environment to avoid file-lock conflicts with running server
os.environ["QDRANT_PATH"] = ":memory:"
os.environ["APP_ENV"] = "test"

# Add project root to python path for testing
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.db.database import init_database
init_database()

