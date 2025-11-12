#!/bin/bash
# restart_docker.sh - Restart Docker Desktop on macOS

set -e

echo "🐳 Stopping Docker Desktop..."
osascript -e 'quit app "Docker"' 2>/dev/null || true
sleep 3

echo "🔨 Killing remaining Docker processes..."
pkill -f Docker 2>/dev/null || true
pkill -f com.docker 2>/dev/null || true
sleep 2

echo "✅ Docker Desktop stopped"
echo ""
echo "🚀 Starting Docker Desktop..."
open -a Docker

echo "⏳ Waiting for Docker to start (this may take 30-60 seconds)..."
counter=0
max_attempts=60

while ! docker info >/dev/null 2>&1; do
    counter=$((counter + 1))
    if [ $counter -gt $max_attempts ]; then
        echo "❌ Docker failed to start within 60 seconds"
        echo "Please start Docker Desktop manually and wait for it to be ready."
        exit 1
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "✅ Docker Desktop is running!"
docker info --format 'Docker version: {{.ServerVersion}}'
echo "Ready to run containers!"
