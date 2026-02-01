#!/usr/bin/env bash
# Run TrendSignal API in Docker on a VM.
# Usage: ./run-docker.sh [build]
# Set OPENAI_API_KEY in .env in the project root.
set -e
cd "$(dirname "$0")/../.."
if [[ "$1" == "build" ]]; then
  docker build -f deploy/Dockerfile -t trend-signal .
fi
docker rm -f trend-signal 2>/dev/null || true
docker run -d --name trend-signal -p 8001:8001 --env-file .env --restart unless-stopped trend-signal
echo "API running at http://$(hostname -I | awk '{print $1}'):8001"
