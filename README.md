# JMH-split

`JMH-split` 是鸡米花项目的前后端分离整理版。

目录说明：

- `MoviePop-front`：前端静态页面，包含 `index.html`、`app.js`、`styles.css`
- `MoviePop-backend`：后端接口服务，包含 `backend`、`config`、`core`、`utils` 等运行依赖

推荐结构：

```text
JMH-split/
├─ MoviePop-front/
├─ MoviePop-backend/
├─ README.md
└─ API.md
```

运行方式：

1. 首次使用先进入 `MoviePop-backend`
2. 安装依赖：`pip install -r requirements.txt`
3. 回到 `JMH-split` 根目录后双击 `start.bat`
4. 或手动执行：`cd MoviePop-backend && python run_backend.py`

启动结果：

- 后端默认监听 `http://127.0.0.1:8765`
- 启动时会自动打开浏览器
- 终端窗口保持运行属于正常现象，因为它正在提供服务

说明：

- 当前分离版沿用了原项目的 FastAPI + 原生 HTML/CSS/JS 结构
- 后端已调整为从同级 `MoviePop-front` 目录加载前端资源
- 如需彻底独立部署，建议将前端挂到 Nginx，并把 `/api`、`/covers` 反向代理到后端服务
