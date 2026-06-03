# MoviePop SQLite 数据库集成文档

## 1. 概述

本文档描述了 MoviePop 应用程序的数据存储架构规范，包括 SQLite 嵌入式数据库系统的集成设计、配置说明、数据模型设计以及异常处理机制。SQLite 作为内置数据库，无需用户手动安装配置，实现真正的开箱即用。

## 2. 环境配置说明

### 2.1 SQLite 数据库要求

- **版本要求**: SQLite 3.30+（Python 内置，无需额外安装）
- **字符集**: UTF-8 (支持完整 Unicode 字符)
- **存储模式**: WAL (Write-Ahead Logging) 模式，支持并发读写

### 2.2 安装依赖

SQLite 是 Python 标准库的一部分，无需额外安装。在项目根目录执行以下命令安装其他依赖：

```bash
pip install -r requirements.txt
```

### 2.3 配置方式

#### 2.3.1 配置文件配置

应用启动后会在 `data/config.ini` 文件中持久化配置：

```ini
[database]
db_path = data/moviepop.db
```

#### 2.3.2 数据库文件位置

- 默认数据库文件路径：`data/moviepop.db`
- 备份文件路径：`data/backups/`
- 降级存储路径：`data/cache.json`（SQLite不可用时自动切换）

## 3. 数据库连接管理机制

### 3.1 连接配置

SQLite 连接使用单例模式管理，配置参数如下：

| 参数 | 说明 | 默认值 |
|-----|------|--------|
| check_same_thread | 是否检查线程安全 | false（允许多线程访问） |
| isolation_level | 事务隔离级别 | None（自动提交） |
| journal_mode | 日志模式 | WAL（提高并发性能） |
| foreign_keys | 外键约束 | ON（启用外键检查） |

### 3.2 连接管理模块

连接管理模块位于 `utils/sqlite_connection.py`，提供以下功能：

- **单例模式**: 全局唯一连接实例
- **自动初始化**: 首次使用时自动初始化
- **连接获取**: 通过 `get_sqlite_connection()` 获取连接
- **健康检查**: 通过 `is_connected()` 检查连接状态

### 3.3 使用示例

```python
from utils.sqlite_connection import get_sqlite_connection

conn = get_sqlite_connection()

# 执行 SQL
cursor = conn.execute("SELECT * FROM videos LIMIT 10")
result = cursor.fetchall()

# 使用上下文管理器
with conn:
    conn.execute("INSERT INTO ...")
```

## 4. 数据模型设计规范

### 4.1 数据库表结构

#### 4.1.1 videos 表 (视频信息表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 视频唯一标识 |
| title | TEXT | NOT NULL | 视频标题 |
| name | TEXT | DEFAULT '' | 视频文件名 |
| type | TEXT | DEFAULT '视频' | 视频类型 |
| year | INTEGER | DEFAULT 2024 | 年份 |
| duration | TEXT | DEFAULT '未知' | 时长 |
| director | TEXT | DEFAULT '未知' | 导演 |
| actors | TEXT | - | 演员列表 |
| intro | TEXT | - | 简介 |
| is_series | INTEGER | DEFAULT 0 | 是否为剧集 |
| episodes | TEXT | - | 剧集信息(JSON) |
| episode_files | TEXT | - | 剧集文件列表(JSON) |
| path | TEXT | NOT NULL UNIQUE | 视频路径 |
| cover_path | TEXT | DEFAULT '' | 封面路径 |
| season | INTEGER | DEFAULT 0 | 季数 |
| category | TEXT | DEFAULT '' | 分类 |
| rating | REAL | DEFAULT 0.0 | 评分 |
| is_favorite | INTEGER | DEFAULT 0 | 是否收藏 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

#### 4.1.2 favorites 表 (收藏表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 收藏记录唯一标识 |
| video_id | INTEGER | FOREIGN KEY | 关联视频ID |
| added_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 添加时间 |

#### 4.1.3 recent_plays 表 (最近播放表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 播放记录唯一标识 |
| video_id | INTEGER | FOREIGN KEY | 关联视频ID |
| played_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 播放时间 |

#### 4.1.4 playback_progress 表 (播放进度表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 进度记录唯一标识 |
| video_id | INTEGER | FOREIGN KEY | 关联视频ID |
| progress | INTEGER | DEFAULT 0 | 播放进度(秒) |
| duration | INTEGER | DEFAULT 0 | 视频时长(秒) |
| episode_index | INTEGER | DEFAULT 0 | 剧集索引 |

