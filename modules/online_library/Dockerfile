FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app
WORKDIR /app
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-cicd.txt /tmp/requirements-cicd.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /tmp/requirements-cicd.txt

FROM base AS test
RUN pip install "pytest>=9.0.0" "pytest-cov>=7.0.0" "httpx>=0.28.1"
RUN mkdir -p /app/modules/online_library /tmp/test-results
COPY . /app/modules/online_library
WORKDIR /app/modules/online_library
CMD ["python", "-m", "pytest", "-q", "tests", "--junitxml=/tmp/test-results/pytest.xml", "--cov=.", "--cov-config=.coveragerc", "--cov-report=term-missing", "--cov-report=xml:/tmp/test-results/coverage.xml"]

FROM base AS runtime
RUN mkdir -p /app/modules/online_library
COPY . /app/modules/online_library
EXPOSE 8003
CMD ["python", "-m", "uvicorn", "modules.online_library.api:app", "--host", "0.0.0.0", "--port", "8003"]
