# MoviePop 后端 API 文档

## 目录
1. [引导接口](#1-引导接口)
2. [配置管理](#2-配置管理)
3. [目录浏览](#3-目录浏览)
4. [影片库管理](#4-影片库管理)
5. [影片操作](#5-影片操作)
6. [标签管理](#6-标签管理)
7. [推荐系统](#7-推荐系统)
8. [数据报告](#8-数据报告)
9. [后台任务](#9-后台任务)
10. [缓存管理](#10-缓存管理)
11. [OpenList 网盘管理](#11-openlist-网盘管理)
12. [VLC 受控播放会话](#12-vlc-受控播放会话)
13. [播放器运行时](#13-播放器运行时)
14. [流媒体代理](#14-流媒体代理)

---

## 1. 引导接口

### 1.1 应用初始化数据
#### 1.1.1 基本信息
请求路径：/api/bootstrap

请求方式：GET

接口描述：该接口用于获取应用初始化数据，包括配置信息、统计数据和是否有影片库

#### 1.1.2 请求参数
无

#### 1.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- config | object | 非必须 | 应用配置信息 |
| |- stats | object | 非必须 | 统计数据 |
| |- has_library | boolean | 非必须 | 是否有影片库 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "config": {
      "remote_provider": "webdav",
      "has_any_library": true,
      "ui_theme": "amber",
      "interface_language": "zh"
    },
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 8
    },
    "has_library": true
  }
}
```

---

## 2. 配置管理

### 2.1 获取当前配置
#### 2.1.1 基本信息
请求路径：/api/config

请求方式：GET

接口描述：该接口用于获取当前应用配置信息

#### 2.1.2 请求参数
无

#### 2.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- remote_provider | string | 非必须 | 远程源类型 (webdav/openlist) |
| |- webdav_host | string | 非必须 | WebDAV 主机地址 |
| |- webdav_user | string | 非必须 | WebDAV 用户名 |
| |- webdav_pass | string | 非必须 | WebDAV 密码 |
| |- remote_cookie | string | 非必须 | 远程源 Cookie |
| |- scan_max_depth | number | 非必须 | 扫描最大深度 |
| |- saved_mount_dirs | array | 非必须 | 已保存的挂载目录列表 |
| |- local_scan_max_depth | number | 非必须 | 本地扫描最大深度 |
| |- local_mount_dirs | array | 非必须 | 本地挂载目录列表 |
| |- potplayer_path | string | 非必须 | PotPlayer 可执行文件路径 |
| |- vlc_path | string | 非必须 | VLC 可执行文件路径 |
| |- default_player | string | 非必须 | 默认播放器 (potplayer/vlc) |
| |- video_formats | array | 非必须 | 视频格式列表 |
| |- enable_auto_scrape | boolean | 非必须 | 是否启用自动刮削 |
| |- scrape_source | string | 非必须 | 刮削源 (auto/tmdb) |
| |- tmdb_api_key | string | 非必须 | TMDB API 密钥 |
| |- tmdb_api_base | string | 非必须 | TMDB API 基础地址 |
| |- tmdb_web_base | string | 非必须 | TMDB 网站地址 |
| |- tmdb_image_base | string | 非必须 | TMDB 图片地址 |
| |- ui_theme | string | 非必须 | UI 主题 |
| |- interface_theme | string | 非必须 | 界面主题 |
| |- interface_language | string | 非必须 | 界面语言 (zh/en) |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "remote_provider": "webdav",
    "webdav_host": "https://dav.example.com",
    "webdav_user": "user",
    "webdav_pass": "",
    "remote_cookie": "",
    "scan_max_depth": 2,
    "saved_mount_dirs": ["/movies", "/tv"],
    "local_scan_max_depth": 3,
    "local_mount_dirs": [],
    "potplayer_path": "C:\\Program Files\\PotPlayer\\PotPlayerMini64.exe",
    "vlc_path": "",
    "default_player": "potplayer",
    "video_formats": [".mp4", ".mkv", ".avi", ".mov"],
    "enable_auto_scrape": true,
    "scrape_source": "auto",
    "tmdb_api_key": "",
    "tmdb_api_base": "https://api.themoviedb.org/3",
    "tmdb_web_base": "https://www.themoviedb.org",
    "tmdb_image_base": "https://image.tmdb.org/t/p/w500",
    "ui_theme": "amber",
    "interface_theme": "amber",
    "interface_language": "zh"
  }
}
```

### 2.2 保存配置
#### 2.2.1 基本信息
请求路径：/api/config

请求方式：PUT

接口描述：该接口用于保存应用配置信息

#### 2.2.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| remote_provider | string | 非必须 | 远程源类型 (webdav/openlist) |
| webdav_host | string | 非必须 | WebDAV 主机地址 |
| webdav_user | string | 非必须 | WebDAV 用户名 |
| webdav_pass | string | 非必须 | WebDAV 密码 |
| remote_cookie | string | 非必须 | 远程源 Cookie |
| scan_max_depth | number | 非必须 | 扫描最大深度 |
| saved_mount_dirs | array | 非必须 | 已保存的挂载目录列表 |
| local_scan_max_depth | number | 非必须 | 本地扫描最大深度 |
| local_mount_dirs | array | 非必须 | 本地挂载目录列表 |
| potplayer_path | string | 非必须 | PotPlayer 可执行文件路径 |
| vlc_path | string | 非必须 | VLC 可执行文件路径 |
| default_player | string | 非必须 | 默认播放器 (potplayer/vlc) |
| video_formats | array | 非必须 | 视频格式列表 |
| enable_auto_scrape | boolean | 非必须 | 是否启用自动刮削 |
| scrape_source | string | 非必须 | 刮削源 (auto/tmdb) |
| tmdb_api_key | string | 非必须 | TMDB API 密钥 |
| tmdb_api_base | string | 非必须 | TMDB API 基础地址 |
| tmdb_web_base | string | 非必须 | TMDB 网站地址 |
| tmdb_image_base | string | 非必须 | TMDB 图片地址 |
| ui_theme | string | 非必须 | UI 主题 |
| interface_theme | string | 非必须 | 界面主题 |
| interface_language | string | 非必须 | 界面语言 (zh/en) |

请求参数样例：
```json
{
  "remote_provider": "webdav",
  "webdav_host": "https://dav.example.com",
  "webdav_user": "user",
  "webdav_pass": "password",
  "scan_max_depth": 3,
  "default_player": "vlc",
  "interface_language": "zh"
}
```

#### 2.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 更新后的配置信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "remote_provider": "webdav",
    "webdav_host": "https://dav.example.com",
    "webdav_user": "user",
    "default_player": "vlc",
    "interface_language": "zh"
  }
}
```

### 2.3 测试连接
#### 2.3.1 基本信息
请求路径：/api/config/test

请求方式：POST

接口描述：该接口用于测试远程源连接是否正常

#### 2.3.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| remote_provider | string | 非必须 | 远程源类型 (webdav/openlist) |
| webdav_host | string | 非必须 | WebDAV 主机地址 |
| webdav_user | string | 非必须 | WebDAV 用户名 |
| webdav_pass | string | 非必须 | WebDAV 密码 |
| remote_cookie | string | 非必须 | 远程源 Cookie |

请求参数样例：
```json
{
  "remote_provider": "webdav",
  "webdav_host": "https://dav.example.com",
  "webdav_user": "user",
  "webdav_pass": "password"
}
```

#### 2.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 连接是否成功 |
| |- message | string | 非必须 | 连接结果消息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "message": "连接成功"
  }
}
```

---

## 3. 目录浏览

### 3.1 列出 WebDAV 目录
#### 3.1.1 基本信息
请求路径：/api/directories

请求方式：GET

接口描述：该接口用于列出 WebDAV 目录内容

#### 3.1.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| path | string | 非必须 | 目录路径，默认为 "/" |

请求参数样例：
```
/api/directories?path=/movies
```

#### 3.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | array | 非必须 | 目录列表 |
| |- name | string | 非必须 | 目录名称 |
| |- full_path | string | 非必须 | 完整路径 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": [
    {
      "name": "movies",
      "full_path": "/movies"
    },
    {
      "name": "tv",
      "full_path": "/tv"
    }
  ]
}
```

### 3.2 用临时配置浏览远程目录
#### 3.2.1 基本信息
请求路径：/api/directories

请求方式：POST

接口描述：该接口用于使用临时配置浏览远程目录

#### 3.2.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| remote_provider | string | 非必须 | 远程源类型 |
| webdav_host | string | 非必须 | WebDAV 主机地址 |
| webdav_user | string | 非必须 | WebDAV 用户名 |
| webdav_pass | string | 非必须 | WebDAV 密码 |
| remote_cookie | string | 非必须 | 远程源 Cookie |
| path | string | 非必须 | 目录路径，默认为 "/" |

请求参数样例：
```json
{
  "remote_provider": "webdav",
  "webdav_host": "https://dav.example.com",
  "webdav_user": "user",
  "webdav_pass": "password",
  "path": "/movies"
}
```

#### 3.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | array | 非必须 | 目录列表 |
| |- name | string | 非必须 | 目录名称 |
| |- full_path | string | 非必须 | 完整路径 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": [
    {
      "name": "action",
      "full_path": "/movies/action"
    },
    {
      "name": "comedy",
      "full_path": "/movies/comedy"
    }
  ]
}
```

### 3.3 列出本地目录
#### 3.3.1 基本信息
请求路径：/api/local-directories

请求方式：GET

接口描述：该接口用于列出本地目录内容

#### 3.3.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| path | string | 非必须 | 目录路径，默认为空（根目录） |

请求参数样例：
```
/api/local-directories?path=C:\Users
```

#### 3.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | array | 非必须 | 目录列表 |
| |- name | string | 非必须 | 目录名称 |
| |- full_path | string | 非必须 | 完整路径 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": [
    {
      "name": "Desktop",
      "full_path": "C:\\Users\\user\\Desktop"
    },
    {
      "name": "Documents",
      "full_path": "C:\\Users\\user\\Documents"
    }
  ]
}
```

---

## 4. 影片库管理

### 4.1 获取影片列表
#### 4.1.1 基本信息
请求路径：/api/library

请求方式：GET

接口描述：该接口用于获取影片列表，支持按模式、来源、搜索词筛选

#### 4.1.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| mode | string | 非必须 | 模式：all/favorites/recent，默认为 "all" |
| source | string | 非必须 | 来源：remote/local/combined，默认为 "remote" |
| search | string | 非必须 | 搜索关键词 |
| force_refresh | boolean | 非必须 | 是否强制刷新，默认为 false |

请求参数样例：
```
/api/library?mode=favorites&source=remote
/api/library?search=速度&source=combined
```

#### 4.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 影片列表 |
| |- stats | object | 非必须 | 统计数据 |

影片对象参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| title | string | 非必须 | 标题 |
| name | string | 非必须 | 名称 |
| type | string | 非必须 | 类型：电影/剧集/动画/视频 |
| year | number | 非必须 | 年份 |
| intro | string | 非必须 | 简介 |
| rating | number | 非必须 | 评分 |
| duration | string | 非必须 | 时长 |
| director | string | 非必须 | 导演 |
| actors | string | 非必须 | 演员 |
| is_series | boolean | 非必须 | 是否为剧集 |
| episodes | array | 非必须 | 剧集标题列表 |
| episode_files | array | 非必须 | 剧集文件路径列表 |
| path | string | 非必须 | 文件路径 |
| cover_path | string | 非必须 | 封面本地路径 |
| cover_url | string | 非必须 | 封面 URL |
| is_favorite | boolean | 非必须 | 是否收藏 |
| episode_count | number | 非必须 | 剧集数 |
| source | string | 非必须 | 来源：remote/local |
| remote_provider | string | 非必须 | 远程源类型：webdav/openlist |
| source_label | string | 非必须 | 来源标签显示名 |
| playback | object | 非必须 | 播放进度 |
| |- progress | number | 非必须 | 播放进度（秒） |
| |- duration | number | 非必须 | 总时长（秒） |
| |- percent | number | 非必须 | 播放百分比 |
| |- timestamp | number | 非必须 | 时间戳 |
| |- has_progress | boolean | 非必须 | 是否有播放进度 |
| tags | array | 非必须 | 标签列表 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "title": "速度与激情10",
        "name": "速度与激情10",
        "type": "电影",
        "year": 2023,
        "intro": "在完成了无数任务之后...",
        "rating": 7.5,
        "duration": "141分钟",
        "director": "路易斯·莱特里尔",
        "actors": "范·迪塞尔, 米歇尔·罗德里格兹",
        "is_series": false,
        "episodes": [],
        "episode_files": [],
        "path": "/movies/速度与激情10.mp4",
        "cover_path": "data/covers/xxx.jpg",
        "cover_url": "https://image.tmdb.org/t/p/w500/xxx.jpg",
        "is_favorite": true,
        "episode_count": 0,
        "source": "remote",
        "remote_provider": "webdav",
        "source_label": "WebDAV",
        "playback": {
          "progress": 3600,
          "duration": 8460,
          "percent": 42,
          "timestamp": 1714123456,
          "has_progress": true
        },
        "tags": ["动作", "赛车"]
      }
    ],
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 8
    }
  }
}
```

### 4.2 刷新影片库
#### 4.2.1 基本信息
请求路径：/api/library/refresh

请求方式：POST

接口描述：该接口用于刷新影片库，扫描远程或本地目录并更新缓存

#### 4.2.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| source | string | 非必须 | 来源：remote/local/combined，默认为 "remote" |
| auto_scrape | boolean | 非必须 | 是否自动刮削元数据，默认为 true |

请求参数样例：
```
/api/library/refresh?source=remote&auto_scrape=true
```

#### 4.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- job_id | string | 非必须 | 异步任务 ID，用于查询任务进度 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "job_id": "abc123-def456"
  }
}
```

### 4.3 批量刮削元数据
#### 4.3.1 基本信息
请求路径：/api/library/scrape

请求方式：POST

接口描述：该接口用于批量刮削影片库的元数据

#### 4.3.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| source | string | 非必须 | 来源：remote/local/combined，默认为 "remote" |

请求参数样例：
```
/api/library/scrape?source=combined
```

#### 4.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- job_id | string | 非必须 | 异步任务 ID，用于查询任务进度 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "job_id": "xyz789-abc123"
  }
}
```

---

## 5. 影片操作

### 5.1 切换收藏状态
#### 5.1.1 基本信息
请求路径：/api/movies/favorite

请求方式：POST

接口描述：该接口用于切换影片的收藏状态

#### 5.1.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |

请求参数样例：
```json
{
  "movie_path": "/movies/速度与激情10.mp4"
}
```

#### 5.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 更新后的影片信息 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "is_favorite": true,
      "path": "/movies/速度与激情10.mp4"
    },
    "stats": {
      "total": 150,
      "favorites": 13,
      "recent": 8
    }
  }
}
```

### 5.2 获取单部影片详情
#### 5.2.1 基本信息
请求路径：/api/movies/item

请求方式：GET

接口描述：该接口用于获取单部影片的详细信息

#### 5.2.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| source | string | 非必须 | 来源：remote/local |

请求参数样例：
```
/api/movies/item?movie_path=/movies/速度与激情10.mp4&source=remote
```

#### 5.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 影片详细信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "name": "速度与激情10",
      "type": "电影",
      "year": 2023,
      "intro": "在完成了无数任务之后...",
      "rating": 7.5,
      "duration": "141分钟",
      "director": "路易斯·莱特里尔",
      "actors": "范·迪塞尔, 米歇尔·罗德里格兹",
      "is_series": false,
      "episodes": [],
      "episode_files": [],
      "path": "/movies/速度与激情10.mp4",
      "cover_path": "data/covers/xxx.jpg",
      "cover_url": "https://image.tmdb.org/t/p/w500/xxx.jpg",
      "is_favorite": true,
      "episode_count": 0,
      "source": "remote",
      "remote_provider": "webdav",
      "source_label": "WebDAV",
      "playback": {
        "progress": 3600,
        "duration": 8460,
        "percent": 42,
        "timestamp": 1714123456,
        "has_progress": true
      },
      "tags": ["动作", "赛车"]
    }
  }
}
```

