#!/usr/bin/env bash

set -euo pipefail

REMOTE="mbbb"
REMOTE_DIR="/srv/www/mbbb/"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! ssh -O check "$REMOTE" >/dev/null 2>&1; then
    echo "No active SSH connection for '$REMOTE'."
    echo
    echo "Open one with:"
    echo "  ssh -MNf $REMOTE"
    exit 1
fi

echo "Deploying Melvin Beddow Big Band demo website..."

rsync -avz \
    --delete \
    --exclude '.git/' \
    --exclude '.gitignore' \
    --exclude '.vscode/' \
    --exclude '*:Zone.Identifier' \
    --exclude '*.bak' \
    --exclude 'deploy.sh' \
    --exclude 'deploy-command.txt' \
    --exclude 'README.md' \
    --exclude 'page-template.html' \
    --exclude='server/' \
    --exclude='*.env' \
    --exclude='__pycache__/' \
    ./ "$REMOTE:$REMOTE_DIR"

echo
echo "Deployment complete."
echo "https://mbbb.dcsmail.uk"