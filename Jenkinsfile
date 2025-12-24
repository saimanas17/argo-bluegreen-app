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
    }
    
    post {
        always {
            echo '🧹 Cleaning up...'
            sh """
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
            
            📦 Built Image:
               ${FRONTEND_IMAGE}:${BUILD_NUMBER}
            
            📝 Updated Manifest:
               rollout.yaml
            
            🔄 Next Steps:
               1. ArgoCD will detect the manifest change
               2. Argo Rollouts will create preview pods with new image
               3. Test preview at: http://<node-ip>:30081
               4. Promote when ready using kubectl or Argo Rollouts Dashboard
            
            📊 Active (Current): http://<node-ip>:30080
            📊 Preview (Build ${BUILD_NUMBER}): http://<node-ip>:30081
            
            💡 To promote:
               kubectl argo rollouts promote bluegreen-frontend
            
            💡 To check status:
               kubectl argo rollouts status bluegreen-frontend
               kubectl argo rollouts get rollout bluegreen-frontend --watch
            """
        }
        failure {
            echo """
            ❌ ========================================
            ❌ Pipeline failed!
            ❌ ========================================
            
            Check the logs above for errors.
            Common issues:
            - Docker build failures (check Dockerfile)
            - Docker Hub authentication (check credentials)
            - Git credentials (check github-credentials)
            - Manifest repository access
            """
        }
    }
}