### 5.3 添加到最近播放
#### 5.3.1 基本信息
请求路径：/api/movies/recent

请求方式：POST

接口描述：该接口用于将影片添加到最近播放列表

#### 5.3.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |

请求参数样例：
```json
{
  "movie_path": "/movies/速度与激情10.mp4"
}
```

#### 5.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 影片信息 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4"
    },
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 9
    }
  }
}
```

### 5.4 清空最近播放
#### 5.4.1 基本信息
请求路径：/api/movies/recent

请求方式：DELETE

接口描述：该接口用于清空最近播放列表

#### 5.4.2 请求参数
无

#### 5.4.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 0
    }
  }
}
```

### 5.5 调用外部播放器播放
#### 5.5.1 基本信息
请求路径：/api/movies/play

请求方式：POST

接口描述：该接口用于调用外部播放器播放影片

#### 5.5.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| episode_index | number | 非必须 | 剧集索引，默认为 0 |

请求参数样例：
```json
{
  "movie_path": "/tv/权力的游戏/第一季.mp4",
  "episode_index": 2
}
```

#### 5.5.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- result | object | 非必须 | 播放结果 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "result": {
      "player": "potplayer",
      "path": "C:\\Program Files\\PotPlayer\\PotPlayerMini64.exe"
    },
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 9
    }
  }
}
```

### 5.6 更新影片信息
#### 5.6.1 基本信息
请求路径：/api/movies/update

请求方式：POST

接口描述：该接口用于更新影片的自定义信息

#### 5.6.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| updates | object | 必须 | 要更新的字段 |

请求参数样例：
```json
{
  "movie_path": "/movies/速度与激情10.mp4",
  "updates": {
    "title": "速度与激情10：最终章",
    "rating": 8.0
  }
}
```

#### 5.6.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 更新后的影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10：最终章",
      "rating": 8.0,
      "path": "/movies/速度与激情10.mp4"
    }
  }
}
```

