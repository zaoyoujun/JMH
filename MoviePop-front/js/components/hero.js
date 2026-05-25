function renderShelfHero(movie, heroItems = []) {
  const items = heroItems.length ? heroItems : (movie ? [movie] : []);
  if (!items.length) return "";
  const activeIndex = state.heroCarouselIndex % items.length;
  const activeMovie = items[activeIndex] || movie || items[0];
  const activeTitleText = activeMovie.is_series ? getSeriesDisplayTitle(activeMovie) : (activeMovie.title || activeMovie.name || "未命名");
  const cover = activeMovie.cover_url
    ? `<img src="${activeMovie.cover_url}" alt="${escapeHtml(activeTitleText || "封面")}">`
    : `<div class="shelf-hero-backdrop fallback"></div>`;
  const title = escapeHtml(activeTitleText);
  const resumeHint = formatResumeHint(activeMovie);
  const progressPercent = Number(activeMovie.playback?.percent || 0);
  const playPath = activeMovie.resume_path || activeMovie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(activeMovie);
  const meta = [
    activeMovie.type || "视频",
    activeMovie.year || "年份未知",
    activeMovie.source_label || "媒体库",
    activeMovie.is_series ? `${activeMovie.season_count > 1 ? `${activeMovie.season_count} ${"季"} / ` : ""}${activeMovie.episode_count} ${"集"}` : "单片",
  ]
    .filter(Boolean)
    .map((item) => `<span>${escapeHtml(String(item))}</span>`)
    .join("");
  const carouselMarkup = items.length > 1
    ? `
      <div class="hero-carousel-shell">
        <div class="hero-carousel-head">
          <span class="section-eyebrow">${"封面轮播"}</span>
          <strong>${activeIndex + 1} / ${items.length}</strong>
        </div>
        <div class="hero-carousel-track">
          ${items.map((item, index) => `
            <button class="hero-carousel-card ${index === activeIndex ? "active" : ""}" data-hero-pick="${escapeAttr(item.path)}" aria-label="${"切换到"} ${escapeAttr(item.title || item.name || "封面")}">
              ${item.cover_url ? `<img src="${escapeAttr(item.cover_url)}" alt="${escapeHtml(item.is_series ? getSeriesDisplayTitle(item) : (item.title || item.name || "封面"))}">` : `<span>${escapeHtml(item.is_series ? getSeriesDisplayTitle(item) : (item.title || item.name || "未命名"))}</span>`}
            </button>
          `).join("")}
        </div>
      </div>
    `
    : "";

  return `
    <section class="shelf-hero">
      <div class="shelf-hero-backdrop">${cover}</div>
      <div class="shelf-hero-overlay"></div>
      <div class="shelf-hero-content">
        <div class="shelf-hero-copy">
          <span class="section-eyebrow">${resumeHint ? "继续观看" : state.view === "recent" ? "继续观看" : "首页精选"}</span>
          <h3>${title}</h3>
          <div class="hero-meta">${meta}</div>
          ${resumeHint ? `<div class="hero-resume">${escapeHtml(resumeHint)}</div>` : ""}
          ${progressPercent > 0 ? `<div class="hero-progress"><span style="width:${progressPercent}%"></span></div>` : ""}
          <div class="hero-actions">
            <button class="primary-btn" data-play-movie="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}">${resumeHint ? "继续播放" : "立即播放"}</button>
            <button class="ghost-btn" data-open-detail="${escapeAttr(activeMovie.path)}">${"查看详情"}</button>
          </div>
        </div>
        <div class="hero-side hero-side-rich">
          <div class="hero-side-stats">
            <div class="hero-side-stat">
              <strong>${state.externalRecommendations?.length || 0}</strong>
              <span>${"站外推荐"}</span>
            </div>
            <div class="hero-side-stat">
              <strong>${getResumeShelfItems().length}</strong>
              <span>${"继续观看"}</span>
            </div>
            <div class="hero-side-stat">
              <strong>${getDisplayItems().length}</strong>
              <span>${"片库条目"}</span>
            </div>
          </div>
          ${carouselMarkup}
        </div>
      </div>
    </section>
  `;
}

