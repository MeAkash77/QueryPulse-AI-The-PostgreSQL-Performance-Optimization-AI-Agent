#!/bin/bash

echo "🚀 Starting QueryPulse-AI..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Pull latest Ollama model (optional)
echo "📦 Pulling LLM model..."
docker exec querypulse-ai-ollama-1 ollama pull llama2

# Run with docker-compose
echo "🐳 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services..."
sleep 10

# Run initial setup
echo "🔧 Running setup..."
docker-compose exec app python scripts/seed_data.py

echo "✅ QueryPulse-AI is running!"
echo "📍 Access at: http://localhost:8501"
echo "📧 Default login: admin@example.com / admin123"