#!/bin/bash
# Deployment script for Flowdeck on IBM Cloud Kubernetes Service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IBM_CLOUD_REGION="${IBM_CLOUD_REGION:-us-south}"
IBM_CLOUD_RESOURCE_GROUP="${IBM_CLOUD_RESOURCE_GROUP:-default}"
CLUSTER_NAME="${CLUSTER_NAME:-flowdeck-cluster}"
REGISTRY_NAMESPACE="${REGISTRY_NAMESPACE:-flowdeck}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo -e "${GREEN}=== Flowdeck IBM Cloud Deployment ===${NC}"

# Check if IBM Cloud CLI is installed
if ! command -v ibmcloud &> /dev/null; then
    echo -e "${RED}Error: IBM Cloud CLI is not installed${NC}"
    echo "Install from: https://cloud.ibm.com/docs/cli?topic=cli-getting-started"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    echo "Install from: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Login to IBM Cloud${NC}"
ibmcloud login --sso || ibmcloud login

echo -e "${YELLOW}Step 2: Target resource group and region${NC}"
ibmcloud target -r "$IBM_CLOUD_REGION" -g "$IBM_CLOUD_RESOURCE_GROUP"

echo -e "${YELLOW}Step 3: Configure Container Registry${NC}"
ibmcloud cr region-set "$IBM_CLOUD_REGION"
ibmcloud cr login

# Create namespace if it doesn't exist
if ! ibmcloud cr namespace-list | grep -q "$REGISTRY_NAMESPACE"; then
    echo "Creating registry namespace: $REGISTRY_NAMESPACE"
    ibmcloud cr namespace-add "$REGISTRY_NAMESPACE"
fi

echo -e "${YELLOW}Step 4: Build and push Docker images${NC}"

# Build backend image
echo "Building backend image..."
docker build -t "us.icr.io/$REGISTRY_NAMESPACE/flowdeck-backend:$IMAGE_TAG" -f docker/backend.Dockerfile .
echo "Pushing backend image..."
docker push "us.icr.io/$REGISTRY_NAMESPACE/flowdeck-backend:$IMAGE_TAG"

# Build frontend image
echo "Building frontend image..."
docker build -t "us.icr.io/$REGISTRY_NAMESPACE/flowdeck-frontend:$IMAGE_TAG" -f docker/frontend.Dockerfile .
echo "Pushing frontend image..."
docker push "us.icr.io/$REGISTRY_NAMESPACE/flowdeck-frontend:$IMAGE_TAG"

echo -e "${YELLOW}Step 5: Configure kubectl for cluster${NC}"
ibmcloud ks cluster config --cluster "$CLUSTER_NAME"

echo -e "${YELLOW}Step 6: Create secrets (if not exists)${NC}"
if ! kubectl get secret flowdeck-secrets -n flowdeck &> /dev/null; then
    echo -e "${RED}Warning: flowdeck-secrets not found${NC}"
    echo "Please create secrets manually using:"
    echo "kubectl create secret generic flowdeck-secrets -n flowdeck \\"
    echo "  --from-literal=OPENAI_API_KEY=your-key \\"
    echo "  --from-literal=ALPHA_VANTAGE_API_KEY=your-key \\"
    echo "  --from-literal=JWT_SECRET=your-secret"
    echo ""
    read -p "Press enter to continue after creating secrets..."
fi

echo -e "${YELLOW}Step 7: Update deployment YAML with image names${NC}"
sed -i.bak "s|us.icr.io/your-namespace/flowdeck-backend:latest|us.icr.io/$REGISTRY_NAMESPACE/flowdeck-backend:$IMAGE_TAG|g" ibm-cloud/kubernetes-deployment.yaml
sed -i.bak "s|us.icr.io/your-namespace/flowdeck-frontend:latest|us.icr.io/$REGISTRY_NAMESPACE/flowdeck-frontend:$IMAGE_TAG|g" ibm-cloud/kubernetes-deployment.yaml

echo -e "${YELLOW}Step 8: Apply Kubernetes configurations${NC}"
kubectl apply -f ibm-cloud/kubernetes-deployment.yaml

echo -e "${YELLOW}Step 9: Wait for deployments to be ready${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/flowdeck-backend -n flowdeck
kubectl wait --for=condition=available --timeout=300s deployment/flowdeck-frontend -n flowdeck

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Check deployment status:"
echo "  kubectl get pods -n flowdeck"
echo "  kubectl get services -n flowdeck"
echo "  kubectl get ingress -n flowdeck"
echo ""
echo "View logs:"
echo "  kubectl logs -f deployment/flowdeck-backend -n flowdeck"
echo "  kubectl logs -f deployment/flowdeck-frontend -n flowdeck"
echo ""
echo "Get ingress URL:"
echo "  kubectl get ingress flowdeck-ingress -n flowdeck"

# Made with Bob