### 5.7 刮削单部影片元数据
#### 5.7.1 基本信息
请求路径：/api/movies/scrape

请求方式：POST

接口描述：该接口用于刮削单部影片的元数据

#### 5.7.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| custom_name | string | 非必须 | 自定义搜索名称 |

请求参数样例：
```json
{
  "movie_path": "/movies/未知影片.mp4",
  "custom_name": "速度与激情10"
}
```

#### 5.7.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 刮削后的影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "year": 2023,
      "rating": 7.5,
      "intro": "在完成了无数任务之后...",
      "cover_url": "https://image.tmdb.org/t/p/w500/xxx.jpg",
      "path": "/movies/未知影片.mp4"
    }
  }
}
```

### 5.8 搜索元数据候选结果
#### 5.8.1 基本信息
请求路径：/api/movies/search-candidates

请求方式：POST

接口描述：该接口用于搜索影片元数据的候选结果

#### 5.8.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| custom_name | string | 非必须 | 自定义搜索名称 |

请求参数样例：
```json
{
  "movie_path": "/movies/未知影片.mp4",
  "custom_name": "速度与激情"
}
```

#### 5.8.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 候选结果列表 |
| |- diagnostics | object | 非必须 | 诊断信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "title": "速度与激情10",
        "year": 2023,
        "rating": 7.5,
        "source": "tmdb"
      },
      {
        "title": "速度与激情9",
        "year": 2021,
        "rating": 7.0,
        "source": "tmdb"
      }
    ],
    "diagnostics": {
      "search_term": "速度与激情",
      "source": "tmdb"
    }
  }
}
```

