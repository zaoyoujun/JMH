# MoviePop API 文档

基础信息：

- 默认地址：`http://127.0.0.1:8765`
- 文档风格：REST
- 数据格式：`application/json`
- 静态资源：
  - `/assets/*`：前端静态文件
  - `/covers/*`：封面资源

## 1. 启动与配置

### `GET /api/bootstrap`
返回应用初始化信息。

返回字段：

- `config`：当前公开配置
- `stats`：媒体库统计
- `has_library`：是否已配置片库

### `GET /api/config`
获取当前配置。

### `PUT /api/config`
保存配置。

请求体示例：

```json
{
  "remote_provider": "webdav",
  "webdav_host": "http://example.com/dav",
  "webdav_user": "demo",
  "webdav_pass": "123456",
  "saved_mount_dirs": ["/movies"],
  "local_mount_dirs": ["D:\\Movies"],
  "default_player": "potplayer",
  "enable_auto_scrape": true,
  "tmdb_api_key": "",
  "interface_theme": "amber",
  "interface_language": "zh"
}
```

### `POST /api/config/test`
测试远程连接配置是否可用。

### `GET /api/directories`
读取远程目录列表。

查询参数：

- `path`：目录路径，默认 `/`

### `POST /api/directories`
带临时配置读取远程目录列表。

### `GET /api/local-directories`
读取本地目录列表。

查询参数：

- `path`：为空时返回盘符根目录

### `POST /api/system/pick-player`
打开系统文件选择器，选择播放器可执行文件。

请求体示例：

```json
{
  "player": "potplayer",
  "current_path": "C:\\Program Files\\DAUM\\PotPlayer\\PotPlayerMini64.exe"
}
```

## 2. 媒体库

### `GET /api/library`
获取媒体库列表。

查询参数：

- `mode`：`all`、`favorite`、`recent`
- `source`：`remote`、`local`、`combined`
- `search`：搜索关键字
- `force_refresh`：是否强制刷新

### `POST /api/library/refresh`
触发媒体库刷新任务。

查询参数：

- `source`：`remote`、`local`、`combined`
- `auto_scrape`：刷新后是否自动刮削

返回示例：

```json
{
  "job_id": "refresh-remote-library-xxxx"
}
```

### `POST /api/library/scrape`
触发整库刮削任务。

### `GET /api/jobs/{job_id}`
查询后台任务状态。

常见返回字段：

- `job_id`
- `status`
- `message`
- `progress`
- `progress_percent`
- `result`
- `error`

## 3. 推荐与报告

### `GET /api/recommendations`
获取推荐看板数据。

查询参数：

- `limit`：站内推荐数量，默认 `18`
- `external_limit`：站外推荐数量，默认 `8`

### `POST /api/recommendations/refresh`
刷新推荐结果。

### `POST /api/recommendations/rate`
给影片打分，用于推荐学习。

请求体示例：

```json
{
  "movie_path": "/movies/demo.mp4",
  "rating": 4.5
}
```

### `GET /api/report`
获取观影报告数据。

## 4. 影片操作

### `POST /api/movies/favorite`
切换收藏状态。

### `GET /api/movies/item`
获取单个影片详情。

查询参数：

- `movie_path`：影片路径
- `source`：可选，`remote` 或 `local`

### `POST /api/movies/recent`
写入最近播放记录。

### `DELETE /api/movies/recent`
清空最近播放记录。

### `POST /api/movies/play`
调用外部播放器播放影片。

请求体示例：

```json
{
  "movie_path": "/movies/demo.mp4",
  "episode_index": 0
}
```

### `POST /api/movies/update`
更新影片自定义信息。

请求体示例：

```json
{
  "movie_path": "/movies/demo.mp4",
  "updates": {
    "title": "影片标题",
    "year": 2024,
    "intro": "简介内容"
  }
}
```

### `POST /api/movies/scrape`
刮削单个影片元数据。

### `POST /api/movies/search-candidates`
搜索手动匹配候选项。

### `POST /api/movies/apply-candidate`
应用候选元数据到影片。

## 5. 流媒体与播放进度

### `GET /api/stream/playlist.m3u8`
获取转写后的 m3u8 播放列表。

### `GET|HEAD /api/stream/media`
### `GET|HEAD /api/stream/media/{media_name}`
代理视频媒体流。

### `GET|HEAD /api/stream/segment`
代理 m3u8 分片资源。

### `POST /api/movies/{movie_path}/progress`
保存播放进度。

请求体示例：

```json
{
  "progress": 128.4,
  "duration": 7200
}
```

### `GET /api/movies/{movie_path}/progress`
读取播放进度。

### `DELETE /api/movies/{movie_path}/progress`
清空播放进度。

## 6. 标签

### `GET /api/tags`
获取全部标签及统计。

### `GET /api/movies/{movie_path}/tags`
获取影片标签。

### `POST /api/movies/{movie_path}/tags`
新增影片标签。

请求体示例：

```json
{
  "tag": "科幻"
}
```

### `DELETE /api/movies/{movie_path}/tags/{tag}`
删除影片标签。

### `GET /api/tags/{tag}/movies`
按标签获取影片列表。

## 7. 缓存与数据维护

### `POST /api/cache/clear`
清理指定来源缓存。

查询参数：

- `source`：可为空，或 `remote` / `local`

### `POST /api/cache/clear-all`
清理全部缓存。

### `POST /api/data/clear-all`
清理缓存、记录、标签等业务数据。

## 8. OpenList 管理

### `GET /api/openlist/status`
获取 OpenList 运行状态。

### `POST /api/openlist/start`
启动 OpenList。

### `POST /api/openlist/stop`
停止 OpenList。

### `POST /api/openlist/restart`
重启 OpenList。

### `GET /api/openlist/config`
获取 OpenList 配置。

### `PUT /api/openlist/config`
保存 OpenList 配置。

请求体示例：

```json
{
  "enabled": true,
  "port": 5244,
  "admin_password": "123456",
  "auto_start": true
}
```

### `POST /api/openlist/download`
下载 OpenList 二进制文件。

### `GET /api/openlist/version`
检查 OpenList 版本和更新状态。

### `POST /api/openlist/reset-password`
重置 OpenList 管理员密码。

### `GET /api/openlist/drivers`
获取支持的存储驱动列表。

### `GET /api/openlist/storages`
获取当前存储挂载列表。

### `GET /api/openlist/directories`
读取 OpenList 目录。

查询参数：

- `path`：默认 `/`
- `recursive`：是否递归

### `POST /api/openlist/storages`
新增存储驱动。

### `PUT /api/openlist/storages`
更新存储驱动。

### `DELETE /api/openlist/storages`
删除存储驱动。

查询参数：

- `storage_id`：存储 ID

### `POST /api/openlist/storages/enable`
启用存储驱动。

### `POST /api/openlist/storages/disable`
禁用存储驱动。

## 9. 错误约定

接口失败时通常返回：

```json
{
  "detail": "错误信息"
}
```

常见状态码：

- `200`：成功
- `400`：请求参数错误或业务失败
- `404`：资源不存在
- `500`：服务内部异常
