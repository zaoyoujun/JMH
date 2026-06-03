#!/usr/bin/env python3
"""
SQLite存储系统测试脚本
验证所有核心功能是否正常工作
"""

import os
import sys
import tempfile
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.sqlite_storage import (
    SQLiteStorage,
    VideoDAO,
    FavoriteDAO,
    PlaybackDAO,
    TagDAO,
    RecentPlayDAO,
    ConfigDAO,
    FeedbackDAO,
    ProfileDAO,
    RecommendationDAO
)


def test_database_init():
    """测试数据库初始化"""
    print("=== 测试数据库初始化 ===")
    storage = SQLiteStorage()
    print(f"数据库路径: {storage.db_path}")
    print(f"数据库大小: {storage.get_db_size()} bytes")
    print("数据库初始化成功")
    return True


def test_video_dao():
    """测试视频数据访问"""
    print("\n=== 测试视频数据访问 ===")
    storage = SQLiteStorage()
    dao = VideoDAO(storage)
    
    # 测试插入
    video_data = {
        'path': '/movies/test.mp4',
        'title': '测试电影',
        'name': 'test.mp4',
        'type': '电影',
        'year': 2024,
        'duration': '120分钟',
        'director': '导演A',
        'actors': '演员A, 演员B',
        'intro': '这是一部测试电影',
        'is_series': 0,
        'rating': 8.5
    }
    
    row_id = dao.insert_video(video_data)
    print(f"插入视频成功，ID: {row_id}")
    
    # 测试查询
    video = dao.get_video_by_path('/movies/test.mp4')
    assert video is not None, "查询视频失败"
    assert video['title'] == '测试电影', "视频标题不正确"
    print("查询视频成功")
    
    # 测试搜索
    results = dao.search_videos('测试')
    assert len(results) > 0, "搜索失败"
    print(f"搜索成功，找到 {len(results)} 条结果")
    
    # 测试更新
    updated = dao.update_video('/movies/test.mp4', {'rating': 9.0})
    assert updated, "更新失败"
    video = dao.get_video_by_path('/movies/test.mp4')
    assert video['rating'] == 9.0, "更新后评分不正确"
    print("更新视频成功")
    
    # 测试删除
    deleted = dao.delete_video('/movies/test.mp4')
    assert deleted, "删除失败"
    video = dao.get_video_by_path('/movies/test.mp4')
    assert video is None, "删除后仍能查询到"
    print("删除视频成功")
    
    return True


def test_favorite_dao():
    """测试收藏数据访问"""
    print("\n=== 测试收藏数据访问 ===")
    storage = SQLiteStorage()
    dao = VideoDAO(storage)
    fav_dao = FavoriteDAO(storage)
    
    # 先插入测试视频
    video_data = {
        'path': '/movies/favorite.mp4',
        'title': '收藏测试',
        'name': 'favorite.mp4',
        'type': '电影',
        'year': 2024
    }
    dao.insert_video(video_data)
    
    # 测试添加收藏
    added = fav_dao.add_favorite('/movies/favorite.mp4')
    assert added, "添加收藏失败"
    
    # 测试检查收藏状态
    is_fav = fav_dao.is_favorite('/movies/favorite.mp4')
    assert is_fav, "检查收藏状态失败"
    print("添加收藏成功")
    
    # 测试获取收藏列表
    favorites = fav_dao.get_favorites()
    assert len(favorites) > 0, "获取收藏列表失败"
    print(f"获取收藏列表成功，共 {len(favorites)} 条")
    
    # 测试移除收藏
    removed = fav_dao.remove_favorite('/movies/favorite.mp4')
    assert removed, "移除收藏失败"
    
    is_fav = fav_dao.is_favorite('/movies/favorite.mp4')
    assert not is_fav, "移除后仍显示为收藏"
    print("移除收藏成功")
    
    # 清理
    dao.delete_video('/movies/favorite.mp4')
    
    return True


