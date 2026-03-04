"""
Chief Dashboard - Streamlit entry point.
Run with: streamlit run streamlit_app.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import main

main()
