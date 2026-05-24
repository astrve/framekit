FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ffmpeg \
      mediainfo \
      mkvtoolnix \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -e ".[web]"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "framekit.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