def test_playback_dao():
    """测试播放进度数据访问"""
    print("\n=== 测试播放进度数据访问 ===")
    storage = SQLiteStorage()
    dao = VideoDAO(storage)
    pb_dao = PlaybackDAO(storage)
    
    # 先插入测试视频
    video_data = {
        'path': '/movies/playback.mp4',
        'title': '播放进度测试',
        'name': 'playback.mp4',
        'type': '电影',
        'year': 2024
    }
    dao.insert_video(video_data)
    
    # 测试保存进度
    saved = pb_dao.save_progress('/movies/playback.mp4', 120.5, 600.0, 0)
    assert saved, "保存进度失败"
    print("保存播放进度成功")
    
    # 测试获取进度
    progress = pb_dao.get_progress('/movies/playback.mp4')
    assert progress is not None, "获取进度失败"
    assert abs(progress['progress'] - 120.5) < 0.01, "进度值不正确"
    print("获取播放进度成功")
    
    # 测试获取所有进度
    all_progress = pb_dao.get_all_progress()
    assert '/movies/playback.mp4' in [p['video_path'] for p in all_progress], "获取所有进度失败"
    print("获取所有播放进度成功")
    
    # 测试清除进度
    cleared = pb_dao.clear_progress('/movies/playback.mp4')
    assert cleared, "清除进度失败"
    progress = pb_dao.get_progress('/movies/playback.mp4')
    assert progress is None, "清除后仍有进度"
    print("清除播放进度成功")
    
    # 清理
    dao.delete_video('/movies/playback.mp4')
    
    return True


def test_tag_dao():
    """测试标签数据访问"""
    print("\n=== 测试标签数据访问 ===")
    storage = SQLiteStorage()
    dao = VideoDAO(storage)
    tag_dao = TagDAO(storage)
    
    # 先插入测试视频
    video_data = {
        'path': '/movies/tag.mp4',
        'title': '标签测试',
        'name': 'tag.mp4',
        'type': '电影',
        'year': 2024
    }
    dao.insert_video(video_data)
    
    # 测试创建标签
    created = tag_dao.create_tag('动作', '#ff0000')
    assert created, "创建标签失败"
    print("创建标签成功")
    
    # 测试添加视频标签
    added = tag_dao.add_video_tag('/movies/tag.mp4', '动作', 0.8)
    assert added, "添加视频标签失败"
    print("添加视频标签成功")
    
    # 测试获取视频标签
    tags = tag_dao.get_video_tags('/movies/tag.mp4')
    assert '动作' in tags, "获取视频标签失败"
    print(f"获取视频标签成功: {tags}")
    
    # 测试获取所有标签
    all_tags = tag_dao.get_all_tags()
    assert len(all_tags) > 0, "获取所有标签失败"
    print(f"获取所有标签成功，共 {len(all_tags)} 个")
    
    # 测试获取具有标签的视频
    movies = tag_dao.get_movies_by_tag('动作')
    assert len(movies) > 0, "获取标签视频失败"
    print(f"获取标签视频成功，共 {len(movies)} 部")
    
    # 测试移除视频标签
    removed = tag_dao.remove_video_tag('/movies/tag.mp4', '动作')
    assert removed, "移除视频标签失败"
    tags = tag_dao.get_video_tags('/movies/tag.mp4')
    assert '动作' not in tags, "移除后仍有标签"
    print("移除视频标签成功")
    
    # 清理
    dao.delete_video('/movies/tag.mp4')
    
    return True


def test_recent_play_dao():
    """测试最近播放数据访问"""
    print("\n=== 测试最近播放数据访问 ===")
    storage = SQLiteStorage()
    dao = VideoDAO(storage)
    rp_dao = RecentPlayDAO(storage)
    
    # 先插入测试视频
    video_data = {
        'path': '/movies/recent.mp4',
        'title': '最近播放测试',
        'name': 'recent.mp4',
        'type': '电影',
        'year': 2024
    }
    dao.insert_video(video_data)
    
    # 测试添加最近播放
    added = rp_dao.add_recent_play('/movies/recent.mp4')
    assert added, "添加最近播放失败"
    print("添加最近播放成功")
    
    # 测试获取最近播放
    recent = rp_dao.get_recent_play(limit=10)
    assert len(recent) > 0, "获取最近播放失败"
    print(f"获取最近播放成功，共 {len(recent)} 条")
    
    # 测试清除最近播放
    cleared = rp_dao.clear_recent_play()
    assert cleared, "清除最近播放失败"
    recent = rp_dao.get_recent_play()
    assert len(recent) == 0, "清除后仍有记录"
    print("清除最近播放成功")
    
    # 清理
    dao.delete_video('/movies/recent.mp4')
    
    return True


