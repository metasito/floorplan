#!/bin/zsh
# Double-click to open the Unit 13 configurator. Starts the local server if it isn't running,
# then opens the editor in your browser. Close this window to stop the server.
# First run sets up .venv with the Python packages (needs python3: install from python.org).
cd "${0:A:h}/.."
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up Python packages..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || { echo "Setup failed"; read; exit 1; }
fi
URL=http://localhost:8013
if ! curl -s -o /dev/null "$URL/api/jobs"; then
  .venv/bin/python configurator/server.py &
  sleep 1
fi
open "$URL"
echo "Configurator running at $URL. Keep this window open while you work and render."
wait
