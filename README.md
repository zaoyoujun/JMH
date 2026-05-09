# JMH-split（鸡米花）

影视库管理工具，将本地磁盘和远程 WebDAV/OpenList 网盘中的视频文件统一管理，提供元数据刮削、智能推荐、ECharts 数据可视化大屏等功能。

## 功能特性

- **多源媒体库管理**：支持 WebDAV、OpenList 网盘（夸克/阿里/115/百度）、本地目录三种来源
- **元数据刮削**：从 TMDB、豆瓣、动漫科自动获取封面、简介、年份
- **智能推荐系统**：基于用户画像的内容相似度推荐 + 协同过滤 + 多平台外部推荐
- **ECharts 数据可视化大屏**：饼图、折线图、条形图、雷达图交互式观影分析
- **播放进度同步**：支持 PotPlayer / VLC / VLC 受控模式，跨设备播放进度记录
- **标签系统**：自动标签生成 + 手动标签管理
- **观影报告**：类型分布、年代趋势、完播统计、近期动态
- **多主题界面**：amber / graphite / forest / coast 四种配色

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML5 / CSS3 / JavaScript + ECharts 5.4 |
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 数据存储 | JSON 文件 + SQLite + 可选 ClickHouse 数据仓库 |
| 元数据源 | TMDB API / 豆瓣 / 动漫科 |
| 网盘集成 | WebDAV / OpenList（AList 兼容） |

## 项目结构

```
JMH-split/
├── MoviePop-front/          # 前端
│   ├── index.html           # 页面入口
│   ├── app.js               # 交互逻辑
│   └── styles.css           # 样式
├── MoviePop-backend/        # 后端
│   ├── backend/
│   │   ├── app.py           # FastAPI 路由
│   │   ├── services.py      # 业务服务层
│   │   ├── recommendations.py # 推荐引擎
│   │   ├── analytics.py     # 数据分析 ETL
│   │   ├── warehouse.py     # ClickHouse 数据仓库
│   │   ├── jobs.py          # 后台任务管理
│   │   └── runtime_state.py # 播放器运行时状态
│   ├── config/
│   │   └── app_config.py    # 全局配置
│   ├── core/
│   │   ├── cover_scraper.py # 元数据刮削器
│   │   ├── video_library.py # 远程媒体库
│   │   ├── local_video_library.py # 本地媒体库
│   │   ├── webdav_client.py # WebDAV 客户端
│   │   ├── openlist_client.py # OpenList API
│   │   └── openlist_manager.py # OpenList 进程管理
│   ├── utils/
│   │   ├── database.py      # JSON 缓存层
│   │   ├── filename_parser.py # 文件名解析
│   │   └── logger.py        # 日志配置
│   ├── requirements.txt     # Python 依赖
│   └── run_api.py           # 启动入口（含 nginx 反向代理）
├── nginx-1.30.0/            # 内置 Nginx
├── API.md                   # API 接口文档
├── README.md                # 项目说明
└── start_nginx.bat          # Windows 启动脚本
```

## 快速开始

### 环境要求

- Python 3.10+
- Windows 10/11（推荐，支持 PotPlayer/VLC 自动检测）

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/zaoyoujun/JMH.git
cd JMH

# 2. 安装后端依赖
cd MoviePop-backend
pip install -r requirements.txt

# 3. 启动服务（含 Nginx 反向代理）
python run_api.py
```

或直接双击根目录的 `start_nginx.bat`。

启动后浏览器自动打开 `http://localhost:8088`（Nginx 代理端口，可在 config.ini 中修改 `nginx_port`）。

### 首次配置

1. 进入「设置」页面
2. 选择远程源类型（WebDAV 或 OpenList）
3. 填写连接信息并测试连接
4. 选择要扫描的目录
5. 回到「我的片库」点击「刷新片库」

## API 文档

详见 [API.md](./API.md)，包含全部接口的请求参数、响应格式和示例。

## 部署说明

项目采用 Nginx 反向代理架构：

- `run_api.py` 启动时自动生成 `nginx.conf` 并启动内置 Nginx（`nginx-1.30.0/`）
- Nginx 监听 `nginx_port`（默认 8088），提供前端静态资源和 API 反向代理
- 后端 API 监听 `port`（默认 8765），通过 Nginx 代理访问
- 端口配置在 `MoviePop-backend/data/config.ini` 的 `[server]` 段

如需独立部署，将前端挂到 Nginx，`/api` 和 `/covers` 反向代理到后端 API 端口。

可选启用 ClickHouse 数据仓库，用于 OLAP 多维分析。
