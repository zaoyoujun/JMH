from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import json
import os

from utils.logger import get_logger
from utils.storage import Storage

logger = get_logger()
def _parse_duration_to_seconds(value: str) -> int:
    """Parse duration string like '01:32:00' or '45:30' to seconds."""
    if not value or value == '未知':
        return 0
    parts = str(value).strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


class BehaviorAnalyticsService:
    """观影行为分析服务 - 基于用户观影记录生成大数据分析报告"""
    
    def __init__(self, data_dir: str = "data", storage: Storage | None = None):
        self.data_dir = data_dir
        self.storage = storage or Storage()
        os.makedirs(data_dir, exist_ok=True)
        
    def _load_behavior_data(self) -> List[Dict]:
        """加载用户行为数据（包括从最近播放记录导入的数据）"""
        behaviors = []

        # 加载新的行为数据
        raw = self.storage.get_behavior_data()
        for item in raw:
            behaviors.append({
                'type': 'watch',
                'media_id': item.get('media_path', ''),
                'duration': item.get('duration', 0),
                'progress': item.get('progress', 0),
                'media_type': item.get('media_type', 'movie'),
                'genres': item.get('genres', []),
                'timestamp': item.get('timestamp', ''),
            })

        # 从最近播放记录导入历史数据
        try:
            recent_play_data = self._load_recent_play_data()
            for item in recent_play_data:
                media_id = item.get('path', '')
                if not media_id:
                    continue
                if any(b.get('media_id') == media_id for b in behaviors):
                    continue

                playback = item.get('playback', {})
                duration = playback.get('duration', 0)
                if duration == 0:
                    duration = 300

                timestamp = playback.get('timestamp')
                if timestamp:
                    import time as _time
                    timestamp = datetime.fromtimestamp(timestamp).isoformat()
                else:
                    timestamp = datetime.now().isoformat()

                genres = []
                for tag_list in [item.get('tags', []), item.get('inferred_tags', []), item.get('manual_tags', [])]:
                    if isinstance(tag_list, list):
                        genres.extend(tag_list)

                behaviors.append({
                    'type': 'watch',
                    'media_id': media_id,
                    'duration': duration,
                    'progress': playback.get('percent', 0),
                    'media_type': 'series' if item.get('is_series') else 'movie',
                    'genres': genres,
                    'timestamp': timestamp,
                })
        except Exception as e:
            logger.error(f"导入最近播放记录失败: {e}")

        return behaviors
    
    def _load_recent_play_data(self) -> List[Dict]:
        """加载最近播放记录"""
        items = self.storage.get_recent_play()
        result = []
        for item in items:
            merged = dict(item)
            movie_json_raw = item.get('movie_json', '{}')
            if isinstance(movie_json_raw, str):
                try:
                    movie_data = json.loads(movie_json_raw)
                except (json.JSONDecodeError, TypeError):
                    movie_data = {}
            elif isinstance(movie_json_raw, dict):
                movie_data = movie_json_raw
            else:
                movie_data = {}
            merged.update(movie_data)
            result.append(merged)
        return result
    
    def _save_behavior_data(self, behaviors: List[Dict]) -> None:
        """保存用户行为数据 (deprecated - Storage handles persistence)"""
        pass
    
    def _load_media_data(self) -> Dict[str, Dict]:
        """加载媒体库数据"""
        videos = self.storage.load_video_cache() or []
        result = {}
        for i, item in enumerate(videos):
            path = item.get('path', str(i))
            # Build genres from tags
            genres = []
            tags = item.get('tags', [])
            if isinstance(tags, list):
                genres.extend(tags)
            inferred = item.get('inferred_tags', [])
            if isinstance(inferred, list):
                genres.extend(inferred)
            manual = item.get('manual_tags', [])
            if isinstance(manual, list):
                genres.extend(manual)
            item_copy = dict(item)
            item_copy['id'] = path
            item_copy['genres'] = list(set(genres))
            result[path] = item_copy
        return result
    
    def record_watch_behavior(self, media_id: str, duration: int, progress: float = None, media_type: str = None, genres: List[str] = None) -> None:
        """记录观看行为数据"""
        self.storage.record_watch_behavior(media_id, duration, progress, media_type, genres)
    
    def _load_behavior_data_without_recent(self) -> List[Dict]:
        """只加载新的行为数据 (deprecated)"""
        return self.storage.get_behavior_data()
    
    def has_valid_behavior_data(self) -> bool:
        """检查是否有有效的行为数据"""
        behaviors = self._load_behavior_data()
        # 至少需要有3条观看记录且总观看时长超过5分钟才视为有效数据
        watch_behavior = [b for b in behaviors if b.get('type') == 'watch']
        total_duration = sum(b.get('duration', 0) for b in watch_behavior)
        return len(watch_behavior) >= 3 or total_duration >= 300
    
    def analyze_watch_duration_trend(self, days: int = 30) -> Dict[str, Any]:
        """分析观影时长趋势（按日期分组）"""
        behaviors = self._load_behavior_data()
        trend = defaultdict(int)
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for behavior in behaviors:
            if behavior.get('type') == 'watch':
                timestamp = behavior.get('timestamp')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        if dt >= cutoff_date:
                            date_key = dt.strftime('%Y-%m-%d')
                            duration = behavior.get('duration', 0)
                            trend[date_key] += duration
                    except:
                        pass
        
        # 填充缺失日期
        result = []
        current_date = datetime.now().date()
        for i in range(days):
            date_str = (current_date - timedelta(days=i)).strftime('%Y-%m-%d')
            result.append({
                'date': date_str,
                'duration_minutes': round(trend[date_str] / 60, 1)
            })
        
        return sorted(result, key=lambda x: x['date'])
    
    def analyze_genre_preference(self) -> List[Dict[str, Any]]:
        """分析类型偏好分布"""
        behaviors = self._load_behavior_data()
        
        genre_counts = defaultdict(int)
        genre_duration = defaultdict(int)
        
        for behavior in behaviors:
            if behavior.get('type') == 'watch':
                genres = behavior.get('genres', [])
                duration = int(behavior.get('duration', 0))
                for genre in genres:
                    genre_counts[str(genre)] += 1
                    genre_duration[str(genre)] += duration
        
        # 转换为百分比并排序
        total_count = sum(genre_counts.values()) or 1
        result = []
        for genre, count in genre_counts.items():
            result.append({
                'genre': genre,
                'count': count,
                'percentage': round((count / total_count) * 100, 1),
                'total_duration_minutes': round(genre_duration[genre] / 60, 1)
            })
        
        return sorted(result, key=lambda x: x['count'], reverse=True)[:10]
    
    def analyze_watch_time_distribution(self) -> List[Dict[str, Any]]:
        """分析观看时段分布（按小时分组）"""
        behaviors = self._load_behavior_data()
        hour_counts = defaultdict(int)
        
        for behavior in behaviors:
            if behavior.get('type') == 'watch':
                timestamp = behavior.get('timestamp')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        hour = dt.hour
                        hour_counts[hour] += 1
                    except:
                        pass
        
        result = []
        for hour in range(24):
            result.append({
                'hour': hour,
                'count': hour_counts[hour],
                'label': f"{hour:02d}:00"
            })
        
        return result
    
    def analyze_completion_rate(self) -> Dict[str, Any]:
        """分析完播率"""
        behaviors = self._load_behavior_data()
        media_data = self._load_media_data()
        
        completed = 0
        in_progress = 0
        not_started = 0
        
        for media_id, media in media_data.items():
            # 查找该影片的观看记录
            watch_records = [b for b in behaviors 
                           if b.get('type') == 'watch' and str(b.get('media_id')) == media_id]
            
            if not watch_records:
                not_started += 1
                continue
            
            # Convert duration to seconds (handles string like '01:32:00' or '未知')
            total_duration = _parse_duration_to_seconds(str(media.get('duration', '0')))
            watched_duration = sum(r.get('duration', 0) for r in watch_records)
            
            # 判断完播状态（80%以上视为完成）
            if total_duration > 0 and (watched_duration / total_duration) >= 0.8:
                completed += 1
            else:
                in_progress += 1
        
        total = completed + in_progress + not_started
        return {
            'completed': completed,
            'in_progress': in_progress,
            'not_started': not_started,
            'completion_rate': round((completed / total) * 100, 1) if total > 0 else 0
        }
    
    def analyze_user_profile(self) -> Dict[str, Any]:
        """生成用户画像"""
        behaviors = self._load_behavior_data()
        media_data = self._load_media_data()
        
        # 计算总观影时长
        total_duration = sum(b.get('duration', 0) for b in behaviors if b.get('type') == 'watch')
        
        # 分析年份偏好
        year_counts = defaultdict(int)
        for behavior in behaviors:
            if behavior.get('type') == 'watch':
                media_id = behavior.get('media_id')
                media = media_data.get(str(media_id))
                if media and media.get('year'):
                    year_counts[media['year']] += 1
        
        # 找出最活跃的观看时间
        hour_counts = defaultdict(int)
        for behavior in behaviors:
            if behavior.get('type') == 'watch':
                timestamp = behavior.get('timestamp')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        hour_counts[dt.hour] += 1
                    except:
                        pass
        
        most_active_hour = max(hour_counts, key=hour_counts.get, default=20)
        genre_pref = self.analyze_genre_preference()
        most_watched_genre = genre_pref[0]['genre'] if genre_pref else '未统计'
        completion_rate = self.analyze_completion_rate()
        
        # 生成 MBTI 类型
        mbti_code, mbti_name = self._generate_mbti_type(completion_rate['completion_rate'], most_watched_genre, most_active_hour)
        
        return {
            'total_watch_minutes': round(total_duration / 60, 1),
            'total_watch_hours': round(total_duration / 3600, 1),
            'most_watched_genre': most_watched_genre,
            'most_active_hour': most_active_hour,
            'most_active_period': self._get_period_label(most_active_hour),
            'total_movies_watched': len(set(b.get('media_id') for b in behaviors if b.get('type') == 'watch')),
            'mbti_code': mbti_code,
            'mbti_name': mbti_name,
            'preferred_decade': self._get_preferred_decade(year_counts)
        }
    
    def _get_period_label(self, hour: int) -> str:
        """根据小时返回时段标签"""
        if 6 <= hour < 9:
            return '早晨'
        elif 9 <= hour < 12:
            return '上午'
        elif 12 <= hour < 14:
            return '中午'
        elif 14 <= hour < 18:
            return '下午'
        elif 18 <= hour < 22:
            return '晚上'
        else:
            return '深夜'
    
    def _generate_mbti_type(self, completion_rate: float, genre: str, active_hour: int) -> tuple:
        """根据用户行为生成观影人格类型（类MBTI）"""
        # E/I: 外向/内向 - 根据活跃时间判断
        ei = 'E' if active_hour >= 18 or active_hour <= 2 else 'I'
        
        # S/N: 现实/幻想 - 根据类型偏好判断
        realistic_genres = ['剧情', '爱情', '家庭', '传记', '历史', '纪录片']
        fantasy_genres = ['科幻', '奇幻', '动画', '冒险', '动作', '恐怖']
        sn = 'S' if genre in realistic_genres else ('N' if genre in fantasy_genres else 'S')
        
        # F/T: 情感/理性 - 根据完播率判断
        ft = 'F' if completion_rate > 60 else 'T'
        
        # J/P: 规划/随性 - 根据活跃时间规律性判断
        jp = 'J' if 19 <= active_hour <= 22 else 'P'
        
        mbti_code = ei + sn + ft + jp
        
        # 根据MBTI类型返回人格名称
        mbti_names = {
            'ESFJ': '剧情共情家',
            'ESFP': '热情观影者',
            'ENFJ': '洞察影评人',
            'ENFP': '创意观影家',
            'ISFJ': '温情鉴赏家',
            'ISFP': '细腻感受者',
            'INFJ': '深度思考者',
            'INFP': '理想观影家',
            'ESTJ': '秩序规划者',
            'ESTP': '刺激追求者',
            'ENTJ': '策略分析家',
            'ENTP': '好奇探索者',
            'ISTJ': '严谨观察者',
            'ISTP': '技术探索者',
            'INTJ': '战略思考者',
            'INTP': '逻辑分析家'
        }
        
        return mbti_code, mbti_names.get(mbti_code, '独立探索者')
    
    def _get_preferred_decade(self, year_counts: dict) -> str:
        """根据观看记录判断偏好年代"""
        if not year_counts:
            return '未统计'
        
        most_watched_year = max(year_counts, key=year_counts.get)
        if most_watched_year < 1990:
            return '80'
        elif 1990 <= most_watched_year < 2000:
            return '90'
        elif 2000 <= most_watched_year < 2010:
            return '00'
        elif 2010 <= most_watched_year < 2020:
            return '10'
        else:
            return '20'
    
    def generate_full_report(self) -> Dict[str, Any]:
        """生成完整的行为分析报告"""
        return {
            'generated_at': datetime.now().isoformat(),
            'user_profile': self.analyze_user_profile(),
            'watch_duration_trend': self.analyze_watch_duration_trend(),
            'genre_preference': self.analyze_genre_preference(),
            'time_distribution': self.analyze_watch_time_distribution(),
            'completion_rate': self.analyze_completion_rate()
        }