### 5.9 应用选中的候选结果
#### 5.9.1 基本信息
请求路径：/api/movies/apply-candidate

请求方式：POST

接口描述：该接口用于应用选中的元数据候选结果

#### 5.9.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| candidate | object | 必须 | 候选结果对象 |

请求参数样例：
```json
{
  "movie_path": "/movies/未知影片.mp4",
  "candidate": {
    "title": "速度与激情10",
    "year": 2023,
    "rating": 7.5,
    "source": "tmdb"
  }
}
```

#### 5.9.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 应用后的影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "year": 2023,
      "rating": 7.5,
      "intro": "在完成了无数任务之后...",
      "cover_url": "https://image.tmdb.org/t/p/w500/xxx.jpg",
      "path": "/movies/未知影片.mp4"
    }
  }
}
```

### 5.10 选择播放器可执行文件
#### 5.10.1 基本信息
请求路径：/api/system/pick-player

请求方式：POST

接口描述：该接口用于选择播放器可执行文件

#### 5.10.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| player | string | 非必须 | 播放器类型：potplayer/vlc，默认为 "potplayer" |
| current_path | string | 非必须 | 当前路径 |

请求参数样例：
```json
{
  "player": "vlc",
  "current_path": "C:\\Program Files"
}
```

#### 5.10.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- path | string | 非必须 | 选择的可执行文件路径 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
  }
}
```

### 5.11 保存播放进度
#### 5.11.1 基本信息
请求路径：/api/movies/{movie_path}/progress

请求方式：POST

接口描述：该接口用于保存影片的播放进度

#### 5.11.2 请求参数
参数格式：application/json

路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |

请求体参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| progress | number | 必须 | 播放进度（秒） |
| duration | number | 必须 | 总时长（秒） |

请求参数样例：
```
POST /api/movies/%2Fmovies%2F速度与激情10.mp4/progress
```
```json
{
  "progress": 3600,
  "duration": 8460
}
```

#### 5.11.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- movie | object | 非必须 | 影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4",
      "playback": {
        "progress": 3600,
        "duration": 8460,
        "percent": 42,
        "timestamp": 1714123456,
        "has_progress": true
      }
    }
  }
}
```

### 5.12 获取播放进度
#### 5.12.1 基本信息
请求路径：/api/movies/{movie_path}/progress

请求方式：GET

接口描述：该接口用于获取影片的播放进度

#### 5.12.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |

请求参数样例：
```
GET /api/movies/%2Fmovies%2F速度与激情10.mp4/progress
```

#### 5.12.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- progress | number | 非必须 | 播放进度（秒） |
| |- movie | object | 非必须 | 影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "progress": 3600,
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4",
      "playback": {
        "progress": 3600,
        "duration": 8460,
        "percent": 42,
        "timestamp": 1714123456,
        "has_progress": true
      }
    }
  }
}
```

### 5.13 清除播放进度
#### 5.13.1 基本信息
请求路径：/api/movies/{movie_path}/progress

请求方式：DELETE

接口描述：该接口用于清除影片的播放进度

#### 5.13.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |

请求参数样例：
```
DELETE /api/movies/%2Fmovies%2F速度与激情10.mp4/progress
```

#### 5.13.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- movie | object | 非必须 | 影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4",
      "playback": {
        "progress": 0,
        "duration": 0,
        "percent": 0,
        "timestamp": 0,
        "has_progress": false
      }
    }
  }
}
```

---

## 6. 标签管理

### 6.1 获取所有标签及计数
#### 6.1.1 基本信息
请求路径：/api/tags

请求方式：GET

接口描述：该接口用于获取所有标签及其关联的影片数量

#### 6.1.2 请求参数
无

#### 6.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- tags | object | 非必须 | 标签和计数的映射 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "tags": {
      "动作": 25,
      "科幻": 18,
      "喜剧": 12,
      "爱情": 8
    }
  }
}
```

### 6.2 获取影片的标签
#### 6.2.1 基本信息
请求路径：/api/movies/{movie_path}/tags

请求方式：GET

接口描述：该接口用于获取指定影片的标签列表

#### 6.2.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |

请求参数样例：
```
GET /api/movies/%2Fmovies%2F速度与激情10.mp4/tags
```

