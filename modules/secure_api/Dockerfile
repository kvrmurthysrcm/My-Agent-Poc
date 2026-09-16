FROM python:3.13-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

FROM base AS test
ENV PYTHONPATH=/app
RUN python -m pip install "pytest>=9.0.2" "pytest-cov>=7.0.0" "httpx2>=0.1.0"
COPY .coveragerc pytest.ini ./
COPY app ./app
COPY tests ./tests
RUN mkdir -p /tmp/test-results
CMD ["python", "-m", "pytest", "-q", "--junitxml=/tmp/test-results/pytest.xml", "--cov=app", "--cov-config=.coveragerc", "--cov-report=term-missing", "--cov-report=xml:/tmp/test-results/coverage.xml"]

FROM base AS runtime
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
