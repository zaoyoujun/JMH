function getCardDisplayTitle(movie) {
  return movie?.is_series ? getSeriesDisplayTitle(movie) : (movie?.title || movie?.name || "未命名");
}

function renderPosterMedia({ src, alt, fallback = "暂无封面", referrerPolicy = "" }) {
  if (!src) return `<div class="poster-fallback">${fallback}</div>`;
  const referrerAttr = referrerPolicy ? ` referrerpolicy="${escapeAttr(referrerPolicy)}"` : "";
  return `<img src="${escapeAttr(src)}" alt="${escapeHtml(alt || "封面")}"${referrerAttr}>`;
}

function renderPosterDetailTrigger(moviePath, title) {
  return `<button class="poster-cover-trigger" data-open-detail="${escapeAttr(moviePath)}" aria-label="${"查看"} ${escapeAttr(title)} ${"详情"}"></button>`;
}

function renderCardTags(type, year) {
  return `
    <div class="card-tags">
      <span class="pill">${escapeHtml(type || "视频")}</span>
      <span class="year-pill">${year || "----"}</span>
    </div>
  `;
}

function renderCardSourceBadge(label) {
  return `<div class="card-source-badge">${label}</div>`;
}

function renderPosterActions({ moviePath, playPath, episodeIndex = 0, isFavorite = false, playLabel = "播放" }) {
  return `
    <div class="poster-overlay-actions">
      <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(playPath)}" data-episode-index="${episodeIndex}">${playLabel}</button>
      <button class="poster-overlay-btn ${isFavorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(moviePath)}">${isFavorite ? "已藏" : "收藏"}</button>
    </div>
  `;
}

function renderCardProgress(percent) {
  const value = Number(percent || 0);
  return value > 0 ? `<div class="card-progress"><span style="width:${value}%"></span></div>` : "";
}

function renderPosterFrame({
  moviePath = "",
  title = "",
  media = "",
  type = "视频",
  year = "----",
  sourceBadge = "",
  actions = "",
  progress = "",
  extraClass = "",
}) {
  const posterClass = ["poster-frame", extraClass].filter(Boolean).join(" ");
  return `
    <div class="${posterClass}">
      ${moviePath ? renderPosterDetailTrigger(moviePath, title) : ""}
      ${media}
      <div class="poster-shade"></div>
      ${renderCardTags(type, year)}
      ${sourceBadge}
      ${actions}
      ${progress}
    </div>
  `;
}

function renderCardMeta(left, right) {
  return `
    <div class="card-meta">
      <span>${left}</span>
      <span>${right}</span>
    </div>
  `;
}

function renderMiniTags(tags = []) {
  return tags.length
    ? `<div class="card-inline-tags">${tags.map((tag) => `<span class="mini-tag">${escapeHtml(tag)}</span>`).join("")}</div>`
    : "";
}

function renderRatingChips(moviePath, ratings) {
  return ratings
    .map((rating) => `<button class="rating-chip" data-rate-movie="${escapeAttr(moviePath)}" data-rating="${rating}">${rating}★</button>`)
    .join("");
}

function renderMovieCard(movie) {
  const displayTitle = getCardDisplayTitle(movie);
  const title = escapeHtml(displayTitle);
  const episodeMeta = movie.is_series
    ? `${movie.season_count > 1 ? `${movie.season_count} ${"季"} / ` : ""}${movie.episode_count} ${"集"}`
    : "单片";
  const seasonMeta = movie.is_series && !movie.is_grouped_series ? getSeasonEntryLabel(movie, movie, 0) : "";
  const tags = Array.isArray(movie.tags) ? movie.tags.slice(0, 2) : [];
  const progressPercent = Number(movie.playback?.percent || 0);
  const resumeHint = formatResumeHint(movie);
  const playPath = movie.resume_path || movie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  const poster = renderPosterFrame({
    moviePath: movie.path,
    title: displayTitle,
    media: renderPosterMedia({ src: movie.cover_url, alt: displayTitle }),
    type: movie.type || "视频",
    year: movie.year || "----",
    sourceBadge: renderCardSourceBadge(escapeHtml(movie.source_label || "媒体库")),
    actions: renderPosterActions({
      moviePath: movie.path,
      playPath,
      episodeIndex: resumeEpisodeIndex,
      isFavorite: movie.is_favorite,
      playLabel: resumeHint ? "继续" : "播放",
    }),
    progress: renderCardProgress(progressPercent),
  });

  return `
    <article class="media-card" data-card-play="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}" title="${"双击直接播放"}">
      ${poster}
      <div class="card-body">
        <h3 title="${title}">${title}</h3>
        ${renderCardMeta(episodeMeta, movie.is_grouped_series ? "多季已合并" : seasonMeta || (movie.is_favorite ? "已收藏" : "未收藏"))}
        ${resumeHint ? `<div class="card-resume">${escapeHtml(resumeHint)}</div>` : ""}
        ${renderMiniTags(tags)}
      </div>
    </article>
  `;
}

function reasonClass(reason) {
  if (/偏好标签/.test(reason)) return "reason-tag";
  if (/风格接近/.test(reason)) return "reason-similar";
  if (/最近偏好/.test(reason)) return "reason-type";
  if (/年代/.test(reason)) return "reason-year";
  if (/评分/.test(reason)) return "reason-rating";
  return "";
}

function renderRecommendationReasons(reasons = []) {
  return reasons.map((reason) => `<span class="recommend-reason ${reasonClass(reason)}">${escapeHtml(reason)}</span>`).join("");
}

