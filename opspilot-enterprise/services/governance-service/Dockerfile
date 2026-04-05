FROM python:3.12-slim
WORKDIR /app
COPY ../../packages/shared-schema /shared-schema
RUN pip install --no-cache-dir /shared-schema
COPY . .
RUN pip install --no-cache-dir -e . --no-deps
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic
EXPOSE 8071
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8071"]
