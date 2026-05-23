#!/usr/bin/env python3
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.filename_parser import parse_video_filename, _path_parts, _detect_season, _detect_special_type, _detect_part, _pick_title_candidate

# 测试目录结构
test_cases = [
    # 第一季
    "/quark/动漫/石纪元/S1/石纪元.S01E01.mkv",
    # 第二季 Stone Wars
    "/quark/动漫/石纪元/石纪元 Stone Wars/石纪元.S02E01.mkv",
    # 第三季 NEW WORLD（上）
    "/quark/动漫/石纪元/石纪元 NEW WORLD/石纪元.S03E01.mkv",
    # 第三季 NEW WORLD（下）- Part.2
    "/quark/动漫/石纪元/石纪元 NEW WORLD Part.2/石纪元.S03E12.mkv",
    # 第四季 科学与未来
    "/quark/动漫/石纪元/石纪元 科学与未来/石纪元.S04E01.mkv",
    # 第四季 科学与未来 #2
    "/quark/动漫/石纪元/石纪元 科学与未来 #2/石纪元.S04E13.mkv",
    # 第四季 科学与未来 #3
    "/quark/动漫/石纪元/石纪元 科学与未来 #3/石纪元.S04E25.mkv",
    # 龙水篇
    "/quark/动漫/石纪元/石纪元 龙水篇/石纪元.龙水篇.mkv",
]

print("测试文件名解析结果：")
print("=" * 80)

for test_path in test_cases:
    parts = _path_parts(test_path)
    filename = parts[-1] if parts else os.path.basename(test_path)
    name, ext = os.path.splitext(filename)
    
    print(f"\n路径: {test_path}")
    print(f"  parts: {parts}")
    print(f"  filename: {filename}")
    print(f"  name: {name}")
    
    # 检测季数
    season, season_alias = _detect_season(name, *(parts[-4:]))
    print(f"  _detect_season result: season={season}, season_alias={season_alias}")
    
    # 检测特殊类型
    special_type = _detect_special_type(name, *(parts[-4:]))
    print(f"  _detect_special_type result: {special_type}")
    
    # 检测部分编号
    part_number = _detect_part(name, *(parts[-4:]))
    print(f"  _detect_part result: {part_number}")
    
    # 提取标题候选
    title, folder_season_title = _pick_title_candidate(parts[:-1], name, season, special_type)
    print(f"  _pick_title_candidate result: title={repr(title)}, folder_season_title={repr(folder_season_title)}")
    
    # 检查 title 是否为空
    if not title:
        print("  WARNING: title is empty after _pick_title_candidate!")
    
    # 测试 _clean_text 对 title 的影响
    from utils.filename_parser import _clean_text
    cleaned_title = _clean_text(title)
    print(f"  _clean_text(title) result: {repr(cleaned_title)}")
    
    result = parse_video_filename(test_path)
    print(f"\n  最终结果:")
    print(f"    title: {result.get('title', '')}")
    print(f"    season: {result.get('season', '')}")
    print(f"    season_title: {result.get('season_title', '')}")
    print(f"    special_type: {result.get('special_type', '')}")
    print(f"    part: {result.get('part', '')}")
    print(f"    series_group: {result.get('series_group', '')}")
    print(f"    search_name: {result.get('search_name', '')}")