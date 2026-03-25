# IBM Cloud Deployment Guide for Flowdeck

This guide walks you through deploying Flowdeck as a containerized application on IBM Cloud infrastructure using IBM Cloud Kubernetes Service (IKS).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Quick Start](#quick-start)
4. [Detailed Deployment Steps](#detailed-deployment-steps)
5. [Configuration](#configuration)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Cost Optimization](#cost-optimization)

---

## Prerequisites

### Required Tools

1. **IBM Cloud CLI**
   ```bash
   curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
   ```
   Or download from: https://cloud.ibm.com/docs/cli?topic=cli-getting-started

2. **kubectl** (Kubernetes CLI)
   ```bash
   # macOS
   brew install kubectl
   
   # Linux
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   chmod +x kubectl
   sudo mv kubectl /usr/local/bin/
   ```

3. **Docker**
   - Install from: https://docs.docker.com/get-docker/

4. **IBM Cloud Plugins**
   ```bash
   ibmcloud plugin install container-service
   ibmcloud plugin install container-registry
   ```

### IBM Cloud Account Setup

1. Create an IBM Cloud account at https://cloud.ibm.com
2. Set up billing (required for Kubernetes clusters)
3. Create an API key:
   ```bash
   ibmcloud iam api-key-create flowdeck-deploy-key -d "Flowdeck deployment key"
   ```

---

## Architecture Overview

Flowdeck on IBM Cloud consists of:

- **Frontend**: React application served by Nginx (2+ replicas)
- **Backend**: FastAPI Python application (2+ replicas)
- **Storage**: IBM Cloud Block Storage for persistent data
- **Ingress**: IBM Cloud Load Balancer with SSL/TLS
- **Auto-scaling**: Horizontal Pod Autoscaler for both services
- **Optional**: Redis for caching (can be added)

```
┌─────────────────────────────────────────────────────┐
│                  IBM Cloud                          │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │         Kubernetes Cluster (IKS)             │  │
│  │                                              │  │
│  │  ┌────────────┐      ┌──────────────────┐  │  │
│  │  │  Ingress   │──────│  Load Balancer   │  │  │
│  │  └────────────┘      └──────────────────┘  │  │
│  │         │                                   │  │
│  │         ├──────────┬──────────────┐        │  │
│  │         │          │              │        │  │
│  │    ┌────▼───┐ ┌───▼────┐   ┌────▼────┐   │  │
│  │    │Frontend│ │Frontend│   │ Backend │   │  │
│  │    │  Pod   │ │  Pod   │   │   Pod   │   │  │
│  │    └────────┘ └────────┘   └─────────┘   │  │
│  │                                  │        │  │
│  │                            ┌─────▼─────┐ │  │
│  │                            │ Block     │ │  │
│  │                            │ Storage   │ │  │
│  │                            └───────────┘ │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │     Container Registry (ICR)             │  │
│  │  - flowdeck-backend:latest               │  │
│  │  - flowdeck-frontend:latest              │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## Quick Start

### Option 1: Automated Deployment Script

```bash
# 1. Set environment variables
export IBM_CLOUD_REGION="us-south"
export CLUSTER_NAME="flowdeck-cluster"
export REGISTRY_NAMESPACE="flowdeck"

# 2. Run deployment script
./ibm-cloud/deploy.sh
```

### Option 2: Manual Deployment

Follow the [Detailed Deployment Steps](#detailed-deployment-steps) below.

---

## Detailed Deployment Steps

### Step 1: Create Kubernetes Cluster

```bash
# Login to IBM Cloud
ibmcloud login --sso

# Target your resource group
ibmcloud target -g default

# Create a Kubernetes cluster (this takes 15-30 minutes)
ibmcloud ks cluster create classic \
  --name flowdeck-cluster \
  --zone dal10 \
  --flavor b3c.4x16 \
  --workers 3 \
  --public-vlan <your-public-vlan-id> \
  --private-vlan <your-private-vlan-id>

# Wait for cluster to be ready
ibmcloud ks cluster get --cluster flowdeck-cluster

# Configure kubectl
ibmcloud ks cluster config --cluster flowdeck-cluster
```

**Alternative: Use IBM Cloud Console**
- Navigate to Kubernetes → Clusters → Create
- Choose cluster type, location, and worker pool configuration

### Step 2: Set Up Container Registry

```bash
# Set registry region
ibmcloud cr region-set us-south

# Login to registry
ibmcloud cr login

# Create namespace
ibmcloud cr namespace-add flowdeck

# Verify
ibmcloud cr namespace-list
```

### Step 3: Build and Push Docker Images

```bash
# Build backend image
docker build -t us.icr.io/flowdeck/flowdeck-backend:latest -f docker/backend.Dockerfile .

# Build frontend image
docker build -t us.icr.io/flowdeck/flowdeck-frontend:latest -f docker/frontend.Dockerfile .

# Push images
docker push us.icr.io/flowdeck/flowdeck-backend:latest
docker push us.icr.io/flowdeck/flowdeck-frontend:latest

# Verify images
ibmcloud cr image-list --restrict flowdeck
```

### Step 4: Create Kubernetes Secrets

Create a file `secrets.yaml` with your actual values:

```bash
kubectl create secret generic flowdeck-secrets -n flowdeck \
  --from-literal=OPENAI_API_KEY='your-openai-key' \
  --from-literal=ALPHA_VANTAGE_API_KEY='your-alpha-vantage-key' \
  --from-literal=JWT_SECRET='your-jwt-secret-min-32-chars' \
  --from-literal=GOOGLE_CLIENT_ID='your-google-client-id' \
  --from-literal=GOOGLE_CLIENT_SECRET='your-google-client-secret' \
  --from-literal=PAYPAL_CLIENT_ID='your-paypal-client-id' \
  --from-literal=PAYPAL_CLIENT_SECRET='your-paypal-client-secret' \
  --from-literal=SMTP_HOST='smtp.gmail.com' \
  --from-literal=SMTP_PORT='587' \
  --from-literal=SMTP_USER='your-email@gmail.com' \
  --from-literal=SMTP_PASSWORD='your-app-password' \
  --from-literal=SMTP_FROM='noreply@yourdomain.com'
```

### Step 5: Update Deployment Configuration

Edit `ibm-cloud/kubernetes-deployment.yaml`:

1. Replace `your-namespace` with your registry namespace
2. Update `your-domain.com` with your actual domain
3. Adjust resource limits based on your needs

### Step 6: Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f ibm-cloud/kubernetes-deployment.yaml

# Verify deployments
kubectl get all -n flowdeck

# Check pod status
kubectl get pods -n flowdeck -w
```

### Step 7: Configure DNS and SSL

```bash
# Get the Ingress external IP
kubectl get ingress flowdeck-ingress -n flowdeck

# Configure your DNS:
# Create an A record pointing your-domain.com to the Ingress IP

# SSL is automatically provisioned via cert-manager and Let's Encrypt
```

### Step 8: Verify Deployment

```bash
# Check backend health
kubectl exec -it deployment/flowdeck-backend -n flowdeck -- curl http://localhost:8002/health

# Check frontend
curl https://your-domain.com/health

# View logs
kubectl logs -f deployment/flowdeck-backend -n flowdeck
kubectl logs -f deployment/flowdeck-frontend -n flowdeck
```

---

## Configuration

### Environment Variables

Update the ConfigMap in `kubernetes-deployment.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flowdeck-config
  namespace: flowdeck
data:
  CORS_ORIGINS: "https://your-domain.com"
  ENABLE_DAILY_SYNC: "true"
  ENABLE_MARKET_OVERVIEW_CACHE_REFRESH: "true"
  ENABLE_DIGEST_SCHEDULER: "true"
  PAYPAL_MODE: "live"  # or "sandbox" for testing
```

### Scaling Configuration

Adjust replicas and autoscaling:

```yaml
# Manual scaling
kubectl scale deployment flowdeck-backend --replicas=5 -n flowdeck

# Autoscaling limits (edit HPA)
kubectl edit hpa flowdeck-backend-hpa -n flowdeck
```

### Storage Configuration

To increase storage:

```bash
# Edit PVC
kubectl edit pvc flowdeck-data-pvc -n flowdeck

# Update storage size
spec:
  resources:
    requests:
      storage: 50Gi  # Increase from 10Gi
```

---

## Monitoring and Maintenance

### View Logs

```bash
# Real-time logs
kubectl logs -f deployment/flowdeck-backend -n flowdeck
kubectl logs -f deployment/flowdeck-frontend -n flowdeck

# Logs from specific pod
kubectl logs <pod-name> -n flowdeck

# Previous container logs (if crashed)
kubectl logs <pod-name> -n flowdeck --previous
```

### Monitor Resources

```bash
# Pod resource usage
kubectl top pods -n flowdeck

# Node resource usage
kubectl top nodes

# Describe pod for events
kubectl describe pod <pod-name> -n flowdeck
```

### Update Application

```bash
# Build and push new images with version tag
docker build -t us.icr.io/flowdeck/flowdeck-backend:v1.1.0 -f docker/backend.Dockerfile .
docker push us.icr.io/flowdeck/flowdeck-backend:v1.1.0

# Update deployment
kubectl set image deployment/flowdeck-backend \
  backend=us.icr.io/flowdeck/flowdeck-backend:v1.1.0 \
  -n flowdeck

# Check rollout status
kubectl rollout status deployment/flowdeck-backend -n flowdeck

# Rollback if needed
kubectl rollout undo deployment/flowdeck-backend -n flowdeck
```

### Backup Database

```bash
# Create a backup pod
kubectl run backup-pod --image=alpine --rm -it -n flowdeck \
  --overrides='{"spec":{"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"flowdeck-data-pvc"}}],"containers":[{"name":"backup","image":"alpine","volumeMounts":[{"name":"data","mountPath":"/data"}],"command":["sh"]}]}}'

# Inside the pod, copy database
tar -czf /tmp/backup-$(date +%Y%m%d).tar.gz /data/flowdeck.db
```

---

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n flowdeck

# Describe pod for events
kubectl describe pod <pod-name> -n flowdeck

# Check logs
kubectl logs <pod-name> -n flowdeck
```

Common issues:
- **ImagePullBackOff**: Check image name and registry credentials
- **CrashLoopBackOff**: Check application logs for errors
- **Pending**: Check resource availability and PVC binding

### Connection Issues

```bash
# Test backend from within cluster
kubectl run test-pod --image=curlimages/curl --rm -it -n flowdeck -- \
  curl http://flowdeck-backend:8002/health

# Check service endpoints
kubectl get endpoints -n flowdeck

# Check ingress
kubectl describe ingress flowdeck-ingress -n flowdeck
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -n flowdeck
kubectl top nodes

# Check HPA status
kubectl get hpa -n flowdeck

# Increase resources if needed
kubectl edit deployment flowdeck-backend -n flowdeck
```

### Database Issues

```bash
# Access database directly
kubectl exec -it deployment/flowdeck-backend -n flowdeck -- \
  sqlite3 /app/data/flowdeck.db

# Check PVC status
kubectl get pvc -n flowdeck
kubectl describe pvc flowdeck-data-pvc -n flowdeck
```

---

## Cost Optimization

### Cluster Sizing

- **Development**: 2 worker nodes (b3c.4x16)
- **Production**: 3+ worker nodes with autoscaling
- **High Traffic**: 5+ worker nodes (c3c.8x32)

### Resource Limits

Adjust based on actual usage:

```yaml
resources:
  requests:
    memory: "1Gi"    # Minimum guaranteed
    cpu: "500m"
  limits:
    memory: "2Gi"    # Maximum allowed
    cpu: "1000m"
```

### Autoscaling Strategy

```yaml
# Conservative (cost-effective)
minReplicas: 1
maxReplicas: 3
targetCPUUtilization: 80

# Aggressive (performance-focused)
minReplicas: 2
maxReplicas: 10
targetCPUUtilization: 60
```

### Storage Optimization

- Use appropriate storage class (bronze/silver/gold)
- Clean up old logs and temporary files
- Consider object storage for large files

---

## Additional Resources

- [IBM Cloud Kubernetes Service Documentation](https://cloud.ibm.com/docs/containers)
- [IBM Container Registry Documentation](https://cloud.ibm.com/docs/Registry)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Documentation](https://docs.docker.com/)

---

## Support

For issues specific to Flowdeck deployment:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review application logs
3. Open an issue on the GitHub repository

For IBM Cloud infrastructure issues:
- IBM Cloud Support: https://cloud.ibm.com/unifiedsupport/supportcenter
