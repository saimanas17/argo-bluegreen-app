pipeline {
    agent any
    
    environment {
        // Docker Hub configuration
        DOCKER_REGISTRY = 'saimanasg'
        DOCKER_CREDENTIALS_ID = 'dockerhub-credentials'
        
        // Image names
        BACKEND_IMAGE = "${DOCKER_REGISTRY}/bluegreen-backend"
        FRONTEND_IMAGE = "${DOCKER_REGISTRY}/bluegreen-frontend"
        
        // Git configuration
        GIT_CREDENTIALS_ID = 'github-credentials'
        GIT_USER_EMAIL = 'gourabathini.s@northeastern.edu'
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo '📥 Checking out source code...'
                checkout scm
            }
        }
        
        stage('Build Docker Images') {
            steps {
                script {
                    echo "🔨 Building Docker images with tag: ${BUILD_NUMBER}"
                    
                    // Build backend
                    dir('backend') {
                        sh """
                            docker build -t ${BACKEND_IMAGE}:${BUILD_NUMBER} .
                            docker tag ${BACKEND_IMAGE}:${BUILD_NUMBER} ${BACKEND_IMAGE}:latest
                        """
                    }
                    
                    // Build frontend
                    dir('frontend') {
                        sh """
                            docker build -t ${FRONTEND_IMAGE}:${BUILD_NUMBER} .
                            docker tag ${FRONTEND_IMAGE}:${BUILD_NUMBER} ${FRONTEND_IMAGE}:latest
                        """
                    }
                    
                    echo "✅ Images built successfully"
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                script {
                    echo '📤 Pushing images to Docker Hub...'
                    
                    withCredentials([usernamePassword(
                        credentialsId: "${DOCKER_CREDENTIALS_ID}",
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )]) {
                        sh """
                            echo \$DOCKER_PASS | docker login -u \$DOCKER_USER --password-stdin
                            
                            # Push backend images
                            docker push ${BACKEND_IMAGE}:${BUILD_NUMBER}
                            docker push ${BACKEND_IMAGE}:latest
                            
                            # Push frontend images
                            docker push ${FRONTEND_IMAGE}:${BUILD_NUMBER}
                            docker push ${FRONTEND_IMAGE}:latest
                            
                            docker logout
                        """
                    }
                    
                    echo "✅ Images pushed successfully"
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
                            git clone https://${GIT_USER}:${GIT_TOKEN}@\${REPO_PATH} manifests-temp
                            
                            cd manifests-temp
                            
                            # Configure git
                            git config user.email "${GIT_USER_EMAIL}"
                            git config user.name "${GIT_USER}"
                            
                            # Update backend deployment (regular deployment)
                            sed -i 's|image: .*/bluegreen-backend:.*|image: ${BACKEND_IMAGE}:${BUILD_NUMBER}|g' backend-deployment.yaml
                            
                            # Update frontend Rollout (blue-green deployment)
                            sed -i 's|image: .*/bluegreen-frontend:.*|image: ${FRONTEND_IMAGE}:${BUILD_NUMBER}|g' frontend-rollout.yaml
                            
                            # Update ConfigMap with build number
                            sed -i 's|BUILD_NUMBER: .*|BUILD_NUMBER: "${BUILD_NUMBER}"|g' configmap.yaml
                            
                            # Check if there are changes
                            if git diff --quiet; then
                                echo "No changes to commit"
                            else
                                # Commit and push changes
                                git add backend-deployment.yaml frontend-rollout.yaml configmap.yaml
                                git commit -m "Build ${BUILD_NUMBER}: Update backend deployment and frontend rollout"
                                git push origin main
                                echo "✅ Manifests updated and pushed to Git"
                            fi
                            
                            # Cleanup
                            cd ..
                            rm -rf manifests-temp
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
                # Remove built images to save space
                docker rmi ${BACKEND_IMAGE}:${BUILD_NUMBER} || true
                docker rmi ${BACKEND_IMAGE}:latest || true
                docker rmi ${FRONTEND_IMAGE}:${BUILD_NUMBER} || true
                docker rmi ${FRONTEND_IMAGE}:latest || true
            """
            cleanWs()
        }
        success {
            echo """
            ✅ ========================================
            ✅ Pipeline completed successfully!
            ✅ ========================================
            
            📦 Built Images:
               - ${BACKEND_IMAGE}:${BUILD_NUMBER}
               - ${FRONTEND_IMAGE}:${BUILD_NUMBER}
            
            📝 Updated Manifests:
               - backend-deployment.yaml (rolling update)
               - frontend-rollout.yaml (blue-green preview)
               - configmap.yaml
            
            🔄 Next Steps:
               1. ArgoCD will sync changes (within 3 minutes)
               2. Frontend Rollout creates preview pods with new image
               3. Test preview at: http://<node-ip>:30081
               4. Promote when ready: kubectl argo rollouts promote frontend-rollout -n bluegreen-demo
            
            📊 Active Dashboard: http://<node-ip>:30080 (current version)
            📊 Preview Dashboard: http://<node-ip>:30081 (new version - build ${BUILD_NUMBER})
            
            💡 To promote preview to active:
               kubectl argo rollouts promote frontend-rollout -n bluegreen-demo
            
            💡 To check rollout status:
               kubectl argo rollouts status frontend-rollout -n bluegreen-demo
            """
        }
        failure {
            echo """
            ❌ ========================================
            ❌ Pipeline failed!
            ❌ ========================================
            
            Check the logs above for errors.
            Common issues:
            - Docker build failures
            - Docker Hub authentication
            - Git credential
            - Manifest repo access
            """
        }
    }
}