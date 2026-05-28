#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 数据库集成测试脚本
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.app_config import AppConfig
from utils.sqlite_connection import get_sqlite_connection, init_sqlite_database
from utils.sqlite_initializer import init_sqlite_database as init_db, backup_sqlite_database
from utils.sqlite_dao import SQLiteVideoDAO, SQLiteFavoriteDAO, SQLiteTagDAO


def test_database_connection():
    print("=== Test Database Connection ===")
    
    try:
        conn = get_sqlite_connection()
        if init_sqlite_database():
            print("[OK] SQLite database initialized successfully")
            
            result = conn.query("SELECT 1 as test")
            if result and result[0]["test"] == 1:
                print("[OK] Database query successful")
            else:
                print("[FAIL] Database query failed")
                return False
            
            if conn.is_connected():
                print("[OK] Database connection status normal")
            else:
                print("[FAIL] Database connection status abnormal")
                return False
            
            return True
        else:
            print("[FAIL] SQLite database initialization failed")
            return False
    except Exception as e:
        print("[ERROR] Connection test exception:", str(e))
        return False


def test_database_initialization():
    print("\n=== Test Database Initialization ===")
    
    try:
        if init_db():
            print("[OK] Database initialization successful")
            return True
        else:
            print("[FAIL] Database initialization failed")
            return False
    except Exception as e:
        print("[ERROR] Initialization test exception:", str(e))
        return False


def test_dao_operations():
    print("\n=== Test DAO Operations ===")
    
    try:
        video_dao = SQLiteVideoDAO()
        
        test_video = {
            "title": "Test Video",
            "name": "test_video.mp4",
            "path": "/test/path/test_video.mp4",
            "year": 2024,
            "duration": "1:30:00",
            "director": "Test Director"
        }
        
        video_id = video_dao.insert_video(test_video)
        if video_id > 0:
            print("[OK] Insert video successful, ID:", video_id)
        else:
            print("[FAIL] Insert video failed")
            return False
        
        video = video_dao.get_video_by_path("/test/path/test_video.mp4")
        if video and video["title"] == "Test Video":
            print("[OK] Query video successful")
        else:
            print("[FAIL] Query video failed")
            return False
        
        update_result = video_dao.update_video(video_id, {"rating": 8.5})
        if update_result:
            print("[OK] Update video successful")
        else:
            print("[FAIL] Update video failed")
            return False
        
        search_result = video_dao.search_videos("Test")
        if len(search_result) > 0:
            print("[OK] Search video successful")
        else:
            print("[FAIL] Search video failed")
            return False
        
        delete_result = video_dao.delete_video(video_id)
        if delete_result:
            print("[OK] Delete video successful")
        else:
            print("[FAIL] Delete video failed")
            return False
        
        tag_dao = SQLiteTagDAO()
        tag_count = tag_dao.get_all_tags()
        print("[OK] Tag query successful, total:", len(tag_count))
        
        return True
    
    except Exception as e:
        print("[ERROR] DAO test exception:", str(e))
        return False


def test_favorite_dao():
    print("\n=== Test Favorite DAO ===")
    
    try:
        video_dao = SQLiteVideoDAO()
        favorite_dao = SQLiteFavoriteDAO()
        
        test_video = {
            "title": "Favorite Test Video",
            "path": "/test/path/favorite_test.mp4"
        }
        video_id = video_dao.insert_video(test_video)
        
        if favorite_dao.add_favorite(video_id):
            print("[OK] Add favorite successful")
        else:
            print("[FAIL] Add favorite failed")
            return False
        
        if favorite_dao.is_favorite(video_id):
            print("[OK] Check favorite status successful")
        else:
            print("[FAIL] Check favorite status failed")
            return False
        
        favorites = favorite_dao.get_all_favorites()
        if len(favorites) > 0:
            print("[OK] Get favorites list successful")
        else:
            print("[FAIL] Get favorites list failed")
            return False
        
        if favorite_dao.remove_favorite(video_id):
            print("[OK] Remove favorite successful")
        else:
            print("[FAIL] Remove favorite failed")
            return False
        
        video_dao.delete_video(video_id)
        
        return True
    
    except Exception as e:
        print("[ERROR] Favorite test exception:", str(e))
        return False


def test_backup():
    print("\n=== Test Backup Function ===")
    
    try:
        backup_path = backup_sqlite_database()
        if backup_path:
            print("[OK] Backup successful, file:", backup_path)
            return True
        else:
            print("[FAIL] Backup failed")
            return False
    except Exception as e:
        print("[ERROR] Backup test exception:", str(e))
        return False


def test_video_cache():
    print("\n=== Test Video Cache Integration ===")
    
    try:
        from utils.database import VideoCache
        
        cache = VideoCache()
        
        test_videos = [
            {
                "title": "Cache Test Video 1",
                "path": "/test/cache/video1.mp4",
                "year": 2024,
                "duration": "1:00:00"
            },
            {
                "title": "Cache Test Video 2",
                "path": "/test/cache/video2.mp4",
                "year": 2023,
                "duration": "2:00:00"
            }
        ]
        
        if cache.save_cache(test_videos):
            print("[OK] Save cache successful")
        else:
            print("[FAIL] Save cache failed")
            return False
        
        loaded_videos = cache.load_cache()
        if loaded_videos and len(loaded_videos) == 2:
            print("[OK] Load cache successful")
        else:
            print("[FAIL] Load cache failed")
            return False
        
        cache.add_favorite(test_videos[0])
        if cache.is_favorite("/test/cache/video1.mp4"):
            print("[OK] Cache favorite function normal")
        else:
            print("[FAIL] Cache favorite function abnormal")
            return False
        
        cache.save_playback_progress("/test/cache/video1.mp4", 120, 3600)
        progress = cache.get_playback_progress("/test/cache/video1.mp4")
        if progress and progress.get("progress") == 120:
            print("[OK] Playback progress save successful")
        else:
            print("[FAIL] Playback progress save failed")
            return False
        
        cache.add_movie_tag("/test/cache/video1.mp4", "test_tag")
        tags = cache.get_movie_tags("/test/cache/video1.mp4")
        if "test_tag" in tags:
            print("[OK] Tag function normal")
        else:
            print("[FAIL] Tag function abnormal")
            return False
        
        return True
    
    except Exception as e:
        print("[ERROR] Cache test exception:", str(e))
        return False


def main():
    print("=" * 60)
    print("MoviePop SQLite Embedded Database Integration Test")
    print("=" * 60)
    
    config = AppConfig()
    print("\nCurrent Configuration:")
    print("  Storage Type: SQLite (Built-in)")
    print("  Data Directory:", config.DATA_DIR)
    print("  SQLite Database File:", config.DATA_DIR / "moviepop.db")
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Database Initialization", test_database_initialization),
        ("DAO Operations", test_dao_operations),
        ("Favorite Function", test_favorite_dao),
        ("Backup Function", test_backup),
        ("Video Cache Integration", test_video_cache),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        if test_func():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print("Test Results:", passed, "passed,", failed, "failed")
    print("=" * 60)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()