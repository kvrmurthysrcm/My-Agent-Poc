pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        choice(
            name: 'MAX_PARALLEL_SERVICES',
            choices: ['2', '1', '3', '4'],
            description: 'Maximum service build/test or deployment workers on the shared Docker/Kubernetes host.'
        )
    }

    environment {
        K8S_NAMESPACE = 'rag-poc'
        KIND_NODE = 'desktop-control-plane'
        KUBECONFIG = '/var/jenkins_home/kubeconfig-jenkins'
        SONAR_HOST_URL = 'http://sonarqube:9000'
        SONAR_DOCKER_NETWORK = 'keycloak_keycloak-network'
        SONAR_INGEST_TOKEN_CREDENTIALS_ID = 'sonarqube-token-rag-ingest'
        SONAR_SEARCH_TOKEN_CREDENTIALS_ID = 'sonarqube-token-rag-search'
        SONAR_ANSWER_TOKEN_CREDENTIALS_ID = 'sonarqube-token-rag-answer'
        SONAR_LIBRARY_TOKEN_CREDENTIALS_ID = 'sonarqube-token'
        SONAR_SECURE_TOKEN_CREDENTIALS_ID = 'sonarqube-token-secure-api'
        SONAR_REPORT_TOKEN_CREDENTIALS_ID = 'sonarqube-report-token'
        SONAR_SCANNER_IMAGE = 'sonarsource/sonar-scanner-cli:12.1.0.3233_8.0.1'
        SONAR_PUBLIC_URL = 'http://localhost:9000'
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
                    test -f scripts/ci/service-worker.sh
                    test -f scripts/ci/init-sonar-summary.sh
                    test -f scripts/ci/sonar-export-summary.py
                    test -f scripts/ci/sonar-service.sh
                    test -f scripts/ci/sonar-export-report.sh
                    test -f scripts/cleanup-old-cicd-images.sh
                    command -v xargs
                    command -v flock
                    docker inspect "$KIND_NODE" >/dev/null
                    kubectl --kubeconfig "$KUBECONFIG" get nodes -o wide
                    kubectl --kubeconfig "$KUBECONFIG" apply -f k8s/namespace.yaml
                '''
            }
        }

        stage('Initialize Sonar Report') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh 'bash scripts/ci/init-sonar-summary.sh "$CI_SERVICES"'
            }
        }

        stage('Build and Test') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh '''
                    echo "Using up to $MAX_PARALLEL_SERVICES parallel build/test workers."
                    bash scripts/ci/build-test-deploy.sh \
                      "$CI_SERVICES" "$IMAGE_TAG" "$K8S_NAMESPACE" \
                      "$KUBECONFIG" "$KIND_NODE" build-test
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true,
                          testResults: 'test-results/**/pytest.xml'
                    archiveArtifacts allowEmptyArchive: true,
                                     artifacts: 'build-reports/image-sizes.tsv,test-results/**/coverage.xml',
                                     fingerprint: true
                }
            }
        }

        stage('Sonar - Five Python Services (Advisory)') {
            when {
                expression {
                    def selected = ",${env.CI_SERVICES ?: ''},"
                    ['ingest', 'search', 'answer', 'library', 'secure'].any {
                        selected.contains(",${it},")
                    }
                }
            }
            steps {
                script {
                    def selected = ",${env.CI_SERVICES ?: ''},"
                    def targets = [
                        [id: 'ingest', credential: env.SONAR_INGEST_TOKEN_CREDENTIALS_ID],
                        [id: 'search', credential: env.SONAR_SEARCH_TOKEN_CREDENTIALS_ID],
                        [id: 'answer', credential: env.SONAR_ANSWER_TOKEN_CREDENTIALS_ID],
                        [id: 'library', credential: env.SONAR_LIBRARY_TOKEN_CREDENTIALS_ID],
                        [id: 'secure', credential: env.SONAR_SECURE_TOKEN_CREDENTIALS_ID]
                    ]
                    targets.each { target ->
                        if (selected.contains(",${target.id},")) {
                            catchError(
                                buildResult: 'SUCCESS',
                                stageResult: 'UNSTABLE',
                                message: "${target.id} Sonar analysis is advisory."
                            ) {
                                withCredentials([
                                    string(
                                        credentialsId: target.credential,
                                        variable: 'SONAR_TOKEN'
                                    )
                                ]) {
                                    sh "bash scripts/ci/sonar-service.sh ${target.id}"
                                }
                            }
                        }
                    }
                }
                catchError(
                    buildResult: 'SUCCESS',
                    stageResult: 'UNSTABLE',
                    message: 'Sonar metrics export is advisory.'
                ) {
                    withCredentials([
                        string(
                            credentialsId: env.SONAR_REPORT_TOKEN_CREDENTIALS_ID,
                            variable: 'SONAR_REPORT_TOKEN'
                        )
                    ]) {
                        sh 'bash scripts/ci/sonar-export-report.sh "$CI_SERVICES"'
                    }
                }
            }
        }

        stage('Deploy') {
            when { expression { env.ANY_SERVICE_CHANGE == 'true' } }
            steps {
                sh '''
                    echo "Using up to $MAX_PARALLEL_SERVICES parallel deployment workers."
                    bash scripts/ci/build-test-deploy.sh \
                      "$CI_SERVICES" "$IMAGE_TAG" "$K8S_NAMESPACE" \
                      "$KUBECONFIG" "$KIND_NODE" deploy
                '''
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

    }

    post {
        always {
            archiveArtifacts allowEmptyArchive: true,
                             artifacts: 'build-reports/sonar/**',
                             fingerprint: true
            sh '''
                if [ "$ANY_SERVICE_CHANGE" = "true" ]; then
                  KEEP_CI_IMAGES=3 bash scripts/cleanup-old-cicd-images.sh || true
                  docker builder prune -f --filter "until=24h" || \
                    docker builder prune -f || true
                fi
            '''
        }
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
