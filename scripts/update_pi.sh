#!/usr/bin/env bash
# Descarga la última versión y reinicia el servicio. Las partidas en curso se pierden.
set -euo pipefail

cd "$(dirname "$0")/.."
git pull --ff-only
.venv/bin/pip install -r requirements.txt
sudo systemctl restart escacs-victor
echo "Actualizado: $(git log -1 --format='%h %s')"
