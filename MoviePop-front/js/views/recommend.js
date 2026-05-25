function renderRecommendationView() {
  const allItems = state.recommendationItems || [];
  const externalItems = state.externalRecommendations || [];

  // 筛选和排序
  const filter = state.recommendFilter;
  const availableTypes = [...new Set(allItems.map((m) => m.type).filter(Boolean))];
  let items = allItems;
  if (filter.type) {
    items = items.filter((m) => m.type === filter.type);
  }
  items = [...items].sort((a, b) => {
    if (filter.sort === "rating") return (Number(b.avg_rating || 0)) - (Number(a.avg_rating || 0));
    if (filter.sort === "year") return (Number(b.year || 0)) - (Number(a.year || 0));
    if (filter.sort === "title") return (a.title || a.name || "").localeCompare(b.title || b.name || "");
    return (Number(b.recommendation_score || 0)) - (Number(a.recommendation_score || 0));
  });
  const profile = state.recommendationProfile || {};
  const topTags = (profile.top_tags || []).slice(0, 6);
  const topTypes = (profile.top_types || []).slice(0, 4);
  const topYearBuckets = (profile.top_year_buckets || []).slice(0, 4);
  const seedTitles = (profile.seed_titles || []).slice(0, 6);
  const generatedText = state.recommendationGeneratedAt
    ? new Date(state.recommendationGeneratedAt * 1000).toLocaleString("zh-CN")
    : "刚刚生成";

  const profileSummary = `
    <section class="recommend-hero">
      <div class="recommend-hero-copy">
        <span class="section-eyebrow">${"推荐画像"}</span>
        <h3>${"你的近期观影偏好"}</h3>
        <p>${"这份推荐会综合收藏、播放进度、手动标签、评分，以及影片内容相似度来排序。"}</p>
        <div class="recommend-meta">
          <span>${"最近生成"}：${escapeHtml(generatedText)}</span>
          <span>${"画像样本"}：${profile.seed_count || 0}</span>
        </div>
      </div>
      <div class="recommend-hero-side">
        <div class="recommend-side-block">
          <strong>${"偏好标签"}</strong>
          <div class="card-inline-tags">
            ${topTags.length ? topTags.map((tag) => `<span class="mini-tag">${escapeHtml(tag.name)}</span>`).join("") : `<span class="mini-tag">${"等待行为数据"}</span>`}
          </div>
        </div>
        <div class="recommend-side-block">
          <strong>${"常看类型"}</strong>
          <div class="card-inline-tags">
            ${topTypes.length ? topTypes.map((tag) => `<span class="mini-tag">${escapeHtml(tag.name)}</span>`).join("") : `<span class="mini-tag">${"尚未形成"}</span>`}
          </div>
        </div>
        <div class="recommend-side-block">
          <strong>${"偏好年代"}</strong>
          <div class="recommend-bars">
            ${topYearBuckets.length ? topYearBuckets.map((item) => renderPreferenceBar(item)).join("") : `<span class="mini-tag">${"等待积累"}</span>`}
          </div>
        </div>
      </div>
    </section>
  `;

  const seedSection = seedTitles.length
    ? `
      <section class="library-grid-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${"画像样本"}</span>
            <h3>${"当前推荐主要参考这些片子"}</h3>
          </div>
          <p>${"收藏、播放较多和手动打分的内容，会更强地影响后面的推荐排序。"}</p>
        </div>
        <div class="seed-chip-row">
          ${seedTitles.map((title) => `<span class="seed-chip">${escapeHtml(title)}</span>`).join("")}
        </div>
      </section>
    `
    : "";

  const filterBar = allItems.length ? `
    <div class="recommend-filter-bar">
      <div class="filter-group">
        <span class="filter-label">${"筛选"}</span>
        <button class="filter-chip ${!filter.type ? "active" : ""}" data-recommend-filter-type="">${"全部类型"}</button>
        ${availableTypes.map((type) => `<button class="filter-chip ${filter.type === type ? "active" : ""}" data-recommend-filter-type="${escapeAttr(type)}">${escapeHtml(type)}</button>`).join("")}
      </div>
      <div class="filter-group">
        <span class="filter-label">${"排序"}</span>
        <button class="filter-chip ${filter.sort === "score" ? "active" : ""}" data-recommend-sort="score">${"推荐度"}</button>
        <button class="filter-chip ${filter.sort === "rating" ? "active" : ""}" data-recommend-sort="rating">${"评分"}</button>
        <button class="filter-chip ${filter.sort === "year" ? "active" : ""}" data-recommend-sort="year">${"年份新→旧"}</button>
        <button class="filter-chip ${filter.sort === "title" ? "active" : ""}" data-recommend-sort="title">${"标题A→Z"}</button>
      </div>
    </div>
  ` : "";

  const librarySection = allItems.length
    ? `
      <section class="library-grid-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${"库内推荐"}</span>
            <h3>${"先从你已有的片库里挑"}</h3>
          </div>
          <p>${"每张卡片都带着推荐理由和评分入口，越用越准。"}</p>
        </div>
        ${filterBar}
        <div class="recommend-grid">
          ${items.map(renderRecommendationCard).join("")}
        </div>
      </section>
    `
    : renderSetupState("还没有生成推荐", "先收藏、播放或给几部片打分，推荐系统就会开始有方向。", "现在先去片库看看");

  const externalSection = externalItems.length
    ? `
      <section class="library-grid-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${"站外发现"}</span>
            <h3>${"来自 TMDB、豆瓣和 IMDb 的补片线索"}</h3>
          </div>
          <p>${"这里是片库外的候选内容，适合补充你下一轮想看的方向。"}</p>
        </div>
        <div class="external-grid">
          ${externalItems.map(renderExternalRecommendationCard).join("")}
        </div>
      </section>
    `
    : "";

  return `<div class="library-home">${profileSummary}${seedSection}${librarySection}${externalSection}</div>`;
}

