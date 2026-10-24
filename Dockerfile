FROM python:3.12-slim

WORKDIR /app

RUN pip install uv \
    && useradd \
        --uid 10001 \
        --user-group \
        --create-home \
        --shell /usr/sbin/nologin \
        app \
    && chown app:app /app

COPY --chown=app:app pyproject.toml uv.lock README.md ./
COPY --chown=app:app src ./src

ENV HOME=/home/app
ENV PYTHONPATH=/app/src

USER app

RUN uv sync --locked --no-dev

CMD ["uv", "run", "--no-dev", "uvicorn", "awesome_project.main:app", "--host", "0.0.0.0", "--port", "8000"]
