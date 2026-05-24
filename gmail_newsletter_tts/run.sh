#!/bin/bash
# Gmail Newsletter TTS 実行スクリプト
# launchd から呼び出される。venv があれば自動で有効化。

set -e
cd "$(dirname "$0")"

# venv があれば有効化
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "../.venv/bin/activate" ]; then
    source "../.venv/bin/activate"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting newsletter TTS pipeline..."
python main.py
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
