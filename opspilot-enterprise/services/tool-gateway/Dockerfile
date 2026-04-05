FROM python:3.12-slim
WORKDIR /app
COPY packages/shared-schema /packages/shared-schema
COPY services/tool-gateway /app
RUN pip install --no-cache-dir /app
EXPOSE 8020
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
