function getHeroItems(movie, heroItems = []) {
  return heroItems.length ? heroItems : (movie ? [movie] : []);
}

function getHeroDisplayTitle(movie) {
  return movie?.is_series ? getSeriesDisplayTitle(movie) : (movie?.title || movie?.name || "未命名");
}

function getHeroEpisodeMeta(movie) {
  if (!movie?.is_series) return "单片";
  const seasonPrefix = movie.season_count > 1 ? `${movie.season_count} ${"季"} / ` : "";
  return `${seasonPrefix}${movie.episode_count} ${"集"}`;
}

// Hero 背景层：只负责输出背景图片或 fallback，不放文案内容。
function renderHeroBackdrop(movie, title) {
  const cover = movie?.cover_url
    ? `<img src="${escapeAttr(movie.cover_url)}" alt="${escapeHtml(title || "封面")}">`
    : `<div class="shelf-hero-backdrop fallback"></div>`;
  return `<div class="shelf-hero-backdrop">${cover}</div>`;
}

// 标题下方的影片信息胶囊：类型、年份、来源、集数。
function renderHeroMeta(movie) {
  return [
    movie?.type || "视频",
    movie?.year || "年份未知",
    movie?.source_label || "媒体库",
    getHeroEpisodeMeta(movie),
  ]
    .filter(Boolean)
    .map((item) => `<span>${escapeHtml(String(item))}</span>`)
    .join("");
}

function renderHeroProgress(progressPercent) {
  return progressPercent > 0 ? `<div class="hero-progress"><span style="width:${progressPercent}%"></span></div>` : "";
}

// Hero 主操作区：播放按钮和详情按钮，相关 data-* 被全局事件委托使用。
function renderHeroActions(movie, resumeHint) {
  const playPath = movie.resume_path || movie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  return `
    <div class="hero-actions">
      <button class="primary-btn" data-play-movie="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}">${resumeHint ? "继续播放" : "立即播放"}</button>
      <button class="ghost-btn" data-open-detail="${escapeAttr(movie.path)}">${"查看详情"}</button>
    </div>
  `;
}

// Hero 左侧主体文案：角标、标题、meta、续播提示、进度条和操作按钮。
function renderHeroCopy(movie) {
  const title = getHeroDisplayTitle(movie);
  const resumeHint = formatResumeHint(movie);
  const progressPercent = Number(movie.playback?.percent || 0);
  const eyebrow = resumeHint ? "继续观看" : state.view === "recent" ? "继续观看" : "首页精选";

  return `
    <div class="shelf-hero-copy">
      <span class="section-eyebrow">${eyebrow}</span>
      <h3>${escapeHtml(title)}</h3>
      <div class="hero-meta">${renderHeroMeta(movie)}</div>
      ${resumeHint ? `<div class="hero-resume">${escapeHtml(resumeHint)}</div>` : ""}
      ${renderHeroProgress(progressPercent)}
      ${renderHeroActions(movie, resumeHint)}
    </div>
  `;
}

// Hero 右侧统计卡片中的单个指标。
function renderHeroSideStat(value, label) {
  return `
    <div class="hero-side-stat">
      <strong>${value}</strong>
      <span>${label}</span>
    </div>
  `;
}

// Hero 右侧统计区：目前展示站外推荐、继续观看、片库条目。
function renderHeroSideStats() {
  return `
    <div class="hero-side-stats">
      ${renderHeroSideStat(state.externalRecommendations?.length || 0, "站外推荐")}
      ${renderHeroSideStat(getResumeShelfItems().length, "继续观看")}
      ${renderHeroSideStat(getDisplayItems().length, "片库条目")}
    </div>
  `;
}

// 右侧封面轮播中的单张缩略图，data-hero-pick 用于切换当前 hero。
function renderHeroCarouselCard(item, index, activeIndex) {
  const title = getHeroDisplayTitle(item);
  const content = item.cover_url
    ? `<img src="${escapeAttr(item.cover_url)}" alt="${escapeHtml(title || "封面")}">`
    : `<span>${escapeHtml(title)}</span>`;
  return `
    <button class="hero-carousel-card ${index === activeIndex ? "active" : ""}" data-hero-pick="${escapeAttr(item.path)}" aria-label="${"切换到"} ${escapeAttr(item.title || item.name || "封面")}">
      ${content}
    </button>
  `;
}

// Hero 右侧封面轮播；只有 2 个及以上候选项时才展示。
function renderHeroCarousel(items, activeIndex) {
  if (items.length <= 1) return "";
  return `
    <div class="hero-carousel-shell">
      <div class="hero-carousel-head">
        <span class="section-eyebrow">${"封面轮播"}</span>
        <strong>${activeIndex + 1} / ${items.length}</strong>
      </div>
      <div class="hero-carousel-track">
        ${items.map((item, index) => renderHeroCarouselCard(item, index, activeIndex)).join("")}
      </div>
    </div>
  `;
}

// Hero 右侧栏：统计区 + 轮播区。
function renderHeroSide(items, activeIndex) {
  return `
    <div class="hero-side hero-side-rich">
      ${renderHeroSideStats()}
      ${renderHeroCarousel(items, activeIndex)}
    </div>
  `;
}

// 首页/列表顶部大 Hero 入口，外部仍然只调用这个函数。
function renderShelfHero(movie, heroItems = []) {
  const items = getHeroItems(movie, heroItems);
  if (!items.length) return "";

  const activeIndex = state.heroCarouselIndex % items.length;
  const activeMovie = items[activeIndex] || movie || items[0];
  const activeTitleText = getHeroDisplayTitle(activeMovie);

  return `
    <section class="shelf-hero">
      ${renderHeroBackdrop(activeMovie, activeTitleText)}
      <div class="shelf-hero-overlay"></div>
      <div class="shelf-hero-content">
        ${renderHeroCopy(activeMovie)}
        ${renderHeroSide(items, activeIndex)}
      </div>
    </section>
  `;
}
