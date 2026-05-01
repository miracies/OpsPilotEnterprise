FROM python:3.12-slim

WORKDIR /app

ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_DEFAULT_TIMEOUT=120

COPY packages/shared-schema /packages/shared-schema
COPY services/memory-service /app

RUN pip install --retries 10 --timeout 120 setuptools wheel
RUN pip install --retries 10 --timeout 120 "pydantic>=2.0"
RUN pip install --retries 10 --timeout 120 --no-build-isolation -e /packages/shared-schema
RUN pip install --retries 10 --timeout 120 \
    "fastapi>=0.115" \
    "uvicorn>=0.30" \
    "httpx>=0.27" \
    "neo4j>=5.0" \
    "psycopg[binary]>=3.2"
RUN pip install --retries 10 --timeout 120 --no-build-isolation --no-deps -e /app

EXPOSE 8073

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8073"]
