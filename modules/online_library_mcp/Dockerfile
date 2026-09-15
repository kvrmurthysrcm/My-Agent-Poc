FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app
WORKDIR /app
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY modules/online_library_mcp/requirements-cicd.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r /tmp/requirements.txt
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/online_library_mcp /app/modules/online_library_mcp

FROM base AS test
RUN python -m compileall -q /app/modules/online_library_mcp \
    && python -c "from modules.online_library_mcp.server import create_mcp_server; assert create_mcp_server()"

FROM base AS runtime
EXPOSE 8004
CMD ["python", "-m", "modules.online_library_mcp.server"]

