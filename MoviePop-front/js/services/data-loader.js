async function loadBootstrap() {
  const payload = await guarded(() => api("/api/bootstrap"), true, "正在初始化应用...");
  if (!payload) return;

  if (state.view === "local") {
    state.view = "all";
  }
  state.config = payload.config;
  state.stats = payload.stats;
  state.playerRuntime = payload.player_runtime || null;
  state.scanStatus = payload.scan_status || null;
  state.webdavDirs = new Set(normalizeRemoteDirSetItems(payload.config.saved_mount_dirs || []));
  state.localDirs = new Set(payload.config.local_mount_dirs || []);
  applyTheme(payload.config.ui_theme || payload.config.interface_theme);
  updateSidebarStatus();
  await recoverInlinePlayerSession({ silent: false });
  render();
}

async function loadCurrentView() {
  render();

  if (state.view === "settings") {
    return;
  }

  if (state.view === "recommend") {
    await loadRecommendations();
    return;
  }

  if (state.view === "report") {
    await loadReport();
    render();
    return;
  }

  if (state.view === "all" && !state.config?.has_any_library) {
    state.items = [];
    render();
    return;
  }

  if (!isListView(state.view)) {
    return;
  }

  const source = getLibrarySourceForView(state.view);
  const query = new URLSearchParams({
    mode: getModeForView(state.view),
    source,
    search: state.search,
  });
  const payload = await guarded(() => api(`/api/library?${query.toString()}`), true, "正在加载媒体库...");
  if (!payload) return;

  state.items = payload.items;
  state.stats = payload.stats;
  if (state.view === "all") {
    await loadRecommendations(false);
    return;
  }
  syncSelectedMovie();
  render();
}

function isListView(view) {
  return ["all", "favorite", "recent"].includes(view);
}

async function loadRecommendations(showLoading = true) {
  // 推荐功能已移除，返回空数据
  state.recommendationItems = [];
  state.externalRecommendations = [];
  state.recommendationProfile = null;
  state.recommendationStats = null;
  state.recommendationGeneratedAt = 0;
  render();
}

async function refreshRecommendations(showToastAfter = false) {
  // 推荐功能已移除，返回空数据
  state.recommendationItems = [];
  state.externalRecommendations = [];
  state.recommendationProfile = null;
  state.recommendationGeneratedAt = 0;
  state.recommendationStats = null;
  if (showToastAfter) {
    showToast("推荐结果已更新", "success");
  }
  render();
}

function getHomeHeroItems() {
  const merged = [];
  const seen = new Set();
  const candidates = [...(state.items || []), ...(state.recommendationItems || [])];
  candidates.forEach((item) => {
    if (!item?.path || seen.has(item.path)) return;
    seen.add(item.path);
    merged.push(resolveMovieViewModel(item));
  });
  return merged.slice(0, 8);
}

function getResumeShelfItems(items = getDisplayItems()) {
  return (items || [])
    .filter((item) => item?.playback?.has_progress)
    .sort((left, right) => Number(right.playback?.timestamp || 0) - Number(left.playback?.timestamp || 0))
    .slice(0, 8);
}

function getMergedRecommendationItems() {
  const libraryItems = (state.recommendationItems || []).slice(0, 4).map(resolveMovieViewModel);
  const externalItems = (state.externalRecommendations || []).slice(0, 12);
  return [
    ...externalItems.map((item) => ({ ...item, recommendation_origin: "external" })),
    ...libraryItems.map((item) => ({ ...item, recommendation_origin: "library" })),
  ];
}

function resolveMovieViewModel(movie) {
  if (!movie?.path) return movie;
  const latest = (state.items || []).find((item) => item.path === movie.path);
  if (!latest) return movie;
  return {
    ...movie,
    ...latest,
    recommendation_score: movie.recommendation_score,
    recommendation_breakdown: movie.recommendation_breakdown,
    recommendation_reasons: movie.recommendation_reasons,
    recommendation_origin: movie.recommendation_origin,
    feedback: movie.feedback,
    auto_tags: movie.auto_tags,
  };
}

