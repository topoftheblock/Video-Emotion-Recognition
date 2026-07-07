#!/usr/bin/env python3
"""
Entry point for the DUUI CAS-to-Postgres parser.

Usage:
    python main.py [path/to/file.xmi]

Configuration (DB credentials, typesystem paths, default XMI path) is
read from duui_parser/config.py, and can be overridden via the
environment variables listed there (DUUI_DB_NAME, DUUI_XMI_FILE, etc.)
"""

import sys

from duui_parser.pipeline import run

if __name__ == "__main__":
    xmi_path = sys.argv[1] if len(sys.argv) > 1 else None
    run(xmi_path)
