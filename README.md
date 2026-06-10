# JMH-split（鸡米花）

影视库管理工具，将本地磁盘和远程 WebDAV/OpenList 网盘中的视频文件统一管理，提供元数据刮削、智能推荐、ECharts 数据可视化大屏等功能。

## 功能特性

- **多源媒体库管理**：支持 WebDAV、OpenList 网盘（夸克/阿里/115/百度）、本地目录三种来源
- **元数据刮削**：从 TMDB、豆瓣自动获取封面、简介、年份
- **智能推荐系统**：基于用户画像的内容相似度推荐 + 协同过滤 + 多平台外部推荐 + SQLite 持久化推荐数据
- **ECharts 数据可视化大屏**：饼图、折线图、条形图、雷达图交互式观影分析
- **播放进度同步**：支持 MPV 桌面播放器及 MPV 受控模式，跨设备播放进度记录
- **标签系统**：自动标签生成 + 手动标签管理 + 增强文件名解析识别
- **观影报告**：类型分布、年代趋势、完播统计、近期动态
- **观影行为分析**：用户画像、观影时长趋势、类型偏好、时段分布、完播率分析
- **多主题界面**：amber / graphite / forest / coast 四种配色
- **SQLite 数据库**：内置嵌入式数据库，无需额外安装，支持自动备份和恢复

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML5 / CSS3 / JavaScript + ECharts 5.4 |
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 数据存储 | SQLite（主要）+ JSON（降级）|
| 元数据源 | TMDB API / 豆瓣 |
| 网盘集成 | WebDAV / OpenList（AList 兼容） |

## 项目结构

```
JMH-split/
├── MoviePop-front/          # 前端
│   ├── index.html           # 页面入口
│   ├── styles.css           # 样式
│   ├── js/                  # JavaScript 模块
│   │   ├── components/      # UI 组件
│   │   ├── config/          # 配置管理
│   │   ├── core/            # 核心功能
│   │   ├── modals/          # 弹窗组件
│   │   ├── models/          # 数据模型
│   │   ├── openlist/        # OpenList 集成
│   │   ├── player/          # 播放器控制
│   │   ├── services/        # API 服务
│   │   ├── settings/        # 设置管理
│   │   ├── utils/           # 工具函数
│   │   └── views/           # 视图逻辑
│   └── README.md            # 前端说明
├── MoviePop-backend/        # 后端
│   ├── backend/             # 业务逻辑
│   │   ├── app.py           # FastAPI 路由
│   │   ├── services.py      # 业务服务层
│   │   ├── behavior_analytics.py  # 观影行为分析
│   │   ├── recommendation_repository.py # 推荐数据持久化
│   │   ├── analytics.py     # 数据分析 ETL
│   │   ├── jobs.py          # 后台任务管理
│   │   ├── runtime_state.py # 播放器运行时状态
│   │   └── server.py        # 服务器配置
│   ├── config/              # 配置管理
│   │   └── app_config.py    # 全局配置
│   ├── core/                # 核心功能
│   │   ├── cover_scraper.py # 元数据刮削器
│   │   ├── video_library.py # 远程媒体库
│   │   ├── local_video_library.py # 本地媒体库
│   │   ├── remote_source.py # 远程源统一抽象
│   │   ├── webdav_client.py # WebDAV 客户端
│   │   ├── openlist_client.py # OpenList API
│   │   └── openlist_manager.py # OpenList 进程管理
│   ├── utils/               # 工具类
│   │   ├── database.py      # 统一缓存接口
│   │   ├── filename_parser.py # 文件名解析
│   │   ├── logger.py        # 日志配置
│   │   ├── sqlite_connection.py # SQLite 连接管理
│   │   ├── sqlite_dao.py    # 数据访问层
│   │   ├── sqlite_initializer.py # 数据库初始化
│   │   └── storage.py       # 存储抽象
│   ├── docs/                # 文档
│   │   └── DATABASE_INTEGRATION.md # 数据库集成文档
│   ├── data/                # 数据目录（运行时生成）
│   │   ├── moviepop.db      # SQLite 数据库
│   │   ├── backups/         # 数据库备份
│   │   └── cache.json       # JSON 缓存（降级）
│   ├── requirements.txt     # Python 依赖
│   ├── run_api.py           # API 启动入口
│   ├── run_backend.py       # 后端启动入口
│   ├── run_backend_only.py  # 仅后端启动
│   ├── run_desktop.py       # 桌面模式启动
│   ├── migrate_data.py      # 数据迁移脚本
│   └── README.md            # 后端说明
├── API.md                   # API 接口文档
├── DATA_ASSETS.md           # 数据资产说明
├── README.md                # 项目说明（本文件）
└── quick_start_desktop.bat  # Windows 快速启动脚本
```

## 快速开始

### 环境要求