def test_config_dao():
    """测试配置数据访问"""
    print("\n=== 测试配置数据访问 ===")
    storage = SQLiteStorage()
    dao = ConfigDAO(storage)
    
    # 测试设置配置
    saved = dao.set_config('test_key', 'test_value')
    assert saved, "设置配置失败"
    
    # 测试设置复杂配置
    saved = dao.set_config('test_dict', {'name': 'test', 'value': 123})
    assert saved, "设置复杂配置失败"
    print("设置配置成功")
    
    # 测试获取配置
    value = dao.get_config('test_key')
    assert value == 'test_value', "获取配置失败"
    
    # 测试获取复杂配置
    value = dao.get_config('test_dict')
    assert isinstance(value, dict), "获取复杂配置失败"
    assert value['name'] == 'test', "复杂配置值不正确"
    print("获取配置成功")
    
    # 测试获取不存在的配置
    value = dao.get_config('nonexistent', 'default')
    assert value == 'default', "默认值不正确"
    print("获取不存在的配置成功")
    
    # 测试获取所有配置
    configs = dao.get_all_configs()
    assert 'test_key' in configs, "获取所有配置失败"
    print(f"获取所有配置成功，共 {len(configs)} 项")
    
    # 测试删除配置
    deleted = dao.delete_config('test_key')
    assert deleted, "删除配置失败"
    value = dao.get_config('test_key')
    assert value is None, "删除后仍存在"
    print("删除配置成功")
    
    # 清理
    dao.delete_config('test_dict')
    
    return True


def test_feedback_dao():
    """测试反馈数据访问"""
    print("\n=== 测试反馈数据访问 ===")
    storage = SQLiteStorage()
    dao = FeedbackDAO(storage)
    
    # 测试插入反馈
    saved = dao.upsert_feedback('/movies/feedback.mp4', rating=8.0, watch_count=3, last_watched=int(time.time()))
    assert saved, "插入反馈失败"
    print("插入反馈成功")
    
    # 测试更新反馈
    saved = dao.upsert_feedback('/movies/feedback.mp4', watch_count=4)
    assert saved, "更新反馈失败"
    print("更新反馈成功")
    
    # 测试获取反馈
    feedback_map = dao.get_feedback_map()
    assert '/movies/feedback.mp4' in feedback_map, "获取反馈失败"
    assert feedback_map['/movies/feedback.mp4']['watch_count'] == 4, "反馈值不正确"
    print(f"获取反馈成功: {feedback_map}")
    
    return True


def test_profile_dao():
    """测试用户画像数据访问"""
    print("\n=== 测试用户画像数据访问 ===")
    storage = SQLiteStorage()
    dao = ProfileDAO(storage)
    
    # 测试保存画像
    profile = {
        'preferences': {'genre': '动作', 'year': 2020},
        'history': ['movie1', 'movie2'],
        'stats': {'watched': 100, 'favorites': 20}
    }
    saved = dao.save_profile(profile)
    assert saved, "保存画像失败"
    print("保存用户画像成功")
    
    # 测试加载画像
    loaded = dao.load_profile()
    assert 'preferences' in loaded, "加载画像失败"
    assert loaded['preferences']['genre'] == '动作', "画像值不正确"
    print(f"加载用户画像成功: {loaded}")
    
    return True


def test_recommendation_dao():
    """测试推荐数据访问"""
    print("\n=== 测试推荐数据访问 ===")
    storage = SQLiteStorage()
    dao = RecommendationDAO(storage)
    
    # 测试保存推荐
    recommendations = [
        {'path': '/movie1.mp4', 'score': 0.9},
        {'path': '/movie2.mp4', 'score': 0.8},
        {'path': '/movie3.mp4', 'score': 0.7}
    ]
    saved = dao.save_recommendations(recommendations)
    assert saved, "保存推荐失败"
    print("保存推荐成功")
    
    # 测试加载推荐
    loaded = dao.load_recommendations(limit=2)
    assert len(loaded['items']) == 2, "加载推荐失败"
    print(f"加载推荐成功: {loaded}")
    
    # 测试保存外部推荐
    external = [{'path': '/ext1.mp4', 'source': 'external'}]
    saved = dao.save_external_recommendations(external)
    assert saved, "保存外部推荐失败"
    print("保存外部推荐成功")
    
    # 测试加载外部推荐
    loaded = dao.load_external_recommendations()
    assert len(loaded['items']) == 1, "加载外部推荐失败"
    print(f"加载外部推荐成功: {loaded}")
    
    return True


