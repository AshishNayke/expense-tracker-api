FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --locked --no-dev

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "--no-dev", "uvicorn", "awesome_project.main:app", "--host", "0.0.0.0", "--port", "8000"]
