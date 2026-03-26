#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR/backend"

uvicorn app:app --reload --host 127.0.0.1 --port 8000