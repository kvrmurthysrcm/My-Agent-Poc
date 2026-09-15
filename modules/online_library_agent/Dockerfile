FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app
WORKDIR /app
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY modules/online_library_agent/requirements-cicd.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /tmp/requirements.txt
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/online_library_agent /app/modules/online_library_agent

FROM base AS test
RUN python -m compileall -q /app/modules/online_library_agent \
    && python -c "from modules.online_library_agent.api import app; assert app.title"

FROM base AS runtime
EXPOSE 8005
CMD ["python", "-m", "uvicorn", "modules.online_library_agent.api:app", "--host", "0.0.0.0", "--port", "8005"]