- Python 3.10+
- Windows 10/11（推荐，支持 MPV 播放器集成）

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/zaoyoujun/JMH.git
cd JMH

# 2. 安装后端依赖
cd MoviePop-backend
pip install -r requirements.txt

# 3. 启动后端服务
python run_backend.py
```

或直接双击根目录的 `quick_start_desktop.bat` 快速启动。

启动后浏览器自动打开 `http://127.0.0.1:{自动分配端口}`。

### 首次配置

1. 进入「设置」页面
2. 选择远程源类型（WebDAV 或 OpenList）
3. 填写连接信息并测试连接
4. 选择要扫描的目录
5. 回到「我的片库」点击「刷新片库」

## 数据库集成

### SQLite 数据库

项目使用 SQLite 作为主要数据存储方案：

- **自动初始化**：首次启动时自动创建数据库和表结构
- **无需配置**：Python 内置支持，无需额外安装
- **自动备份**：支持数据库备份和恢复功能
- **降级机制**：SQLite 不可用时自动切换到 JSON 文件存储

### 数据库表结构

- `videos`：视频信息表
- `favorites`：收藏表
- `recent_plays`：最近播放表
- `playback_progress`：播放进度表
- `tags`：标签表
- `movie_tags`：电影标签关联表
- `custom_info`：自定义信息表
- `database_version`：版本记录表

详细说明请参考 [DATABASE_INTEGRATION.md](./MoviePop-backend/docs/DATABASE_INTEGRATION.md)

## API 文档

详见 [API.md](./API.md)，包含全部接口的请求参数、响应格式和示例。

主要接口分类：

1. 引导接口 - 应用初始化
2. 配置管理 - 配置读取和保存
3. 目录浏览 - 远程和本地目录浏览
4. 影片库管理 - 影片列表和刷新
5. 影片操作 - 收藏、评分、标签等
6. 标签管理 - 标签增删改查
7. 推荐系统 - 智能推荐
8. 数据报告 - 观影统计和分析
9. 后台任务 - 异步任务管理
10. 缓存管理 - 缓存清理和刷新
11. OpenList 网盘管理 - 网盘操作
12. MPV 受控播放会话 - 播放器控制
13. 播放器运行时 - 运行时状态
14. 流媒体代理 - 视频流代理
15. 观影行为分析 - 用户行为分析

## 部署说明

### 开发环境

```bash
# 后端
cd MoviePop-backend
python run_backend.py

# 前端（如需独立运行前端）
cd MoviePop-front
# 使用 Live Server 或其他静态服务器
```

### 生产环境

推荐使用 Nginx 反向代理：

```nginx
server {
    listen 8088;
    
    location / {
        root /path/to/MoviePop-front;
        index index.html;
    }
    
    location /api {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /covers {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 数据库备份

```bash
# 手动备份
python -c "from utils.sqlite_initializer import backup_database; print(backup_database())"

# 恢复备份
python -c "from utils.sqlite_initializer import restore_database; restore_database('data/backups/backup.db')"
```

## 项目状态

- 开发状态：活跃维护中
- 版本：v2.2（增强版本）

## 更新日志

### v2.2（增强版本）
- 播放器全面迁移至 MPV 桌面版及受控模式
- 新增观影行为分析模块（用户画像、时长趋势、类型偏好、时段分布、完播率）
- 推荐数据迁移至 SQLite 持久化存储
- 新增 `core/remote_source.py` 远程源统一抽象层
- 文件名解析器大幅增强（季数/特别篇/部分识别、系列分组、分辨率/编码解析）
- 缓存数据模型扩展（支持 season_title、special_type、resolution、codec 等新字段）
- 集成 SQLite 数据库，支持自动备份和恢复
- 新增数据库降级机制（SQLite 不可用时自动切换到 JSON）
- API 版本 2.2.0

### v2.0（拆分重构）
- 项目拆分为前后端分离结构
- 后端重构为模块化架构（backend/config/core/utils）
- 前端保持原生 HTML/CSS/JS 实现
- 新增 OpenList 增量同步支持
- 优化推荐算法性能

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 常见问题

### Q: SQLite 数据库文件在哪里？

A: 默认位置为 `MoviePop-backend/data/moviepop.db`，备份文件在 `MoviePop-backend/data/backups/` 目录。

### Q: 如何切换到 JSON 文件存储？

A: 系统会自动检测 SQLite 可用性，不可用时自动降级到 JSON 文件存储（`data/cache.json`）。

### Q: 如何备份数据？

A: 可以手动调用备份函数，或定期执行 `python -c "from utils.sqlite_initializer import backup_database; backup_database()"`。

### Q: 支持哪些视频格式？

A: 支持常见视频格式，包括 .mp4、.mkv、.avi、.mov、.flv、.wmv 等，可在设置中自定义。

### Q: 如何配置 TMDB API？

A: 在设置页面填写 TMDB API Key，系统会自动从 TMDB 获取影片元数据。