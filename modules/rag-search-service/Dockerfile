FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

FROM base AS test
RUN pip install "pytest>=9.0.0"
COPY app ./app
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q", "--junitxml=/tmp/test-results/pytest.xml"]

FROM base AS runtime
COPY app ./app
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
