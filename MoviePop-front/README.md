# MoviePop-front

这是鸡米花项目拆分后的前端目录。

## 目录结构

```
MoviePop-front/
├── index.html    # 页面入口（单页应用）
├── app.js        # 核心交互逻辑和路由
└── styles.css    # 全局样式（支持多主题）
```

## 技术栈

- **框架**：原生 HTML5 / CSS3 / JavaScript（无第三方框架依赖）
- **图表库**：ECharts 5.4（数据可视化大屏）
- **图标**：内联 SVG

## 功能模块

- 影片库浏览（网格/列表视图）
- 影片详情展示
- 播放进度管理
- 智能推荐系统
- ECharts 数据可视化大屏
- 观影行为分析看板
- 多主题切换（amber/graphite/forest/coast）

## 开发说明

- 代码默认通过同源路径 `/api/*` 访问后端接口
- `/covers` 路径用于访问封面图片（需配置反向代理）
- 前端静态资源通过 Nginx 托管，与后端 API 共享同一域名

## 部署方式

推荐部署方式是把前端静态文件托管到 Web 服务，并配置反向代理：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8765/api/;
}

location /covers/ {
    proxy_pass http://127.0.0.1:8765/covers/;
}
```

## 启动方式

开发阶段可直接使用 `MoviePop-backend/run_backend.py` 启动，它会自动配置 Nginx 反向代理，将前端和 API 统一在 `http://localhost:8088` 下提供服务。
