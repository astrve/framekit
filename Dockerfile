FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OURO_CONFIG_DIR=/var/lib/ouro/config
ENV OURO_CACHE_DIR=/var/lib/ouro/cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ffmpeg \
      mediainfo \
      mkvtoolnix \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install .

VOLUME ["/var/lib/ouro/config", "/var/lib/ouro/cache", "/media"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["ouro"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
