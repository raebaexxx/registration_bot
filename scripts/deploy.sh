#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "Файл .env не найден. Скопируй .env.example в .env и заполни значения."
    exit 1
fi

git pull --ff-only
docker compose up -d --build
docker compose ps