#### 6.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- tags | array | 非必须 | 标签列表 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "tags": ["动作", "赛车", "范·迪塞尔"]
  }
}
```

### 6.3 为影片添加标签
#### 6.3.1 基本信息
请求路径：/api/movies/{movie_path}/tags

请求方式：POST

接口描述：该接口用于为指定影片添加标签

#### 6.3.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |

请求体参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| tag | string | 必须 | 标签名称 |

请求参数样例：
```
POST /api/movies/%2Fmovies%2F速度与激情10.mp4/tags
```
```json
{
  "tag": "动作"
}
```

#### 6.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 更新后的影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4",
      "tags": ["动作", "赛车", "范·迪塞尔"]
    }
  }
}
```

### 6.4 移除影片标签
#### 6.4.1 基本信息
请求路径：/api/movies/{movie_path}/tags/{tag}

请求方式：DELETE

接口描述：该接口用于移除指定影片的标签

#### 6.4.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径（URL 编码） |
| tag | string | 必须 | 标签名称 |

请求参数样例：
```
DELETE /api/movies/%2Fmovies%2F速度与激情10.mp4/tags/赛车
```

#### 6.4.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 更新后的影片信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "速度与激情10",
      "path": "/movies/速度与激情10.mp4",
      "tags": ["动作", "范·迪塞尔"]
    }
  }
}
```

### 6.5 按标签获取影片列表
#### 6.5.1 基本信息
请求路径：/api/tags/{tag}/movies

请求方式：GET

接口描述：该接口用于获取指定标签下的所有影片

#### 6.5.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| tag | string | 必须 | 标签名称 |

查询参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| source | string | 非必须 | 来源：remote/local/combined，默认为 "remote" |

请求参数样例：
```
GET /api/tags/动作/movies?source=combined
```

#### 6.5.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 影片列表 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "title": "速度与激情10",
        "type": "电影",
        "year": 2023,
        "tags": ["动作", "赛车"]
      },
      {
        "title": "复仇者联盟",
        "type": "电影",
        "year": 2019,
        "tags": ["动作", "科幻"]
      }
    ]
  }
}
```

---

## 7. 推荐系统

### 7.1 获取推荐面板数据
#### 7.1.1 基本信息
请求路径：/api/recommendations

请求方式：GET

接口描述：该接口用于获取推荐面板数据

#### 7.1.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| limit | number | 非必须 | 推荐数量限制，默认为 18，范围 1-48 |
| external_limit | number | 非必须 | 外部推荐数量限制，默认为 8，范围 0-24 |

请求参数样例：
```
/api/recommendations?limit=24&external_limit=12
```

#### 7.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 推荐影片列表 |
| |- external_items | array | 非必须 | 外部推荐列表 |
| |- profile | object | 非必须 | 用户偏好配置 |
| |- generated_at | string | 非必须 | 生成时间 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "title": "盗梦空间",
        "type": "电影",
        "year": 2010,
        "rating": 8.8,
        "reason": "基于您的观影历史推荐"
      }
    ],
    "external_items": [
      {
        "title": "沙丘2",
        "type": "电影",
        "year": 2024,
        "source": "tmdb"
      }
    ],
    "profile": {
      "favorite_genres": ["科幻", "动作"],
      "favorite_years": [2020, 2023]
    },
    "generated_at": "2024-05-04T10:30:00",
    "stats": {
      "total": 150,
      "favorites": 12
    }
  }
}
```

### 7.2 刷新推荐
#### 7.2.1 基本信息
请求路径：/api/recommendations/refresh

请求方式：POST

接口描述：该接口用于刷新推荐数据

#### 7.2.2 请求参数
无

#### 7.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 推荐影片列表 |
| |- external_items | array | 非必须 | 外部推荐列表 |
| |- profile | object | 非必须 | 用户偏好配置 |
| |- generated_at | string | 非必须 | 生成时间 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [...],
    "external_items": [...],
    "profile": {...},
    "generated_at": "2024-05-04T11:00:00",
    "stats": {...}
  }
}
```

### 7.3 为影片评分
#### 7.3.1 基本信息
请求路径：/api/recommendations/rate

请求方式：POST

接口描述：该接口用于为影片评分，用于优化推荐算法

#### 7.3.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| rating | number | 必须 | 评分，范围 0-5 |

请求参数样例：
```json
{
  "movie_path": "/movies/盗梦空间.mp4",
  "rating": 4.5
}
```

#### 7.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- movie | object | 非必须 | 影片信息 |
| |- rating | number | 非必须 | 评分 |
| |- profile | object | 非必须 | 更新后的用户偏好配置 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "movie": {
      "title": "盗梦空间",
      "path": "/movies/盗梦空间.mp4"
    },
    "rating": 4.5,
    "profile": {
      "favorite_genres": ["科幻", "动作"],
      "favorite_directors": ["克里斯托弗·诺兰"]
    }
  }
}
```

---

## 8. 数据报告

### 8.1 获取统计数据报告
#### 8.1.1 基本信息
请求路径：/api/report

请求方式：GET

接口描述：该接口用于获取影片库的统计数据报告

#### 8.1.2 请求参数
无

#### 8.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- overview | object | 非必须 | 概览数据 |
| |- type_distribution | object | 非必须 | 类型分布 |
| |- genre_preferences | object | 非必须 | 类型偏好 |
| |- year_distribution | object | 非必须 | 年份分布 |
| |- source_distribution | object | 非必须 | 来源分布 |
| |- completion_stats | object | 非必须 | 完成度统计 |
| |- recent_activity | object | 非必须 | 最近活动 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "overview": {
      "total_movies": 150,
      "total_series": 25,
      "total_episodes": 500,
      "total_duration": "1250小时"
    },
    "type_distribution": {
      "电影": 120,
      "剧集": 25,
      "动画": 5
    },
    "genre_preferences": {
      "动作": 45,
      "科幻": 35,
      "喜剧": 30,
      "剧情": 25
    },
    "year_distribution": {
      "2024": 15,
      "2023": 25,
      "2022": 20,
      "2021": 18
    },
    "source_distribution": {
      "remote": 120,
      "local": 30
    },
    "completion_stats": {
      "with_metadata": 140,
      "with_cover": 135,
      "with_rating": 120
    },
    "recent_activity": {
      "last_scan": "2024-05-04T10:00:00",
      "last_scrape": "2024-05-04T09:30:00",
      "recent_plays": 8
    }
  }
}
```

