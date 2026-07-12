# TaskHub Kubernetes Deployment Guide

Deploy the TaskHub FastAPI application on a Kubernetes cluster running on an AWS EC2 instance.

## Kubernetes Resources

| Resource | File | Purpose |
|----------|------|---------|
| Namespace | `namespace.yaml` | Isolates all resources under `taskhub` |
| Secret | `secret.yaml` | Stores `POSTGRES_PASSWORD` and `SECRET_KEY` |
| ConfigMap | `configmap.yaml` | Non-sensitive config (DB host, environment, etc.) |
| PVC | `postgres/pvc.yaml` | 5Gi persistent storage for PostgreSQL |
| PostgreSQL Service | `postgres/service.yaml` | Internal DNS (`postgres:5432`) via ClusterIP |
| PostgreSQL Deployment | `postgres/deployment.yaml` | Single-replica PostgreSQL 17 with probes |
| Migration Job | `api/migration-job.yaml` | One-shot Alembic migration runner |
| API Deployment | `api/deployment.yaml` | 2-replica FastAPI with rolling updates |
| API Service | `api/service.yaml` | NodePort service exposed on port `30080` |
| HPA | `api/hpa.yaml` | Auto-scales API pods (2–10) at 70% CPU |

## Architecture

```
                  Internet
                      |
              EC2 Public IP
                      |
                 NodePort:30080
                      |
             +----------------+
             | API Service    |
             +----------------+
                      |
          +-----------+-----------+
          |                       |
     API Pod 1               API Pod 2
          |                       |
          +-----------+-----------+
                      |
             PostgreSQL Service
                      |
             PostgreSQL Deployment
                      |
             Persistent Volume Claim
```

## Folder Structure

```
taskhub-k8s/
├── namespace.yaml
├── secret.yaml
├── configmap.yaml
├── postgres/
│   ├── pvc.yaml
│   ├── service.yaml
│   └── deployment.yaml
├── api/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml
│   └── migration-job.yaml
└── README.md
```

---

## Prerequisites

1. An AWS EC2 instance with Kubernetes installed (e.g., Minikube, kubeadm, or k3s)
2. `kubectl` configured and connected to the cluster
3. Docker image pushed to DockerHub

## Build & Push the Docker Image

Kubernetes doesn't build images — you must push to a registry first.

```bash
docker build -t YOUR_DOCKERHUB_USERNAME/YOUR_IMAGE_NAME:TAG .
docker login
docker push YOUR_DOCKERHUB_USERNAME/YOUR_IMAGE_NAME:TAG
```

> **Important:** Replace `YOUR_DOCKERHUB_USERNAME` and `YOUR_IMAGE_NAME` in `api/deployment.yaml` and `api/migration-job.yaml` with your actual DockerHub username and image name before deploying.
> 
> **Tip for Local Development:** If you are running Kubernetes locally (e.g., Docker Desktop, Minikube, or KinD), you can skip pushing to a registry. Simply build the image locally (e.g., `docker build -t sany2k8/taskhub:v2 .`), ensure `imagePullPolicy: IfNotPresent` is set in the manifests, and Kubernetes will load the image directly from your local Docker cache.

---

## Deployment

> **Note on Local vs. AWS EC2 Deployment:** The deployment process (applying manifests using `kubectl`) is identical whether you are running locally (on Docker Desktop, Minikube, or KinD) or on an AWS EC2 instance. The only differences are how you manage the Docker image (remote registry push vs. local cache) and how you access the API (NodePort via Public IP vs. local port forwarding).

Apply resources in this order — dependencies must exist before the resources that reference them.

```bash
# 1. Namespace (must exist first)
kubectl apply -f namespace.yaml

# 2. Secret & ConfigMap (referenced by deployments)
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml

# 3. PostgreSQL (PVC → Service → Deployment)
kubectl apply -f postgres/

# 4. Run database migrations
kubectl apply -f api/migration-job.yaml

# 5. API Deployment & Service
kubectl apply -f api/deployment.yaml
kubectl apply -f api/service.yaml

# 6. Horizontal Pod Autoscaler
kubectl apply -f api/hpa.yaml
```

