pipeline {
    agent any
    
    environment {
        // Docker Hub configuration
        DOCKER_REGISTRY = 'saimanasg'  // CHANGE THIS
        DOCKER_CREDENTIALS_ID = 'dockerhub-credentials'  // Jenkins credential ID
        
        // Image names
        BACKEND_IMAGE = "${DOCKER_REGISTRY}/bluegreen-backend"
        FRONTEND_IMAGE = "${DOCKER_REGISTRY}/bluegreen-frontend"
        
        // Git configuration - will be set from Jenkins env or credentials
        GIT_CREDENTIALS_ID = 'github-credentials'  // Jenkins credential ID
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
                    echo '📝 Updating Kubernetes manifests...'
                    
                    // Get manifest repo URL from environment variable
                    def manifestRepo = env.MANIFEST_REPO_URL //?: 'https://github.com/your-username/argo-bluegreen-manifests.git'
                    
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
                            
                            # Configure git - use Jenkins user or credential username
                            git config user.email "${GIT_USER_EMAIL}"
                            git config user.name "${GIT_USER}"
                            
                            # Update backend deployment image
                            sed -i 's|image: .*/bluegreen-backend:.*|image: ${BACKEND_IMAGE}:${BUILD_NUMBER}|g' backend-deployment.yaml
                            
                            # Update green frontend deployment image (deploy to inactive)
                            sed -i 's|image: .*/bluegreen-frontend:.*|image: ${FRONTEND_IMAGE}:${BUILD_NUMBER}|g' frontend-deployment-green.yaml
                            
                            # Update ConfigMap with build number
                            sed -i 's|BUILD_NUMBER: .*|BUILD_NUMBER: "${BUILD_NUMBER}"|g' configmap.yaml
                            
                            # Check if there are changes
                            if git diff --quiet; then
                                echo "No changes to commit"
                            else
                                # Commit and push changes
                                git add backend-deployment.yaml frontend-deployment-green.yaml configmap.yaml
                                git commit -m "Build ${BUILD_NUMBER}: Update backend and green frontend images"
                                git push origin main
                                echo "✅ Manifests updated and pushed"
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
               - backend-deployment.yaml
               - frontend-deployment-green.yaml
               - configmap.yaml
            
            🔄 ArgoCD will sync within 3 minutes
            
            📊 Dashboard: http://<node-ip>:30080
            
            💡 To switch traffic to green:
               kubectl patch svc nginx-bluegreen -n bluegreen-demo -p '{"spec":{"selector":{"version":"green"}}}'
            """
        }
        failure {
            echo """
            ❌ ========================================
            ❌ Pipeline failed!
            ❌ ========================================
            
            Check the logs above for errors.
            """
        }
    }
}