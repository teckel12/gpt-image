#!/bin/zsh
# Start the Flask API.

set -euo pipefail

cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
    print -u2 "Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

print "Starting Flask API at http://127.0.0.1:5050"
exec .venv/bin/python -m backend
