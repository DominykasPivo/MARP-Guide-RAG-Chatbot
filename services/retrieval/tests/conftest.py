"""Pytest configuration for retrieval service tests."""
import sys
import os

# Add the app directory to Python path
app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.insert(0, app_path)