def test_backup_restore():
    """测试备份与恢复功能"""
    print("\n=== 测试备份与恢复功能 ===")
    storage = SQLiteStorage()
    video_dao = VideoDAO(storage)
    
    # 先插入测试数据
    video_data = {
        'path': '/movies/backup_test.mp4',
        'title': '备份测试',
        'name': 'backup_test.mp4',
        'type': '电影',
        'year': 2024
    }
    video_dao.insert_video(video_data)
    
    # 确保数据写入磁盘（关闭所有连接）
    with storage._pool_lock:
        while storage._connection_pool:
            conn = storage._connection_pool.pop()
            conn.close()
    
    # 测试备份
    with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as f:
        backup_path = f.name
    
    backup_path = storage.backup(backup_path)
    assert os.path.exists(backup_path), "备份文件不存在"
    print(f"备份成功，路径: {backup_path}")
    
    # 重新获取连接并清除数据库
    storage.execute("DELETE FROM videos")
    count = storage.get_table_count('videos')
    assert count == 0, "清除失败"
    
    # 测试恢复
    restored = storage.restore(backup_path)
    assert restored, "恢复失败"
    
    # 验证恢复的数据
    video = video_dao.get_video_by_path('/movies/backup_test.mp4')
    assert video is not None, "恢复的数据不正确"
    assert video['title'] == '备份测试', "恢复的数据不正确"
    print("恢复成功")
    
    # 清理
    os.unlink(backup_path)
    
    return True


def test_transaction():
    """测试事务功能"""
    print("\n=== 测试事务功能 ===")
    storage = SQLiteStorage()
    video_dao = VideoDAO(storage)
    
    @storage.transaction
    def test_trans(conn):
        # 在事务中插入两条记录
        conn.execute(
            "INSERT INTO videos (path, title, name, type, year) VALUES (?, ?, ?, ?, ?)",
            ('/movies/tx1.mp4', '事务测试1', 'tx1.mp4', '电影', 2024)
        )
        conn.execute(
            "INSERT INTO videos (path, title, name, type, year) VALUES (?, ?, ?, ?, ?)",
            ('/movies/tx2.mp4', '事务测试2', 'tx2.mp4', '电影', 2024)
        )
        return True
    
    result = test_trans()
    assert result, "事务执行失败"
    
    # 验证数据
    count = storage.get_table_count('videos')
    assert count >= 2, "事务未正确提交"
    print("事务测试成功")
    
    # 清理
    storage.execute("DELETE FROM videos WHERE path LIKE '/movies/tx%'")
    
    return True


def test_concurrent_access():
    """测试并发访问"""
    print("\n=== 测试并发访问 ===")
    import threading
    
    storage = SQLiteStorage()
    success_count = [0]
    error_count = [0]
    
    def insert_video(i):
        try:
            video_dao = VideoDAO(storage)
            video_data = {
                'path': f'/movies/concurrency_{i}.mp4',
                'title': f'并发测试{i}',
                'name': f'concurrency_{i}.mp4',
                'type': '电影',
                'year': 2024
            }
            video_dao.insert_video(video_data)
            success_count[0] += 1
        except Exception as e:
            error_count[0] += 1
            print(f"线程 {i} 错误: {e}")
    
    # 创建多个线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=insert_video, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    print(f"并发测试完成: 成功 {success_count[0]} 次, 失败 {error_count[0]} 次")
    assert error_count[0] == 0, "并发访问出现错误"
    
    # 清理
    storage.execute("DELETE FROM videos WHERE path LIKE '/movies/concurrency_%'")
    
    return True


def test_optimization():
    """测试数据库优化功能"""
    print("\n=== 测试数据库优化功能 ===")
    storage = SQLiteStorage()
    
    # 测试VACUUM
    storage.vacuum()
    print("VACUUM操作成功")
    
    # 测试获取表记录数
    count = storage.get_table_count('videos')
    print(f"视频表记录数: {count}")
    
    return True


def main():
    """运行所有测试"""
    print("="*60)
    print("SQLite存储系统功能测试")
    print("="*60)
    
    tests = [
        test_database_init,
        test_video_dao,
        test_favorite_dao,
        test_playback_dao,
        test_tag_dao,
        test_recent_play_dao,
        test_config_dao,
        test_feedback_dao,
        test_profile_dao,
        test_recommendation_dao,
        test_backup_restore,
        test_transaction,
        test_concurrent_access,
        test_optimization
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
                print("\n[OK] %s 测试通过" % test.__name__)
        except Exception as e:
            failed += 1
            print("\n[FAIL] %s 测试失败: %s" % (test.__name__, e))
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("="*60)
    
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)