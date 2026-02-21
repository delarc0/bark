#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found. Run setup first."
    exit 1
fi
source .venv/bin/activate
python dictation.py
