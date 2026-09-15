# Timezone Synchronization for Local CI/CD

This document explains why timezone synchronization is used in the local development environment and how Jenkins and Kubernetes application pods are configured to use the same local timezone as the Windows laptop.

## Why We Are Doing This

The Windows laptop uses:

```text
America/New_York
```

Jenkins previously showed timestamps such as:

```text
2026-09-14 22:54
```

while the laptop showed approximately:

```text
2026-09-14 18:54
```

These represented the same instant. Jenkins was using UTC while the laptop was showing Eastern Daylight Time.

Although technically correct, mixed visible timezones make troubleshooting harder when correlating Git pushes, Jenkins builds, Docker activity, Kubernetes deployments, application logs, pod restarts, and health checks.

For this local POC, operational logs are standardized on:

```text
America/New_York
```

Use `America/New_York` rather than hardcoding `EST` because it automatically handles EST/EDT daylight-saving transitions.

---

# Jenkins Timezone

Jenkins runs in Docker and Jenkins itself is a Java application.

The container timezone is configured with:

```text
TZ=America/New_York
```

The Jenkins JVM timezone is explicitly configured with:

```text
JAVA_OPTS=-Duser.timezone=America/New_York
```

Both are used so that the container operating system and the Jenkins JVM agree on the local timezone.

## Current Jenkins Container

```text
Container name: jenkins
Image: local-jenkins:cicd
Host port: 9090
Container port: 8080
```

Jenkins data is persisted in:

```text
jenkins_home:/var/jenkins_home
```

Important mounts:

```text
jenkins_home:/var/jenkins_home
/run/host-services/docker.proxy.sock:/var/run/docker.sock
/run/desktop/mnt/host/d/common:/workspace
/run/desktop/mnt/host/c/Users/kvrmu/.kube:/var/jenkins_home/.kube:ro
```

Because `jenkins_home` is a persistent Docker volume, recreating the Jenkins container does not remove Jenkins jobs or configuration as long as the same volume is reused.

---

# Important Jenkins Home Permission Check

The Jenkins container runs as a non-root Linux user and must be able to write to:

```text
/var/jenkins_home
```

A restart loop with an error similar to:

```text
touch: cannot touch '/var/jenkins_home/copy_reference_file.log': Permission denied
Can not write to /var/jenkins_home/copy_reference_file.log. Wrong volume permissions?
```

means the persistent Docker volume has incorrect Linux ownership.

This is not a timezone problem.

## Check Jenkins Volume Ownership

```powershell
docker run --rm `
  -v jenkins_home:/var/jenkins_home `
  alpine `
  sh -c "ls -ldn /var/jenkins_home; ls -ln /var/jenkins_home | head"
```

For the standard Jenkins container, ownership is typically:

```text
1000:1000
```

## Fix Jenkins Volume Ownership If Required

Stop Jenkins:

```powershell
docker stop jenkins
```

Correct the ownership:

```powershell
docker run --rm `
  -v jenkins_home:/var/jenkins_home `
  alpine `
  sh -c "chown -R 1000:1000 /var/jenkins_home"
```

Verify again:

```powershell
docker run --rm `
  -v jenkins_home:/var/jenkins_home `
  alpine `
  sh -c "ls -ldn /var/jenkins_home; ls -ln /var/jenkins_home | head"
```

This does not delete Jenkins data. It only restores write permission for the Jenkins runtime user.

---

# Recreate Jenkins with Local Timezone

Once the persistent volume permissions are correct:

```powershell
docker stop jenkins
docker rm jenkins
```

Then recreate:

```powershell
docker run -d `
  --name jenkins `
  --restart unless-stopped `
  -p 9090:8080 `
  -p 50000:50000 `
  -e TZ=America/New_York `
  -e JAVA_OPTS="-Duser.timezone=America/New_York" `
  -v jenkins_home:/var/jenkins_home `
  -v /run/host-services/docker.proxy.sock:/var/run/docker.sock `
  -v /run/desktop/mnt/host/d/common:/workspace `
  -v /run/desktop/mnt/host/c/Users/kvrmu/.kube:/var/jenkins_home/.kube:ro `
  local-jenkins:cicd
```

Both port mappings in the same command are valid:

```text
9090:8080   Jenkins web UI
50000:50000 Jenkins inbound agent port
```

The `50000` mapping is optional if inbound Jenkins agents are not used.

---

# Verify Jenkins After Restart

Check status:

```powershell
docker ps --filter name=jenkins
```

If restarting:

```powershell
docker ps -a --filter name=jenkins
docker logs --tail 100 jenkins
```

Verify container time:

```powershell
docker exec jenkins date
```

Verify JVM timezone:

```powershell
docker exec jenkins sh -c 'java -XshowSettings:properties -version 2>&1 | grep user.timezone'
```

Expected:

```text
user.timezone = America/New_York
```

Verify logs:

```powershell
docker logs --tail 30 jenkins
```

---

# Kubernetes Application Pod Timezone

The five deployed application services are:

```text
rag-ingest-service
rag-search-service
rag-answer-service
online-library
secure-api
```

Each service ConfigMap contains:

```yaml
TZ: "America/New_York"
```

The Deployment injects the ConfigMap into the container environment through `envFrom`.

---

# Why tzdata Is Installed in the Python Images

The application images use slim Python base images.

Slim images may not contain the full timezone database. Therefore the Dockerfiles install:

```text
tzdata
```

Example:

```dockerfile
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
```

The combination is:

```text
TZ=America/New_York
        +
tzdata
        ↓
Correct EDT / EST handling
```

---

# Verify Kubernetes Pod Time

After Jenkins rebuilds and redeploys:

```powershell
kubectl -n rag-poc exec deployment/rag-ingest-service -- date
kubectl -n rag-poc exec deployment/rag-search-service -- date
kubectl -n rag-poc exec deployment/rag-answer-service -- date
kubectl -n rag-poc exec deployment/online-library -- date
kubectl -n rag-poc exec deployment/secure-api -- date
```

Expected output should contain `EDT` or `EST`.

---

# Python Application Logging

The `TZ` variable affects normal local-time behavior, but code can still explicitly generate UTC timestamps.

Example:

```python
datetime.now(timezone.utc)
```

For easier troubleshooting, prefer timezone-aware ISO timestamps such as:

```text
2026-09-14T19:30:00-04:00
```

---

# PostgreSQL Recommendation

Keep stored database timestamps in UTC.

Recommended model:

```text
Database stored timestamps
        UTC
         ↓
Application / Jenkins / Pod logs
   America/New_York
         ↓
Developer troubleshooting
     Same visible time
```

---

# Target Timezone Configuration

```text
Windows laptop          America/New_York
Jenkins container       America/New_York
Jenkins JVM             America/New_York
Kubernetes pods         America/New_York
Python application logs America/New_York where local time is used
Keycloak                To be configured separately
PostgreSQL stored time  UTC
Ollama                  Uses Windows host time
```

---

# Summary

Yes, the Jenkins restart commands in this document can be reused safely, provided:

1. the same `jenkins_home` volume is reused,
2. the volume ownership is correct for Jenkins,
3. the existing Docker socket/workspace/kubeconfig mounts are preserved.

The timezone changes make Jenkins and pod timestamps match the laptop, reducing confusion when tracing CI/CD events.
