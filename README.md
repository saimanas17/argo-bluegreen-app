# Blue-Green Frontend Application

Simple nginx-based application with automated CI/CD pipeline for blue-green deployment.

## 📂 Structure
```
argo-bluegreen-app/
├── index.html          # Application
├── Dockerfile          # Container definition
├── Jenkinsfile         # CI/CD pipeline
└── README.md
```

## 🔄 Jenkins Pipeline Stages

1. **Checkout** - Clone code
2. **Build** - Create Docker image with build number tag
3. **Push** - Upload to Docker Hub
4. **Update Manifests** - Commit new image tag to manifest repo
5. **Wait for Sync** - ArgoCD detects changes
6. **Wait for Preview** - New pods become healthy
7. **Get URLs** - Display preview and production endpoints
8. **Manual Approval** - ⏸️ Pause for testing (30 min timeout)
9. **Promote** - Switch traffic to new version
10. **Verify** - Confirm deployment success

## 🚀 Usage
```bash
# Make changes
vim index.html

# Push to trigger pipeline
git add .
git commit -m "Update content"
git push origin main
```

## 🔧 Jenkins Setup

### Required Credentials

**Docker Hub** (`dockerhub-credentials`):
```
Type: Username with password
Username: <docker-hub-username>
Password: <docker-hub-token>
```

**GitHub** (`github-credentials`):
```
Type: Username with password
Username: <github-username>
Password: <github-personal-access-token>
```

### Environment Variables

Jenkins → Manage Jenkins → System → Global properties → Environment variables:
```
MANIFEST_REPO_URL = https://github.com/saimanas17/argo-bluegreen-manifests
EXT_IP = IP_Address
```

### Kubeconfig Setup
```bash
sudo cp ~/.kube/config /var/lib/jenkins/.kube/config
sudo chown jenkins:jenkins /var/lib/jenkins/.kube/config
sudo chmod 600 /var/lib/jenkins/.kube/config
```

### GitHub Webhook

Settings → Webhooks → Add webhook:
```
Payload URL: http://<JENKINS_IP>:8080/github-webhook/
Content type: application/json
Events: Just the push event
```

## 🐛 Quick Troubleshooting
```bash
# Check Docker
sudo systemctl status docker

# Check rollout
kubectl argo rollouts get rollout bluegreen-frontend -n bluegreen-demo

# Check pods
kubectl get pods -n bluegreen-demo

# Rollback
kubectl argo rollouts undo bluegreen-frontend -n bluegreen-demo
```

## 🔗 Related

- [Manifest Repository](https://github.com/saimanas17/argo-bluegreen-manifests)
- [Parent Repository](https://github.com/saimanas17/argocd-bluegreen)