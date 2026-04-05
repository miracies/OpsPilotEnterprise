FROM python:3.12-slim
WORKDIR /app
COPY packages/shared-schema /packages/shared-schema
COPY services/vmware-skill-gateway /app
RUN pip install --no-cache-dir /packages/shared-schema /app
EXPOSE 8030
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030"]
