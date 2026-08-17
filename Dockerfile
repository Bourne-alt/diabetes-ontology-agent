FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system dmo \
    && useradd --system --gid dmo --home-dir /app dmo

# 先复制包元数据和 Python 源码，让依赖安装层可被 Docker 缓存。
COPY pyproject.toml README.md ./
COPY src ./src
# 项目运行时按源码路径定位 /app/ontology；editable 安装保留 /app/src/dmo 路径。
RUN python -m pip install --upgrade pip \
    && python -m pip install --editable ".[serve,db]"

# API 运行时需要本体哈希、SPARQL 规则和 GraphDB HTTP 客户端，不能只复制 src/。
COPY ontology ./ontology

# 条件推演会在这里缓存只读的知识层快照。
RUN mkdir -p /app/ontology/dist/.sandbox-cache \
    && chown -R dmo:dmo /app/ontology/dist/.sandbox-cache

USER dmo

EXPOSE 8100

CMD ["uvicorn", "dmo.api:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
