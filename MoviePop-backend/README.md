# MoviePop-backend

这是鸡米花项目拆分后的后端目录。

包含内容：

- `backend`：FastAPI 路由和业务服务
- `config`：配置模块
- `core`：媒体库、WebDAV、OpenList、刮削等核心能力
- `utils`：缓存、日志、文件名解析等工具模块
- `data`：运行期数据目录
- `covers`：封面缓存目录
- `run_api.py`：API 启动入口
- `run_backend.py`：后端启动入口（含 Nginx 反向代理配置）

启动步骤：

```bash
pip install -r requirements.txt
python run_backend.py
```

默认监听：

- Nginx 代理端口：`http://localhost:8088`
- 后端 API 端口：`http://127.0.0.1:8765`

补充说明：

- 当前版本通过 Nginx 反向代理提供前端静态资源和 API 路由
- `python run_api.py` 会自动生成 nginx.conf 并启动 Nginx + 后端 API
- 启动后通过 Nginx 端口（默认 8088）访问，端口可在 `data/config.ini` 的 `[server]` 段修改
- 如果后续要完全拆仓，建议保留 `backend/config/core/utils` 这一层结构，避免导入路径大面积改动
