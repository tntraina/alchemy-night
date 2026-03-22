#!/bin/sh
source .venv/bin/activate
python3 -u -m flask --app app run -p 8000 --host crowdcoach.club --debug
