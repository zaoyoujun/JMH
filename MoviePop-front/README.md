# MoviePop-front

这是鸡米花项目拆分后的前端目录。

内容：

- `index.html`：页面入口
- `app.js`：交互逻辑
- `styles.css`：样式文件

说明：

- 当前前端是原生 HTML/CSS/JavaScript
- 代码默认通过同源路径访问后端接口，例如 `/api/*`
- 推荐部署方式是把前端静态文件托管到 Web 服务，并把 `/api` 和 `/covers` 代理到 `MoviePop-backend`
