#!/bin/bash

# Deploy to production

echo "🚀 Deploying QueryPulse-AI..."

# Build and push Docker image
docker build -t querypulse-ai:latest .
docker tag querypulse-ai:latest your-registry/querypulse-ai:latest
docker push your-registry/querypulse-ai:latest

# Deploy to Kubernetes (if using k8s)
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Or deploy to cloud run
gcloud run deploy querypulse-ai \
    --image your-registry/querypulse-ai:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2

echo "✅ Deployment complete!"