#### 4.1.5 tags 表 (标签表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 标签唯一标识 |
| name | TEXT | NOT NULL UNIQUE | 标签名称 |

#### 4.1.6 movie_tags 表 (电影标签关联表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 关联记录唯一标识 |
| video_id | INTEGER | FOREIGN KEY | 关联视频ID |
| tag_id | INTEGER | FOREIGN KEY | 关联标签ID |

#### 4.1.7 custom_info 表 (自定义信息表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 记录唯一标识 |
| video_id | INTEGER | FOREIGN KEY | 关联视频ID |
| data | TEXT | - | 自定义数据(JSON) |

#### 4.1.8 database_version 表 (版本记录表)

| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 版本记录唯一标识 |
| version | TEXT | NOT NULL UNIQUE | 版本号 |
| applied_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 应用时间 |

### 4.2 索引设计

| 表名 | 索引名 | 字段 | 类型 |
|-----|-------|------|------|
| videos | idx_path | path | UNIQUE |
| videos | idx_title | title | NORMAL |
| videos | idx_is_favorite | is_favorite | NORMAL |
| videos | idx_year | year | NORMAL |
| videos | idx_category | category | NORMAL |
| favorites | idx_video_id | video_id | UNIQUE |
| recent_plays | idx_played_at | played_at | NORMAL |
| playback_progress | idx_video_id | video_id | UNIQUE |
| tags | idx_name | name | NORMAL |
| movie_tags | idx_video_tag | video_id, tag_id | UNIQUE |
| custom_info | idx_video_id | video_id | UNIQUE |

## 5. 统一数据访问层接口

### 5.1 DAO 模块结构

数据访问层位于 `utils/sqlite_dao.py`，包含以下 DAO 类：

| DAO 类 | 职责 |
|-------|------|
| SQLiteVideoDAO | 视频数据的增删改查 |
| SQLiteFavoriteDAO | 收藏记录管理 |
| SQLiteRecentPlayDAO | 最近播放记录管理 |
| SQLitePlaybackProgressDAO | 播放进度管理 |
| SQLiteTagDAO | 标签管理 |
| SQLiteCustomInfoDAO | 自定义信息管理 |
| VideoCacheSQLite | 统一缓存接口实现 |

### 5.2 SQLiteVideoDAO 接口

```python
class SQLiteVideoDAO:
    def insert_video(video_data: Dict) -> int        # 插入/更新视频
    def get_video_by_path(path: str) -> Dict         # 按路径获取视频
    def get_video_by_id(video_id: int) -> Dict       # 按ID获取视频
    def get_all_videos() -> List[Dict]               # 获取所有视频
    def get_favorite_videos() -> List[Dict]          # 获取收藏视频
    def update_video(video_id: int, data: Dict) -> bool # 更新视频
    def delete_video(video_id: int) -> bool          # 删除视频
    def search_videos(keyword: str) -> List[Dict]    # 搜索视频
```

### 5.3 统一缓存接口

`VideoCache` 类提供统一的缓存接口，支持 SQLite 和 JSON 文件两种存储方式的自动切换：

```python
from utils.database import VideoCache

cache = VideoCache()

# 保存视频缓存
cache.save_cache(video_list)

# 加载视频缓存
videos = cache.load_cache()

# 添加收藏
cache.add_favorite(movie_data)

# 保存播放进度
cache.save_playback_progress(path, progress, duration)
```

## 6. 数据库初始化脚本

### 6.1 初始化流程

应用启动时自动执行以下初始化流程：

1. **数据库目录检查**: 检查 `data/` 目录是否存在，不存在则创建
2. **连接初始化**: 创建 SQLite 连接
3. **Schema 执行**: 执行表结构创建语句
4. **索引创建**: 创建必要的索引
5. **版本记录**: 更新 `database_version` 表

### 6.2 使用方式

```python
from utils.sqlite_initializer import init_sqlite_database

# 初始化数据库（应用启动时自动调用）
success = init_sqlite_database()
if success:
    print("数据库初始化成功")
else:
    print("数据库初始化失败，将使用 JSON 文件存储")
```

## 7. 数据库备份与恢复策略

### 7.1 备份功能

```python
from utils.sqlite_initializer import backup_database, restore_database

# 创建备份（默认保存到 data/backups/ 目录）
backup_path = backup_database()
print(f"备份已保存到: {backup_path}")

# 指定备份路径
backup_path = backup_database("/path/to/backup.db")
```

