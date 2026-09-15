pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        K8S_NAMESPACE = 'rag-poc'
        KIND_NODE = 'desktop-control-plane'
        KUBECONFIG = '/var/jenkins_home/kubeconfig-jenkins'
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    def scmVars = checkout scm
                    env.GIT_COMMIT = scmVars.GIT_COMMIT ?: sh(
                        script: 'git rev-parse HEAD', returnStdout: true
                    ).trim()
                    env.GIT_SHORT = sh(
                        script: 'git rev-parse --short=7 HEAD', returnStdout: true
                    ).trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_SHORT}"

                    def base = (
                        scmVars.GIT_PREVIOUS_SUCCESSFUL_COMMIT ?:
                        scmVars.GIT_PREVIOUS_COMMIT ?:
                        ''
                    ).trim()
                    if (!base) {
                        base = sh(
                            script: 'git rev-parse HEAD^ 2>/dev/null || true',
                            returnStdout: true
                        ).trim()
                    }
                    env.CI_BASE_COMMIT = base
                }
            }
        }

        stage('Plan') {
            steps {
                script {
                    env.CI_SERVICES = sh(
                        script: 'bash scripts/ci/detect-changes.sh "$CI_BASE_COMMIT" "$GIT_COMMIT"',
                        returnStdout: true
                    ).trim()
                    env.ANY_SERVICE_CHANGE = env.CI_SERVICES ? 'true' : 'false'
                    currentBuild.description = "${env.GIT_SHORT} | ${env.CI_SERVICES ?: 'docs/no-op'}"
                    echo "Selected services: ${env.CI_SERVICES ?: '<none>'}"
                }
            }
        }

        stage('Preflight') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh '''
                    set -eux
                    git --version
                    docker --version
                    kubectl version --client
                    test -f "$KUBECONFIG"
                    test -f scripts/ci/build-test-deploy.sh
                    test -f scripts/cleanup-old-cicd-images.sh
                    docker inspect "$KIND_NODE" >/dev/null
                    kubectl --kubeconfig "$KUBECONFIG" get nodes -o wide
                    kubectl --kubeconfig "$KUBECONFIG" apply -f k8s/namespace.yaml
                '''
            }
        }

        stage('Build Test Deploy') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh '''
                    bash scripts/ci/build-test-deploy.sh \
                      "$CI_SERVICES" "$IMAGE_TAG" "$K8S_NAMESPACE" \
                      "$KUBECONFIG" "$KIND_NODE"
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true,
                          testResults: 'test-results/**/*.xml'
                }
            }
        }

        stage('Verify Stack') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh '''
                    set -eux
                    kubectl --kubeconfig "$KUBECONFIG" -n "$K8S_NAMESPACE" \
                      get deployments -o custom-columns=NAME:.metadata.name,READY:.status.readyReplicas,IMAGE:.spec.template.spec.containers[*].image
                    kubectl --kubeconfig "$KUBECONFIG" -n "$K8S_NAMESPACE" get pods -o wide
                    kubectl --kubeconfig "$KUBECONFIG" -n "$K8S_NAMESPACE" get services
                '''
            }
        }

        stage('Cleanup') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                catchError(
                    buildResult: 'SUCCESS',
                    stageResult: 'UNSTABLE',
                    message: 'Image retention cleanup failed; deployments are unchanged.'
                ) {
                    sh 'KEEP_CI_IMAGES=3 bash scripts/cleanup-old-cicd-images.sh'
                }
                catchError(
                    buildResult: 'SUCCESS',
                    stageResult: 'UNSTABLE',
                    message: 'Docker builder-cache cleanup failed.'
                ) {
                    sh '''
                        docker builder prune -f --filter "until=24h" || \
                          docker builder prune -f
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Selective CI/CD pipeline completed successfully.'
        }
        failure {
            sh '''
                bash scripts/ci/diagnostics.sh \
                  "$K8S_NAMESPACE" "$KUBECONFIG" || true
            '''
        }
        cleanup {
            deleteDir()
        }
    }
}
