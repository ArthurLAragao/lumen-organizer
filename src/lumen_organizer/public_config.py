"""Portable destinations; personal configuration stays in the user's environment."""
import os
from pathlib import Path

VAULT = Path(os.environ.get('LUMEN_VAULT', str(Path.home() / 'Documents' / 'Obsidian'))).expanduser()
ATLAS = Path(os.environ.get('ATLAS_ROOT', str(Path.home() / 'atlas'))).expanduser()
NOTION_LIBRARY_ID = os.environ.get('LUMEN_NOTION_LIBRARY_ID', '')
NOTION_LIBRARY_URL = os.environ.get('LUMEN_NOTION_LIBRARY_URL', 'https://www.notion.so/')
SIDE_HUSTLE_URL = os.environ.get('LUMEN_SIDE_HUSTLE_URL', '')
