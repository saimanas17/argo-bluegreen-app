pipeline {
    agent any
    
    environment {
        // Docker Hub configuration
        DOCKER_REGISTRY = 'saimanasg'
        DOCKER_CREDENTIALS_ID = 'dockerhub-credentials'
        
        // Image name
        FRONTEND_IMAGE = "${DOCKER_REGISTRY}/bluegreen-frontend"
        
        // Git configuration
        GIT_CREDENTIALS_ID = 'github-credentials'
        GIT_USER_EMAIL = 'gourabathini.s@northeastern.edu'
        
        // Kubernetes configuration
        ROLLOUT_NAME = 'bluegreen-frontend'
        NAMESPACE = 'bluegreen-demo'
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    echo "🔨 Building Docker image with tag: ${BUILD_NUMBER}"
                    
                    sh """
                        docker build -t ${FRONTEND_IMAGE}:${BUILD_NUMBER} .
                        docker tag ${FRONTEND_IMAGE}:${BUILD_NUMBER} ${FRONTEND_IMAGE}:latest
                    """
                    
                    echo "✅ Image built successfully"
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                script {
                    echo '📤 Pushing image to Docker Hub...'
                    
                    withCredentials([usernamePassword(
                        credentialsId: "${DOCKER_CREDENTIALS_ID}",
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin
                            
                            docker push ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                            docker push ${FRONTEND_IMAGE}:latest
                            
                            docker logout
                        """
                    }
                    
                    echo "✅ Image pushed successfully"
                }
            }
        }
        
        stage('Update Manifest Repository') {
            steps {
                script {
                    echo '📝 Updating Kubernetes manifests for Argo Rollouts...'
                    
                    def manifestRepo = env.MANIFEST_REPO_URL
                    
                    withCredentials([usernamePassword(
                        credentialsId: "${GIT_CREDENTIALS_ID}",
                        usernameVariable: 'GIT_USER',
                        passwordVariable: 'GIT_TOKEN'
                    )]) {
                        sh """
                            # Clone manifest repository
                            rm -rf manifests-temp
                            
                            # Extract repo path for git clone with credentials
                            REPO_PATH=\$(echo ${manifestRepo} | sed 's|https://||')
                            git clone https://\${GIT_USER}:\${GIT_TOKEN}@\${REPO_PATH} manifests-temp
                            
                            cd manifests-temp
                            
                            # Configure git
                            git config user.email "${GIT_USER_EMAIL}"
                            git config user.name "\${GIT_USER}"
                            
                            # Update frontend Rollout with new image tag
                            sed -i 's|image: .*/bluegreen-frontend:.*|image: ${FRONTEND_IMAGE}:${BUILD_NUMBER}|g' rollout.yaml
                            
                            # Check if there are changes
                            if git diff --quiet; then
                                echo "⚠️  No changes to commit"
                            else
                                # Commit and push changes
                                git add rollout.yaml
                                git commit -m "Build ${BUILD_NUMBER}: Update frontend image to ${BUILD_NUMBER}"
                                git push origin main
                                echo "✅ Manifest updated and pushed to Git"
                            fi
                            
                            # Cleanup
                            cd ..
                            rm -rf manifests-temp
                        """
                    }
                }
            }
        }
        
        stage('Wait for ArgoCD Sync') {
            steps {
                script {
                    echo '⏳ Waiting for ArgoCD to sync and deploy preview...'
                    
                    timeout(time: 5, unit: 'MINUTES') {
                        sh """
                            echo "Waiting for rollout to update..."
                            sleep 15
                            
                            echo "Checking if rollout exists..."
                            kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
                            
                            echo "✅ Rollout found!"
                        """
                    }
                }
            }
        }
        
        stage('Wait for Preview Deployment') {
            steps {
                script {
                    echo '⏳ Waiting for preview pods to be ready...'
                    sh """
                        sleep 60
                    """
                }
            }
        }
        
        stage('Get Preview URLs') {
            steps {
                script {
                    echo '📊 Getting service endpoints...'
                    
                    sh """
                        echo "==================================="
                        echo "Service Information:"
                        echo "==================================="
                        
                        # Get node IP
                        NODE_IP=\$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
                        echo "Node IP: \$NODE_IP"
                        
                        # Get active service port
                        ACTIVE_PORT=\$(kubectl get service bluegreen-frontend-active -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30080")
                        echo ""
                        echo "🟢 Active (Production): http://\$NODE_IP:\$ACTIVE_PORT"
                        
                        # Get preview service port
                        PREVIEW_PORT=\$(kubectl get service bluegreen-frontend-preview -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30081")
                        echo "🔵 Preview (Build ${BUILD_NUMBER}): http://\$NODE_IP:\$PREVIEW_PORT"
                        echo ""
                        echo "==================================="
                        
                        # Save for later stages
                        echo "ACTIVE_URL=http://\$NODE_IP:\$ACTIVE_PORT" > urls.txt
                        echo "PREVIEW_URL=http://\$NODE_IP:\$PREVIEW_PORT" >> urls.txt
                    """
                    
                    // Read URLs
                    def urls = readFile('urls.txt').trim()
                    echo urls
                }
            }
        }
        
        stage('Manual Approval - Test Preview') {
            steps {
                script {
                    // Read URLs
                    def urlsContent = readFile('urls.txt').trim()
                    def lines = urlsContent.split('\n')
                    def activeUrl = lines[0].split('=')[1]
                    def previewUrl = lines[1].split('=')[1]
                    
                    echo """
                    ╔════════════════════════════════════════════════════════╗
                    ║          🎯 PREVIEW READY FOR TESTING                  ║
                    ╚════════════════════════════════════════════════════════╝
                    
                    📦 Build Number: ${BUILD_NUMBER}
                    🐳 Image: ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                    
                    🌐 URLs:
                    ├─ 🟢 Production (Active):  ${activeUrl}
                    └─ 🔵 Preview (New):        ${previewUrl}
                    
                    ✅ Test Checklist:
                    ├─ [ ] Application loads correctly
                    ├─ [ ] All features work as expected
                    ├─ [ ] UI/UX changes look good
                    ├─ [ ] No console errors
                    └─ [ ] Performance is acceptable
                    
                    ⚠️  IMPORTANT: Test the PREVIEW URL before promoting!
                    
                    ═══════════════════════════════════════════════════════
                    Click 'Proceed' to PROMOTE to Production
                    Click 'Abort' to CANCEL deployment
                    ═══════════════════════════════════════════════════════
                    """
                    
                    // Manual approval with 30-minute timeout
                    timeout(time: 30, unit: 'MINUTES') {
                        input message: "🚀 Promote Build ${BUILD_NUMBER} to Production?", 
                              ok: 'Yes, Promote Now!',
                              submitter: 'admin,devops'  // Optional: restrict to specific users
                    }
                }
            }
        }
        
        stage('Promote to Production') {
            steps {
                script {
                    echo '🚀 Promoting new version to production...'
                    
                    sh """
                        echo "Executing promotion..."
                        
                        # Promote the rollout
                        kubectl argo rollouts promote ${ROLLOUT_NAME} -n ${NAMESPACE}
                        
                        echo "✅ Promotion command executed successfully"
                        echo ""
                        echo "Waiting for promotion to complete..."
                        sleep 5
                        
                        # Show rollout status
                        kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
                    """
                }
            }
        }
        
        stage('Verify Production Deployment') {
            steps {
                script {
                    echo '✅ Verifying production deployment...'
                    
                    timeout(time: 5, unit: 'MINUTES') {
                        sh """
                            # Wait for rollout to be fully healthy
                            kubectl argo rollouts status ${ROLLOUT_NAME} -n ${NAMESPACE}
                            
                            echo ""
                            echo "Final rollout status:"
                            kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
                            
                            echo ""
                            echo "✅ Production deployment verified!"
                        """
                    }
                }
            }
        }
    }
    
    post {
        always {
            echo '🧹 Cleaning up...'
            sh """
                docker rmi ${FRONTEND_IMAGE}:${BUILD_NUMBER} || true
                docker rmi ${FRONTEND_IMAGE}:latest || true
                rm -f urls.txt
            """
            cleanWs()
        }
        success {
            script {
                def urlsContent = readFile('urls.txt').trim()
                def lines = urlsContent.split('\n')
                def activeUrl = lines[0].split('=')[1]
                
                echo """
                ╔════════════════════════════════════════════════════════╗
                ║       ✅ DEPLOYMENT COMPLETED SUCCESSFULLY! ✅          ║
                ╚════════════════════════════════════════════════════════╝
                
                📦 Build: ${BUILD_NUMBER}
                🐳 Image: ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                
                🌐 Production URL: ${activeUrl}
                
                ═══════════════════════════════════════════════════════
                
                💡 Useful Commands:
                
                📊 Check rollout status:
                   kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
                
                📊 Watch rollout live:
                   kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE} --watch
                
                ↩️  Rollback if needed:
                   kubectl argo rollouts undo ${ROLLOUT_NAME} -n ${NAMESPACE}
                
                📜 View rollout history:
                   kubectl argo rollouts history ${ROLLOUT_NAME} -n ${NAMESPACE}
                
                ═══════════════════════════════════════════════════════
                """
            }
        }
        aborted {
            echo """
            ╔════════════════════════════════════════════════════════╗
            ║            ⏸️  DEPLOYMENT ABORTED ⏸️                    ║
            ╚════════════════════════════════════════════════════════╝
            
            The promotion was cancelled by user.
            
            📊 Current State:
            ├─ Preview pods are still running
            ├─ Production traffic on OLD version
            └─ Preview available for testing
            
            ═══════════════════════════════════════════════════════
            
            💡 Next Actions:
            
            ✅ To promote manually:
               kubectl argo rollouts promote ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            ❌ To abort the rollout:
               kubectl argo rollouts abort ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            📊 Check current status:
               kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            ═══════════════════════════════════════════════════════
            """
        }
        failure {
            echo """
            ╔════════════════════════════════════════════════════════╗
            ║              ❌ PIPELINE FAILED! ❌                     ║
            ╚════════════════════════════════════════════════════════╝
            
            Check the logs above for detailed error information.
            
            ═══════════════════════════════════════════════════════
            
            🔍 Troubleshooting Commands:
            
            📊 Check rollout status:
               kubectl argo rollouts get rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            📜 Check rollout events:
               kubectl describe rollout ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            📋 Check pod logs:
               kubectl logs -l app=bluegreen-frontend -n ${NAMESPACE} --tail=50
            
            📋 Check all pods:
               kubectl get pods -n ${NAMESPACE} -l app=bluegreen-frontend
            
            ❌ Abort failed rollout:
               kubectl argo rollouts abort ${ROLLOUT_NAME} -n ${NAMESPACE}
            
            ═══════════════════════════════════════════════════════
            
            Common Issues:
            ├─ Docker build failures → Check Dockerfile
            ├─ Docker Hub auth → Check dockerhub-credentials
            ├─ Git push failures → Check github-credentials
            ├─ Rollout not found → Check ArgoCD Application
            └─ Pods not starting → Check image name/tag
            
            ═══════════════════════════════════════════════════════
            """
        }
    }
}