function syncHeroCarousel() {
  const shouldRun = state.view === "all" && getHomeHeroItems().length > 1;
  if (!shouldRun) {
    if (heroCarouselTimer) {
      window.clearInterval(heroCarouselTimer);
      heroCarouselTimer = null;
    }
    state.heroCarouselIndex = 0;
    return;
  }

  if (heroCarouselTimer) return;
  heroCarouselTimer = window.setInterval(() => {
    const items = getHomeHeroItems();
    if (!items.length || state.view !== "all") return;
    state.heroCarouselIndex = (state.heroCarouselIndex + 1) % items.length;
    render();
  }, 5500);
}

function clearRecommendationCarousel() {
  if (recommendCarouselTimer) {
    window.clearInterval(recommendCarouselTimer);
    recommendCarouselTimer = null;
  }
  state.recommendCarouselPaused = false;
}

function getRecommendationStep(row) {
  if (!row) return 0;
  const firstCard = row.querySelector(".compact-shelf-card");
  const styles = window.getComputedStyle(row);
  const gap = Number.parseFloat(styles.columnGap || styles.gap || "0") || 0;
  return firstCard ? firstCard.getBoundingClientRect().width + gap : row.clientWidth * 0.85;
}

function scrollRecommendationCarousel(direction = 1) {
  const row = document.querySelector(".mixed-recommend-row");
  if (!row) return;
  const maxScroll = Math.max(0, row.scrollWidth - row.clientWidth);
  if (maxScroll <= 0) return;
  const step = getRecommendationStep(row);
  const threshold = Math.max(24, step * 0.35);
  let nextLeft = row.scrollLeft + step * direction;
  if (direction > 0 && row.scrollLeft >= maxScroll - threshold) {
    nextLeft = 0;
  } else if (direction < 0 && row.scrollLeft <= threshold) {
    nextLeft = maxScroll;
  }
  row.scrollTo({ left: Math.max(0, Math.min(maxScroll, nextLeft)), behavior: "smooth" });
}

function syncRecommendationCarousel() {
  const shell = document.querySelector("[data-recommend-carousel]");
  const row = shell?.querySelector(".mixed-recommend-row");
  const shouldRun = state.view === "all" && row && row.children.length > 3;

  if (!shouldRun) {
    clearRecommendationCarousel();
    return;
  }

  if (!shell.dataset.carouselBound) {
    shell.dataset.carouselBound = "1";
    shell.addEventListener("mouseenter", () => {
      state.recommendCarouselPaused = true;
    });
    shell.addEventListener("mouseleave", () => {
      state.recommendCarouselPaused = false;
    });
    shell.addEventListener("focusin", () => {
      state.recommendCarouselPaused = true;
    });
    shell.addEventListener("focusout", () => {
      state.recommendCarouselPaused = false;
    });
  }

  if (recommendCarouselTimer) return;
  recommendCarouselTimer = window.setInterval(() => {
    if (state.view !== "all" || state.recommendCarouselPaused) return;
    const maxScroll = Math.max(0, row.scrollWidth - row.clientWidth);
    if (maxScroll <= 0) return;
    if (row.scrollLeft >= maxScroll - 2) {
      row.scrollLeft = 0;
      return;
    }
    row.scrollLeft += 1.1;
  }, 32);
}

function getModeForView(view) {
  if (view === "favorite") return "favorite";
  if (view === "recent") return "recent";
  return "all";
}

function getLibrarySourceForView(view) {
  return "combined";
}

async function loadReport() {
  if (state.reportData && state.hasAnalyticsData !== undefined) return;
  const [reportPayload, analyticsPayload, hasDataPayload] = await Promise.all([
    guarded(() => api("/api/report"), false),
    guarded(() => api("/api/analytics/full-report"), false),
    guarded(() => api("/api/analytics/has-data"), false)
  ]);
  
  state.reportData = reportPayload || {};
  state.analyticsData = analyticsPayload || {};
  state.hasAnalyticsData = hasDataPayload?.has_data || false;
}