function renderHomeRecommendationSection() {
  const mergedRecommendationItems = getMergedRecommendationItems();
  const libraryItems = mergedRecommendationItems.filter((item) => item.recommendation_origin === "library");
  const externalItems = mergedRecommendationItems.filter((item) => item.recommendation_origin === "external");
  const resumeItems = getResumeShelfItems().slice(0, 8);
  const profile = state.recommendationProfile || {};
  const topTags = (profile.top_tags || []).slice(0, 5);
  const topTypes = (profile.top_types || []).slice(0, 3);
  const topYearBuckets = (profile.top_year_buckets || []).slice(0, 3);
  const seedTitles = (profile.seed_titles || []).slice(0, 4);

  if (!mergedRecommendationItems.length) {
    return "";
  }

  const summaryLine = [
    topTags.length ? `${"偏好："}${topTags.map((tag) => tag.name).join(" / ")}` : "",
    seedTitles.length ? `${"参考："}${seedTitles.join(" / ")}` : "",
  ].filter(Boolean).join(" · ");

  const sourceLabels = [...new Set(externalItems.map((item) => item.source).filter(Boolean))].slice(0, 4);
  const shelfMeta = [
    externalItems.length ? `${"站外"} ${externalItems.length}` : "",
    libraryItems.length ? `${"片库内"} ${libraryItems.length}` : "",
    sourceLabels.length ? sourceLabels.join(" / ") : "",
  ].filter(Boolean);

  const profilePanel = `
    <section class="library-grid-shell home-profile-shell compact">
      <div class="section-head">
        <div>
          <span class="section-eyebrow">${"用户画像"}</span>
          <h3>${"最近的看片偏好"}</h3>
        </div>
        <p>${"基于收藏、播放进度、评分反馈和影片信息，动态构建你的当前口味画像。"}</p>
      </div>
      <div class="home-profile-grid">
        <article class="home-profile-card">
          <strong>${"偏好标签"}</strong>
          <div class="card-inline-tags">
            ${topTags.length ? topTags.map((tag) => `<span class="mini-tag">${escapeHtml(tag.name)}</span>`).join("") : `<span class="mini-tag">${"等待积累"}</span>`}
          </div>
        </article>
        <article class="home-profile-card">
          <strong>${"常看类型"}</strong>
          <div class="card-inline-tags">
            ${topTypes.length ? topTypes.map((tag) => `<span class="mini-tag">${escapeHtml(tag.name)}</span>`).join("") : `<span class="mini-tag">${"等待积累"}</span>`}
          </div>
        </article>
        <article class="home-profile-card">
          <strong>${"偏好年代"}</strong>
          <div class="home-profile-bars">
            ${topYearBuckets.length ? topYearBuckets.map((item) => renderPreferenceBar(item)).join("") : `<span class="mini-tag">${"等待积累"}</span>`}
          </div>
        </article>
      </div>
    </section>
  `;

  const resumeSection = resumeItems.length
    ? `
      <section class="library-grid-shell home-shelf-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${"继续观看"}</span>
            <h3>${"从上次看到的地方接着来"}</h3>
          </div>
          <p>${"把最近看过但还没看完的内容单独放在首页，不用再专门切到最近播放里找。"}</p>
        </div>
        <div class="home-shelf-row">
          ${resumeItems.map(renderMovieCard).join("")}
        </div>
      </section>
    `
    : "";

  const mergedSection = mergedRecommendationItems.length
    ? `
      <section class="library-grid-shell home-shelf-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${"影视推荐"}</span>
            <h3>${"下一部先看这些"}</h3>
          </div>
        </div>
        <div class="home-recommend-summary">
          ${shelfMeta.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
          <span>${"评分与播放记录共同参与排序"}</span>
          <span>${"推荐理由可视化"}</span>
        </div>
        <div class="recommend-carousel-shell" data-recommend-carousel>
          <button class="carousel-arrow left" data-recommend-arrow="-1" aria-label="${"查看上一组推荐"}">‹</button>
          <div class="home-shelf-row mixed-recommend-row">
            ${mergedRecommendationItems.map((item) => item.recommendation_origin === "external" ? renderExternalRecommendationCard(item) : renderHomeRecommendationCard(item)).join("")}
          </div>
          <button class="carousel-arrow right" data-recommend-arrow="1" aria-label="${"查看下一组推荐"}">›</button>
        </div>
      </section>
    `
    : "";

  const libraryInsight = libraryItems.length
    ? `
      <div class="home-recommend-footnote">
        ${escapeHtml(summaryLine || "综合收藏、播放进度、标签和评分，从你的片库里继续挑更适合现在看的内容。")}
      </div>
    `
    : "";

  return `<div class="home-discovery-stack">${profilePanel}${mergedSection}${libraryInsight}${resumeSection}</div>`;
}

