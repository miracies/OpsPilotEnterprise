FROM python:3.12-slim
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ENV PIP_INDEX_URL=${PIP_INDEX_URL} PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} PIP_DISABLE_PIP_VERSION_CHECK=1 OPSPILOT_REPO_DIR=/
WORKDIR /app
COPY packages/shared-schema /packages/shared-schema
COPY services/knowledge-service /app
COPY fixtures /fixtures
RUN pip install --no-cache-dir /packages/shared-schema
RUN pip install --no-cache-dir -e /app --no-deps
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic pyyaml
EXPOSE 8072
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8072"]
