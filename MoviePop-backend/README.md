# MoviePop-backend

这是鸡米花项目拆分后的后端目录。

包含内容：

- `backend`：FastAPI 路由和业务服务
- `config`：配置模块
- `core`：媒体库、WebDAV、OpenList、刮削等核心能力
- `utils`：缓存、日志、文件名解析等工具模块
- `data`：运行期数据目录
- `covers`：封面缓存目录
- `run_backend.py`：独立启动入口

启动步骤：

```bash
pip install -r requirements.txt
python run_backend.py
```

默认监听：

- `http://127.0.0.1:8765`

补充说明：

- 当前版本已适配同级 `MoviePop-front` 目录作为静态资源来源
- `python run_backend.py` 会保持当前终端不退出，这是正常的服务运行状态
- 启动时会自动打开浏览器
- 如果后续要完全拆仓，建议保留 `backend/config/core/utils` 这一层结构，避免导入路径大面积改动