function renderRecommendationCard(movie) {
  const displayTitle = getCardDisplayTitle(movie);
  const title = escapeHtml(displayTitle);
  const reasons = (movie.recommendation_reasons || []).slice(0, 3);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const breakdown = movie.recommendation_breakdown || {};
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  const poster = renderPosterFrame({
    moviePath: movie.path,
    title: displayTitle,
    media: renderPosterMedia({ src: movie.cover_url, alt: displayTitle || "封面" }),
    type: movie.type || "视频",
    year: movie.year || "----",
    sourceBadge: renderCardSourceBadge(`${"推荐"} ${score}`),
    actions: renderPosterActions({
      moviePath: movie.path,
      playPath: movie.resume_path || movie.path,
      episodeIndex: resumeEpisodeIndex,
      isFavorite: movie.is_favorite,
      playLabel: "播放",
    }),
  });

  return `
    <article class="media-card recommend-card">
      ${poster}
      <div class="card-body">
        <h3 title="${title}">${title}</h3>
        ${renderCardMeta(escapeHtml(movie.source_label || "媒体库"), movie.is_series ? `${movie.episode_count || 0} ${"集"}` : "单片")}
        <div class="recommend-reasons">
          ${renderRecommendationReasons(reasons)}
        </div>
        <div class="recommend-breakdown">
          ${renderBreakdownPill("内容", breakdown.content)}
          ${renderBreakdownPill("相似", breakdown.collaborative)}
          ${renderBreakdownPill("类型", breakdown.type)}
          ${renderBreakdownPill("年份", breakdown.year)}
        </div>
        <div class="recommend-rating">
          ${renderRatingChips(movie.path, [1, 2, 3, 4, 5])}
        </div>
      </div>
    </article>
  `;
}

function renderHomeRecommendationCard(movie) {
  const displayTitle = getCardDisplayTitle(movie);
  const title = escapeHtml(displayTitle);
  const rawReason = (movie.recommendation_reasons || [])[0] || "和你最近常看的内容气质接近";
  const reason = escapeHtml(rawReason);
  const reasonCls = reasonClass(rawReason);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const playPath = movie.resume_path || movie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  const metaLine = movie.is_series ? `${movie.episode_count || 0} ${"集"}` : "单片";
  const poster = renderPosterFrame({
    moviePath: movie.path,
    title: displayTitle,
    media: renderPosterMedia({ src: movie.cover_url, alt: displayTitle || "封面" }),
    type: movie.type || "视频",
    year: movie.year || "----",
    sourceBadge: renderCardSourceBadge(`${"推荐"} ${score}`),
    actions: renderPosterActions({
      moviePath: movie.path,
      playPath,
      episodeIndex: resumeEpisodeIndex,
      isFavorite: movie.is_favorite,
      playLabel: "播放",
    }),
    extraClass: "compact-poster",
  });

  return `
    <article class="media-card home-recommend-card compact-shelf-card">
      ${poster}
      <div class="card-body">
        <div class="recommend-origin-label">${"片库内推荐"}</div>
        <h3 title="${title}">${title}</h3>
        ${renderCardMeta(escapeHtml(movie.source_label || "媒体库"), metaLine)}
        <div class="home-recommend-reason ${reasonCls}">${reason}</div>
        <div class="compact-card-foot">
          <div class="card-source-badge inline-badge">${"推荐"} ${score}</div>
          <div class="recommend-rating compact mini-rating">
            ${renderRatingChips(movie.path, [3, 4, 5])}
          </div>
        </div>
      </div>
    </article>
  `;
}

function renderPreferenceBar(item) {
  const weight = Number(item?.weight || 0);
  const width = Math.max(18, Math.min(100, Math.round(weight * 24)));
  return `
    <div class="preference-bar">
      <span>${escapeHtml(item?.name || "未知")}</span>
      <div class="preference-track"><i style="width:${width}%"></i></div>
    </div>
  `;
}

function renderBreakdownPill(label, value) {
  const percent = Math.max(0, Math.min(100, Math.round(Number(value || 0) * 100)));
  const width = Math.max(6, percent);
  return `
    <div class="breakdown-item">
      <span class="breakdown-label">${escapeHtml(label)}</span>
      <div class="breakdown-track"><i style="width:${width}%"></i></div>
      <span class="breakdown-value">${percent}</span>
    </div>
  `;
}

function renderExternalRecommendationCard(item) {
  const reason = escapeHtml((item.reasons || [])[0] || "来自站外片单与兴趣画像的匹配结果。");
  const score = Math.round(Number(item.score || 0) * 100);
  const poster = renderPosterFrame({
    media: renderPosterMedia({
      src: item.poster_url,
      alt: item.title || "封面",
      fallback: "站外发现",
      referrerPolicy: "no-referrer",
    }),
    type: item.source || "外部",
    year: item.year || "----",
    extraClass: "external-poster compact-poster",
  });

  return `
    <article class="media-card external-card external-rich-card compact-shelf-card">
      ${poster}
      <div class="card-body">
        <div class="recommend-origin-label">${"站外发现"}</div>
        <h3 title="${escapeHtml(item.title || "")}">${escapeHtml(item.title || "未命名")}</h3>
        ${renderCardMeta(escapeHtml(item.source || "外部片库"), item.year || "年份未知")}
        <div class="home-recommend-reason">${reason}</div>
        <div class="compact-card-foot">
          <div class="card-source-badge inline-badge">${"推荐"} ${score || "--"}</div>
          ${item.url ? `<a class="ghost-btn external-link" href="${escapeAttr(item.url)}" target="_blank" rel="noreferrer">${"查看来源"}</a>` : ""}
        </div>
      </div>
    </article>
  `;
}

// 设置标签页配置
