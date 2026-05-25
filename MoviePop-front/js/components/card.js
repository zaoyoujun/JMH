function renderMovieCard(movie) {
  const displayTitle = movie.is_series ? getSeriesDisplayTitle(movie) : (movie.title || movie.name || "未命名");
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(displayTitle)}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const episodeMeta = movie.is_series
    ? `${movie.season_count > 1 ? `${movie.season_count} ${"季"} / ` : ""}${movie.episode_count} ${"集"}`
    : "单片";
  const title = escapeHtml(displayTitle);
  const seasonMeta = movie.is_series && !movie.is_grouped_series ? getSeasonEntryLabel(movie, movie, 0) : "";
  const tags = Array.isArray(movie.tags) ? movie.tags.slice(0, 2) : [];
  const progressPercent = Number(movie.playback?.percent || 0);
  const resumeHint = formatResumeHint(movie);
  const playPath = movie.resume_path || movie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);

  return `
    <article class="media-card" data-card-play="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}" title="${"双击直接播放"}">
      <div class="poster-frame">
        <button class="poster-cover-trigger" data-open-detail="${escapeAttr(movie.path)}" aria-label="${"查看"} ${title} ${"详情"}"></button>
        ${cover}
        <div class="poster-shade"></div>
        <div class="card-tags">
          <span class="pill">${escapeHtml(movie.type || "视频")}</span>
          <span class="year-pill">${movie.year || "----"}</span>
        </div>
        <div class="card-source-badge">${escapeHtml(movie.source_label || "媒体库")}</div>
        <div class="poster-overlay-actions">
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}">${resumeHint ? "继续" : "播放"}</button>
          <button class="poster-overlay-btn ${movie.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(movie.path)}">${movie.is_favorite ? "已藏" : "收藏"}</button>
        </div>
        ${progressPercent > 0 ? `<div class="card-progress"><span style="width:${progressPercent}%"></span></div>` : ""}
      </div>
      <div class="card-body">
        <h3 title="${title}">${title}</h3>
        <div class="card-meta">
          <span>${episodeMeta}</span>
          <span>${movie.is_grouped_series ? "多季已合并" : seasonMeta || (movie.is_favorite ? "已收藏" : "未收藏")}</span>
        </div>
        ${resumeHint ? `<div class="card-resume">${escapeHtml(resumeHint)}</div>` : ""}
        ${tags.length ? `<div class="card-inline-tags">${tags.map((tag) => `<span class="mini-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
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

function renderRecommendationCard(movie) {
  const displayTitle = movie.is_series ? getSeriesDisplayTitle(movie) : (movie.title || movie.name || "未命名");
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(displayTitle || "封面")}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const title = escapeHtml(displayTitle);
  const reasons = (movie.recommendation_reasons || []).slice(0, 3);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const breakdown = movie.recommendation_breakdown || {};
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  return `
    <article class="media-card recommend-card">
      <div class="poster-frame">
        <button class="poster-cover-trigger" data-open-detail="${escapeAttr(movie.path)}" aria-label="${"查看"} ${title} ${"详情"}"></button>
        ${cover}
        <div class="poster-shade"></div>
        <div class="card-tags">
          <span class="pill">${escapeHtml(movie.type || "视频")}</span>
          <span class="year-pill">${movie.year || "----"}</span>
        </div>
        <div class="card-source-badge">${"推荐"} ${score}</div>
        <div class="poster-overlay-actions">
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(movie.resume_path || movie.path)}" data-episode-index="${resumeEpisodeIndex}">${"播放"}</button>
          <button class="poster-overlay-btn ${movie.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(movie.path)}">${movie.is_favorite ? "已藏" : "收藏"}</button>
        </div>
      </div>
      <div class="card-body">
        <h3 title="${title}">${title}</h3>
        <div class="card-meta">
          <span>${escapeHtml(movie.source_label || "媒体库")}</span>
          <span>${movie.is_series ? `${movie.episode_count || 0} ${"集"}` : "单片"}</span>
        </div>
        <div class="recommend-reasons">
          ${reasons.map((reason) => `<span class="recommend-reason ${reasonClass(reason)}">${escapeHtml(reason)}</span>`).join("")}
        </div>
        <div class="recommend-breakdown">
          ${renderBreakdownPill("内容", breakdown.content)}
          ${renderBreakdownPill("相似", breakdown.collaborative)}
          ${renderBreakdownPill("类型", breakdown.type)}
          ${renderBreakdownPill("年份", breakdown.year)}
        </div>
        <div class="recommend-rating">
          ${[1, 2, 3, 4, 5].map((rating) => `<button class="rating-chip" data-rate-movie="${escapeAttr(movie.path)}" data-rating="${rating}">${rating}★</button>`).join("")}
        </div>
      </div>
    </article>
  `;
}

function renderHomeRecommendationCard(movie) {
  const displayTitle = movie.is_series ? getSeriesDisplayTitle(movie) : (movie.title || movie.name || "未命名");
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(displayTitle || "封面")}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const title = escapeHtml(displayTitle);
  const rawReason = (movie.recommendation_reasons || [])[0] || "和你最近常看的内容气质接近";
  const reason = escapeHtml(rawReason);
  const reasonCls = reasonClass(rawReason);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const playPath = movie.resume_path || movie.path;
  const resumeEpisodeIndex = getResumeEpisodeIndex(movie);
  const metaLine = movie.is_series ? `${movie.episode_count || 0} ${"集"}` : "单片";

  return `
    <article class="media-card home-recommend-card compact-shelf-card">
      <div class="poster-frame compact-poster">
        <button class="poster-cover-trigger" data-open-detail="${escapeAttr(movie.path)}" aria-label="${"查看"} ${title} ${"详情"}"></button>
        ${cover}
        <div class="poster-shade"></div>
        <div class="card-tags">
          <span class="pill">${escapeHtml(movie.type || "视频")}</span>
          <span class="year-pill">${movie.year || "----"}</span>
        </div>
        <div class="card-source-badge">${"推荐"} ${score}</div>
        <div class="poster-overlay-actions">
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(playPath)}" data-episode-index="${resumeEpisodeIndex}">${"播放"}</button>
          <button class="poster-overlay-btn ${movie.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(movie.path)}">${movie.is_favorite ? "已藏" : "收藏"}</button>
        </div>
      </div>
      <div class="card-body">
        <div class="recommend-origin-label">${"片库内推荐"}</div>
        <h3 title="${title}">${title}</h3>
        <div class="card-meta">
          <span>${escapeHtml(movie.source_label || "媒体库")}</span>
          <span>${metaLine}</span>
        </div>
        <div class="home-recommend-reason ${reasonCls}">${reason}</div>
        <div class="compact-card-foot">
          <div class="card-source-badge inline-badge">${"推荐"} ${score}</div>
          <div class="recommend-rating compact mini-rating">
            ${[3, 4, 5].map((rating) => `<button class="rating-chip" data-rate-movie="${escapeAttr(movie.path)}" data-rating="${rating}">${rating}★</button>`).join("")}
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
  const poster = item.poster_url
    ? `<img src="${escapeAttr(item.poster_url)}" alt="${escapeHtml(item.title || "封面")}" referrerpolicy="no-referrer">`
    : `<div class="poster-fallback">${"站外发现"}</div>`;
  const reason = escapeHtml((item.reasons || [])[0] || "来自站外片单与兴趣画像的匹配结果。");
  const score = Math.round(Number(item.score || 0) * 100);
  return `
    <article class="media-card external-card external-rich-card compact-shelf-card">
      <div class="poster-frame external-poster compact-poster">
        ${poster}
        <div class="poster-shade"></div>
        <div class="card-tags">
          <span class="pill">${escapeHtml(item.source || "外部")}</span>
          <span class="year-pill">${item.year || "----"}</span>
        </div>
      </div>
      <div class="card-body">
        <div class="recommend-origin-label">${"站外发现"}</div>
        <h3 title="${escapeHtml(item.title || "")}">${escapeHtml(item.title || "未命名")}</h3>
        <div class="card-meta">
          <span>${escapeHtml(item.source || "外部片库")}</span>
          <span>${item.year || "年份未知"}</span>
        </div>
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