---

## 9. 后台任务

### 9.1 查询异步任务状态
#### 9.1.1 基本信息
请求路径：/api/jobs/{job_id}

请求方式：GET

接口描述：该接口用于查询异步任务的状态和进度

#### 9.1.2 请求参数
路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| job_id | string | 必须 | 任务 ID |

请求参数样例：
```
GET /api/jobs/abc123-def456
```

#### 9.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- job_id | string | 非必须 | 任务 ID |
| |- name | string | 非必须 | 任务名称 |
| |- status | string | 非必须 | 任务状态：queued/running/completed/failed |
| |- current | number | 非必须 | 当前进度 |
| |- total | number | 非必须 | 总进度 |
| |- message | string | 非必须 | 进度消息 |
| |- error | string | 非必须 | 错误信息 |
| |- result | object | 非必须 | 任务结果 |

任务状态流转：queued -> running -> completed/failed

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "job_id": "abc123-def456",
    "name": "refresh-remote-library",
    "status": "running",
    "current": 50,
    "total": 150,
    "message": "正在扫描 WebDAV 目录",
    "error": null,
    "result": null
  }
}
```

任务完成时的响应：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "job_id": "abc123-def456",
    "name": "refresh-remote-library",
    "status": "completed",
    "current": 150,
    "total": 150,
    "message": "扫描完成",
    "error": null,
    "result": {
      "movie_count": 150,
      "scrape": {
        "total": 150,
        "updated": 120
      },
      "source": "remote"
    }
  }
}
```

---

## 10. 缓存管理

### 10.1 清除指定源的影片缓存
#### 10.1.1 基本信息
请求路径：/api/cache/clear

请求方式：POST

接口描述：该接口用于清除指定来源的影片缓存

#### 10.1.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| source | string | 非必须 | 来源：remote/local，为空则清除所有 |

请求参数样例：
```
/api/cache/clear?source=remote
```

#### 10.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

### 10.2 清除所有缓存
#### 10.2.1 基本信息
请求路径：/api/cache/clear-all

请求方式：POST

接口描述：该接口用于清除所有缓存，包括封面和日志

#### 10.2.2 请求参数
无

#### 10.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

### 10.3 清除所有数据（重置应用）
#### 10.3.1 基本信息
请求路径：/api/data/clear-all

请求方式：POST

接口描述：该接口用于清除所有数据，重置应用到初始状态

#### 10.3.2 请求参数
无

#### 10.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

---

## 11. OpenList 网盘管理

### 11.1 获取 OpenList 运行状态
#### 11.1.1 基本信息
请求路径：/api/openlist/status

请求方式：GET

接口描述：该接口用于获取 OpenList 的运行状态

#### 11.1.2 请求参数
无

#### 11.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的状态信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "running": true,
    "pid": 12345,
    "port": 5244,
    "uptime": "2小时30分钟"
  }
}
```

### 11.2 启动 OpenList
#### 11.2.1 基本信息
请求路径：/api/openlist/start

请求方式：POST

接口描述：该接口用于启动 OpenList 服务

#### 11.2.2 请求参数
无

#### 11.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- message | string | 非必须 | 结果消息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "message": "OpenList 已启动"
  }
}
```

### 11.3 停止 OpenList
#### 11.3.1 基本信息
请求路径：/api/openlist/stop

请求方式：POST

接口描述：该接口用于停止 OpenList 服务

#### 11.3.2 请求参数
无

#### 11.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- message | string | 非必须 | 结果消息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "message": "OpenList 已停止"
  }
}
```

### 11.4 重启 OpenList
#### 11.4.1 基本信息
请求路径：/api/openlist/restart

请求方式：POST

接口描述：该接口用于重启 OpenList 服务

#### 11.4.2 请求参数
无

#### 11.4.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- message | string | 非必须 | 结果消息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "message": "OpenList 已重启"
  }
}
```

### 11.5 获取 OpenList 配置
#### 11.5.1 基本信息
请求路径：/api/openlist/config

请求方式：GET

接口描述：该接口用于获取 OpenList 配置信息

#### 11.5.2 请求参数
无

#### 11.5.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- enabled | boolean | 非必须 | 是否启用 |
| |- port | number | 非必须 | 端口号 |
| |- admin_password | string | 非必须 | 管理员密码 |
| |- auto_start | boolean | 非必须 | 是否自动启动 |
| |- binary_version | string | 非必须 | 二进制版本 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "enabled": true,
    "port": 5244,
    "admin_password": "",
    "auto_start": true,
    "binary_version": "3.25.0"
  }
}
```

### 11.6 保存 OpenList 配置
#### 11.6.1 基本信息
请求路径：/api/openlist/config

请求方式：PUT

接口描述：该接口用于保存 OpenList 配置

#### 11.6.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| enabled | boolean | 非必须 | 是否启用 |
| port | number | 非必须 | 端口号，默认为 5244 |
| admin_password | string | 非必须 | 管理员密码 |
| auto_start | boolean | 非必须 | 是否自动启动，默认为 true |

请求参数样例：
```json
{
  "enabled": true,
  "port": 5244,
  "admin_password": "newpassword",
  "auto_start": true
}
```

#### 11.6.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 更新后的配置信息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "enabled": true,
    "port": 5244,
    "admin_password": "",
    "auto_start": true,
    "binary_version": "3.25.0"
  }
}
```

### 11.7 下载 OpenList 二进制
#### 11.7.1 基本信息
请求路径：/api/openlist/download

请求方式：POST

接口描述：该接口用于下载 OpenList 二进制文件（异步任务）

#### 11.7.2 请求参数
无

