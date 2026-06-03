async function openDetail(movie) {
  state.selectedMovie = movie;
  state.selectedSeasonPath = movie.resume_path || (Array.isArray(movie.seasons) && movie.seasons.length ? movie.seasons[0].path : movie.path);
  const activeSeason = (Array.isArray(movie.seasons) ? movie.seasons.find((item) => item.path === state.selectedSeasonPath) : null) || movie;
  state.selectedEpisode = getResumeEpisodeIndex(activeSeason);
  renderDetail();
  openModal("detailModal");
}

function renderDetail() {
  const movie = state.selectedMovie;
  if (!movie) return;
  const currentSeason = getActiveSeasonEntry(movie) || movie;
  const episodeCount = Number(currentSeason.episode_count || currentSeason.episode_files?.length || currentSeason.episodes?.length || 0);
  if (episodeCount > 0) {
    state.selectedEpisode = Math.max(0, Math.min(episodeCount - 1, Number(state.selectedEpisode || 0)));
  } else {
    state.selectedEpisode = 0;
  }
  const currentTitle = movie.is_series ? getSeriesDisplayTitle(movie) : (currentSeason.title || currentSeason.name || movie.title || movie.name || "未命名");
  const title = escapeHtml(currentTitle);
  const seasonLabel = getSeasonEntryLabel(currentSeason, movie, (Array.isArray(movie.seasons) ? movie.seasons.indexOf(currentSeason) : 0));
  const cover = currentSeason.cover_url || movie.cover_url || "";
  const progressPercent = Number(currentSeason.playback?.percent || 0);
  const meta = [
    currentSeason.type || movie.type || "视频",
    currentSeason.is_series ? `${currentSeason.episode_count || currentSeason.episode_files?.length || 0} ${"集"}` : movie.is_series ? `${movie.season_count > 1 ? `${movie.season_count} ${"季"} / ` : ""}${movie.episode_count} ${"集"}` : "单片",
    currentSeason.year || movie.year || "年份未知",
    currentSeason.source_label || movie.source_label || "媒体库",
  ]
    .filter(Boolean)
    .map((item) => `<span>${escapeHtml(String(item))}</span>`)
    .join("");
  const seasons = Array.isArray(movie.seasons) && movie.seasons.length ? movie.seasons : [movie];
  const isResumeTarget = isSelectedEpisodeResumeTarget(currentSeason, state.selectedEpisode);
  const playbackText = isResumeTarget ? formatPlaybackText(currentSeason.playback, movie) : "";
  const seriesResumeHint = movie.is_series ? formatResumeHint(movie) : "";
  const selectedEpisodeLabel = currentSeason.is_series ? formatEpisodeLabel(state.selectedEpisode) : "";
  const seasonPicker = movie.is_series && seasons.length > 1
    ? `
      <label class="detail-season-picker">
        <span>${"季别"}</span>
        <select id="detailSeasonSelect">
          ${seasons.map((item, index) => `
            <option value="${escapeAttr(item.path)}" ${item.path === currentSeason.path ? "selected" : ""}>
              ${escapeHtml(`${getSeasonEntryLabel(item, movie, index)} · ${item.episode_count || item.episode_files?.length || 0} ${"集"}`)}
            </option>
          `).join("")}
        </select>
      </label>
    `
    : "";
  const episodes = currentSeason.episodes || [];
  const episodesPerPage = 12;
  const totalPages = Math.ceil(episodes.length / episodesPerPage);
  const currentPage = Number(state.episodePage || 0);
  const startIndex = currentPage * episodesPerPage;
  const endIndex = startIndex + episodesPerPage;
  const paginatedEpisodes = episodes.slice(startIndex, endIndex);

  const getEpisodeProgress = (episodeIndex) => {
    if (!currentSeason.episode_files || !currentSeason.episode_files[episodeIndex]) return null;
    const episodePath = currentSeason.episode_files[episodeIndex];
    const progressData = allPlaybackProgress[episodePath];
    if (!progressData || !progressData.progress || !progressData.duration) return null;
    return Math.round((progressData.progress / progressData.duration) * 100);
  };

  const episodeCards = currentSeason.is_series
    ? `
      <div class="detail-episode-strip">
        ${paginatedEpisodes.map((episode, pageIndex) => {
          const actualIndex = startIndex + pageIndex;
          const progress = getEpisodeProgress(actualIndex);
          return `
            <button class="episode-card ${actualIndex === state.selectedEpisode ? "active" : ""}" data-episode-btn="${actualIndex}" title="${"双击播放这一集"}">
              <span class="episode-card-index">E${String(actualIndex + 1).padStart(2, "0")}</span>
              <strong>${escapeHtml(episode || `第 ${actualIndex + 1} 集`)}</strong>
              ${progress !== null ? `
                <span class="episode-card-progress">
                  <span class="episode-card-progress-bar" style="width:${progress}%"></span>
                  <span class="episode-card-progress-text">${progress}%</span>
                </span>
              ` : ""}
              <span>${escapeHtml(seasonLabel)}</span>
            </button>
          `;
        }).join("")}
      </div>
      ${totalPages > 1 ? `
        <div class="detail-episode-pagination">
          <button class="pagination-btn ${currentPage === 0 ? "disabled" : ""}" data-page-btn="${currentPage - 1}">${"上一页"}</button>
          <span class="pagination-info">${currentPage + 1} / ${totalPages}</span>
          <button class="pagination-btn ${currentPage >= totalPages - 1 ? "disabled" : ""}" data-page-btn="${currentPage + 1}">${"下一页"}</button>
        </div>
      ` : ""}
    `
    : "";

  const tags = currentSeason.tags || movie.tags || [];
  const watchedCount = movie.is_series ? getWatchedEpisodeCount(movie) : 0;
  const totalEpisodes = movie.is_series ? (movie.episode_count || 0) : 0;
  
  document.getElementById("detailContent").innerHTML = `
    <div class="detail-hero" style="background-image: url(${cover || 'https://via.placeholder.com/1920x1080?text=No+Cover'})">
      <div class="detail-content">
        <img class="detail-poster" src="${cover || 'https://via.placeholder.com/400x600?text=No+Poster'}" alt="${title}">
        <div class="detail-main">
          <h1 class="detail-title">${title}</h1>
          <div class="detail-meta">
            <span>${currentSeason.year || movie.year || "年份未知"}</span>
            <span>${currentSeason.region || movie.region || "地区未知"}</span>
            ${movie.is_series ? `<span>${movie.season_count > 1 ? `全${movie.season_count}季 · ` : ''}${totalEpisodes}集</span>` : `<span>${currentSeason.duration || movie.duration || "时长未知"}</span>`}
            ${currentSeason.rating || movie.rating ? `<span class="rating">${currentSeason.rating || movie.rating}</span>` : ''}
          </div>
          ${tags.length > 0 ? `<div class="detail-tags">${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
          <p class="detail-desc">${escapeHtml(currentSeason.intro || movie.intro || "暂无简介")}</p>
          <div class="action-buttons">
            <button class="btn btn-primary" data-play-movie="${escapeAttr(currentSeason.path)}" data-episode-index="${state.selectedEpisode}">▶ ${playbackText ? "继续播放" : "立即播放"}</button>
            <button class="btn btn-secondary ${currentSeason.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(currentSeason.path)}">⭐ ${currentSeason.is_favorite ? "取消收藏" : "加入收藏"}</button>
            <button class="btn btn-secondary" data-edit-movie="${escapeAttr(currentSeason.path)}">📁 编辑信息</button>
            <button class="btn btn-secondary" data-scrape-movie="${escapeAttr(currentSeason.path)}">🔍 手动刮削</button>
          </div>
        </div>
      </div>
    </div>

    <div class="detail-container">
      ${movie.is_series && seasons.length > 1 ? `
        <div class="section">
          <h2 class="section-title">选择季数</h2>
          <div class="season-selector">
            ${seasons.map((item, index) => `
              <button class="season-btn ${item.path === currentSeason.path ? "active" : ""}" data-season-btn="${escapeAttr(item.path)}">
                ${escapeHtml(getSeasonEntryLabel(item, movie, index))}
              </button>
            `).join('')}
          </div>
        </div>
      ` : ''}

      ${movie.is_series && episodes.length > 0 ? `
        <div class="section">
          <h3 style="margin-bottom: 16px; color: var(--text-secondary); font-size: 16px;">${escapeHtml(seasonLabel)} · ${episodes.length}集</h3>
          <div class="episode-grid">
            ${episodes.map((episode, index) => {
              const progress = getEpisodeProgress(index);
              const isWatched = progress !== null && progress >= 90;
              return `
                <button class="episode-card ${index === state.selectedEpisode ? "active" : ""} ${isWatched ? "watched" : ""}" data-episode-btn="${index}" title="${"点击播放"}">
                  <div class="episode-num">${String(index + 1).padStart(2, "0")}</div>
                  <div class="episode-title">${escapeHtml(episode || `第 ${index + 1} 集`)}</div>
                  ${progress !== null && progress < 90 ? `<div class="episode-progress-bar"><span style="width:${progress}%"></span></div>` : ""}
                </button>
              `;
            }).join('')}
          </div>
        </div>
      ` : ''}

      <div class="section">
        <h2 class="section-title">文件信息</h2>
        <div class="info-grid">
          <div class="info-card">
            <div class="info-label">存储路径</div>
            <div class="info-value">${escapeHtml(formatMovieSourcePath(currentSeason))}</div>
          </div>
          <div class="info-card">
            <div class="info-label">文件大小</div>
            <div class="info-value">${currentSeason.file_size || movie.file_size || "未知"}</div>
          </div>
          <div class="info-card">
            <div class="info-label">画质规格</div>
            <div class="info-value">${currentSeason.video_spec || movie.video_spec || "未知"}</div>
          </div>
          <div class="info-card">
            <div class="info-label">字幕信息</div>
            <div class="info-value">${currentSeason.subtitle_info || movie.subtitle_info || "未知"}</div>
          </div>
          ${movie.is_series && totalEpisodes > 0 ? `
            <div class="info-card">
              <div class="info-label">已观看</div>
              <div class="info-value">${watchedCount}/${totalEpisodes}集</div>
            </div>
          ` : playbackText ? `
            <div class="info-card">
              <div class="info-label">播放进度</div>
              <div class="info-value">${progressPercent}% · ${playbackText}</div>
            </div>
          ` : ''}
          <div class="info-card">
            <div class="info-label">最近播放</div>
            <div class="info-value">${currentSeason.last_play_time || movie.last_play_time || "暂无记录"}</div>
          </div>
        </div>
      </div>

      ${tags.length > 0 ? `
        <div class="section">
          <h2 class="section-title">标签</h2>
          <div class="detail-tags">
            ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
          </div>
        </div>
      ` : ''}
    </div>
  `;

  document.querySelectorAll("[data-episode-btn]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.episodeBtn);
      if (state.selectedEpisode === index) return;
      state.selectedEpisode = index;
      document.querySelectorAll("[data-episode-btn]").forEach((btn) => {
        btn.classList.toggle("active", Number(btn.dataset.episodeBtn) === index);
      });
      const playBtn = document.querySelector(".btn-primary[data-play-movie]");
      if (playBtn) playBtn.dataset.episodeIndex = String(index);
    });
  });

  document.querySelectorAll("[data-season-btn]").forEach((button) => {
    button.addEventListener("click", () => {
      const seasonPath = button.dataset.seasonBtn;
      if (state.selectedSeasonPath === seasonPath) return;
      state.selectedSeasonPath = seasonPath;
      const selectedSeason = (Array.isArray(movie.seasons) ? movie.seasons.find((item) => item.path === seasonPath) : null) || movie;
      state.selectedEpisode = getResumeEpisodeIndex(selectedSeason);
      syncSelectedMovie();
      renderDetail();
    });
  });

  document.querySelectorAll("[data-scrape-movie]").forEach((button) => {
    button.addEventListener("click", () => {
      scrapeSingle(button.dataset.scrapeMovie);
    });
  });
}

