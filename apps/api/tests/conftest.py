import os
import sys
import pytest

# Ensure apps/api directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