#### 11.7.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- job_id | string | 非必须 | 异步任务 ID |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "job_id": "download-abc123"
  }
}
```

### 11.8 检查 OpenList 更新
#### 11.8.1 基本信息
请求路径：/api/openlist/version

请求方式：GET

接口描述：该接口用于检查 OpenList 是否有可用更新

#### 11.8.2 请求参数
无

#### 11.8.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- has_update | boolean | 非必须 | 是否有更新 |
| |- current_version | string | 非必须 | 当前版本 |
| |- latest_version | string | 非必须 | 最新版本 |
| |- binary_available | boolean | 非必须 | 二进制是否可用 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "has_update": true,
    "current_version": "3.25.0",
    "latest_version": "3.26.0",
    "binary_available": true
  }
}
```

### 11.9 重置管理员密码
#### 11.9.1 基本信息
请求路径：/api/openlist/reset-password

请求方式：POST

接口描述：该接口用于重置 OpenList 管理员密码

#### 11.9.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| password | string | 必须 | 新密码 |

请求参数样例：
```json
{
  "password": "newpassword123"
}
```

#### 11.9.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- message | string | 非必须 | 结果消息 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "message": "密码已重置"
  }
}
```

### 11.10 获取支持的存储驱动
#### 11.10.1 基本信息
请求路径：/api/openlist/drivers

请求方式：GET

接口描述：该接口用于获取 OpenList 支持的存储驱动列表

#### 11.10.2 请求参数
无

#### 11.10.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 驱动列表 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "name": "本地存储",
        "driver": "Local"
      },
      {
        "name": "阿里云盘",
        "driver": "Aliyundrive"
      },
      {
        "name": "百度网盘",
        "driver": "BaiduNetdisk"
      }
    ]
  }
}
```

### 11.11 列出存储挂载
#### 11.11.1 基本信息
请求路径：/api/openlist/storages

请求方式：GET

接口描述：该接口用于列出所有存储挂载配置

#### 11.11.2 请求参数
无

#### 11.11.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- items | array | 非必须 | 存储挂载列表 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "mount_path": "/aliyun",
        "driver": "Aliyundrive",
        "order": 0,
        "cache_expiration": 30,
        "status": "work"
      }
    ]
  }
}
```

### 11.12 浏览 OpenList 目录
#### 11.12.1 基本信息
请求路径：/api/openlist/directories

请求方式：GET

接口描述：该接口用于浏览 OpenList 目录内容

#### 11.12.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| path | string | 非必须 | 目录路径，默认为 "/" |
| recursive | boolean | 非必须 | 是否递归列出，默认为 false |

请求参数样例：
```
/api/openlist/directories?path=/aliyun/movies&recursive=false
```

#### 11.12.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | array | 非必须 | 目录列表 |
| |- name | string | 非必须 | 目录名称 |
| |- full_path | string | 非必须 | 完整路径 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": [
    {
      "name": "movies",
      "full_path": "/aliyun/movies"
    },
    {
      "name": "tv",
      "full_path": "/aliyun/tv"
    }
  ]
}
```

### 11.13 添加存储挂载
#### 11.13.1 基本信息
请求路径：/api/openlist/storages

请求方式：POST

接口描述：该接口用于添加新的存储挂载配置

#### 11.13.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| mount_path | string | 必须 | 挂载路径 |
| driver | string | 必须 | 存储驱动 |
| addition | object | 非必须 | 驱动配置 |
| order | number | 非必须 | 排序，默认为 0 |
| cache_expiration | number | 非必须 | 缓存过期时间（分钟），默认为 30 |

请求参数样例：
```json
{
  "mount_path": "/aliyun",
  "driver": "Aliyundrive",
  "addition": {
    "refresh_token": "xxx",
    "root_folder": "/"
  },
  "order": 0,
  "cache_expiration": 30
}
```

#### 11.13.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的结果 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "id": 2,
    "mount_path": "/aliyun",
    "driver": "Aliyundrive",
    "status": "work"
  }
}
```

### 11.14 更新存储挂载
#### 11.14.1 基本信息
请求路径：/api/openlist/storages

请求方式：PUT

接口描述：该接口用于更新存储挂载配置

#### 11.14.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| id | number | 必须 | 存储挂载 ID |
| mount_path | string | 非必须 | 挂载路径 |
| driver | string | 非必须 | 存储驱动 |
| addition | object | 非必须 | 驱动配置 |
| order | number | 非必须 | 排序 |
| cache_expiration | number | 非必须 | 缓存过期时间（分钟） |

请求参数样例：
```json
{
  "id": 2,
  "mount_path": "/aliyun",
  "addition": {
    "refresh_token": "new_token",
    "root_folder": "/movies"
  }
}
```

#### 11.14.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的结果 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "id": 2,
    "mount_path": "/aliyun",
    "driver": "Aliyundrive",
    "status": "work"
  }
}
```

### 11.15 删除存储挂载
#### 11.15.1 基本信息
请求路径：/api/openlist/storages

请求方式：DELETE

接口描述：该接口用于删除存储挂载配置

#### 11.15.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| storage_id | number | 必须 | 存储挂载 ID |

请求参数样例：
```
/api/openlist/storages?storage_id=2
```

#### 11.15.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的结果 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

### 11.16 启用存储挂载
#### 11.16.1 基本信息
请求路径：/api/openlist/storages/enable

请求方式：POST

接口描述：该接口用于启用存储挂载

#### 11.16.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| storage_id | number | 必须 | 存储挂载 ID |

请求参数样例：
```
/api/openlist/storages/enable?storage_id=2
```

#### 11.16.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的结果 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

### 11.17 禁用存储挂载
#### 11.17.1 基本信息
请求路径：/api/openlist/storages/disable

请求方式：POST

接口描述：该接口用于禁用存储挂载

#### 11.17.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| storage_id | number | 必须 | 存储挂载 ID |

请求参数样例：
```
/api/openlist/storages/disable?storage_id=2
```

