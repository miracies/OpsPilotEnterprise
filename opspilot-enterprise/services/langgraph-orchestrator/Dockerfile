FROM python:3.12-slim
WORKDIR /app
COPY packages/shared-schema /packages/shared-schema
COPY services/langgraph-orchestrator /app
RUN pip install --no-cache-dir /app
EXPOSE 8010
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
