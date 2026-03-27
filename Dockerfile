FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        procps \
        tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m venv /app/.venv \
    && /app/.venv/bin/pip install --upgrade pip \
    && /app/.venv/bin/pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/run_live_dashboard.sh \
    /app/run_dashboard_tmux.sh \
    /app/run_sendgrid_tmux.sh \
    /app/run_runtime_worker.sh

EXPOSE 8001

CMD ["bash", "./run_live_dashboard.sh"]
