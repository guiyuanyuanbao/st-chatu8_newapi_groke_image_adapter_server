# st-chatu8_newapi_groke_image_adapter_server

一个用于转发 `/v1` 请求的轻量级中继服务。

它会在请求转发到上游前，检查 JSON 请求体中的 `messages` 字段：

- 如果 `messages[].content` 是仅由 `{ "type": "text", "text": "..." }` 组成的数组
- 就会把这些文本片段拼接成一个字符串
- 然后再把请求转发给上游服务

这适合兼容只接受字符串 `content` 的上游接口。

## 本地运行

```bash
python relay_server.py \
  --listen-host 0.0.0.0 \
  --listen-port 3100 \
  --upstream-host 127.0.0.1 \
  --upstream-port 3000 \
  --upstream-scheme http \
  --timeout 60
```

## Docker

构建镜像：

```bash
docker build -t relay-server:local .
```

运行容器：

```bash
docker run --rm -p 3100:3100 \
  -e UPSTREAM_HOST=host.docker.internal \
  -e UPSTREAM_PORT=3000 \
  -e UPSTREAM_SCHEME=http \
  -e UPSTREAM_TIMEOUT=60 \
  relay-server:local
```

也可以直接使用仓库里的 `docker-compose.yml`。

## GitHub 自动构建镜像

仓库已包含 `.github/workflows/docker.yml`：

- 推送到 `main` 时自动构建并推送镜像
- 推送 `v*` 标签时自动构建并推送镜像
- 镜像会发布到 `ghcr.io/guiyuanyuanbao/st-chatu8_newapi_groke_image_adapter_server`

常见标签包括：

- `latest`
- `main`
- `sha-<commit>`
- `v1.0.0` 这类 Git 标签
