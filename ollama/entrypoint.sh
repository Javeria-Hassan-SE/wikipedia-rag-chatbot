#!/bin/sh
set -e

ollama serve &
SERVER_PID=$!

# wait until the REST API is accepting connections
until ollama list > /dev/null 2>&1; do
    sleep 2
done

ollama pull all-minilm
ollama pull llama3.2:3b

wait $SERVER_PID
