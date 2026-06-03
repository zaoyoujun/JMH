# MoviePop-backend

这是鸡米花项目拆分后的后端目录，提供 RESTful API 服务。

## 目录结构

```
MoviePop-backend/
├── backend/           # FastAPI 路由和业务服务层
│   ├── app.py         # FastAPI 应用实例和路由注册
│   ├── services.py    # 业务服务逻辑
│   ├── behavior_analytics.py  # 观影行为分析服务
│   ├── recommendation_repository.py  # 推荐数据 SQLite 持久化
│   ├── analytics.py   # 数据分析 ETL
│   ├── warehouse.py   # ClickHouse 数据仓库集成
│   ├── jobs.py        # 后台任务管理
│   ├── server.py      # 服务启动和生命周期管理
│   └── runtime_state.py    # 播放器运行时状态
├── config/            # 配置模块
│   └── app_config.py  # 全局配置管理
├── core/              # 核心能力模块
│   ├── cover_scraper.py    # 元数据刮削器（TMDB/豆瓣/动漫科）
│   ├── video_library.py    # 远程媒体库抽象
│   ├── local_video_library.py  # 本地媒体库
│   ├── remote_source.py    # 远程源统一抽象层
│   ├── webdav_client.py    # WebDAV 客户端
│   ├── openlist_client.py  # OpenList API 客户端
│   └── openlist_manager.py # OpenList 进程管理
├── utils/             # 工具模块
│   ├── database.py    # JSON 缓存层（扩展字段）
│   ├── filename_parser.py  # 文件名解析（增强版，支持季/特别篇/分辨率等）
│   └── logger.py      # 日志配置
├── data/              # 运行期数据目录（自动创建）
│   └── config.ini     # 配置文件
├── covers/            # 封面缓存目录（自动创建）
├── test_parse.py      # 文件名解析测试脚本
├── run_api.py         # API 启动入口（仅启动后端，无 Nginx）
├── run_backend.py     # 后端启动入口（含 Nginx 反向代理）
├── run_backend_only.py     # 仅启动后端（无 Nginx）
├── run_desktop.py     # 桌面模式启动入口
└── requirements.txt   # Python 依赖列表
```

## 技术栈

- **框架**：FastAPI 0.100+ / Uvicorn
- **语言**：Python 3.10+
- **数据库**：SQLite（轻量级）+ JSON 文件缓存 + 可选 ClickHouse（OLAP）
- **网盘集成**：WebDAV / OpenList（AList 兼容）
- **元数据源**：TMDB API / 豆瓣 / 动漫科

## 核心功能

1. **多源媒体库管理**：WebDAV、OpenList 网盘、本地目录
2. **元数据刮削**：自动从 TMDB/豆瓣/动漫科获取封面、简介、评分等
3. **智能推荐系统**：内容相似度推荐 + 协同过滤 + SQLite 持久化
4. **播放进度同步**：支持 MPV 桌面播放器及 MPV 受控模式
5. **ECharts 数据可视化大屏**：观影数据分析
6. **观影行为分析**：用户画像、时长趋势、类型偏好、时段分布、完播率
7. **标签系统**：自动标签生成 + 手动标签管理
8. **增强文件名解析**：季数/特别篇/部分编号识别，系列自动分组

## 启动方式

### 方式一：完整启动（推荐）

```bash
pip install -r requirements.txt
python run_backend.py
```

自动生成 Nginx 配置并启动 Nginx + 后端 API。

### 方式二：仅启动 API

```bash
python run_api.py
```

仅启动 FastAPI 服务，不启动 Nginx。

### 方式三：双击启动

直接双击根目录的 `quick_start_desktop.bat`。

## 默认端口

- **Nginx 代理端口**：`http://localhost:8088`（对外访问）
- **后端 API 端口**：`http://127.0.0.1:8765`（内部）

## 配置说明

端口和其他配置可在 `data/config.ini` 的 `[server]` 段修改：

```ini
[server]
port = 8765
nginx_port = 8088
```

## MPV 上一集/下一集切换功能

MoviePop 提供 mpv 播放器上一集/下一集快捷切换功能。

### 功能说明

- 按 `>` 键切换到下一集
- 按 `<` 键切换到上一集
- 支持剧集列表缓存，切换更快速
- 新集从头播放，不继承上一集进度

### 相关文件

- `data/mpv-profile/scripts/episode_switcher.lua` - Lua 脚本处理切换逻辑
- `data/mpv-profile/input.conf` - 键盘快捷键绑定
- `data/mpv-profile/script-opts/uosc.conf` - 控制栏按钮配置

### 使用条件

- 使用内嵌播放器模式播放剧集时功能可用
- 需要后端 API `/api/movies/item` 正常工作

## API 文档

启动服务后访问：
- Swagger UI：`http://localhost:8088/docs`
- Redoc：`http://localhost:8088/redoc`

完整的 API 文档见根目录的 `API.md`。
