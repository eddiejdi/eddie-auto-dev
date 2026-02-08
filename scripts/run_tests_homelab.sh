#!/bin/bash
set -euo pipefail
# Script to prepare environment and run site Selenium tests on homelab
# Usage (remote):
#   scp scripts/run_tests_homelab.sh homelab:/tmp/
#   ssh homelab "/tmp/run_tests_homelab.sh"

DEST_DIR="/tmp/eddie_test"
ARCHIVE="/tmp/eddie_auto_dev.tar.gz"

echo "Preparing test workspace in $DEST_DIR"
mkdir -p "$DEST_DIR"
rm -rf "$DEST_DIR"/*

if [ -f "$ARCHIVE" ]; then
  echo "Extracting archive $ARCHIVE -> $DEST_DIR"
  tar -xzf "$ARCHIVE" -C "$DEST_DIR"
else
  echo "Archive $ARCHIVE not found. Place the project tarball at that path and re-run."
  exit 2
fi

cd "$DEST_DIR"

echo "Creating virtualenv .venv_test"
python3 -m venv .venv_test
. .venv_test/bin/activate

echo "Upgrading pip tooling (best-effort)"
python -m pip install --upgrade pip setuptools wheel || true

echo "Installing test dependencies (pytest, selenium, webdriver-manager, requests)"
python -m pip install --no-cache-dir pytest selenium webdriver-manager requests || true

echo "Running tests"
pytest -q tests/test_site_selenium.py 2>&1 | tee /tmp/selenium_run_homelab.log || true

echo DONE > /tmp/selenium_done_flag
