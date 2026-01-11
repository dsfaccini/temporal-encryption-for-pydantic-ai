#!/bin/bash
set -e

# Ensure we're in the project directory
cd "$(dirname "$0")"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Copy .env.example to .env and fill in your keys:"
    echo "  cp .env.example .env"
    exit 1
fi

# Source environment
source .venv/bin/activate
source .env

# Check required env vars
if [ -z "$TEMPORAL_ENCRYPTION_KEY" ]; then
    echo "Error: TEMPORAL_ENCRYPTION_KEY not set"
    echo "Generate one with: python -c \"import os; print(os.urandom(32).hex())\""
    exit 1
fi


case "${1:-help}" in
    worker)
        echo "Starting worker with encrypted payloads..."
        python -m temporal_encryption.worker
        ;;
    run)
        echo "Executing workflow..."
        python -m temporal_encryption.starter
        ;;
    temporal)
        echo "Starting Temporal dev server..."
        temporal server start-dev
        ;;
    help|*)
        echo "Usage: ./start.sh <command>"
        echo ""
        echo "Commands:"
        echo "  temporal  Start Temporal dev server (run first, in separate terminal)"
        echo "  worker    Start the worker with encrypted payloads"
        echo "  run       Execute a workflow"
        echo ""
        echo "Quick start:"
        echo "  Terminal 1: ./start.sh temporal"
        echo "  Terminal 2: ./start.sh worker"
        echo "  Terminal 3: ./start.sh run"
        ;;
esac
