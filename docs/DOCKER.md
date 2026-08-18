# Docker 部署

API 容器只包含应用。本项目依赖的两个 PostgreSQL 数据库和 GraphDB 应先准备好，
然后通过环境变量把连接地址传给容器。

Compose 运行时会把服务器当前项目中的 `src/` 和 `ontology/` 只读挂载进容器。
因此容器使用的是服务器本地代码，而不是镜像构建时留下的代码副本。条件推演缓存使用
独立的 `sandbox-cache` Docker volume，不会修改服务器源码目录。

## 启动

```bash
cp deploy/env.example .env.docker
# 编辑 .env.docker，填入实际连接信息
chmod 600 .env.docker

docker compose config
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

验证服务和三个后端的连接：

```bash
curl http://127.0.0.1:8100/health
docker compose exec api dmo db status
docker compose exec api dmo db guard-test
```

`/health` 返回体中的 `ok` 应为 `true`。该端点同时检查目标 PostgreSQL 和 GraphDB，
因此容器已经启动不代表业务依赖一定可用。

## 停止与重新启动

仅停止 API 容器，并保留容器、镜像和推演缓存：

```bash
docker compose stop api
```

之后可以直接重新启动：

```bash
docker compose start api
```

停止并删除 API 容器及 Compose 网络，但保留镜像和 `sandbox-cache` 缓存卷：

```bash
docker compose down
```

再次启动时执行：

```bash
docker compose up -d
```

只有明确需要清空可重新生成的推演缓存时才使用 `-v`：

```bash
docker compose down -v
```

`down -v` 会删除 `sandbox-cache` volume；不会删除服务器本地的 `src/`、`ontology/`
或数据库数据，但下次条件推演需要重新从 GraphDB 拉取知识层快照。

## 地址填写规则

- 数据库在其他云主机：使用 VPC 内网 IP，不要绕公网。
- 数据库在 Docker 宿主机：使用 `host.docker.internal`；Compose 已配置 Linux
  所需的 `host-gateway` 映射。
- 数据库在另一个 Compose 服务：使用服务名，例如 `postgres` 或 `graphdb`。
- 容器里的 `127.0.0.1` 是 API 容器自己，不能用来连接宿主机服务。
- `DMO_GRAPHDB_ENDPOINT` 只填根地址，例如 `http://graphdb:7200`，不能带
  `/repositories`；应用会自动拼接 `/repositories/<repository>`。

## 对外提供 HTTPS

Compose 默认把 API 映射到宿主机 `127.0.0.1:8100`，公网无法直接访问。将
`deploy/nginx.conf.example` 复制到 Nginx 配置目录，替换域名后启用：

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/dmo-api
sudo ln -s /etc/nginx/sites-available/dmo-api /etc/nginx/sites-enabled/dmo-api
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d api.example.com
```

当前 API 没有身份认证，并会返回患者相关信息。生产环境应在 Nginx、VPN 或零信任
网关处增加访问控制；云安全组只开放 80/443，不要开放 8100、5432 或 7200。

## 更新与运维

只修改 Python、本体或 SPARQL 规则时，拉取服务器本地代码后重启即可：

```bash
git pull
docker compose restart api
docker compose logs --tail=200 api
```

如果 `pyproject.toml`、Python 版本或 Dockerfile 有变化，需要重建依赖镜像：

```bash
git pull
docker compose up -d --build
```

生产模式没有启用 Uvicorn `--reload`。文件虽然会立即出现在容器中，但已经运行的
worker 只会在 `docker compose restart api` 后重新加载模块。

默认启动两个 Uvicorn worker。小内存服务器可改为：

```bash
DMO_API_WORKERS=1 docker compose up -d
```

如需使用其他环境文件：

```bash
DMO_ENV_FILE=/secure/path/dmo.env docker compose up -d
```