### 7.2 恢复功能

```python
# 从备份恢复
success = restore_database("/path/to/backup.db")
if success:
    print("恢复成功")
```

### 7.3 备份策略建议

1. **定期备份**: 建议每天凌晨执行自动备份
2. **保留策略**: 保留最近 7 天的备份文件
3. **备份位置**: 将备份文件存储在不同磁盘或远程存储

### 7.4 备份文件格式

备份文件为 SQLite 数据库文件格式（.db），可直接用于恢复。

## 8. 异常处理机制

### 8.1 异常分类

| 异常类型 | 说明 | 处理策略 |
|---------|------|---------|
| 连接异常 | 无法连接到数据库 | 降级到 JSON 文件存储 |
| 查询异常 | SQL 执行失败 | 记录日志，返回空结果 |
| 事务异常 | 事务提交失败 | 回滚事务，记录日志 |
| 数据异常 | 数据格式错误 | 记录日志，返回错误信息 |

### 8.2 连接降级机制

当 SQLite 不可用时，系统自动降级到 JSON 文件存储：

```python
# VideoCache._get_cache() 中的降级逻辑
try:
    from utils.sqlite_initializer import init_sqlite_database
    if init_sqlite_database():
        self._cache = VideoCacheSQLite()
    else:
        self._cache = VideoCacheJson()  # 降级到 JSON
except Exception as e:
    logger.error(f"Failed to initialize SQLite cache: {e}, falling back to JSON")
    self._cache = VideoCacheJson()      # 异常时降级
```

### 8.3 日志记录

所有数据库操作异常都会记录到日志文件：

```python
import logging

logger = logging.getLogger(__name__)

try:
    # 数据库操作
except Exception as e:
    logger.error(f"数据库操作失败: {e}")
```

### 8.4 错误处理示例

```python
from utils.database import VideoCache

cache = VideoCache()

try:
    videos = cache.load_cache()
except Exception as e:
    logger.error(f"加载缓存失败: {e}")
    videos = []  # 返回空列表，保证业务继续运行
```

## 9. 性能优化策略

### 9.1 索引优化

- 为常用查询字段创建索引
- 使用复合索引优化多条件查询
- 定期分析索引使用情况

### 9.2 连接优化

- 使用 WAL 模式提高并发性能
- 设置合理的缓存大小
- 启用外键约束保证数据完整性

### 9.3 查询优化

- 使用批量插入减少数据库交互
- 避免 SELECT *，只查询需要的字段
- 使用 LIMIT 限制返回数据量

### 9.4 缓存策略

- 应用层缓存热门数据
- 定期清理过期数据

## 10. 并发访问支持

### 10.1 WAL 模式并发

SQLite 在 WAL 模式下支持：

- 多个读操作同时进行
- 读操作和写操作同时进行
- 单个写操作（SQLite 写操作是串行的）

### 10.2 事务隔离

使用默认的 DEFERRED 事务模式，保证：

- 读取已提交的数据
- 防止脏读

### 10.3 锁机制

- SQLite 数据库级锁
- 使用 WAL 模式减少锁竞争
- 乐观锁更新（版本号机制）

## 11. 安全规范

### 11.1 数据安全

- 数据库文件存储在应用目录内
- 定期备份防止数据丢失
- 敏感数据不记录到日志

### 11.2 SQL 注入防护

- 使用参数化查询
- 对用户输入进行验证和过滤

### 11.3 访问控制

- 限制数据库文件的访问权限
- 使用最小权限原则

## 12. 文件结构

```
MoviePop-backend/
├── config/
│   └── app_config.py           # 应用配置
├── data/
│   ├── moviepop.db             # SQLite 数据库文件
│   ├── backups/                # 备份目录
│   └── cache.json              # 降级存储文件
├── utils/
│   ├── database.py             # 统一缓存接口
│   ├── sqlite_connection.py    # 连接管理
│   ├── sqlite_dao.py           # 数据访问层
│   └── sqlite_initializer.py   # 数据库初始化
└── docs/
    └── DATABASE_INTEGRATION.md # 集成文档
```

## 13. 附录

### 13.1 配置示例

完整的配置文件示例：

```ini
[database]
db_path = data/moviepop.db
```

### 13.2 状态码说明

| 状态码 | 含义 |
|-------|------|
| 0 | 操作成功 |
| 1 | 连接失败 |
| 2 | 数据不存在 |
| 3 | 数据已存在 |
| 4 | 参数错误 |
| 5 | 权限不足 |