### Verify Everything is Running

```bash
kubectl get all -n taskhub
```

### Access the API

#### On AWS EC2 (NodePort)
The NodePort service binds directly to your EC2 instance's external IP on port `30080`. Open your browser at:
```
http://<EC2_PUBLIC_IP>:30080
http://<EC2_PUBLIC_IP>:30080/docs
```
> Make sure your EC2 Security Group allows inbound traffic on port `30080`.

#### On Local Development (Docker Desktop / Port Forwarding)
While NodePort works directly on EC2, it might not bind directly to `localhost` in local development clusters (like Docker Desktop, Minikube, or KinD). Use port forwarding instead:
```bash
kubectl port-forward svc/api 8000:8000 -n taskhub
```
Then open your browser or Postman at:
```
http://localhost:8000
http://localhost:8000/docs
```

---

## Key Design Decisions

### Why a Namespace?
All resources live under `taskhub` instead of `default`, keeping them isolated. Always use `-n taskhub` with kubectl commands.

### Why Secrets instead of inline env vars?
Passwords in plain YAML are visible to anyone with repo access. Secrets are base64-encoded and can be integrated with external secret managers.

### Why an initContainer?
The API's `wait-for-postgres` init container ensures PostgreSQL is accepting connections before FastAPI starts — replacing Docker Compose's `depends_on`.

### Why a separate Migration Job?
Running `alembic upgrade head` inside every API pod is dangerous when scaling to many replicas (concurrent migrations can corrupt data). The Job runs once, then you deploy the API.

### Why ReadWriteOnce for the PVC?
Only one PostgreSQL pod writes to the volume. This is correct for a single-replica database.

### Why Resource Requests & Limits?
Without them, a runaway container could consume all node resources and crash everything. Requests reserve resources; limits cap usage.

---

## Scaling

### Manual Scaling

```bash
kubectl scale deployment api --replicas=5 -n taskhub
```

### Autoscaling (HPA)

The HPA automatically scales between 2–10 replicas based on CPU utilization (target: 70%).

```bash
kubectl get hpa -n taskhub
```

No Service changes are needed — the Service automatically routes to all matching pods.

---

## Updating the Application

### Deploy a New Version

```bash
# Build and push the new image
docker build -t YOUR_DOCKERHUB_USERNAME/YOUR_NEW_IMAGE_NAME:YOUR_NEW_TAG .
docker push YOUR_DOCKERHUB_USERNAME/YOUR_NEW_IMAGE_NAME:YOUR_NEW_TAG
```

Update the image tag in `api/deployment.yaml`, then:

```bash
kubectl apply -f api/deployment.yaml
```

The **Rolling Update** strategy ensures zero downtime — pods are replaced one at a time.

### Rollback

```bash
# View history
kubectl rollout history deployment/api -n taskhub

# Rollback to previous version
kubectl rollout undo deployment/api -n taskhub

# Check status
kubectl rollout status deployment/api -n taskhub
```

---

## Debugging

```bash
# List all resources
kubectl get all -n taskhub

# Pod status
kubectl get pods -n taskhub

# Pod details (shows events, errors)
kubectl describe pod <POD_NAME> -n taskhub

# Container logs
kubectl logs <POD_NAME> -n taskhub

# Shell into a pod
kubectl exec -it <POD_NAME> -n taskhub -- sh

# Cluster events
kubectl get events -n taskhub --sort-by='.lastTimestamp'

# Migration job logs
kubectl logs job/taskhub-migration -n taskhub
```

---

## Future Improvements


| Current | Production Upgrade |
|---------|--------------------|
| NodePort (port 30080) | AWS Load Balancer → Ingress Controller → ClusterIP |
| `emptyDir` for uploads | Amazon S3 or EFS |
| PostgreSQL Deployment | Amazon RDS or StatefulSet |
| `imagePullPolicy: Always` | Immutable tags (`v1.0.1`) with `IfNotPresent` |