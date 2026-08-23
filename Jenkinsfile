pipeline {
    agent any

    environment {
        // Your K3s Master Node IP and Registry NodePort
        REGISTRY = '192.168.2.100:30500'

        // Dynamic image tag using the Git short commit hash
        IMAGE_TAG = "${env.GIT_COMMIT.take(7)}"

        // Image names mapped to your K3s configurations
        FE_IMAGE_NAME = 'signal-frontend'
        BE_IMAGE_NAME = 'signal-backend'

        // Target GitOps repository
        GITOPS_REPO_URL = 'github.com/space0w1/homelab-infrastructure.git'
        GITOPS_CRED_ID  = 'github-token-id' // The Credential ID you saved in Jenkins UI
    }

    stages {
        stage('Checkout Code') {
            steps {
                echo "Pulling latest application code..."
                checkout scm
            }
        }

        stage('Build & Push Frontend') {
            steps {
                echo "Building Frontend using ./frontend/Dockerfile..."
                sh "docker build --load -t ${REGISTRY}/${FE_IMAGE_NAME}:${IMAGE_TAG} ./frontend"

                echo "Pushing Frontend to K3s Registry..."
                sh "docker push ${REGISTRY}/${FE_IMAGE_NAME}:${IMAGE_TAG}"
            }
        }

        stage('Build & Push Backend') {
            steps {
                echo "Building Backend using ./backend/Dockerfile..."
                sh "docker build --load -t ${REGISTRY}/${BE_IMAGE_NAME}:${IMAGE_TAG} ./backend"

                echo "Pushing Backend to K3s Registry..."
                sh "docker push ${REGISTRY}/${BE_IMAGE_NAME}:${IMAGE_TAG}"
            }
        }

        stage('Update GitOps Manifests') {
            steps {
                echo "Updating Homelab Infrastructure repository..."
                withCredentials([usernamePassword(credentialsId: "${GITOPS_CRED_ID}", usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                    sh """
                        # Wipe out any leftovers from previous builds
                        rm -rf gitops-dir

                        # Clone the infrastructure repository
                        git clone https://${GIT_USER}:${GIT_TOKEN}@${GITOPS_REPO_URL} gitops-dir
                        cd gitops-dir

                        # Dynamically update the tags inside the 'apps/signal/' folder manifest
                        sed -i 's|image: ${REGISTRY}/${FE_IMAGE_NAME}:.*|image: ${REGISTRY}/${FE_IMAGE_NAME}:${IMAGE_TAG}|g' apps/signal/signal-k3s.yaml
                        sed -i 's|image: ${REGISTRY}/${BE_IMAGE_NAME}:.*|image: ${REGISTRY}/${BE_IMAGE_NAME}:${IMAGE_TAG}|g' apps/signal/signal-k3s.yaml

                        # Configure automation identity
                        git config user.name "Jenkins CI"
                        git config user.email "jenkins@home.lab"

                        # Stage, commit, and push changes back
                        git add apps/signal/signal-k3s.yaml

                        if ! git diff-index --quiet HEAD; then
                            git commit -m "Jenkins CI: Update Signal images to ${IMAGE_TAG} [skip ci]"
                            git push origin main
                        else
                            echo "No manifest changes detected. Skipping push."
                        fi
                    """
                }
            }
        }
    }

    post {
        always {
            echo "Cleaning up local workspace images..."
            // Deletes the newly built images from your desktop to keep your hard drive clean
            sh "docker rmi ${REGISTRY}/${FE_IMAGE_NAME}:${IMAGE_TAG} || true"
            sh "docker rmi ${REGISTRY}/${BE_IMAGE_NAME}:${IMAGE_TAG} || true"
        }
    }
}
