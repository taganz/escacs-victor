#!/usr/bin/env bash
# Instala Escacs Victor como servicio en una Raspberry Pi (o cualquier Linux
# con systemd). Ejecútalo con tu usuario normal, sin sudo:
#
#   ./scripts/install_pi.sh
#
# Variables opcionales: PORT (8000) y HOST (0.0.0.0 = accesible desde la red de casa).
set -euo pipefail

cd "$(dirname "$0")/.."
DIR="$(pwd)"
USER_NAME="$(id -un)"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

if [ "$(id -u)" -eq 0 ]; then
    echo "Ejecuta este script con tu usuario normal, sin sudo." >&2
    exit 1
fi

echo "==> Paquetes del sistema"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git

echo "==> Entorno de Python"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
mkdir -p games

echo "==> Servicio escacs-victor"
sed -e "s|@USER@|$USER_NAME|g" -e "s|@DIR@|$DIR|g" -e "s|@HOST@|$HOST|g" -e "s|@PORT@|$PORT|g" \
    deploy/escacs-victor.service | sudo tee /etc/systemd/system/escacs-victor.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable escacs-victor
sudo systemctl restart escacs-victor

sleep 3
if systemctl is-active --quiet escacs-victor; then
    echo
    echo "Funcionando. Desde la red de casa: http://$(hostname).local:$PORT"
    echo "Registros: journalctl -u escacs-victor -f"
else
    echo "El servicio no ha arrancado. Mira los registros:" >&2
    echo "  journalctl -u escacs-victor -n 50" >&2
    exit 1
fi
