FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

FROM base AS test
ENV PYTHONPATH=/app
RUN pip install "pytest>=9.0.0"
COPY app ./app
COPY tests ./tests
RUN mkdir -p /tmp/test-results
CMD ["python", "-m", "pytest", "-q", "--junitxml=/tmp/test-results/pytest.xml"]

FROM base AS runtime
COPY app ./app
RUN mkdir -p /app/storage
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
