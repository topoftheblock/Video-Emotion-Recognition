#!/bin/sh
# Entry point for the `tests` service: provision, then run pytest.
#
# Provisioning is the runner's job rather than a pytest fixture, so that a test
# run never issues CREATE DATABASE against whatever DUUI_DB_NAME happens to
# point at.
set -e
python /app/tests/ensure_test_db.py
exec python -m pytest "$@"
