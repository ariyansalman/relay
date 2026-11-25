FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Exactly the versions that were tested (regenerate with
# `uv pip compile pyproject.toml -o requirements.lock` after changing a dependency).
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY relay ./relay
RUN useradd --create-home relay
USER relay

CMD ["python", "-m", "relay"]