#### 11.17.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的结果 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true
  }
}
```

---

## 12. VLC 受控播放会话

### 12.1 启动 VLC 受控播放会话
#### 12.1.1 基本信息
请求路径：/api/vlc/session/start

请求方式：POST

接口描述：该接口用于启动 VLC 受控播放会话，通过 VLC 的 RC 接口实现播放进度自动同步

#### 12.1.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| episode_index | number | 非必须 | 剧集索引，默认为 0 |

请求参数样例：
```json
{
  "movie_path": "/movies/速度与激情10.mp4",
  "episode_index": 0
}
```

#### 12.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- result | object | 非必须 | 播放结果 |
| |- stats | object | 非必须 | 统计数据 |

响应数据样例：
```json
{
  "code": 1,
  "msg": "success",
  "data": {
    "success": true,
    "result": {
      "player": "vlc",
      "path": "D:/app/VLC/vlc.exe"
    },
    "stats": {
      "total": 150,
      "favorites": 12,
      "recent": 9
    }
  }
}
```

### 12.2 获取 VLC 受控播放会话状态
#### 12.2.1 基本信息
请求路径：/api/vlc/session

请求方式：GET

接口描述：该接口用于获取当前 VLC 受控播放会话的状态信息

#### 12.2.2 请求参数
无

#### 12.2.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- result | object | 非必须 | 会话状态信息 |

### 12.3 控制 VLC 受控播放会话
#### 12.3.1 基本信息
请求路径：/api/vlc/session/command

请求方式：POST

接口描述：该接口用于向 VLC 受控播放会话发送控制指令（暂停、跳转、音量等）

#### 12.3.2 请求参数
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| action | string | 必须 | 控制动作：play/pause/seek/volume/stop 等 |
| value | string | 非必须 | 动作参数值 |

请求参数样例：
```json
{
  "action": "seek",
  "value": "3600"
}
```

#### 12.3.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |
| |- success | boolean | 非必须 | 操作是否成功 |
| |- result | object | 非必须 | 控制结果 |

### 12.4 停止 VLC 受控播放会话
#### 12.4.1 基本信息
请求路径：/api/vlc/session

请求方式：DELETE

接口描述：该接口用于停止当前 VLC 受控播放会话

#### 12.4.2 请求参数
无

#### 12.4.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 返回的数据 |

---

## 13. 播放器运行时

### 13.1 获取播放器运行时状态
#### 13.1.1 基本信息
请求路径：/api/player/runtime

请求方式：GET

接口描述：该接口用于获取播放器运行时状态信息，包括 VLC 会话状态等

#### 13.1.2 请求参数
无

#### 13.1.3 响应数据
参数格式：application/json

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| code | number | 必须 | 响应码，1 代表成功，0 代表失败 |
| msg | string | 非必须 | 提示信息 |
| data | object | 非必须 | 运行时状态信息 |

---

## 14. 流媒体代理

### 14.1 代理 M3U8 播放列表
#### 12.1.1 基本信息
请求路径：/api/stream/playlist.m3u8

请求方式：GET

接口描述：该接口用于代理 M3U8 播放列表，自动重写分片地址

#### 12.1.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| provider | string | 非必须 | 远程源类型：webdav/openlist |

请求参数样例：
```
/api/stream/playlist.m3u8?movie_path=/movies/video.mp4&provider=webdav
```

#### 12.1.3 响应数据
参数格式：application/vnd.apple.mpegurl

响应为 M3U8 播放列表文件内容

### 14.2 代理媒体文件流
#### 12.2.1 基本信息
请求路径：/api/stream/media 或 /api/stream/media/{media_name}

请求方式：GET, HEAD

接口描述：该接口用于代理媒体文件流，支持 Range 请求

#### 12.2.2 请求参数
参数格式：query

路径参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| media_name | string | 非必须 | 媒体文件名 |

查询参数：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| movie_path | string | 必须 | 影片文件路径 |
| provider | string | 非必须 | 远程源类型：webdav/openlist |

请求参数样例：
```
/api/stream/media?movie_path=/movies/video.mp4&provider=webdav
/api/stream/media/video.mp4?movie_path=/movies/video.mp4
```

#### 12.2.3 响应数据
参数格式：根据媒体类型自动设置

响应为媒体文件流，支持 Range 请求用于进度条拖动

### 14.3 代理 HLS 分片
#### 12.3.1 基本信息
请求路径：/api/stream/segment

请求方式：GET, HEAD

接口描述：该接口用于代理 HLS 分片文件

#### 12.3.2 请求参数
参数格式：query

参数说明：

| 参数名 | 类型 | 是否必须 | 备注 |
|--------|------|----------|------|
| upstream | string | 必须 | 上游分片 URL |
| provider | string | 非必须 | 远程源类型：webdav/openlist |

请求参数样例：
```
/api/stream/segment?upstream=https://example.com/segment001.ts&provider=webdav
```

#### 12.3.3 响应数据
参数格式：根据媒体类型自动设置

响应为 HLS 分片文件内容

---

## 附录

### A. 通用响应格式
所有接口的响应都遵循以下格式：
```json
{
  "code": 1,
  "msg": "success",
  "data": {...}
}
```

- `code`: 响应码，1 代表成功，0 代表失败
- `msg`: 提示信息
- `data`: 返回的数据

### B. 错误响应
当请求失败时，响应格式为：
```json
{
  "code": 0,
  "msg": "错误信息",
  "data": null
}
```

### C. 任务状态流转
异步任务的状态流转：
- `queued`: 任务已排队
- `running`: 任务正在执行
- `completed`: 任务已完成
- `failed`: 任务失败

### D. 影片来源
- `remote`: 远程来源（WebDAV 或 OpenList）
- `local`: 本地来源
- `combined`: 合并来源（远程 + 本地）

### E. 远程源类型
- `webdav`: WebDAV 协议
- `openlist`: OpenList 网盘服务

### F. URL 编码
路径参数中的特殊字符需要进行 URL 编码，例如：
- `/movies/video.mp4` -> `%2Fmovies%2Fvideo.mp4`
- 空格 -> `%20`
