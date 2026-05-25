let allPlaybackProgress = {};

async function loadAllPlaybackProgress() {
  try {
    const payload = await api("/api/movies/all-progress");
    if (payload?.success && payload.progress) {
      allPlaybackProgress = payload.progress;
    }
  } catch (e) {
    console.log("加载所有播放进度失败:", e);
  }
}

function getWatchedEpisodeCount(movie) {
  if (!movie?.is_series) return 0;
  
  let watchedCount = 0;
  const seasons = Array.isArray(movie.seasons) ? movie.seasons : [movie];
  
  for (const season of seasons) {
    const episodeFiles = Array.isArray(season.episode_files) ? season.episode_files : [];
    
    for (const episodePath of episodeFiles) {
      const progressData = allPlaybackProgress[episodePath];
      if (progressData && progressData.progress && progressData.duration) {
        const percent = (progressData.progress / progressData.duration) * 100;
        if (percent >= 90) {
          watchedCount++;
        }
      }
    }
  }
  
  return watchedCount;
}

function getSeriesAverageProgress(movie) {
  if (!movie?.is_series) return 0;
  
  let totalProgress = 0;
  let episodeCount = 0;
  
  const seasons = Array.isArray(movie.seasons) ? movie.seasons : [movie];
  
  for (const season of seasons) {
    const episodeFiles = Array.isArray(season.episode_files) ? season.episode_files : [];
    
    for (const episodePath of episodeFiles) {
      const progressData = allPlaybackProgress[episodePath];
      if (progressData && progressData.progress && progressData.duration) {
        const percent = (progressData.progress / progressData.duration) * 100;
        totalProgress += percent;
        episodeCount++;
      }
    }
  }
  
  return episodeCount > 0 ? totalProgress / episodeCount : 0;
}

function formatPlaybackText(playback, movie = null) {
  if (!playback?.has_progress) return "";
  
  if (movie?.is_series) {
    const avgProgress = getSeriesAverageProgress(movie);
    if (avgProgress >= 90) {
      return "已看完";
    }
  }
  
  const percent = Number(playback.percent || 0);
  if (percent <= 0 && Number(playback.progress || 0) > 0) {
    return `${"看到"} ${formatDuration(playback.progress)}`;
  }
  return `${"已观看"} ${percent}%`;
}

function formatEpisodeLabel(index) {
  const episodeNumber = Number(index || 0) + 1;
  if (!Number.isFinite(episodeNumber) || episodeNumber <= 0) return "";
  return `第 ${episodeNumber} 集`;
}

function formatResumeEpisodeHint(movie) {
  if (!movie?.is_series) return "";
  const episodeIndex = getResumeEpisodeIndex(movie);
  return formatEpisodeLabel(episodeIndex);
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remain = total % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(remain).padStart(2, "0")}`;
  return `${minutes}:${String(remain).padStart(2, "0")}`;
}

function formatResumeHint(movie) {
  if (!movie?.playback?.has_progress) return "";
  const parts = [];
  if (movie.resume_season_label) parts.push(movie.resume_season_label);
  const episodeLabel = formatResumeEpisodeHint(movie);
  if (episodeLabel) parts.push(episodeLabel);
  parts.push(formatPlaybackText(movie.playback, movie));
  return parts.filter(Boolean).join(" · ");
}

function getResumeEpisodeIndex(movie) {
  return Math.max(0, Number(movie?.resume_episode_index ?? movie?.playback?.episode_index ?? 0) || 0);
}

function isSelectedEpisodeResumeTarget(movie, selectedEpisode) {
  if (!movie?.playback?.has_progress) return false;
  if (!movie?.is_series) return true;
  return getResumeEpisodeIndex(movie) === Math.max(0, Number(selectedEpisode || 0));
}


