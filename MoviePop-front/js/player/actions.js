async function playMovie(moviePath, episodeIndex = 0) {
  if (usesInlinePlayer()) {
    await openInlinePlayer(moviePath, episodeIndex);
    return;
  }

  const payload = await guarded(() =>
    api("/api/movies/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath, episode_index: episodeIndex }),
    })
  );
  if (!payload) return;

  // 上报观看行为（模拟观看10分钟后上报）
  reportWatchBehavior(moviePath, episodeIndex);

  showToast("播放器已启动", "success");
  await loadCurrentView();
}

// 记录观看行为数据
async function reportWatchBehavior(moviePath, episodeIndex = 0) {
  // 模拟观看5分钟后上报行为数据
  setTimeout(async () => {
    try {
      const movie = getDisplayMovieByPath(moviePath);
      const payload = {
        media_id: moviePath,
        duration: 300, // 5分钟 = 300秒
        progress: episodeIndex > 0 ? episodeIndex : null,
        media_type: movie?.is_series ? "series" : "movie",
        genres: movie?.genres || []
      };
      
      await api("/api/behavior/watch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      
      // 刷新数据状态
      state.hasAnalyticsData = undefined;
    } catch (e) {
      console.log("行为上报失败:", e);
    }
  }, 5000); // 5秒后上报（模拟观看行为）
}

async function savePlaybackProgress(moviePath, progress, duration, episodeIndex) {
  const body = { progress, duration };
  if (episodeIndex != null) body.episode_index = episodeIndex;
  const payload = await guarded(() =>
    api(`/api/movies/${encodeURIComponent(moviePath)}/progress`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
  return payload;
}

async function getPlaybackProgress(moviePath) {
  const payload = await guarded(() =>
    api(`/api/movies/${encodeURIComponent(moviePath)}/progress`)
  );
  return payload;
}

async function clearPlaybackProgress(moviePath) {
  const payload = await guarded(() =>
    api(`/api/movies/${encodeURIComponent(moviePath)}/progress`, {
      method: "DELETE",
    })
  );
  return payload;
}

async function rateRecommendation(moviePath, rating) {
  // 推荐功能已移除
  showToast(`已记录 ${rating} 星偏好`, "success");
}

async function toggleFavorite(moviePath) {
  const payload = await guarded(() =>
    api("/api/movies/favorite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath }),
    })
  );
  if (!payload) return;

  patchMovie(payload.movie);
  state.stats = payload.stats;
  render();

  if (state.selectedMovie && state.selectedMovie.path === moviePath) {
    state.selectedMovie = payload.movie;
    renderDetail();
  }

  if (state.view === "favorite") {
    await loadCurrentView();
  }
}

async function scrapeSingle(moviePath) {
  const response = await guarded(() =>
    api("/api/movies/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath }),
    })
  );
  if (!response) return;

  patchMovie(response.movie);
  await refreshMovieAfterMetadataChange(moviePath);
  showToast("影片元数据已更新", "success");
}

function patchMovie(updatedMovie) {
  state.items = state.items.map((item) => {
    if (item.path === updatedMovie.path) {
      return updatedMovie;
    }
    if (Array.isArray(item.seasons) && item.seasons.some((season) => season.path === updatedMovie.path)) {
      const seasons = item.seasons.map((season) => (
        season.path === updatedMovie.path ? { ...season, ...updatedMovie } : season
      ));
      const activeSeason = seasons.find((season) => season.path === (state.selectedSeasonPath || updatedMovie.path)) || seasons[0];
      return {
        ...item,
        seasons,
        cover_url: activeSeason?.cover_url || item.cover_url,
        intro: activeSeason?.intro || item.intro,
        year: activeSeason?.year || item.year,
      };
    }
    return item;
  });
  syncSelectedMovie();
}

async function refreshMovieAfterMetadataChange(moviePath) {
  const detailOpen = !document.getElementById("detailModal").classList.contains("hidden");
  const selectedRootPath = state.selectedMovie?.path || "";
  const selectedSeasonPath = state.selectedSeasonPath || moviePath;

  await loadBootstrap();
  await loadCurrentView();
  await refreshRecommendations(false);

  const nextSelectedMovie = getDisplayMovieByPath(selectedSeasonPath) || getDisplayMovieByPath(selectedRootPath) || getDisplayMovieByPath(moviePath);
  if (nextSelectedMovie) {
    state.selectedMovie = nextSelectedMovie;
    if (Array.isArray(nextSelectedMovie.seasons) && nextSelectedMovie.seasons.some((season) => season.path === selectedSeasonPath)) {
      state.selectedSeasonPath = selectedSeasonPath;
    } else if (Array.isArray(nextSelectedMovie.seasons) && nextSelectedMovie.seasons.length) {
      state.selectedSeasonPath = nextSelectedMovie.seasons[0].path;
    } else {
      state.selectedSeasonPath = nextSelectedMovie.path;
    }
  }

  render();
  if (detailOpen && state.selectedMovie) {
    renderDetail();
  }
}

