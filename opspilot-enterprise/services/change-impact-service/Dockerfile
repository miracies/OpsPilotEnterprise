FROM python:3.12-slim
WORKDIR /app
COPY packages/shared-schema /packages/shared-schema
COPY services/change-impact-service /app
# pyproject path dep resolves ../../packages/shared-schema from /app -> /packages/shared-schema
RUN pip install --no-cache-dir /app
EXPOSE 8040
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8040"]
