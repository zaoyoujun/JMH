
// 应用状态管理
const state = {
  view: "all",
  search: "",
  config: null,
  stats: { all: 0, remote: 0, local: 0, favorite: 0, recent: 0 },
  items: [],
  recommendationItems: [],
  externalRecommendations: [],
  recommendationProfile: null,
  recommendationStats: null,
  recommendationGeneratedAt: 0,
  heroCarouselIndex: 0,
  recommendCarouselPaused: false,
  recommendFilter: { type: "", sort: "score" },
  selectedMovie: null,
  selectedSeasonPath: "",
  selectedEpisode: 0,
  editMovie: null,
  webdavDirs: new Set(),
  localDirs: new Set(),
  directoryScope: "webdav",
  directoryPath: "/",
  directoryItems: [],
  candidateMovie: null,
  candidateSelection: null,
  candidateItems: [],
  candidateDiagnostics: [],
  candidateSearchText: "",
  candidateStatus: null,
  activeJobId: null,
  searchTimer: null,
  allTags: {},
  tagInputValue: "",
  reportData: null,
  openlistStatus: null,
  openlistStorages: [],
  openlistDrivers: [],
  openlistDriverForm: null,
};

// 视图元数据
const _viewMetaZH = {
  all: { kicker: "媒体库", title: "我的片库", subtitle: "集中浏览本地与 WebDAV 的影视内容。" },
  recommend: { kicker: "推荐", title: "为你推荐", subtitle: "根据收藏、播放进度、标签和评分生成个性化推荐。" },
  favorite: { kicker: "收藏", title: "我的收藏", subtitle: "保留你想长期留着的影片和剧集。" },
  recent: { kicker: "最近播放", title: "最近播放", subtitle: "回到最近看过的内容，接着播放。" },
  settings: { kicker: "设置", title: "应用设置", subtitle: "管理片库来源、播放器和扫描目录。" },
  report: { kicker: "报告", title: "观影报告", subtitle: "基于你的收藏、播放和评分生成可视化观影分析。" },
};
function viewMetaFor(key) {
  const m = _viewMetaZH[key];
  return { kicker: m.kicker, title: m.title, subtitle: m.subtitle };
}

// DOM 元素引用
const elements = {
  contentShell: document.getElementById("contentShell"),
  statsStrip: document.getElementById("statsStrip"),
  navList: document.getElementById("navList"),
  searchInput: document.getElementById("searchInput"),
  refreshBtn: document.getElementById("refreshBtn"),
  toastHost: document.getElementById("toastHost"),
  sidebarStatus: document.getElementById("sidebarStatus"),
  jobBanner: document.getElementById("jobBanner"),
  jobTitle: document.getElementById("jobTitle"),
  jobMessage: document.getElementById("jobMessage"),
  jobProgressText: document.getElementById("jobProgressText"),
  jobProgressBar: document.getElementById("jobProgressBar"),
};

let heroCarouselTimer = null;
let recommendCarouselTimer = null;

const _themeOptionsBase = [
  { value: "amber", label: "暖光" },
  { value: "graphite", label: "石墨" },
  { value: "forest", label: "森绿" },
  { value: "coast", label: "海岸" },
];
function getThemeOptions() { return _themeOptionsBase; }

const _remoteProviderOptionsBase = [
  { value: "openlist", label: "OpenList 网盘" },
  { value: "webdav", label: "WebDAV" },
];
function getRemoteProviderOptions() { return _remoteProviderOptionsBase; }

const _remoteProviderPresetsBase = {
  webdav: {
    host: "",
    placeholder: "http://host:port",
    help: "适合群晖、坚果云、rclone 等标准 WebDAV 入口，使用账号密码连接。",
  },
  openlist: {
    host: "",
    placeholder: "自动连接本地内置 OpenList",
    help: "使用内置 OpenList 网盘服务，支持夸克、阿里云盘、115、百度网盘等多种网盘。在下方 OpenList 管理面板中添加存储驱动后，挂载目录会自动列出。",
  },
};
function getRemoteProviderPresets() { return _remoteProviderPresetsBase; }

function getRemoteProfiles(config = state.config || {}) {
  const normalizeRemoteMountDirs = (dirs) => {
    return Array.isArray(dirs) ? dirs.map((item) => String(item).trim()).filter(Boolean) : [];
  };
  const base = {
    webdav: { webdav_host: "", webdav_user: "", webdav_pass: "", remote_cookie: "", openlist_source_mode: "builtin", saved_mount_dirs: [] },
    openlist: { webdav_host: "", webdav_user: "", webdav_pass: "", remote_cookie: "", openlist_source_mode: "builtin", saved_mount_dirs: [] },
  };
  const source = config.remote_profiles && typeof config.remote_profiles === "object" ? config.remote_profiles : {};
  Object.keys(base).forEach((provider) => {
    const raw = source[provider] || {};
    base[provider] = {
      webdav_host: String(raw.webdav_host || "").trim(),
      webdav_user: String(raw.webdav_user || "").trim(),
      webdav_pass: String(raw.webdav_pass || "").trim(),
      remote_cookie: String(raw.remote_cookie || "").trim(),
      openlist_source_mode: normalizeOpenListSourceMode(raw.openlist_source_mode || (provider === "openlist" ? config.openlist_source_mode : "builtin")),
      saved_mount_dirs: normalizeRemoteMountDirs(raw.saved_mount_dirs),
    };
  });
  const currentProvider = normalizeRemoteProvider(config.remote_provider);
  base[currentProvider] = {
    webdav_host: String(config.webdav_host || base[currentProvider].webdav_host || "").trim(),
    webdav_user: String(config.webdav_user || base[currentProvider].webdav_user || "").trim(),
    webdav_pass: String(config.webdav_pass || base[currentProvider].webdav_pass || "").trim(),
    remote_cookie: String(config.remote_cookie || base[currentProvider].remote_cookie || "").trim(),
    openlist_source_mode: normalizeOpenListSourceMode(config.openlist_source_mode || base[currentProvider].openlist_source_mode || "builtin"),
    saved_mount_dirs: normalizeRemoteMountDirs(Array.isArray(config.saved_mount_dirs) ? config.saved_mount_dirs : (base[currentProvider].saved_mount_dirs || [])),
  };
  return base;
}

function normalizeOpenListSourceMode(mode) {
  const value = String(mode || "").trim().toLowerCase();
  return value === "external" ? "external" : "builtin";
}

function getOpenListSourceMode(config = state.config || {}) {
  const provider = normalizeRemoteProvider(config.remote_provider);
  const profiles = getRemoteProfiles(config);
  if (provider === "openlist") {
    return normalizeOpenListSourceMode(config.openlist_source_mode || profiles.openlist?.openlist_source_mode);
  }
  return normalizeOpenListSourceMode(profiles.openlist?.openlist_source_mode);
}

function formatRemotePathLabel(path) {
  return String(path || "");
}

function formatMovieSourcePath(movie) {
  if (!movie) return "未知路径";
  const rawPath = String(movie.path || "").trim();
  return rawPath || "未知路径";
}

function getRemoteRootPath() {
  return "/";
}

function normalizeRemoteDirectoryPath(path) {
  let value = String(path || "/").trim().replace(/\\/g, "/");
  if (!value) value = "/";
  value = value.replace(/\/+/g, "/");
  if (!value.startsWith("/")) value = `/${value}`;
  return value.length > 1 ? value.replace(/\/+$/, "") : "/";
}

function isRemoteRootPath(path) {
  return normalizeRemoteDirectoryPath(path) === "/";
}

function getRemoteParentPath(path) {
  const parentParts = normalizeRemoteDirectoryPath(path).split("/").filter(Boolean);
  parentParts.pop();
  return parentParts.length ? `/${parentParts.join("/")}` : "/";
}

function normalizeRemoteDirSetItems(items) {
  const normalized = [];
  const seen = new Set();
  for (const item of Array.isArray(items) ? items : []) {
    const value = normalizeRemoteDirectoryPath(item);
    if (seen.has(value)) continue;
    seen.add(value);
    normalized.push(value);
  }
  return normalized;
}

function resolveOpenListMountRoot(path) {
  const currentPath = normalizeRemoteDirectoryPath(path);
  const mounts = (state.openlistStorages || [])
    .map((item) => normalizeRemoteDirectoryPath(item.mount_path))
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  for (const mount of mounts) {
    if (currentPath === mount || currentPath.startsWith(`${mount}/`)) {
      return mount;
    }
  }
  return currentPath;
}

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindGlobalEvents();
  await loadBootstrap();
  await loadCurrentView();
}

function bindGlobalEvents() {
  elements.navList.addEventListener("click", async (event) => {
    const button = event.target.closest(".nav-item");
    if (!button) return;
    state.view = button.dataset.view;
    state.search = "";
    elements.searchInput.value = "";
    await loadCurrentView();
  });

  elements.searchInput.addEventListener("input", () => {
    state.search = elements.searchInput.value.trim();
    window.clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(() => {
      if (isListView(state.view)) {
        loadCurrentView();
      }
    }, 220);
  });

  elements.refreshBtn.addEventListener("click", async () => {
    if (state.view === "recommend") {
      await refreshRecommendations(true);
      return;
    }

    if (state.view === "report") {
      state.reportData = null;
      await loadReport();
      render();
      return;
    }

    if (state.view === "recent") {
      if (state.items.length === 0) {
        showToast("暂无播放记录", "info");
        return;
      }
      const confirmed = window.confirm("确定清除所有最近播放记录吗？");
      if (!confirmed) return;
      const response = await guarded(() =>
        api("/api/movies/recent", { method: "DELETE" })
      );
      if (response !== null) {
        showToast("最近播放已清除", "success");
        state.items = [];
        render();
      }
      return;
    }

    const persisted = await persistSettingsIfNeeded({ silent: true });
    if (persisted === null) return;

    const source = getMaintenanceSource();
    if (!source) {
      showToast("当前视图没有可刷新的片库。", "error");
      return;
    }
    if (!ensureSourceConfigured(source)) return;

    const response = await guarded(() =>
      api(`/api/library/refresh?source=${encodeURIComponent(source)}&auto_scrape=true`, { method: "POST" })
    );
    if (response) {
      startJobPolling(response.job_id, source, `${getSourceLabel(source)}刷新完成`);
    }
  });

  document.body.addEventListener("click", async (event) => {
    const closeTarget = event.target.closest("[data-close]");
    if (closeTarget) {
      closeModal(closeTarget.dataset.close);
      return;
    }

    const playBtn = event.target.closest("[data-play-movie]");
    if (playBtn) {
      await playMovie(playBtn.dataset.playMovie, Number(playBtn.dataset.episodeIndex || 0));
      return;
    }

    const favoriteBtn = event.target.closest("[data-toggle-favorite]");
    if (favoriteBtn) {
      await toggleFavorite(favoriteBtn.dataset.toggleFavorite);
      return;
    }

  const openDetailBtn = event.target.closest("[data-open-detail]");
  if (openDetailBtn) {
    const movie = getDisplayMovieByPath(openDetailBtn.dataset.openDetail) || state.items.find((item) => item.path === openDetailBtn.dataset.openDetail);
    if (movie) {
      await openDetail(movie);
    }
    return;
  }

  const heroPickBtn = event.target.closest("[data-hero-pick]");
  if (heroPickBtn) {
    const heroItems = getHomeHeroItems();
    const pickedIndex = heroItems.findIndex((item) => item.path === heroPickBtn.dataset.heroPick);
    if (pickedIndex >= 0) {
      state.heroCarouselIndex = pickedIndex;
      render();
    }
    return;
  }

  const recommendArrowBtn = event.target.closest("[data-recommend-arrow]");
  if (recommendArrowBtn) {
    scrollRecommendationCarousel(Number(recommendArrowBtn.dataset.recommendArrow || 1));
    return;
  }

  const filterTypeBtn = event.target.closest("[data-recommend-filter-type]");
  if (filterTypeBtn) {
    state.recommendFilter.type = filterTypeBtn.dataset.recommendFilterType;
    render();
    return;
  }

  const sortBtn = event.target.closest("[data-recommend-sort]");
  if (sortBtn) {
    state.recommendFilter.sort = sortBtn.dataset.recommendSort;
    render();
    return;
  }

    const editBtn = event.target.closest("[data-edit-movie]");
    if (editBtn) {
      const movie = state.items.find((item) => item.path === editBtn.dataset.editMovie) || state.selectedMovie;
      if (movie) openEditModal(movie);
      return;
    }

    const scrapeSingleBtn = event.target.closest("[data-scrape-movie]");
    if (scrapeSingleBtn) {
      await scrapeSingle(scrapeSingleBtn.dataset.scrapeMovie);
      return;
    }

    const manualMatchBtn = event.target.closest("[data-manual-match]");
    if (manualMatchBtn) {
      const movie = state.items.find((item) => item.path === manualMatchBtn.dataset.manualMatch) || state.selectedMovie;
      if (movie) openCandidateModal(movie);
      return;
    }

    const manageTagsBtn = event.target.closest("[data-manage-tags]");
    if (manageTagsBtn) {
      const movie = state.items.find((item) => item.path === manageTagsBtn.dataset.manageTags) || state.selectedMovie;
      if (movie) openTagsModal(movie);
      return;
    }

    const browseBtn = event.target.closest("[data-browse-dirs]");
    if (browseBtn) {
      const scope = browseBtn.dataset.browseDirs;
      await openDirectoryModal(scope, scope === "local" ? "" : getRemoteRootPath());
      return;
    }

    const removeDirBtn = event.target.closest("[data-remove-dir]");
    if (removeDirBtn) {
      getDirectorySet(removeDirBtn.dataset.removeScope).delete(removeDirBtn.dataset.removeDir);
      render();
      return;
    }

    const rateBtn = event.target.closest("[data-rate-movie]");
    if (rateBtn) {
      await rateRecommendation(rateBtn.dataset.rateMovie, Number(rateBtn.dataset.rating || 0));
    }
  });

  document.body.addEventListener("dblclick", async (event) => {
    const episodeBtn = event.target.closest("[data-episode-btn]");
    if (episodeBtn && state.selectedMovie) {
      const currentSeason = getActiveSeasonEntry(state.selectedMovie) || state.selectedMovie;
      await playMovie(currentSeason.path, Number(episodeBtn.dataset.episodeBtn || 0));
      return;
    }

    const directoryEnterBtn = event.target.closest("[data-enter-dir]");
    if (directoryEnterBtn) {
      await loadDirectoryPath(directoryEnterBtn.dataset.enterDir);
      return;
    }

    const directoryItem = event.target.closest("[data-directory-item]");
    if (directoryItem) {
      await loadDirectoryPath(directoryItem.dataset.directoryItem);
      return;
    }

    const mediaCard = event.target.closest("[data-card-play]");
    if (mediaCard) {
      await playMovie(mediaCard.dataset.cardPlay, Number(mediaCard.dataset.episodeIndex || 0));
    }
  });

  document.getElementById("editForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.editMovie) return;

    const formData = new FormData(event.currentTarget);
    const updates = {
      title: String(formData.get("title") || "").trim(),
      name: String(formData.get("name") || "").trim(),
      type: String(formData.get("type") || "").trim(),
      year: Number(formData.get("year") || 2024),
      intro: String(formData.get("intro") || "").trim(),
    };

    const response = await guarded(() =>
      api("/api/movies/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ movie_path: state.editMovie.path, updates }),
      })
    );
    if (!response) return;

    patchMovie(response.movie);
    closeModal("editModal");
    render();
    if (state.selectedMovie && state.selectedMovie.path === response.movie.path) {
      state.selectedMovie = response.movie;
      renderDetail();
    }
    showToast("影片信息已更新", "success");
  });

  document.getElementById("dirBackBtn").addEventListener("click", async () => {
    const root = getDirectoryRootPath();
    const isOpenlist = normalizeRemoteProvider(state.config?.remote_provider) === "openlist";

    // OpenList：在挂载点子目录中，返回上一级；如果已到挂载点根，返回挂载点列表
    if (isOpenlist && _openlistSelectedMount) {
      const parentPath = getRemoteParentPath(state.directoryPath);
      // 如果上一级还在挂载点范围内，继续返回
      if (parentPath.startsWith(_openlistSelectedMount) && parentPath !== _openlistSelectedMount) {
        await loadDirectoryPath(parentPath);
        return;
      }
      // 返回到挂载点列表
      _openlistSelectedMount = null;
      await loadDirectoryPath(root);
      return;
    }

    if (state.directoryPath === root) return;

    let nextPath = root;
    if (state.directoryScope === "local") {
      nextPath = getLocalParentPath(state.directoryPath);
    } else {
      nextPath = getRemoteParentPath(state.directoryPath);
    }
    await loadDirectoryPath(nextPath);
  });

  document.getElementById("dirSelectCurrentBtn").addEventListener("click", () => {
    if (state.directoryScope === "local" && !state.directoryPath) return;
    if (state.directoryScope === "webdav" && isRemoteRootPath(state.directoryPath)) return;
    getDirectorySet(state.directoryScope).add(state.directoryPath);
    renderDirectoryModal();
  });

  document.getElementById("dirConfirmBtn").addEventListener("click", () => {
    closeModal("directoryModal");
    render();
  });

  document.getElementById("candidateSearchBtn").addEventListener("click", async () => {
    await loadCandidates();
  });

  document.getElementById("candidateSearchInput").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    await loadCandidates();
  });

  document.getElementById("candidateApplyBtn").addEventListener("click", async () => {
    if (!state.candidateMovie || !state.candidateSelection) {
      showToast("请先选择一个候选结果。", "error");
      return;
    }

    const response = await guarded(() =>
      api("/api/movies/apply-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          movie_path: state.candidateMovie.path,
          candidate: state.candidateSelection,
        }),
      })
    );
    if (!response) return;

    patchMovie(response.movie);
    closeModal("candidateModal");
    await refreshMovieAfterMetadataChange(response.movie.path);
    showToast("元数据已应用", "success");
  });
}

async function api(url, options = {}) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒超时
    
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      let message = "请求失败";
      try {
        const payload = await response.json();
        message = payload.detail || payload.message || message;
      } catch (error) {
        message = response.statusText || message;
      }
      throw new Error(message);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接');
    } else if (!navigator.onLine) {
      throw new Error('网络连接已断开，请检查网络设置');
    }
    throw error;
  }
}

async function guarded(task, showLoadingFlag = false, loadingMessage = null) {
  if (!loadingMessage) loadingMessage = "加载中...";
  if (showLoadingFlag) {
    showLoading(loadingMessage);
  }
  
  try {
    const result = await task();
    if (showLoadingFlag) {
      hideLoading();
    }
    return result;
  } catch (error) {
    if (showLoadingFlag) {
      hideLoading();
    }
    showToast(error.message || "发生了未知错误", "error");
    return null;
  }
}

async function loadBootstrap() {
  const payload = await guarded(() => api("/api/bootstrap"), true, "正在初始化应用...");
  if (!payload) return;

  if (state.view === "local") {
    state.view = "all";
  }
  state.config = payload.config;
  state.stats = payload.stats;
  state.webdavDirs = new Set(normalizeRemoteDirSetItems(payload.config.saved_mount_dirs || []));
  state.localDirs = new Set(payload.config.local_mount_dirs || []);
  applyTheme(payload.config.ui_theme || payload.config.interface_theme);
  updateSidebarStatus();
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
  const payload = await guarded(() => api("/api/recommendations"), showLoading, "正在生成个性化推荐...");
  if (!payload) return;
  state.recommendationItems = payload.items || [];
  state.externalRecommendations = payload.external_items || [];
  state.recommendationProfile = payload.profile || null;
  state.recommendationStats = payload.stats || null;
  state.recommendationGeneratedAt = payload.generated_at || 0;
  render();
}

async function refreshRecommendations(showToastAfter = false) {
  const payload = await guarded(() => api("/api/recommendations/refresh", { method: "POST" }), true, "正在更新推荐画像...");
  if (!payload) return;
  state.recommendationItems = payload.items || [];
  state.externalRecommendations = payload.external_items || [];
  state.recommendationProfile = payload.profile || null;
  state.recommendationGeneratedAt = payload.generated_at || 0;
  state.recommendationStats = payload.stats || null;
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

function normalizeTheme(theme) {
  const value = String(theme || "").trim().toLowerCase();
  return getThemeOptions().some((item) => item.value === value) ? value : "amber";
}

function applyTheme(theme) {
  const nextTheme = normalizeTheme(theme);
  document.documentElement.dataset.theme = nextTheme;
  if (state.config) {
    state.config.ui_theme = nextTheme;
    state.config.interface_theme = nextTheme;
  }
}

function getModeForView(view) {
  if (view === "favorite") return "favorite";
  if (view === "recent") return "recent";
  return "all";
}

function getLibrarySourceForView(view) {
  return "combined";
}

function getSeasonLabel(movie, fallbackIndex = 0) {
  const seasonNumber = Number(movie?.season || fallbackIndex + 1 || 1);
  return `\u7b2c ${seasonNumber} \u5b63`;
}

function getSeasonEntryLabel(entry, groupMovie = null, fallbackIndex = 0) {
  const seasonLabel = getSeasonLabel(entry, fallbackIndex);
  const rawTitle = String(entry?.title || entry?.name || "").trim();
  const groupTitle = String(groupMovie?.title || groupMovie?.name || "").trim();
  let suffix = rawTitle;
  if (groupTitle && suffix.startsWith(groupTitle)) {
    suffix = suffix.slice(groupTitle.length).trim();
  }
  suffix = suffix
    .replace(/\u7b2c\s*[\d\u4e00-\u5341]+\s*\u5b63/gi, " ")
    .replace(/season\s*\d+/gi, " ")
    .replace(/[#＃]\d+/g, (match) => ` ${match} `)
    .replace(/[（(]/g, " ")
    .replace(/[）)]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^[·:：\-_\s]+/, "")
    .trim();
  if (!suffix) return seasonLabel;
  const normalizedSuffix = normalizeSeriesFolderName(suffix);
  const normalizedGroup = normalizeSeriesFolderName(groupTitle);
  if (!normalizedSuffix || normalizedSuffix === normalizedGroup) return seasonLabel;
  return `${seasonLabel} · ${suffix}`;
}

function normalizeSeriesFolderName(name) {
  return String(name || "")
    .trim()
    .replace(/\u7b2c\s*[\d\u4e00-\u5341]+\s*\u5b63/gi, " ")
    .replace(/season\s*\d+/gi, " ")
    .replace(/s\d{1,2}/gi, " ")
    .replace(/[#＃]\d+/g, " ")
    .replace(/[（(].*?(季|篇|part|final|上|下).*?[)）]/gi, " ")
    .replace(/[._()\[\]-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function getSeriesPathGroupName(movie) {
  const rawPath = String(movie?.path || "");
  if (!rawPath) return "";
  const parts = rawPath.split(/[\\/]+/).filter(Boolean);
  if (parts.length < 4) return "";
  const parent = parts[parts.length - 2];
  const grandparent = parts[parts.length - 3];
  const parentKey = normalizeSeriesFolderName(parent);
  const grandparentKey = normalizeSeriesFolderName(grandparent);
  const parentLooksSeason = /(\u7b2c\s*[\d\u4e00-\u5341]+\s*\u5b63|season\s*\d+|s\d{1,2}|[#＃]\d+|上|下|part)/i.test(parent);
  const genericFolders = new Set([
    "all", "video", "videos", "update", "updates", "webdav", "local", "library", "media",
    "更新中", "动画", "动漫", "剧集", "电视剧", "电影", "综艺", "纪录片", "anime", "shows", "series", "movies"
  ]);
  if (parentLooksSeason && grandparentKey && grandparentKey.length > 1 && !genericFolders.has(grandparentKey)) {
    return grandparentKey;
  }
  return "";
}

function normalizeSeriesKey(movie) {
  const pathBase = getSeriesPathGroupName(movie);
  const titleBase = normalizeSeriesFolderName(movie?.title || movie?.name || "");
  let base = pathBase || titleBase;
  if (!pathBase && /[\u4e00-\u9fff]/.test(String(movie?.title || ""))) {
    const collapsed = String(movie?.title || "")
      .replace(/[（(].*?[)）]/g, " ")
      .replace(/\u7b2c\s*\d+\s*\u5b63/gi, " ")
      .replace(/season\s*\d+/gi, " ")
      .replace(/[#＃]\d+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const firstChunk = collapsed.split(" ")[0];
    if (firstChunk && /[\u4e00-\u9fff]/.test(firstChunk)) {
      base = normalizeSeriesFolderName(firstChunk);
    }
  }
  const source = String(movie?.source || movie?.source_label || "");
  return `${base}::${source}`;
}

function buildGroupedSeries(groupItems) {
  const seasons = [...groupItems].sort((left, right) => Number(left.season || 0) - Number(right.season || 0));
  const primary = seasons.find((item) => item.cover_url || item.intro) || seasons[0];
  const tags = [...new Set(seasons.flatMap((item) => (Array.isArray(item.tags) ? item.tags : [])))];
  const totalEpisodes = seasons.reduce(
    (sum, item) => sum + Number(item.episode_count || item.episode_files?.length || 0),
    0
  );
  const labels = [...new Set(seasons.map((item) => item.source_label).filter(Boolean))];
  const latestPlaybackSeason = seasons
    .filter((item) => item.playback?.has_progress)
    .sort((left, right) => Number(right.playback?.timestamp || 0) - Number(left.playback?.timestamp || 0))[0] || null;
  const playback = latestPlaybackSeason?.playback || {
    progress: 0,
    duration: 0,
    percent: 0,
    timestamp: 0,
    has_progress: false,
  };
  const resumeSeasonLabel = latestPlaybackSeason
    ? getSeasonLabel(latestPlaybackSeason, seasons.indexOf(latestPlaybackSeason))
    : "";
  return {
    ...primary,
    title: primary.title || primary.name,
    name: primary.name || primary.title,
    seasons,
    season_count: seasons.length,
    episode_count: totalEpisodes,
    is_grouped_series: seasons.length > 1,
    is_favorite: seasons.some((item) => item.is_favorite),
    source_label: labels.join(" / ") || primary.source_label || "媒体库",
    tags,
    path: primary.path,
    playback,
    resume_path: latestPlaybackSeason?.path || primary.path,
    resume_season_label: resumeSeasonLabel,
  };
}

function getDisplayItems(items = state.items) {
  const grouped = new Map();
  for (const item of items) {
    if (!item?.is_series) continue;
    const key = normalizeSeriesKey(item);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  }

  const displayItems = [];
  const seenGroups = new Set();
  for (const item of items) {
    if (!item?.is_series) {
      displayItems.push(item);
      continue;
    }
    const key = normalizeSeriesKey(item);
    if (seenGroups.has(key)) continue;
    seenGroups.add(key);
    const groupItems = grouped.get(key) || [item];
    displayItems.push(buildGroupedSeries(groupItems));
  }
  return displayItems;
}

function getDisplayMovieByPath(moviePath) {
  return getDisplayItems().find((item) => {
    if (item.path === moviePath) return true;
    return Array.isArray(item.seasons) && item.seasons.some((season) => season.path === moviePath);
  });
}

function getActiveSeasonEntry(movie) {
  if (!movie) return null;
  const seasons = Array.isArray(movie.seasons) && movie.seasons.length ? movie.seasons : [movie];
  return seasons.find((item) => item.path === state.selectedSeasonPath) || seasons[0] || null;
}

function syncSelectedMovie() {
  if (!state.selectedMovie) return;
  const lookupPath = state.selectedSeasonPath || state.selectedMovie.path;
  const nextMovie = getDisplayMovieByPath(lookupPath);
  if (nextMovie) {
    state.selectedMovie = nextMovie;
  }
}


function formatPlaybackText(playback) {
  if (!playback?.has_progress) return "";
  return `${"已观看"} ${playback.percent}%`;
}

function formatResumeHint(movie) {
  if (!movie?.playback?.has_progress) return "";
  const seasonLabel = movie.resume_season_label ? `${movie.resume_season_label} · ` : "";
  return `${seasonLabel}${formatPlaybackText(movie.playback)}`;
}


function getMaintenanceSource() {
  if (state.view === "all" || state.view === "favorite" || state.view === "recent") return "combined";
  return null;
}

function hasConfiguredScanTargets(config) {
  const remoteDirs = getAllRemoteMountDirs(config);
  const localDirs = Array.isArray(config?.local_mount_dirs) ? config.local_mount_dirs : [];
  return remoteDirs.length > 0 || localDirs.length > 0;
}

function getInitialRefreshSource(config) {
  const hasRemoteDirs = getAllRemoteMountDirs(config).length > 0;
  const hasLocalDirs = Array.isArray(config?.local_mount_dirs) && config.local_mount_dirs.length > 0;
  if (hasRemoteDirs && hasLocalDirs) return "combined";
  if (hasLocalDirs) return "local";
  if (hasRemoteDirs) return "remote";
  return null;
}

function normalizeDirList(list) {
  return [...new Set((Array.isArray(list) ? list : []).map((item) => String(item || "").trim()).filter(Boolean))].sort();
}

function getAllRemoteMountDirs(config) {
  const profiles = getRemoteProfiles(config);
  const merged = [];
  Object.values(profiles).forEach((profile) => {
    merged.push(...(Array.isArray(profile?.saved_mount_dirs) ? profile.saved_mount_dirs : []));
  });
  return normalizeDirList(merged);
}

function getAddedDirectories(nextList, currentList) {
  const currentSet = new Set(normalizeDirList(currentList));
  return normalizeDirList(nextList).filter((item) => !currentSet.has(item));
}

function getPendingMountChanges(payload) {
  const currentRemote = getAllRemoteMountDirs(state.config);
  const currentLocal = normalizeDirList(state.config?.local_mount_dirs || []);
  const nextRemote = getAllRemoteMountDirs(payload);
  const nextLocal = normalizeDirList(payload.local_mount_dirs || []);

  const remoteChanged = currentRemote.join("|") !== nextRemote.join("|");
  const localChanged = currentLocal.join("|") !== nextLocal.join("|");

  return {
    remoteChanged,
    localChanged,
    hasChanges: remoteChanged || localChanged,
    addedRemote: getAddedDirectories(nextRemote, currentRemote),
    addedLocal: getAddedDirectories(nextLocal, currentLocal),
  };
}

function getRefreshSourceForDirectoryChanges(addedRemote, addedLocal, config) {
  if (addedRemote.length && addedLocal.length) return "combined";
  if (addedLocal.length) return "local";
  if (addedRemote.length) return "remote";
  return getInitialRefreshSource(config);
}

function applyConfigResult(result) {
  if (state.view === "local") {
    state.view = "all";
  }
  state.config = result;
  state.webdavDirs = new Set(normalizeRemoteDirSetItems(result.saved_mount_dirs || []));
  state.localDirs = new Set(result.local_mount_dirs || []);
  applyTheme(result.ui_theme || result.interface_theme);
  updateSidebarStatus();
}

async function persistSettingsIfNeeded(options = {}) {
  const { silent = false, force = false } = options;
  const payload = getSettingsPayload();
  const changeInfo = getPendingMountChanges(payload);
  if (!force && !changeInfo.hasChanges) {
    return {
      result: state.config,
      payload,
      saved: false,
      ...changeInfo,
    };
  }

  const result = await guarded(() =>
    api("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    !silent,
    "正在保存挂载目录..."
  );
  if (!result) return null;

  applyConfigResult(result);
  render();
  return {
    result,
    payload,
    saved: true,
    ...changeInfo,
  };
}

function getSourceLabel(source) {
  if (source === "combined") return "影视库";
  if (source === "local") return "本地片库";
  return `${state.config?.remote_provider_label || "远程"}${"片库"}`;
}

function ensureSourceConfigured(source) {
  if (source === "combined" && !state.config?.has_any_library) {
    showToast("先在设置中配置 WebDAV 或本地扫描目录。", "error");
    state.view = "settings";
    render();
    return false;
  }
  if (source === "local" && !state.config?.has_local_config) {
    showToast("先在设置中配置本地扫描目录。", "error");
    state.view = "settings";
    render();
    return false;
  }
  if (source === "remote" && !state.config?.has_basic_config) {
    showToast("先在设置中完成远程媒体源配置。", "error");
    state.view = "settings";
    render();
    return false;
  }
  return true;
}

function updateSidebarStatus() {
  if (!state.config) return;

  let label = "等待完成媒体源配置";
  let color = "#d97d38";
  let glow = "rgba(217, 125, 56, 0.16)";
  const providerLabel = state.config.remote_provider_label || "远程媒体源";

  if (state.config.has_basic_config && state.config.has_local_config) {
    label = `${providerLabel}${"远程媒体源与本地目录都已就绪"}`;
    color = "#49c28d";
    glow = "rgba(73, 194, 141, 0.15)";
  } else if (state.config.has_basic_config) {
    label = `${providerLabel}${"远程媒体源已连接，本地目录未配置"}`;
    color = "#49c28d";
    glow = "rgba(73, 194, 141, 0.15)";
  } else if (state.config.has_local_config) {
    label = `${"本地目录已配置，"}${providerLabel}${"远程媒体源未连接"}`;
    color = "#49c28d";
    glow = "rgba(73, 194, 141, 0.15)";
  }

  sidebarStatus.innerHTML = `
    <span class="status-dot" style="background:${color}; box-shadow: 0 0 0 6px ${glow}"></span>
    <span>${label}</span>
  `;
}

function render() {
  syncHeroCarousel();
  renderTopMeta();
  renderNav();
  renderStats();
  renderToolbarState();
  disposeReportCharts();

  if (state.view === "settings") {
    elements.contentShell.innerHTML = renderSettingsView();
    bindSettingsView();
    if (_currentSettingsTab === "openlist") {
      initOpenListPanel();
    }
    clearRecommendationCarousel();
    return;
  }

  if (state.view === "recommend") {
    elements.contentShell.innerHTML = renderRecommendationView();
    clearRecommendationCarousel();
    return;
  }

  if (state.view === "report") {
    elements.contentShell.innerHTML = renderReportView();
    clearRecommendationCarousel();
    requestAnimationFrame(() => initReportCharts());
    return;
  }

  if (state.view === "all" && !state.config?.has_any_library) {
    elements.contentShell.innerHTML = renderSetupState(
      "还没有接入影视库",
      "接入 WebDAV 或本地目录之后，这里会自动汇总成一个片库。",
      "去设置里接入媒体源"
    );
    clearRecommendationCarousel();
    return;
  }


  const displayItems = getDisplayItems();
  if (!displayItems.length) {
    elements.contentShell.innerHTML = renderEmptyState();
    clearRecommendationCarousel();
    return;
  }

  const heroItems = getHomeHeroItems();
  const featured = heroItems[0] || displayItems[0];
  elements.contentShell.innerHTML = `
    <div class="library-home">
      ${renderShelfHero(featured, heroItems)}
      ${state.view === "all" ? renderHomeRecommendationSection() : ""}
      <section class="library-grid-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${getCollectionEyebrow()}</span>
            <h3>${getCollectionTitle()}</h3>
          </div>
          <p>${getCollectionSummary()}</p>
        </div>
        <div class="library-grid">
          ${displayItems.map(renderMovieCard).join("")}
        </div>
      </section>
    </div>
  `;
  syncRecommendationCarousel();
}

function renderTopMeta() {
  const meta = viewMetaFor(state.view);
  document.getElementById("headlineKicker").textContent = meta.kicker;
  document.getElementById("pageTitle").textContent = meta.title;
  document.getElementById("pageSubtitle").textContent = meta.subtitle;
}

function renderNav() {
  navList.querySelector('[data-view="local"]')?.remove();
  navList.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function renderToolbarState() {
  const source = getMaintenanceSource();
  const searchEnabled = isListView(state.view);
  elements.searchInput.disabled = !searchEnabled;
  elements.searchInput.placeholder = "按标题、别名、简介筛选";

  if (state.view === "recommend") {
    elements.refreshBtn.textContent = "刷新推荐";
    elements.refreshBtn.disabled = false;
    return;
  }

  if (state.view === "report") {
    elements.refreshBtn.textContent = "刷新报告";
    elements.refreshBtn.disabled = false;
    return;
  }

  if (state.view === "recent") {
    elements.refreshBtn.textContent = "清除最近播放";
    elements.refreshBtn.disabled = false;
    return;
  }

  const label = getSourceLabel(source);
  elements.refreshBtn.textContent = "扫描并更新" + label;
  elements.refreshBtn.disabled = !Boolean(source);
}

function getCollectionEyebrow() {
  if (state.search) return `${"搜索结果"} ${state.items.length}`;
  if (state.view === "favorite") return "收藏片单";
  if (state.view === "recent") return "继续观看";
  return "整库浏览";
}

function getCollectionTitle() {
  if (state.search) return `"${escapeHtml(state.search)}" ${"的结果"}`;
  if (state.view === "favorite") return "你最常回看的内容";
  if (state.view === "recent") return "上次看到这里";
  return "整合后的影视库";
}

function getCollectionSummary() {
  const total = state.items.length;
  if (state.search) return `共找到 ${total} 个匹配项。`;
  if (state.view === "all") return "本地与远程内容会统一陈列，播放、收藏和补全都在同一个视图里完成。";
  if (state.view === "favorite") return "把常看和舍不得删的作品留在手边。";
  return "从最近打开的内容继续往下看。";
}

function renderShelfHero(movie, heroItems = []) {
  const items = heroItems.length ? heroItems : (movie ? [movie] : []);
  if (!items.length) return "";
  const activeIndex = state.heroCarouselIndex % items.length;
  const activeMovie = items[activeIndex] || movie || items[0];
  const cover = activeMovie.cover_url
    ? `<img src="${activeMovie.cover_url}" alt="${escapeHtml(activeMovie.title || activeMovie.name || "封面")}">`
    : `<div class="shelf-hero-backdrop fallback"></div>`;
  const title = escapeHtml(activeMovie.title || activeMovie.name || "未命名");
  const resumeHint = formatResumeHint(activeMovie);
  const progressPercent = Number(activeMovie.playback?.percent || 0);
  const playPath = activeMovie.resume_path || activeMovie.path;
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
              ${item.cover_url ? `<img src="${escapeAttr(item.cover_url)}" alt="${escapeHtml(item.title || item.name || "封面")}">` : `<span>${escapeHtml(item.title || item.name || "未命名")}</span>`}
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
            <button class="primary-btn" data-play-movie="${escapeAttr(playPath)}" data-episode-index="0">${resumeHint ? "继续播放" : "立即播放"}</button>
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

function renderStats() {
  if (state.view === "recommend") {
    const stats = state.recommendationStats || {};
    elements.statsStrip.innerHTML = `
      <article class="stat-chip">
        <strong>${stats.library_recommendations || 0}</strong>
        <span>${"库内推荐"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.external_recommendations || 0}</strong>
        <span>${"站外发现"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.profile_tags || 0}</strong>
        <span>${"偏好标签"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.seed_count || 0}</strong>
        <span>${"画像样本"}</span>
      </article>
    `;
    return;
  }
  elements.statsStrip.innerHTML = `
    <article class="stat-chip">
      <strong>${state.stats.all || 0}</strong>
      <span>${"全部条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.remote || 0}</strong>
      <span>${"远程条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.local || 0}</strong>
      <span>${"本地条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.favorite || 0}</strong>
      <span>${"收藏条目"}</span>
    </article>
  `;
}

function renderMovieCard(movie) {
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(movie.title)}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const episodeMeta = movie.is_series
    ? `${movie.season_count > 1 ? `${movie.season_count} ${"季"} / ` : ""}${movie.episode_count} ${"集"}`
    : "单片";
  const title = escapeHtml(movie.title || movie.name || "未命名");
  const tags = Array.isArray(movie.tags) ? movie.tags.slice(0, 2) : [];
  const progressPercent = Number(movie.playback?.percent || 0);
  const resumeHint = formatResumeHint(movie);
  const playPath = movie.resume_path || movie.path;

  return `
    <article class="media-card" data-card-play="${escapeAttr(playPath)}" data-episode-index="0" title="${"双击直接播放"}">
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
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(playPath)}" data-episode-index="0">${resumeHint ? "继续" : "播放"}</button>
          <button class="poster-overlay-btn ${movie.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(movie.path)}">${movie.is_favorite ? "已藏" : "收藏"}</button>
        </div>
        ${progressPercent > 0 ? `<div class="card-progress"><span style="width:${progressPercent}%"></span></div>` : ""}
      </div>
      <div class="card-body">
        <h3 title="${title}">${title}</h3>
        <div class="card-meta">
          <span>${episodeMeta}</span>
          <span>${movie.is_grouped_series ? "多季已合并" : movie.is_favorite ? "已收藏" : "未收藏"}</span>
        </div>
        ${resumeHint ? `<div class="card-resume">${escapeHtml(resumeHint)}</div>` : ""}
        ${tags.length ? `<div class="card-inline-tags">${tags.map((tag) => `<span class="mini-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      </div>
    </article>
  `;
}

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

async function loadReport() {
  if (state.reportData) return;
  const payload = await guarded(() => api("/api/report"), true, "正在生成观影报告...");
  if (payload) {
    state.reportData = payload;
  }
}

const _reportChartInstances = [];
let _reportResizeBound = false;

function disposeReportCharts() {
  _reportChartInstances.forEach((chart) => {
    if (chart && !chart.isDisposed()) chart.dispose();
  });
  _reportChartInstances.length = 0;
}

function _bindReportResize() {
  if (_reportResizeBound) return;
  _reportResizeBound = true;
  window.addEventListener("resize", () => {
    _reportChartInstances.forEach((chart) => {
      if (chart && !chart.isDisposed()) chart.resize();
    });
  });
}

function initReportCharts() {
  disposeReportCharts();
  _bindReportResize();
  const d = state.reportData;
  if (!d || typeof echarts === "undefined") return;

  const theme = {
    bgColor: "transparent",
    textColor: "#c6d6f3",
    titleColor: "#e5efff",
    accent: "#e50914",
    palette: ["#e50914", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"],
  };

  // 1. 饼图：影片类型分布
  const pieEl = document.getElementById("reportPieChart");
  if (pieEl) {
    const chart = echarts.init(pieEl);
    _reportChartInstances.push(chart);
    const typeDist = d.type_distribution || [];
    chart.setOption({
      color: theme.palette,
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
      series: [{
        name: "类型占比",
        type: "pie",
        radius: ["40%", "70%"],
        itemStyle: { borderRadius: 6, borderColor: "#121a2f", borderWidth: 2 },
        label: { color: theme.textColor, fontSize: 12 },
        data: typeDist.map((item) => ({ value: item.count, name: item.name })),
      }],
    });
  }

  // 2. 折线图：观影热度趋势（年代分布）
  const lineEl = document.getElementById("reportLineChart");
  if (lineEl) {
    const chart = echarts.init(lineEl);
    _reportChartInstances.push(chart);
    const yearDist = d.year_distribution || [];
    chart.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: "category",
        data: yearDist.map((item) => item.name),
        axisLabel: { color: theme.textColor, fontSize: 11 },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: theme.textColor, fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
      },
      series: [{
        name: "影片数",
        type: "line",
        smooth: true,
        data: yearDist.map((item) => item.count),
        lineStyle: { color: theme.accent, width: 3 },
        itemStyle: { color: theme.accent },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(229,9,20,0.35)" },
            { offset: 1, color: "rgba(229,9,20,0.02)" },
          ]),
        },
      }],
    });
  }

  // 3. 条形图：热度排行榜
  const barEl = document.getElementById("reportBarChart");
  if (barEl) {
    const chart = echarts.init(barEl);
    _reportChartInstances.push(chart);
    const genres = (d.genre_preferences || []).slice(0, 8).reverse();
    chart.setOption({
      tooltip: { trigger: "axis" },
      grid: { left: 80, right: 30, top: 10, bottom: 20 },
      xAxis: {
        type: "value",
        axisLabel: { color: theme.textColor, fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
      },
      yAxis: {
        type: "category",
        data: genres.map((item) => item.name),
        axisLabel: { color: theme.textColor, fontSize: 12 },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      },
      series: [{
        type: "bar",
        data: genres.map((item) => item.weight),
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: "#3b82f6" },
            { offset: 1, color: "#e50914" },
          ]),
        },
      }],
    });
  }

  // 4. 雷达图：用户偏好画像
  const radarEl = document.getElementById("reportRadarChart");
  if (radarEl) {
    const chart = echarts.init(radarEl);
    _reportChartInstances.push(chart);
    const genres = (d.genre_preferences || []).slice(0, 6);
    const maxWeight = Math.max(1, ...genres.map((g) => g.weight));
    chart.setOption({
      radar: {
        indicator: genres.map((g) => ({ name: g.name, max: Math.ceil(maxWeight * 1.1) })),
        axisName: { color: theme.textColor, fontSize: 12 },
        splitArea: { areaStyle: { color: ["rgba(255,255,255,0.02)", "rgba(255,255,255,0.04)"] } },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      },
      series: [{
        type: "radar",
        data: [{
          value: genres.map((g) => g.weight),
          name: "偏好权重",
          areaStyle: { color: "rgba(229,9,20,0.25)" },
          lineStyle: { color: theme.accent, width: 2 },
          itemStyle: { color: theme.accent },
        }],
      }],
    });
  }
}

function renderReportView() {
  const d = state.reportData;
  if (!d) {
    return renderSetupState(
      "暂无观影数据",
      "开始收藏和播放影片后，这里会生成你的观影报告。",
      ""
    );
  }

  const overview = d.overview || {};
  const typeDist = d.type_distribution || [];
  const genres = d.genre_preferences || [];
  const completion = d.completion_stats || {};
  const activity = d.recent_activity || [];
  const warehouseStatus = d.warehouse_status || {};
  const warehouseText = warehouseStatus.connected ? "仓库在线" : (warehouseStatus.reason || "当前使用应用内分析");
  const topGenres = genres.slice(0, 4).map((item) => item.name).filter(Boolean);
  const typeOptions = ["全部类型", ...typeDist.map((item) => item.name).filter(Boolean).slice(0, 6)];
  const dimensionOptions = ["播放量", "用户评分", "收藏数"];

  const totalCompletion = (completion.completed || 0) + (completion.in_progress || 0) + (completion.not_started || 0) || 1;
  const completedPct = Math.round((completion.completed || 0) / totalCompletion * 100);
  const inProgressPct = Math.round((completion.in_progress || 0) / totalCompletion * 100);
  const notStartedPct = 100 - completedPct - inProgressPct;

  const overviewCards = [
    { label: "总片数", value: overview.total_movies || 0, unit: "" },
    { label: "已观看", value: overview.watched || 0, unit: "" },
    { label: "观影时长", value: overview.total_watch_hours || 0, unit: "小时" },
    { label: "平均评分", value: overview.avg_rating || 0, unit: "★" },
  ];

  return `
    <div class="report-shell">
      <section class="report-stage report-stage-board">
        <div class="report-stage-copy">
          <span class="section-eyebrow report-board-kicker">观影分析大屏</span>
          <h3>爆米花电影 · 数据可视化大屏</h3>
          <p>用户观影分析、片库热度变化和个性偏好会在这里汇总成更适合展示和扫读的分析面板。</p>
          <div class="report-stage-meta">
            <span>${warehouseText}</span>
            <span>${topGenres.length ? `偏好标签：${escapeHtml(topGenres.join(" / "))}` : "等待更多行为数据"}</span>
          </div>
        </div>
        <div class="report-stage-side">
          <div class="report-stage-orbit orbit-a"></div>
          <div class="report-stage-orbit orbit-b"></div>
          <div class="report-stage-radar">
            <strong>${overview.total_movies || 0}</strong>
            <small>总条目</small>
          </div>
        </div>
      </section>

      <section class="report-filter-bar">
        <label class="report-filter-item">
          <span>时间范围</span>
          <select>
            <option>近7天</option>
            <option selected>近30天</option>
            <option>近90天</option>
          </select>
        </label>
        <label class="report-filter-item">
          <span>影片类型</span>
          <select>
            ${typeOptions.map((item, index) => `<option ${index === 0 ? "selected" : ""}>${escapeHtml(item)}</option>`).join("")}
          </select>
        </label>
        <label class="report-filter-item">
          <span>数据维度</span>
          <select>
            ${dimensionOptions.map((item, index) => `<option ${index === 0 ? "selected" : ""}>${escapeHtml(item)}</option>`).join("")}
          </select>
        </label>
      </section>

      <div class="report-overview">
        ${overviewCards.map((c) => `
          <article class="report-kpi-card">
            <small>${c.label}${c.unit ? " " + c.unit : ""}</small>
            <strong>${c.value}</strong>
          </article>
        `).join("")}
      </div>

      <div class="report-grid">
        <section class="report-section">
          <div class="chart-title">影片类型分布</div>
          <div id="reportPieChart" class="report-chart-box"></div>
        </section>

        <section class="report-section">
          <div class="chart-title">观影热度趋势</div>
          <div id="reportLineChart" class="report-chart-box"></div>
        </section>

        <section class="report-section">
          <div class="chart-title">偏好标签排行榜</div>
          <div id="reportBarChart" class="report-chart-box"></div>
        </section>

        <section class="report-section">
          <div class="chart-title">用户偏好画像</div>
          <div id="reportRadarChart" class="report-chart-box"></div>
        </section>
      </div>

      <div class="report-grid report-grid-bottom">
        <section class="report-section">
          <div class="chart-title">完播统计</div>
          <div class="completion-rings">
            <div class="ring-item">
              <div class="ring-progress" style="--pct:${completedPct};--color:var(--success)">${completedPct}%</div>
              <span>已看完</span>
            </div>
            <div class="ring-item">
              <div class="ring-progress" style="--pct:${inProgressPct};--color:var(--teal)">${inProgressPct}%</div>
              <span>在看</span>
            </div>
            <div class="ring-item">
              <div class="ring-progress" style="--pct:${notStartedPct};--color:var(--text-faint)">${notStartedPct}%</div>
              <span>未开始</span>
            </div>
          </div>
        </section>

        <section class="report-section report-timeline-section">
          <div class="chart-title">近期动态</div>
          <div class="timeline">
            ${activity.length ? activity.map((a) => {
              const date = a.timestamp ? new Date(a.timestamp * 1000) : null;
              const dateStr = date ? `${date.getMonth() + 1}/${date.getDate()}` : "";
              return `
                <div class="timeline-item">
                  <span class="timeline-date">${dateStr}</span>
                  <span class="timeline-type">${escapeHtml(a.type)}</span>
                  <span class="timeline-title">${escapeHtml(a.title)}</span>
                  <div class="timeline-progress"><span style="width:${a.progress}%"></span></div>
                </div>
              `;
            }).join("") : `<span class="text-faint">暂无数据</span>`}
          </div>
        </section>
      </div>
    </div>
  `;
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

function reasonClass(reason) {
  if (/偏好标签/.test(reason)) return "reason-tag";
  if (/风格接近/.test(reason)) return "reason-similar";
  if (/最近偏好/.test(reason)) return "reason-type";
  if (/年代/.test(reason)) return "reason-year";
  if (/评分/.test(reason)) return "reason-rating";
  return "";
}

function renderRecommendationCard(movie) {
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(movie.title || movie.name || "封面")}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const title = escapeHtml(movie.title || movie.name || "未命名");
  const reasons = (movie.recommendation_reasons || []).slice(0, 3);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const breakdown = movie.recommendation_breakdown || {};
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
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(movie.resume_path || movie.path)}" data-episode-index="0">${"播放"}</button>
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
  const cover = movie.cover_url
    ? `<img src="${movie.cover_url}" alt="${escapeHtml(movie.title || movie.name || "封面")}">`
    : `<div class="poster-fallback">${"暂无封面"}</div>`;
  const title = escapeHtml(movie.title || movie.name || "未命名");
  const rawReason = (movie.recommendation_reasons || [])[0] || "和你最近常看的内容气质接近";
  const reason = escapeHtml(rawReason);
  const reasonCls = reasonClass(rawReason);
  const score = Math.round(Number(movie.recommendation_score || 0) * 100);
  const playPath = movie.resume_path || movie.path;
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
          <button class="poster-overlay-btn primary" data-play-movie="${escapeAttr(playPath)}" data-episode-index="0">${"播放"}</button>
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
const SETTINGS_TABS = [
  { id: "media", icon: "🌐", label: "媒体源", desc: "连接远程片库和扫描目录" },
  { id: "player", icon: "▶️", label: "播放与本地", desc: "本地目录、播放器和格式" },
  { id: "openlist", icon: "☁️", label: "OpenList", desc: "网盘聚合、挂载和状态" },
  { id: "appearance", icon: "🎨", label: "界面与刮削", desc: "主题、语言和元数据" },
  { id: "maintenance", icon: "⚙️", label: "维护", desc: "缓存清理和重置" },
];

let _currentSettingsTab = "media";

function renderSettingsView() {
  const config = state.config || {};

  return `
    <div class="settings-shell">
      ${renderSettingsOverview(config)}
      <div class="settings-tabs-layout">
        <nav class="settings-tab-nav">
          ${SETTINGS_TABS.map((tab) => `
            <button class="settings-tab-item ${tab.id === _currentSettingsTab ? "active" : ""}" data-settings-tab="${tab.id}">
              <span class="settings-tab-icon">${tab.icon}</span>
              <span class="settings-tab-copy">
                <strong>${tab.label}</strong>
                <small>${tab.desc}</small>
              </span>
              <span class="settings-tab-state ${getSettingsTabStateClass(tab.id, config)}">${getSettingsTabStateText(tab.id, config)}</span>
            </button>
          `).join("")}
        </nav>
        <div class="settings-tab-content">
          ${!config.has_basic_config && !_wizardDismissed ? renderFirstRunGuideCard(config) : ""}
          <form id="settingsForm">
            <div class="settings-tab-panel ${_currentSettingsTab === "media" ? "active" : ""}" data-panel="media">
              ${renderMediaSourceTab(config)}
            </div>
            <div class="settings-tab-panel ${_currentSettingsTab === "player" ? "active" : ""}" data-panel="player">
              ${renderPlayerTab(config)}
            </div>
            <div class="settings-tab-panel ${_currentSettingsTab === "openlist" ? "active" : ""}" data-panel="openlist">
              ${renderOpenListTab(config)}
            </div>
            <div class="settings-tab-panel ${_currentSettingsTab === "appearance" ? "active" : ""}" data-panel="appearance">
              ${renderAppearanceTab(config)}
            </div>
            <div class="settings-tab-panel ${_currentSettingsTab === "maintenance" ? "active" : ""}" data-panel="maintenance">
              ${renderMaintenanceTab(config)}
            </div>
            <div class="settings-actions">
              <button type="button" class="ghost-btn" id="testConnectionBtnFooter">${"测试远程连接"}</button>
              <button type="submit" class="primary-btn">${"保存全部设置"}</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;
}

function renderSettingsOverview(config) {
  const overviewItems = [
    {
      label: "远程媒体源",
      value: config.has_basic_config ? (config.remote_provider_label || "已配置") : "未完成",
      hint: config.has_basic_config ? "可以直接测试连接或刷新片库" : "先配置 WebDAV 或 OpenList",
      ready: !!config.has_basic_config,
    },
    {
      label: "本地目录",
      value: config.has_local_config ? `${(config.local_mount_dirs || []).length} 个目录` : "未添加",
      hint: config.has_local_config ? "刷新时会一起扫描本机目录" : "适合本地硬盘片库",
      ready: !!config.has_local_config,
    },
    {
      label: "默认播放器",
      value: config.default_player === "vlc" ? "VLC" : "PotPlayer",
      hint: "用于外部播放影片",
      ready: true,
    },
  ];

  return `
    <section class="settings-overview">
      <div class="settings-overview-copy">
        <span class="section-eyebrow">${"设置中心"}</span>
        <h3>${"把片库接进来，把播放方式设清楚"}</h3>
        <p>${"左边按任务分类，右边只展示当前需要填写的内容。第一次使用时，建议先完成“媒体源”和“播放与本地”两部分。"}</p>
      </div>
      <div class="settings-overview-grid">
        ${overviewItems.map((item) => `
          <article class="settings-overview-card ${item.ready ? "ready" : "pending"}">
            <span>${item.label}</span>
            <strong>${item.value}</strong>
            <small>${item.hint}</small>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function getSettingsTabStateText(tabId, config) {
  switch (tabId) {
    case "media":
      return config.has_basic_config ? "已配置" : "待配置";
    case "player":
      return config.has_local_config ? "可用" : "可选";
    case "openlist":
      return config.openlist_enabled ? "已启用" : "未启用";
    case "appearance":
      return "通用";
    case "maintenance":
      return "工具";
    default:
      return "";
  }
}

function getSettingsTabStateClass(tabId, config) {
  const text = getSettingsTabStateText(tabId, config);
  if (["已配置", "可用", "已启用"].includes(text)) return "ok";
  if (text === "待配置") return "warn";
  return "muted";
}

function renderFirstRunGuideCard(config) {
  const hasLocal = !!config.has_local_config;
  return `
    <section class="settings-card first-run-guide">
      <div class="first-run-guide-head">
        <div>
          <span class="section-eyebrow">${"首次使用"}</span>
          <h3>${"先接入一个媒体源再开始使用"}</h3>
          <p>${"这里不再锁定界面。你可以直接在下面完成设置，也可以先跳过，稍后再配。"}</p>
        </div>
        <button class="ghost-btn" type="button" id="dismissFirstRunGuideBtn">${"先看看界面"}</button>
      </div>
      <div class="first-run-guide-actions">
        <button class="primary-btn" type="button" data-first-run-source="openlist">${"使用 OpenList 网盘"}</button>
        <button class="ghost-btn" type="button" data-first-run-source="webdav">${"使用 WebDAV"}</button>
        <button class="ghost-btn" type="button" data-browse-dirs="local">${hasLocal ? "继续选择本地目录" : "先添加本地目录"}</button>
      </div>
    </section>
  `;
}

function renderMediaSourceTab(config) {
  const remoteProvider = normalizeRemoteProvider(config.remote_provider);
  const remotePreset = getRemoteProviderPreset(remoteProvider);
  const remoteProfiles = getRemoteProfiles(config);
  const activeRemoteProfile = remoteProfiles[remoteProvider] || {};
  const isOpenlistProvider = remoteProvider === "openlist";
  const openlistSourceMode = getOpenListSourceMode(config);
  const useBuiltinOpenList = isOpenlistProvider && openlistSourceMode === "builtin";
  const useExternalOpenList = isOpenlistProvider && openlistSourceMode === "external";
  const webdavDirs = [...state.webdavDirs];
  const openlistStatus = state.openlistStatus || {};
  const builtinReady = !!(config.openlist_enabled && openlistStatus.binary_available && openlistStatus.status === "running");
  const hasOpenListStorages = (state.openlistStorages || []).length > 0;
  const showRemoteCredentials = !useBuiltinOpenList;
  const connectButtonLabel = useExternalOpenList ? "验证自有 OpenList 并选择目录" : "验证并选择目录";
  const hintText = useBuiltinOpenList
    ? "使用本机内置 OpenList。适合夸克、阿里云盘、115、百度网盘等，先启动并挂载，再回来选扫描目录。"
    : useExternalOpenList
      ? "填写你自己的 OpenList WebDAV 地址，通常是 http://你的地址:5244/dav，再输入账号密码。"
      : remotePreset.help;

  return `
    <div class="settings-section-head">
      <span>${"媒体源"}</span>
      <h3>${"先决定视频从哪里来"}</h3>
      <p>${"如果你用网盘聚合，优先选 OpenList；如果你已经有现成的 WebDAV 地址，就选 WebDAV。"}</p>
    </div>

    <div class="settings-card settings-tip-card">
      <div class="settings-tip-copy">
        <strong>${isOpenlistProvider ? "当前使用 OpenList 方案" : "当前使用 WebDAV 方案"}</strong>
        <p>${isOpenlistProvider ? (useBuiltinOpenList ? "当前使用内置 OpenList，完成驱动挂载后即可直接选择扫描目录。" : "当前使用你自己的 OpenList 实例，会按标准 WebDAV 入口来连接和浏览目录。") : "适合群晖、坚果云、Nextcloud、AList 或其它已经提供 WebDAV 的服务。"}</p>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"1. 选择媒体源配置"}</h4>
        </div>
        <p>${"先选方案，再登录验证。验证通过后，我们会自动保存当前填写的信息并直接进入目录选择。"}</p>
      </div>
      <div class="source-option-grid">
        <button class="source-option-card ${remoteProvider === "webdav" ? "active" : ""}" type="button" data-select-remote-provider="webdav">
          <strong>${"标准 WebDAV"}</strong>
          <span>${"适合群晖、坚果云、rclone、AList WebDAV 等现成入口。"}</span>
        </button>
        <button class="source-option-card ${remoteProvider === "openlist" ? "active" : ""}" type="button" data-select-remote-provider="openlist">
          <strong>${"OpenList 网盘"}</strong>
          <span>${"适合夸克、阿里云盘、115、百度网盘等，也支持你自己的 OpenList。"}</span>
        </button>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-field-grid">
        <label class="${isOpenlistProvider ? "" : "hidden"}">
          <span>${"OpenList 方式"}</span>
          <select name="openlist_source_mode" id="openlistSourceModeSelect">
            <option value="builtin" ${openlistSourceMode === "builtin" ? "selected" : ""}>${"使用内置 OpenList"}</option>
            <option value="external" ${openlistSourceMode === "external" ? "selected" : ""}>${"使用自己的 OpenList"}</option>
          </select>
        </label>
        <label class="${isOpenlistProvider ? "hidden" : ""}">
          <span>${"接入方式"}</span>
          <select name="remote_provider" id="remoteProviderSelect">
            ${getRemoteProviderOptions().map((item) => `<option value="${item.value}" ${item.value === remoteProvider ? "selected" : ""}>${item.label}</option>`).join("")}
          </select>
        </label>
        <label>
          <span id="remoteHostLabel">${useExternalOpenList ? "OpenList WebDAV 地址" : (useBuiltinOpenList ? "地址（自动连接本机）" : "WebDAV 地址")}</span>
          <input name="webdav_host" id="remoteHostInput" value="${escapeAttr(activeRemoteProfile.webdav_host || (useExternalOpenList ? "" : (remotePreset.host || "")))}" placeholder="${escapeAttr(useExternalOpenList ? "http://your-openlist:5244/dav" : remotePreset.placeholder)}" ${useBuiltinOpenList ? "disabled" : ""}>
        </label>
        <div id="remoteCredentialFields" class="settings-inline-grid full-width ${showRemoteCredentials ? "" : "hidden"}">
          <label>
            <span id="remoteUserLabel">${useExternalOpenList ? "OpenList 用户名" : "用户名"}</span>
            <input name="webdav_user" id="remoteUserInput" value="${escapeAttr(activeRemoteProfile.webdav_user || "")}" placeholder="${useExternalOpenList ? "例如 admin" : "登录用户名"}">
          </label>
          <label>
            <span id="remotePassLabel">${useExternalOpenList ? "OpenList 密码" : "密码"}</span>
            <input name="webdav_pass" id="remotePassInput" type="password" value="${escapeAttr(activeRemoteProfile.webdav_pass || "")}" placeholder="${useExternalOpenList ? "OpenList 登录密码" : "登录密码"}">
          </label>
        </div>
        <label class="full-width" id="remoteCookieLabel" style="${showRemoteCredentials ? '' : 'display:none'}">
          <span>${"Cookie / Token（可选）"}</span>
          <textarea name="remote_cookie" id="remoteCookieInput" rows="3" placeholder="${"如果远程源支持网页会话或直链鉴权，也可以把 Cookie 放在这里。"}">${escapeHtml(activeRemoteProfile.remote_cookie || "")}</textarea>
        </label>
        <label>
          <span>${"远程扫描深度"}</span>
          <input name="scan_max_depth" type="number" min="1" max="8" value="${escapeAttr(String(config.scan_max_depth || 2))}">
        </label>
        <div class="full-width">
          <span>${"接入说明"}</span>
          <div id="remoteProviderHint" class="settings-inline-note">
            <span>${escapeHtml(hintText)}</span>
          </div>
        </div>
      </div>
      <div class="source-inline-actions">
        ${useBuiltinOpenList
          ? `
            <button class="primary-btn" type="button" id="browseBuiltinOpenListBtn">${builtinReady && hasOpenListStorages ? "浏览 OpenList 目录" : "去配置内置 OpenList"}</button>
            <button class="ghost-btn" type="button" id="openOpenListManagerBtn">${"打开 OpenList 管理"}</button>
          `
          : `
            <button class="primary-btn" type="button" id="connectAndBrowseBtn">${connectButtonLabel}</button>
            <button class="ghost-btn" type="button" id="testConnectionBtn">${"仅验证连接"}</button>
          `}
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4 id="remoteMountTitle">${isOpenlistProvider ? "需要扫描的 OpenList 挂载目录" : "需要扫描的 WebDAV 目录"}</h4>
        </div>
        <p id="remoteMountDesc">${"只添加真正放影视内容的目录，这样刷新更快，也更容易识别。"}</p>
      </div>
      <div class="mount-list" id="remoteMountList">
        ${renderMountList(webdavDirs, "webdav")}
      </div>
      <button class="primary-btn" type="button" id="browseRemoteDirsBtn">${isOpenlistProvider ? "浏览 OpenList 目录" : "浏览远程目录"}</button>
    </div>
  `;
}

function renderPlayerTab(config) {
  const localDirs = [...state.localDirs];

  return `
    <div class="settings-section-head">
      <span>${"播放与扫描"}</span>
      <h3>${"本机怎么扫描，怎么播放"}</h3>
      <p>${"如果你既有网盘也有本地硬盘，这里建议一起配好，后面就能统一出现在片库里。"}</p>
    </div>

    <div class="settings-card">
      <div class="settings-field-grid">
        <label>
          <span>${"本地扫描深度"}</span>
          <input name="local_scan_max_depth" type="number" min="1" max="12" value="${escapeAttr(String(config.local_scan_max_depth || 3))}">
        </label>
        <label>
          <span>${"默认播放器"}</span>
          <select name="default_player">
            <option value="potplayer" ${config.default_player === "potplayer" ? "selected" : ""}>PotPlayer</option>
            <option value="vlc" ${config.default_player === "vlc" ? "selected" : ""}>VLC</option>
          </select>
        </label>
        <label>
          <span>${"PotPlayer 路径"}</span>
          <div class="path-picker-row">
            <input id="potplayerPathInput" name="potplayer_path" value="${escapeAttr(config.potplayer_path || "")}" placeholder="PotPlayer.exe 路径">
            <button class="ghost-btn" type="button" data-pick-player="potplayer">${"浏览…"}</button>
          </div>
        </label>
        <label>
          <span>${"VLC 路径"}</span>
          <div class="path-picker-row">
            <input id="vlcPathInput" name="vlc_path" value="${escapeAttr(config.vlc_path || "")}" placeholder="vlc.exe 路径">
            <button class="ghost-btn" type="button" data-pick-player="vlc">${"浏览…"}</button>
          </div>
        </label>
        <label class="full-width">
          <span>${"视频格式"}</span>
          <input name="video_formats" value="${escapeAttr((config.video_formats || [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"]).join(", "))}" placeholder=".mp4, .mkv, .avi 等">
        </label>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"需要扫描的本地目录"}</h4>
        </div>
        <p>${"例如电影盘、剧集盘、NAS 映射盘。只添加放视频的目录，避免扫描太慢。"}</p>
      </div>
      <div class="mount-list">
        ${renderMountList(localDirs, "local")}
      </div>
      <button class="primary-btn" type="button" data-browse-dirs="local">${"浏览本地目录"}</button>
    </div>
  `;
}

function renderOpenListTab(config) {
  return `
    <div class="settings-section-head">
      <span>${"网盘聚合"}</span>
      <h3>${"把多个网盘接成一个入口"}</h3>
      <p>${"先启用 OpenList，再添加网盘驱动。添加成功后，再回到“媒体源”里选择要扫描的挂载目录。"}</p>
    </div>

    <div class="settings-card">
      <div class="openlist-status-grid" id="openlistStatusPanel">
        <div class="openlist-status-card">
          <div id="openlistStatusText" style="font-size:18px; font-weight:700;">${"加载中..."}</div>
          <div style="font-size:12px; color:var(--text-soft);">${"运行状态"}</div>
        </div>
        <div class="openlist-status-card">
          <div id="openlistPortText" style="font-size:18px; font-weight:700;">${"5244"}</div>
          <div style="font-size:12px; color:var(--text-soft);">${"监听端口"}</div>
        </div>
        <div class="openlist-status-card">
          <div id="openlistVersionText" style="font-size:18px; font-weight:700;">${"--"}</div>
          <div style="font-size:12px; color:var(--text-soft);">${"版本"}</div>
        </div>
        <div class="openlist-status-card">
          <div id="openlistStorageCount" style="font-size:18px; font-weight:700;">0</div>
          <div style="font-size:12px; color:var(--text-soft);">${"存储驱动"}</div>
        </div>
      </div>
      <div class="settings-field-grid">
        <label>
          <span>${"启用内置 OpenList"}</span>
          <select name="openlist_enabled" id="openlistEnabledSelect">
            <option value="false" ${!config.openlist_enabled ? "selected" : ""}>${"禁用"}</option>
            <option value="true" ${config.openlist_enabled ? "selected" : ""}>${"启用"}</option>
          </select>
        </label>
        <label>
          <span>${"监听端口"}</span>
          <input name="openlist_port" type="number" min="1024" max="65535" value="${escapeAttr(String(config.openlist_port || 5244))}">
        </label>
        <label>
          <span>${"自动启动"}</span>
          <select name="openlist_auto_start">
            <option value="true" ${config.openlist_auto_start !== false ? "selected" : ""}>${"是"}</option>
            <option value="false" ${config.openlist_auto_start === false ? "selected" : ""}>${"否"}</option>
          </select>
        </label>
        <label>
          <span>${"管理员密码"}</span>
          <input name="openlist_admin_password" type="text" value="${escapeAttr(config.openlist_admin_password || "")}" placeholder="${"首次启用时自动生成"}">
        </label>
      </div>
      <div style="margin-top:12px; display:flex; align-items:center; gap:8px;">
        <button class="ghost-btn" type="button" id="openlistResetPasswordBtn">${"重置密码"}</button>
        <span style="font-size:13px; color:var(--text-soft);">${"如果登录失败，点击此按钮重置为当前填写的密码"}</span>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"操作"}</h4>
        </div>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="primary-btn" type="button" id="openlistStartBtn">${"启动"}</button>
        <button class="ghost-btn" type="button" id="openlistStopBtn">${"停止"}</button>
        <button class="ghost-btn" type="button" id="openlistRestartBtn">${"重启"}</button>
        <button class="ghost-btn" type="button" id="openlistDownloadBtn">${"下载/更新"}</button>
      </div>
      <div id="openlistDownloadProgress" class="hidden" style="margin-top:12px;">
        <div class="job-progress-bar"><div id="openlistDownloadProgressBar" style="width:0%"></div></div>
        <span id="openlistDownloadProgressText" class="job-progress-text"></span>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"存储驱动"}</h4>
        </div>
        <p>${"挂载网盘到 OpenList，支持夸克、阿里云盘、115、百度网盘等。"}</p>
      </div>
      <div id="openlistStorageList"></div>
      <div id="openlistDriverForm"></div>
    </div>
  `;
}

function renderAppearanceTab(config) {
  const currentTheme = normalizeTheme(config.ui_theme || config.interface_theme);

  return `
    <div class="settings-section-head">
      <span>${"界面"}</span>
      <h3>${"把界面和元数据偏好设舒服"}</h3>
      <p>${"这里不会影响你的片库内容，只影响显示方式和自动补全信息的行为。"}</p>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"主题"}</h4>
        </div>
      </div>
      <div class="theme-preview-grid">
        ${getThemeOptions().map((theme) => `
          <div class="theme-preview-card ${theme.value === currentTheme ? "selected" : ""}" data-theme-value="${theme.value}">
            <div class="theme-preview-swatch" style="background: ${getThemeColor(theme.value)}">
              ${getThemeEmoji(theme.value)}
            </div>
            <span>${theme.label}</span>
          </div>
        `).join("")}
      </div>
      <input type="hidden" name="ui_theme" id="themeHiddenInput" value="${currentTheme}">
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"自动刮削"}</h4>
        </div>
        <p>${"自动刮削会优先尝试 TMDB 和豆瓣，AniBK 作为备用源参与回退。"}</p>
      </div>
      <div class="settings-field-grid">
        <label>
          <span>${"自动刮削"}</span>
          <select name="enable_auto_scrape">
            <option value="true" ${config.enable_auto_scrape ? "selected" : ""}>${"启用"}</option>
            <option value="false" ${!config.enable_auto_scrape ? "selected" : ""}>${"禁用"}</option>
          </select>
        </label>
        <label>
          <span>${"TMDB API 密钥"}</span>
          <input name="tmdb_api_key" type="password" value="${escapeAttr(config.tmdb_api_key || "")}" placeholder="${"填入你自己的 TMDB API Key"}">
        </label>
      </div>
    </div>
  `;
}

function getThemeColor(theme) {
  const colors = {
    amber: "linear-gradient(135deg, #ff9248, #ffb347)",
    graphite: "linear-gradient(135deg, #6b7280, #9ca3af)",
    forest: "linear-gradient(135deg, #22c55e, #4ade80)",
    coast: "linear-gradient(135deg, #06b6d4, #67e8f9)",
  };
  return colors[theme] || colors.amber;
}

function getThemeEmoji(theme) {
  const emojis = { amber: "🌅", graphite: "🪨", forest: "🌲", coast: "🌊" };
  return emojis[theme] || emojis.amber;
}

function renderMaintenanceTab() {
  return `
    <div class="settings-section-head">
      <span>${"维护"}</span>
      <h3>${"清理缓存，或恢复初始状态"}</h3>
      <p>${"大多数情况下只需要清缓存。只有在配置完全乱掉时，才建议清空全部数据重置。"}</p>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"缓存管理"}</h4>
        </div>
        <p>${"清除缓存不会影响你的配置和收藏。"}</p>
      </div>
      <div class="maintenance-grid">
        <button class="ghost-btn" type="button" id="clearRemoteCacheBtn">${"清除远程缓存"}</button>
        <button class="ghost-btn" type="button" id="clearLocalCacheBtn">${"清除本地缓存"}</button>
        <button class="ghost-btn" type="button" id="clearAllCacheBtn">${"清除全部缓存"}</button>
      </div>
    </div>

    <div class="settings-card" style="border-color: rgba(240, 113, 120, 0.3);">
      <div class="settings-card-head">
        <div>
          <h4 style="color: var(--danger);">${"危险区域"}</h4>
        </div>
        <p>${"此操作不可恢复，请谨慎操作。"}</p>
      </div>
      <button class="ghost-btn danger-btn" type="button" id="clearAllDataBtn">${"清除全部数据并重置"}</button>
    </div>
  `;
}

// 首次配置向导
let _wizardDismissed = false;
let _wizardStep = 1;
let _wizardSource = "openlist";

function renderFirstRunWizard() {
  return `
    <div class="settings-shell">
      <div class="wizard-overlay" id="wizardOverlay" style="position:static; background:none; backdrop-filter:none;">
        <div class="wizard-modal" id="wizardModal">
          <div class="wizard-header">
            <h2>${"欢迎使用鸡米花"}</h2>
            <p>${"只需几步，即可开始管理你的影视库"}</p>
          </div>

          <div class="wizard-steps">
            <div class="wizard-step ${_wizardStep >= 1 ? "active" : ""} ${_wizardStep > 1 ? "done" : ""}">
              <div class="wizard-step-dot">${_wizardStep > 1 ? "✓" : "1"}</div>
              <span>${"选择来源"}</span>
            </div>
            <div class="wizard-step-line"></div>
            <div class="wizard-step ${_wizardStep >= 2 ? "active" : ""} ${_wizardStep > 2 ? "done" : ""}">
              <div class="wizard-step-dot">${_wizardStep > 2 ? "✓" : "2"}</div>
              <span>${"配置连接"}</span>
            </div>
            <div class="wizard-step-line"></div>
            <div class="wizard-step ${_wizardStep >= 3 ? "active" : ""}">
              <div class="wizard-step-dot">3</div>
              <span>${"选择目录"}</span>
            </div>
          </div>

          <div class="wizard-body">
            ${_wizardStep === 1 ? renderWizardStep1() : ""}
            ${_wizardStep === 2 ? renderWizardStep2() : ""}
            ${_wizardStep === 3 ? renderWizardStep3() : ""}
          </div>

          <div class="wizard-footer">
            ${_wizardStep > 1 ? `<button class="ghost-btn" type="button" id="wizardPrevBtn">${"上一步"}</button>` : "<div></div>"}
            ${_wizardStep < 3
              ? `<button class="primary-btn" type="button" id="wizardNextBtn">${"下一步"}</button>`
              : `<button class="primary-btn" type="button" id="wizardFinishBtn">${"完成配置"}</button>`
            }
          </div>

          <div style="text-align:center; margin-top:8px;">
            <button class="ghost-btn" type="button" id="wizardSkipBtn" style="font-size:13px; color:var(--text-soft);">${"跳过向导，手动配置"}</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderWizardStep1() {
  return `
    <div style="text-align:center; margin-bottom:24px;">
      <h3 style="margin:0 0 8px;">${"选择媒体源"}</h3>
      <p style="color:var(--text-soft); margin:0;">${"选择你要从哪里获取视频资源"}</p>
    </div>
    <div class="wizard-source-grid">
      <div class="wizard-source-card ${_wizardSource === "openlist" ? "selected" : ""}" data-wizard-source="openlist">
        <div class="wizard-source-icon">☁️</div>
        <h4>${"OpenList 网盘"}</h4>
        <p>${"支持夸克、阿里云盘、115、百度网盘等多种网盘"}</p>
        <span class="wizard-source-badge">${"推荐"}</span>
      </div>
      <div class="wizard-source-card ${_wizardSource === "webdav" ? "selected" : ""}" data-wizard-source="webdav">
        <div class="wizard-source-icon">🌐</div>
        <h4>${"WebDAV"}</h4>
        <p>${"连接自建的 WebDAV 服务器或坚果云等服务"}</p>
      </div>
    </div>
  `;
}

function renderWizardStep2() {
  if (_wizardSource === "openlist") {
    return `
      <div style="text-align:center; margin-bottom:24px;">
        <h3 style="margin:0 0 8px;">${"配置 OpenList"}</h3>
        <p style="color:var(--text-soft); margin:0;">${"OpenList 是内置的网盘聚合服务"}</p>
      </div>
      <div class="settings-card" style="max-width:400px; margin:0 auto;">
        <p style="color:var(--text-soft); font-size:14px; text-align:center;">
          ${"保存设置后，系统会自动下载并启动 OpenList，然后你可以在 OpenList 管理界面添加网盘驱动。"}
        </p>
        <div class="settings-field-grid">
          <label>
            <span>${"监听端口"}</span>
            <input name="openlist_port" type="number" value="5244" placeholder="5244">
          </label>
          <label>
            <span>${"管理员密码"}</span>
            <input name="openlist_admin_password" type="text" placeholder="${"留空自动生成"}">
          </label>
        </div>
      </div>
    `;
  }

  return `
    <div style="text-align:center; margin-bottom:24px;">
      <h3 style="margin:0 0 8px;">${"配置 WebDAV"}</h3>
      <p style="color:var(--text-soft); margin:0;">${"填写你的 WebDAV 服务器信息"}</p>
    </div>
    <div class="settings-card" style="max-width:480px; margin:0 auto;">
      <div class="settings-field-grid">
        <label class="full-width">
          <span>${"服务器地址"}</span>
          <input name="webdav_host" placeholder="https://example.com/dav">
        </label>
        <label>
          <span>${"用户名"}</span>
          <input name="webdav_user" placeholder="${"登录用户名"}">
        </label>
        <label>
          <span>${"密码"}</span>
          <input name="webdav_pass" type="password" placeholder="${"登录密码"}">
        </label>
        <label class="full-width">
          <span>${"Cookie / Token（可选）"}</span>
          <textarea name="remote_cookie" rows="2" placeholder="${"如果需要额外认证"}"></textarea>
        </label>
      </div>
    </div>
  `;
}

function renderWizardStep3() {
  const remoteDirs = [...state.webdavDirs];
  const localDirs = [...state.localDirs];
  const isOpenlist = _wizardSource === "openlist";

  return `
    <div style="text-align:center; margin-bottom:24px;">
      <h3 style="margin:0 0 8px;">${"选择扫描目录"}</h3>
      <p style="color:var(--text-soft); margin:0;">${"选择要扫描的目录，之后也可以在设置中修改"}</p>
    </div>
    <div style="display:grid; gap:16px; max-width:480px; margin:0 auto;">
      <div class="settings-card">
        <div class="settings-card-head">
          <h4>${isOpenlist ? "OpenList 挂载目录" : "远程目录"}</h4>
        </div>
        <div class="mount-list" id="remoteMountList">
          ${renderMountList(remoteDirs, "webdav")}
        </div>
        <button class="primary-btn" type="button" id="browseRemoteDirsBtn" data-browse-dirs="webdav">${isOpenlist ? "浏览 OpenList 目录" : "浏览远程目录"}</button>
      </div>
      <div class="settings-card">
        <div class="settings-card-head">
          <h4>${"本地目录"}</h4>
        </div>
        <div class="mount-list">
          ${renderMountList(localDirs, "local")}
        </div>
        <button class="primary-btn" type="button" data-browse-dirs="local">${"浏览本地目录"}</button>
      </div>
    </div>
  `;
}

function bindWizard() {
  // 来源选择
  document.querySelectorAll("[data-wizard-source]").forEach((card) => {
    card.addEventListener("click", () => {
      _wizardSource = card.dataset.wizardSource;
      document.querySelectorAll("[data-wizard-source]").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
    });
  });

  // 下一步
  document.getElementById("wizardNextBtn")?.addEventListener("click", () => {
    if (_wizardStep === 1) {
      _wizardStep = 2;
      render();
    } else if (_wizardStep === 2) {
      _wizardStep = 3;
      render();
    }
  });

  // 上一步
  document.getElementById("wizardPrevBtn")?.addEventListener("click", () => {
    if (_wizardStep > 1) {
      _wizardStep--;
      render();
    }
  });

  // 跳过向导
  document.getElementById("wizardSkipBtn")?.addEventListener("click", () => {
    _wizardDismissed = true;
    render();
  });

  // 完成配置
  document.getElementById("wizardFinishBtn")?.addEventListener("click", async () => {
    await handleWizardFinish();
  });

  // 目录浏览
  bindDirectoryBrowseButtons();
}

function bindDirectoryBrowseButtons() {
  document.querySelectorAll("[data-browse-dirs]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const scope = btn.dataset.browseDirs;
      await openDirectoryModal(scope, scope === "local" ? "" : getRemoteRootPath());
    });
  });

  document.querySelectorAll("[data-remove-dir]").forEach((btn) => {
    btn.addEventListener("click", () => {
      getDirectorySet(btn.dataset.removeScope).delete(btn.dataset.removeDir);
      render();
    });
  });
}

async function handleWizardFinish() {
  const openlistPort = document.querySelector("[name='openlist_port']")?.value || "5244";
  const openlistPassword = document.querySelector("[name='openlist_admin_password']")?.value || "";
  const webdavHost = document.querySelector("[name='webdav_host']")?.value || "";
  const webdavUser = document.querySelector("[name='webdav_user']")?.value || "";
  const webdavPass = document.querySelector("[name='webdav_pass']")?.value || "";
  const remoteCookie = document.querySelector("[name='remote_cookie']")?.value || "";

  // 构建配置 payload
  const payload = {
    remote_provider: _wizardSource,
    remote_profiles: {},
    webdav_host: _wizardSource === "webdav" ? webdavHost : "",
    webdav_user: _wizardSource === "webdav" ? webdavUser : "",
    webdav_pass: _wizardSource === "webdav" ? webdavPass : "",
    remote_cookie: _wizardSource === "webdav" ? remoteCookie : "",
    scan_max_depth: 2,
    saved_mount_dirs: [...state.webdavDirs],
    local_scan_max_depth: 3,
    local_mount_dirs: [...state.localDirs],
    potplayer_path: "",
    vlc_path: "",
    default_player: "potplayer",
    video_formats: [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"],
    enable_auto_scrape: true,
    scrape_source: "auto",
    tmdb_api_key: "",
    ui_theme: "amber",
    interface_theme: "amber",
  };

  if (_wizardSource === "webdav") {
    payload.remote_profiles[_wizardSource] = {
      webdav_host: webdavHost,
      webdav_user: webdavUser,
      webdav_pass: webdavPass,
      remote_cookie: remoteCookie,
      saved_mount_dirs: [...state.webdavDirs],
    };
  }

  try {
    // 保存主配置
    const result = await api("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (result) {
      state.config = result;
    }

    // 如果选择了 OpenList，保存 OpenList 配置
    if (_wizardSource === "openlist") {
      await api("/api/openlist/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: true,
          port: Number(openlistPort || 5244),
          auto_start: true,
          admin_password: openlistPassword || "",
        }),
      });

      if (state.config) {
        state.config.openlist_enabled = true;
        state.config.openlist_port = Number(openlistPort || 5244);
      }
    }

    _wizardDismissed = true;
    state.view = "all";
    render();
    showToast("配置完成，正在开始首次扫描…", "success", 3200);

    // 触发首次扫描
    const source = _wizardSource === "openlist" ? "remote" : "remote";
    const refreshResult = await guarded(() =>
      api(`/api/library/refresh?source=${source}&auto_scrape=true`, { method: "POST" })
    );
    if (refreshResult?.job_id) {
      startJobPolling(refreshResult.job_id, source, "首次扫描和刮削完成");
    }
  } catch (e) {
    showToast(`配置失败: ${e.message}`, "error");
  }
}

function renderMountList(items, scope) {
  if (!items.length) {
    return `<div class="mount-item empty"><span>${"还没有选择目录"}</span></div>`;
  }
  return items
    .map(
      (dir) => `
        <div class="mount-item">
          <span>${escapeHtml(scope === "webdav" ? formatRemotePathLabel(dir) : dir)}</span>
          <button class="ghost-btn" data-remove-dir="${escapeAttr(dir)}" data-remove-scope="${scope}">${"移除"}</button>
        </div>
      `
    )
    .join("");
}

function bindSettingsView() {
  const settingsForm = document.getElementById("settingsForm");
  if (!settingsForm) return;

  document.getElementById("dismissFirstRunGuideBtn")?.addEventListener("click", () => {
    _wizardDismissed = true;
    render();
  });

  document.querySelectorAll("[data-first-run-source]").forEach((button) => {
    button.addEventListener("click", () => {
      const source = button.dataset.firstRunSource || "openlist";
      _currentSettingsTab = "media";
      if (state.config) {
        state.config.remote_provider = normalizeRemoteProvider(source);
      }
      if (source === "openlist" && state.config) {
        state.config.openlist_source_mode = getOpenListSourceMode(state.config);
      }
      if (document.getElementById("remoteProviderSelect")) {
        render();
      } else {
        render();
      }
    });
  });

  // 标签页切换
  document.querySelectorAll("[data-settings-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      _currentSettingsTab = btn.dataset.settingsTab;
      render();
    });
  });

  // 主题预览卡片点击
  document.querySelectorAll(".theme-preview-card").forEach((card) => {
    card.addEventListener("click", () => {
      const theme = card.dataset.themeValue;
      document.getElementById("themeHiddenInput").value = theme;
      applyTheme(theme);
      document.querySelectorAll(".theme-preview-card").forEach((c) => c.classList.remove("selected"));
      card.classList.add("selected");
    });
  });

  // 远程来源切换
  const remoteProviderSelect = document.getElementById("remoteProviderSelect");
  if (remoteProviderSelect) {
    remoteProviderSelect.addEventListener("change", (event) => {
      handleRemoteProviderChange(event.target.value);
    });
  }

  document.querySelectorAll("[data-select-remote-provider]").forEach((button) => {
    button.addEventListener("click", () => {
      handleRemoteProviderChange(button.dataset.selectRemoteProvider || "webdav");
    });
  });

  document.getElementById("openlistSourceModeSelect")?.addEventListener("change", (event) => {
    handleOpenListSourceModeChange(event.target.value);
  });

  // 测试连接
  document.getElementById("testConnectionBtn")?.addEventListener("click", async () => {
    await testRemoteConnectionFlow();
  });

  document.getElementById("testConnectionBtnFooter")?.addEventListener("click", async () => {
    await testRemoteConnectionFlow();
  });

  document.getElementById("connectAndBrowseBtn")?.addEventListener("click", async () => {
    await handleRemoteConnectAndBrowse();
  });

  document.getElementById("browseRemoteDirsBtn")?.addEventListener("click", async () => {
    await handleRemoteConnectAndBrowse();
  });

  document.getElementById("openOpenListManagerBtn")?.addEventListener("click", async () => {
    await openBuiltInOpenListManager();
  });

  document.getElementById("browseBuiltinOpenListBtn")?.addEventListener("click", async () => {
    await handleBuiltinOpenListBrowseFlow();
  });

  // 保存设置
  settingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await handleSettingsSubmit();
  });

  // 维护按钮
  document.getElementById("clearRemoteCacheBtn")?.addEventListener("click", async () => {
    const result = await guarded(() => api("/api/cache/clear?source=remote", { method: "POST" }));
    if (result) showToast("远程缓存已清除", "success");
  });

  document.getElementById("clearLocalCacheBtn")?.addEventListener("click", async () => {
    const result = await guarded(() => api("/api/cache/clear?source=local", { method: "POST" }));
    if (result) showToast("本地缓存已清除", "success");
  });

  document.getElementById("clearAllCacheBtn")?.addEventListener("click", async () => {
    const result = await guarded(() => api("/api/cache/clear-all", { method: "POST" }));
    if (result) showToast("全部缓存已清除", "success");
  });

  document.getElementById("clearAllDataBtn")?.addEventListener("click", async () => {
    const confirmed = window.confirm("这会将软件恢复到初始状态，包括：\n\n• 停止并重置内置 OpenList\n• 清除所有网盘配置\n• 清除收藏、播放记录、封面和缓存\n• 重置所有设置到默认值\n\n确定继续吗？");
    if (!confirmed) return;

    const result = await guarded(() => api("/api/data/clear-all", { method: "POST" }));
    if (!result) return;

    await loadBootstrap();
    state.items = [];
    state.view = "settings";
    _currentSettingsTab = "media";
    render();
    showToast("全部数据已清除，软件已恢复初始状态", "success");
  });

  // 播放器路径选择
  settingsForm.querySelectorAll("[data-pick-player]").forEach((button) => {
    button.addEventListener("click", async () => {
      const player = button.dataset.pickPlayer || "potplayer";
      const targetInput = player === "vlc" ? document.getElementById("vlcPathInput") : document.getElementById("potplayerPathInput");
      const currentPath = String(targetInput?.value || "").trim();
      const result = await guarded(() =>
        api("/api/system/pick-player", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ player, current_path: currentPath }),
        })
      );
      if (result?.path && targetInput) {
        targetInput.value = result.path;
      }
    });
  });
}

async function handleSettingsSubmit() {
  // 在 render() 之前读取 OpenList 表单值
  const preSavedOpenlistEnabled = document.getElementById("openlistEnabledSelect")?.value;
  const preSavedOpenlistPort = document.querySelector("[name='openlist_port']")?.value;
  const preSavedOpenlistAutoStart = document.querySelector("[name='openlist_auto_start']")?.value;
  const preSavedOpenlistPassword = document.querySelector("[name='openlist_admin_password']")?.value;

  const wasFirstSetup = !state.config?.has_any_library;
  const persisted = await persistSettingsIfNeeded({ force: true });
  if (!persisted) return;

  // 保存 OpenList 配置
  if (preSavedOpenlistEnabled || preSavedOpenlistPort || preSavedOpenlistAutoStart || preSavedOpenlistPassword) {
    try {
      const openlistPayload = {
        enabled: preSavedOpenlistEnabled === "true",
        port: Number(preSavedOpenlistPort || 5244),
        auto_start: preSavedOpenlistAutoStart !== "false",
        admin_password: preSavedOpenlistPassword || "",
      };
      await api("/api/openlist/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(openlistPayload),
      });
      if (state.config) {
        state.config.openlist_enabled = openlistPayload.enabled;
        state.config.openlist_port = openlistPayload.port;
        state.config.openlist_auto_start = openlistPayload.auto_start;
      }
    } catch (e) {
      showToast(`OpenList 配置保存失败: ${parseOpenListError(e)}`, "error");
    }
  }

  const result = persisted.result;
  const shouldAutoStartSetup = wasFirstSetup && result.has_any_library && hasConfiguredScanTargets(result);
  const shouldAutoRefreshAddedDirs = (persisted.addedRemote.length > 0 || persisted.addedLocal.length > 0) && result.has_any_library;

  if (shouldAutoStartSetup || shouldAutoRefreshAddedDirs) {
    const source = shouldAutoStartSetup
      ? getInitialRefreshSource(result)
      : getRefreshSourceForDirectoryChanges(persisted.addedRemote, persisted.addedLocal, result);
    state.view = "all";
    render();
    showToast(
      shouldAutoStartSetup ? "设置已保存，正在开始首次扫描和刮削…" : "挂载目录已保存，正在自动更新影视库…",
      "success",
      3200
    );

    const response = await guarded(() =>
      api(`/api/library/refresh?source=${encodeURIComponent(source || "combined")}&auto_scrape=true`, { method: "POST" })
    );
    if (response?.job_id) {
      startJobPolling(
        response.job_id,
        source || "combined",
        shouldAutoStartSetup ? "首次扫描和刮削完成" : "影视库已更新并补全元数据"
      );
      return;
    }
  }

  showToast("设置已保存", "success");
}

function handleRemoteProviderChange(newProvider) {
  syncRemoteDraftToState();
  const nextProvider = normalizeRemoteProvider(newProvider);
  if (!state.config) return;
  state.config.remote_provider = nextProvider;
  const remoteProfiles = getRemoteProfiles(state.config);
  const active = remoteProfiles[nextProvider] || {};
  state.config.remote_profiles = remoteProfiles;
  state.config.webdav_host = active.webdav_host || "";
  state.config.webdav_user = active.webdav_user || "";
  state.config.webdav_pass = active.webdav_pass || "";
  state.config.remote_cookie = active.remote_cookie || "";
  if (nextProvider === "openlist") {
    state.config.openlist_source_mode = normalizeOpenListSourceMode(active.openlist_source_mode);
  }
  state.webdavDirs = new Set(normalizeRemoteDirSetItems(Array.isArray(active.saved_mount_dirs) ? active.saved_mount_dirs : []));
  render();
}

function syncRemoteDraftToState() {
  if (!state.config) return;
  const remoteProfiles = getRemoteProfiles(state.config || {});
  const previousProvider = normalizeRemoteProvider(state.config?.remote_provider || "webdav");
  const hostInput = document.getElementById("remoteHostInput");
  const userInput = document.getElementById("remoteUserInput");
  const passInput = document.getElementById("remotePassInput");
  const cookieInput = document.getElementById("remoteCookieInput");
  const openlistModeInput = document.getElementById("openlistSourceModeSelect");
  const openlistSourceMode = normalizeOpenListSourceMode(openlistModeInput?.value || state.config.openlist_source_mode);
  remoteProfiles[previousProvider] = {
    webdav_host: String(hostInput?.value || "").trim(),
    webdav_user: String(userInput?.value || "").trim(),
    webdav_pass: String(passInput?.value || "").trim(),
    remote_cookie: String(cookieInput?.value || "").trim(),
    openlist_source_mode: previousProvider === "openlist" ? openlistSourceMode : normalizeOpenListSourceMode(remoteProfiles[previousProvider]?.openlist_source_mode),
    saved_mount_dirs: [...state.webdavDirs],
  };
  if (remoteProfiles.openlist) {
    remoteProfiles.openlist.openlist_source_mode = normalizeOpenListSourceMode(
      previousProvider === "openlist" ? openlistSourceMode : remoteProfiles.openlist.openlist_source_mode
    );
  }
  state.config.remote_profiles = remoteProfiles;
  state.config.webdav_host = String(hostInput?.value || "").trim();
  state.config.webdav_user = String(userInput?.value || "").trim();
  state.config.webdav_pass = String(passInput?.value || "").trim();
  state.config.remote_cookie = String(cookieInput?.value || "").trim();
  state.config.openlist_source_mode = openlistSourceMode;
  state.config.saved_mount_dirs = [...state.webdavDirs];
}

function handleOpenListSourceModeChange(newMode) {
  syncRemoteDraftToState();
  if (!state.config) return;
  const nextMode = normalizeOpenListSourceMode(newMode);
  const remoteProfiles = getRemoteProfiles(state.config);
  remoteProfiles.openlist = {
    ...(remoteProfiles.openlist || {}),
    openlist_source_mode: nextMode,
  };
  state.config.remote_profiles = remoteProfiles;
  state.config.openlist_source_mode = nextMode;
  if (normalizeRemoteProvider(state.config.remote_provider) === "openlist") {
    const active = remoteProfiles.openlist || {};
    state.config.webdav_host = active.webdav_host || "";
    state.config.webdav_user = active.webdav_user || "";
    state.config.webdav_pass = active.webdav_pass || "";
    state.config.remote_cookie = active.remote_cookie || "";
  }
  render();
}

async function testRemoteConnectionFlow() {
  const payload = getSettingsPayload();
  const result = await guarded(() =>
    api("/api/config/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    true,
    "正在验证远程媒体源..."
  );
  if (!result) return false;
  showToast(result.message || (result.success ? "连接成功" : "连接失败"), result.success ? "success" : "error");
  return !!result.success;
}

async function openBuiltInOpenListManager(message = "") {
  syncRemoteDraftToState();
  const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
  if (!persisted) return false;
  _currentSettingsTab = "openlist";
  render();
  await initOpenListPanel();
  if (message) {
    showToast(message, "info", 4000);
  }
  return true;
}

async function handleBuiltinOpenListBrowseFlow() {
  syncRemoteDraftToState();
  const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
  if (!persisted) return false;

  await Promise.all([fetchOpenListConfig(), fetchOpenListStatus(), fetchOpenListStorages()]);

  const status = state.openlistStatus || {};
  if (!status.binary_available) {
    return openBuiltInOpenListManager("先下载并启动内置 OpenList，然后再回来选择目录。");
  }
  if (!state.config?.openlist_enabled) {
    return openBuiltInOpenListManager("先在 OpenList 面板里启用内置 OpenList。");
  }
  if (status.status !== "running") {
    return openBuiltInOpenListManager("内置 OpenList 还没有运行，先启动后再选择目录。");
  }
  if (!state.openlistStorages.length) {
    return openBuiltInOpenListManager("OpenList 已启动，下一步先添加一个网盘驱动。");
  }

  showToast("内置 OpenList 已就绪，继续选择扫描目录。", "success");
  await openDirectoryModal("webdav", getRemoteRootPath());
  return true;
}

async function handleRemoteConnectAndBrowse() {
  const payload = getSettingsPayload();
  if (normalizeRemoteProvider(payload.remote_provider) === "openlist" && normalizeOpenListSourceMode(payload.openlist_source_mode) === "builtin") {
    return handleBuiltinOpenListBrowseFlow();
  }

  const success = await testRemoteConnectionFlow();
  if (!success) return false;

  syncRemoteDraftToState();
  const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
  if (!persisted) return false;

  showToast("连接成功，已保存当前配置。接下来选择需要扫描的目录。", "success", 3200);
  await openDirectoryModal("webdav", getRemoteRootPath());
  return true;
}

function getSettingsPayload() {
  const form = document.getElementById("settingsForm");
  if (!form) {
    return {
      remote_provider: normalizeRemoteProvider(state.config?.remote_provider),
      remote_profiles: getRemoteProfiles(state.config || {}),
      webdav_host: state.config?.webdav_host || "",
      webdav_user: state.config?.webdav_user || "",
      webdav_pass: state.config?.webdav_pass || "",
      remote_cookie: state.config?.remote_cookie || "",
      openlist_source_mode: normalizeOpenListSourceMode(state.config?.openlist_source_mode),
      scan_max_depth: state.config?.scan_max_depth || 2,
      saved_mount_dirs: [...state.webdavDirs],
      local_scan_max_depth: state.config?.local_scan_max_depth || 3,
      local_mount_dirs: [...state.localDirs],
      potplayer_path: state.config?.potplayer_path || "",
      vlc_path: state.config?.vlc_path || "",
      default_player: state.config?.default_player || "potplayer",
      video_formats: state.config?.video_formats || [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"],
      enable_auto_scrape: state.config?.enable_auto_scrape !== false,
      scrape_source: state.config?.scrape_source || "auto",
      tmdb_api_key: state.config?.tmdb_api_key || "",
      tmdb_api_base: state.config?.tmdb_api_base || "https://api.themoviedb.org/3",
      tmdb_web_base: state.config?.tmdb_web_base || "https://www.themoviedb.org",
      tmdb_image_base: state.config?.tmdb_image_base || "https://image.tmdb.org/t/p/w500",
      ui_theme: normalizeTheme(state.config?.ui_theme || state.config?.interface_theme),
      interface_theme: normalizeTheme(state.config?.ui_theme || state.config?.interface_theme),
    };
  }

  const formData = new FormData(form);
  const currentProvider = normalizeRemoteProvider(formData.get("remote_provider"));
  const remoteProfiles = getRemoteProfiles(state.config || {});
  remoteProfiles[currentProvider] = {
    webdav_host: String(formData.get("webdav_host") || "").trim(),
    webdav_user: String(formData.get("webdav_user") || "").trim(),
    webdav_pass: String(formData.get("webdav_pass") || "").trim(),
    remote_cookie: String(formData.get("remote_cookie") || "").trim(),
    openlist_source_mode: normalizeOpenListSourceMode(
      currentProvider === "openlist"
        ? formData.get("openlist_source_mode")
        : (remoteProfiles.openlist?.openlist_source_mode || state.config?.openlist_source_mode)
    ),
    saved_mount_dirs: [...state.webdavDirs],
  };
  
  // 处理视频格式，从逗号分隔的字符串转换为数组
  const videoFormatsStr = formData.get("video_formats") || "";
  const videoFormats = videoFormatsStr
    .split(",")
    .map(fmt => fmt.trim())
    .filter(fmt => fmt);
  
  return {
    remote_provider: currentProvider,
    remote_profiles: remoteProfiles,
    webdav_host: String(formData.get("webdav_host") || "").trim(),
    webdav_user: String(formData.get("webdav_user") || "").trim(),
    webdav_pass: String(formData.get("webdav_pass") || "").trim(),
    remote_cookie: String(formData.get("remote_cookie") || "").trim(),
    openlist_source_mode: normalizeOpenListSourceMode(formData.get("openlist_source_mode") || state.config?.openlist_source_mode),
    scan_max_depth: Number(formData.get("scan_max_depth") || 2),
    saved_mount_dirs: [...state.webdavDirs],
    local_scan_max_depth: Number(formData.get("local_scan_max_depth") || 3),
    local_mount_dirs: [...state.localDirs],
    potplayer_path: String(formData.get("potplayer_path") || "").trim(),
    vlc_path: String(formData.get("vlc_path") || "").trim(),
    default_player: String(formData.get("default_player") || "potplayer"),
    video_formats: videoFormats,
    enable_auto_scrape: formData.get("enable_auto_scrape") === "true",
    scrape_source: "auto",
    tmdb_api_key: String(formData.get("tmdb_api_key") || "").trim(),
    tmdb_api_base: String(formData.get("tmdb_api_base") || "https://api.themoviedb.org/3").trim(),
    tmdb_web_base: String(formData.get("tmdb_web_base") || "https://www.themoviedb.org").trim(),
    tmdb_image_base: String(formData.get("tmdb_image_base") || "https://image.tmdb.org/t/p/w500").trim(),
    ui_theme: normalizeTheme(formData.get("ui_theme")),
    interface_theme: normalizeTheme(formData.get("ui_theme")),
  };
}

function renderSetupState(title, description, actionLabel) {
  return `
    <div class="empty-state">
      <div class="empty-state-inner">
        <span class="section-eyebrow">${"开始接入"}</span>
        <h3>${title}</h3>
        <p>${description}</p>
        <div class="form-actions centered-actions">
          <button class="primary-btn" onclick="window.__openSettingsFromInline && window.__openSettingsFromInline()">${actionLabel}</button>
        </div>
      </div>
    </div>
  `;
}

window.__openSettingsFromInline = () => {
  state.view = "settings";
  render();
};

function renderEmptyState() {
  const copy =
    state.search
      ? "换个关键词再试试，或者清空搜索条件。"
      : "先刷新片库，或者检查当前媒体源配置是否正确。";

  return `
    <div class="empty-state">
      <div class="empty-state-inner">
        <span class="section-eyebrow">${state.search ? "没有结果" : "片库为空"}</span>
        <h3>${state.search ? "没有匹配结果" : "这里暂时还是空的"}</h3>
        <p>${copy}</p>
      </div>
    </div>
  `;
}

async function openDetail(movie) {
  state.selectedMovie = movie;
  state.selectedSeasonPath = movie.resume_path || (Array.isArray(movie.seasons) && movie.seasons.length ? movie.seasons[0].path : movie.path);
  state.selectedEpisode = 0;
  renderDetail();
  openModal("detailModal");

  const recentPath = state.selectedSeasonPath || movie.path;
  const payload = await guarded(() =>
    api("/api/movies/recent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: recentPath }),
    })
  );
  if (payload) {
    state.stats = payload.stats;
    renderStats();
  }
}

function renderDetail() {
  const movie = state.selectedMovie;
  if (!movie) return;
  const currentSeason = getActiveSeasonEntry(movie) || movie;
  const currentTitle = currentSeason.title || currentSeason.name || movie.title || movie.name || "未命名";
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
  const playbackText = formatPlaybackText(currentSeason.playback);
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
  const episodeCards = currentSeason.is_series
    ? `
      <div class="detail-episode-strip">
        ${(currentSeason.episodes || []).map((episode, index) => `
          <button class="episode-card ${index === state.selectedEpisode ? "active" : ""}" data-episode-btn="${index}" title="${"双击播放这一集"}">
            <span class="episode-card-index">E${String(index + 1).padStart(2, "0")}</span>
            <strong>${escapeHtml(episode || `第 ${index + 1} 集`)}</strong>
            <span>${escapeHtml(seasonLabel)}</span>
          </button>
        `).join("")}
      </div>
    `
    : "";

  document.getElementById("detailContent").innerHTML = `
    <div class="detail-cinematic-shell">
      <div class="detail-backdrop">
        ${cover ? `<img src="${cover}" alt="${title}">` : `<div class="detail-backdrop-fallback"></div>`}
        <div class="detail-backdrop-mask"></div>
      </div>
      <div class="detail-overlay-content">
        <div class="detail-poster-column">
          <div class="detail-cover">
            ${cover ? `<img src="${cover}" alt="${title}">` : `<div class="poster-fallback">${"暂无封面"}</div>`}
          </div>
        </div>
        <div class="detail-info-column">
          <div class="detail-hero detail-hero-rich">
            <span class="section-eyebrow">${"片库详情"}</span>
            <h3>${title}</h3>
            ${movie.is_series ? `<div class="detail-season-name">${escapeHtml(seasonLabel)}</div>` : ""}
            <div class="detail-meta">${meta}</div>
            ${playbackText ? `<div class="detail-resume-pill">${escapeHtml(playbackText)}</div>` : ""}
            ${progressPercent > 0 ? `<div class="detail-progress"><span style="width:${progressPercent}%"></span></div>` : ""}
            <div class="detail-summary">${escapeHtml(currentSeason.intro || movie.intro || "暂无简介")}</div>
          </div>
          <div class="detail-actions">
            <button class="detail-action primary" data-play-movie="${escapeAttr(currentSeason.path)}" data-episode-index="${state.selectedEpisode}">${playbackText ? "继续播放" : "播放"}</button>
            <button class="detail-action favorite ${currentSeason.is_favorite ? "active" : ""}" data-toggle-favorite="${escapeAttr(currentSeason.path)}">${currentSeason.is_favorite ? "取消收藏" : "加入收藏"}</button>
            <button class="detail-action" data-edit-movie="${escapeAttr(currentSeason.path)}">${"编辑信息"}</button>
            <button class="detail-action" data-scrape-movie="${escapeAttr(currentSeason.path)}">${"重新补全"}</button>
            <button class="detail-action" data-manual-match="${escapeAttr(currentSeason.path)}">${"手动匹配"}</button>
            <button class="detail-action" data-manage-tags="${escapeAttr(currentSeason.path)}">${"管理标签"}</button>
          </div>
          <div class="detail-section-grid">
            <div class="detail-section detail-glass-card">
              <div class="detail-section-title">${"剧集概览"}</div>
              <div class="detail-overview-metrics">
                <div><strong>${movie.season_count || 1}</strong><span>${"季 / 分篇"}</span></div>
                <div><strong>${currentSeason.episode_count || currentSeason.episode_files?.length || movie.episode_count || 1}</strong><span>${"当前集数"}</span></div>
                <div><strong>${escapeHtml(String(progressPercent > 0 ? `${progressPercent}%` : (currentSeason.year || movie.year || "--")))}</strong><span>${progressPercent > 0 ? "已观看" : "年份"}</span></div>
              </div>
            </div>
            <div class="detail-section detail-glass-card">
              <div class="detail-section-title">${"源路径"}</div>
              <div class="detail-copy compact">${escapeHtml(formatMovieSourcePath(currentSeason))}</div>
            </div>
          </div>
          ${seasonPicker ? `<div class="detail-section detail-glass-card"><div class="detail-section-title">${"选择季别"}</div>${seasonPicker}</div>` : ""}
          ${movie.tags && movie.tags.length > 0 ? `<div class="detail-section detail-glass-card"><div class="detail-section-title">${"标签"}</div><div class="tags-container">${movie.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join(" ")}</div></div>` : ""}
          ${episodeCards ? `<div class="detail-section detail-glass-card"><div class="detail-section-title">${"分集"}</div>${episodeCards}</div>` : ""}
        </div>
      </div>
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
      const playBtn = document.querySelector(".detail-action.primary[data-play-movie]");
      if (playBtn) playBtn.dataset.episodeIndex = String(index);
    });
  });

  const seasonSelect = document.getElementById("detailSeasonSelect");
  if (seasonSelect) {
    seasonSelect.addEventListener("change", () => {
      state.selectedSeasonPath = seasonSelect.value;
      state.selectedEpisode = 0;
      syncSelectedMovie();
      renderDetail();
    });
  }
}

function openEditModal(movie) {
  state.editMovie = movie;
  const form = document.getElementById("editForm");
  form.elements.title.value = movie.title || "";
  form.elements.name.value = movie.name || "";
  form.elements.type.value = movie.type || "电影";
  form.elements.year.value = movie.year || 2024;
  form.elements.intro.value = movie.intro || "";
  openModal("editModal");
}

async function openDirectoryModal(scope, path) {
  state.directoryScope = scope;
  _openlistSelectedMount = null;
  await loadDirectoryPath(path);
  openModal("directoryModal");
}

function getDirectoryRootPath() {
  return state.directoryScope === "local" ? "" : getRemoteRootPath();
}

function getDirectorySet(scope) {
  return scope === "local" ? state.localDirs : state.webdavDirs;
}

function getLocalParentPath(path) {
  const normalized = String(path || "").replace(/[\\/]+$/, "");
  if (!normalized) return "";
  if (/^[A-Za-z]:$/.test(normalized)) return "";

  const parent = normalized.replace(/[\\/][^\\/]+$/, "");
  if (!parent) return "";
  if (/^[A-Za-z]:$/.test(parent)) return `${parent}\\`;
  return parent;
}

let _directoryLoading = false;
let _openlistSelectedMount = null; // 当前选中的 OpenList 挂载点（如 "/quark"）

async function loadDirectoryPath(path) {
  if (_directoryLoading) return;
  _directoryLoading = true;
  const container = document.getElementById("directoryList");
  if (container) container.innerHTML = '<div class="directory-loading">加载中…</div>';
  try {
    state.directoryPath = state.directoryScope === "local" ? path : normalizeRemoteDirectoryPath(path);
    if (state.directoryScope === "local") {
      const payload = await guarded(() => api(`/api/local-directories?path=${encodeURIComponent(path)}`));
      if (!payload) { state.directoryItems = []; renderDirectoryModal(); return; }
      state.directoryItems = payload;
    } else {
      const isOpenlist = normalizeRemoteProvider(state.config?.remote_provider) === "openlist";
      const isRoot = isRemoteRootPath(state.directoryPath);

      if (isOpenlist && isRoot) {
        _openlistSelectedMount = null;
        let storages = [];
        try {
          const data = await api("/api/openlist/storages");
          storages = (data.items || []).filter((s) => s.status === "work");
        } catch (e) {
          showToast("获取挂载列表失败: " + (e.message || "未知错误"), "error");
        }
        if (storages.length === 1 && storages[0].mount_path === "/") {
          _openlistSelectedMount = "/";
          state.directoryItems = await _fetchOpenListDirs("/");
        } else {
          state.directoryItems = storages.length
            ? storages.map((s) => ({
                name: s.mount_path === "/" ? (s.driver || "根目录") : s.mount_path.replace(/^\//, ""),
                full_path: normalizeRemoteDirectoryPath(s.mount_path),
                _isMount: true,
                _driver: s.driver || "",
              }))
            : [];
        }
      } else if (isOpenlist) {
        _openlistSelectedMount = resolveOpenListMountRoot(state.directoryPath);
        state.directoryItems = await _fetchOpenListDirs(state.directoryPath);
      } else {
        const settingsPayload = getSettingsPayload();
        settingsPayload.path = state.directoryPath;
        const payload = await guarded(() =>
          api("/api/directories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settingsPayload),
          })
        );
        if (!payload) { state.directoryItems = []; renderDirectoryModal(); return; }
        state.directoryItems = payload;
      }
    }
    renderDirectoryModal();
  } catch (e) {
    showToast("加载目录失败: " + (e.message || "未知错误"), "error");
    state.directoryItems = [];
    renderDirectoryModal();
  } finally {
    _directoryLoading = false;
  }
}

// 用 OpenList API 获取当前层级的子目录
async function _fetchOpenListDirs(path) {
  try {
    const result = await api(`/api/openlist/directories?path=${encodeURIComponent(path)}`);
    return result;
  } catch (e) {
    console.warn("OpenList API 失败，回退到 WebDAV:", e.message);
  }
  const sp = getSettingsPayload();
  sp.path = path;
  return await guarded(() =>
    api("/api/directories", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sp) })
  ) || [];
}

function renderDirectoryModal() {
  const scopeLabel = document.getElementById("directoryScopeLabel");
  const title = document.getElementById("directoryTitle");
  const currentPath = document.getElementById("dirCurrentPath");
  const selectCurrentBtn = document.getElementById("dirSelectCurrentBtn");
  const container = document.getElementById("directoryList");
  const searchInput = document.getElementById("dirSearchInput");
  const selectedSet = getDirectorySet(state.directoryScope);

  const isOpenlist = normalizeRemoteProvider(state.config?.remote_provider) === "openlist";
  const remoteScopeLabel = isOpenlist ? "OpenList 目录" : "WebDAV 目录";
  const remoteTitle = isOpenlist ? "选择 OpenList 扫描目录" : "选择 WebDAV 扫描目录";
  scopeLabel.textContent = state.directoryScope === "local" ? "本地目录" : remoteScopeLabel;
  title.textContent = state.directoryScope === "local" ? "选择本地扫描目录" : remoteTitle;
  currentPath.textContent =
    state.directoryScope === "local" ? (state.directoryPath || "此电脑") : formatRemotePathLabel(state.directoryPath);
  selectCurrentBtn.disabled =
    (state.directoryScope === "local" && !state.directoryPath) ||
    (state.directoryScope === "webdav" && isRemoteRootPath(state.directoryPath) && !_openlistSelectedMount);

  if (searchInput) {
    searchInput.style.display = "";
    searchInput.value = "";
  }

  if (!state.directoryItems.length) {
    container.innerHTML = `<div class="mount-item"><span>${"当前目录下没有子目录。"}</span></div>`;
    return;
  }

  function renderList(filter) {
    const q = (filter || "").toLowerCase();
    const items = q
      ? state.directoryItems.filter((item) => item.name.toLowerCase().includes(q))
      : state.directoryItems;

    if (!items.length) {
      container.innerHTML = `<div class="mount-item"><span>${"没有匹配的目录"}</span></div>`;
      return;
    }

    container.innerHTML = items
      .map((item) => {
        const entryPath = item.full_path;
        const checked = selectedSet.has(entryPath) ? "checked" : "";
        const isMount = item._isMount;
        const mountClass = isMount ? " mount-point" : "";
        const mountAttr = isMount ? ' data-is-mount="1"' : "";
        const driverTag = isMount && item._driver ? `<span class="mount-driver-tag">${escapeHtml(item._driver)}</span>` : "";
        return `
          <div class="directory-item${mountClass}" data-directory-item="${escapeAttr(entryPath)}"${mountAttr} data-enter-dir="${escapeAttr(entryPath)}">
            <div class="directory-meta">
              <strong>${escapeHtml(item.name)}${driverTag}</strong>
              <span>${escapeHtml(entryPath)}</span>
            </div>
            <div class="card-actions">
              <button type="button" class="ghost-btn dir-check-btn" data-dir-check-toggle="${escapeAttr(entryPath)}" title="${checked ? "取消选择" : "选中此目录"}">${checked ? "✓" : "+"}</button>
            </div>
          </div>
        `;
      })
      .join("");

    // 点击行进入子目录
    container.querySelectorAll("[data-enter-dir]").forEach((row) => {
      row.addEventListener("click", async (e) => {
        if (e.target.closest("[data-dir-check-toggle]")) return;
        await loadDirectoryPath(row.dataset.enterDir);
      });
    });

    // 选择按钮
    container.querySelectorAll("[data-dir-check-toggle]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const path = btn.dataset.dirCheckToggle;
        if (selectedSet.has(path)) {
          selectedSet.delete(path);
          btn.textContent = "+";
          btn.title = "选中此目录";
        } else {
          selectedSet.add(path);
          btn.textContent = "✓";
          btn.title = "取消选择";
        }
      });
    });
  }

  renderList("");

  if (searchInput) {
    searchInput.oninput = () => renderList(searchInput.value);
  }
}

function openCandidateModal(movie) {
  state.candidateMovie = movie;
  state.candidateSelection = null;
  state.candidateItems = [];
  state.candidateDiagnostics = [];
  state.candidateSearchText = movie.name || movie.title || "";
  state.candidateStatus = { kind: "info", text: "输入更准确的片名、季数或年份，可以同时从 TMDB、豆瓣和 AniBK 拿到更稳的候选结果。" };
  document.getElementById("candidateSearchInput").value = state.candidateSearchText;
  renderCandidateModal();
  openModal("candidateModal");
  loadCandidates();
}

async function openTagsModal(movie) {
  state.selectedMovie = movie;
  state.tagInputValue = "";
  await loadTags();
  document.getElementById("tagInput").value = state.tagInputValue;
  renderTagsList();
  openModal("tagsModal");
}

async function loadTags() {
  const payload = await guarded(() => api("/api/tags"));
  if (payload) {
    state.allTags = payload.tags;
  }
}

async function addTag(moviePath, tag) {
  if (!tag.trim()) return;
  
  const payload = await guarded(() => api(`/api/movies/${encodeURIComponent(moviePath)}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag: tag.trim() }),
  }));
  
  if (payload) {
    patchMovie(payload.movie);
    if (state.selectedMovie && state.selectedMovie.path === moviePath) {
      state.selectedMovie = payload.movie;
      renderDetail();
    }
    await loadTags();
    renderTagsList();
    showToast("标签添加成功");
  }
}

async function removeTag(moviePath, tag) {
  const payload = await guarded(() => api(`/api/movies/${encodeURIComponent(moviePath)}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  }));
  
  if (payload) {
    patchMovie(payload.movie);
    if (state.selectedMovie && state.selectedMovie.path === moviePath) {
      state.selectedMovie = payload.movie;
      renderDetail();
    }
    await loadTags();
    renderTagsList();
    showToast("标签移除成功");
  }
}

function renderTagsList() {
  const movie = state.selectedMovie;
  if (!movie) return;
  
  const tagsList = document.getElementById("tagsList");
  
  // 获取电影的标签
  const movieTags = movie.tags || [];
  
  // 获取所有标签
  const allTags = Object.keys(state.allTags);
  
  tagsList.innerHTML = `
    <div class="tags-section">
      <h4>${"电影标签"}</h4>
      ${movieTags.length > 0 ? `
        <div class="tags-grid">
          ${movieTags.map(tag => `
            <div class="tag-item">
              <span class="tag">${escapeHtml(tag)}</span>
              <button class="tag-remove" data-remove-tag="${escapeAttr(tag)}">×</button>
            </div>
          `).join('')}
        </div>
      ` : `<p>${"暂无标签"}</p>`}
    </div>

    ${allTags.length > 0 ? `
    <div class="tags-section">
      <h4>${"所有标签"}</h4>
      <div class="tags-grid">
        ${allTags.map(tag => !movieTags.includes(tag) ? `
          <div class="tag-item">
            <span class="tag">${escapeHtml(tag)}</span>
            <button class="tag-add" data-add-tag="${escapeAttr(tag)}">+</button>
          </div>
        ` : '').join('')}
      </div>
    </div>
    ` : ''}
  `;
  
  // 添加标签事件
  document.querySelectorAll("[data-add-tag]").forEach(button => {
    button.addEventListener("click", () => {
      const tag = button.dataset.addTag;
      addTag(movie.path, tag);
    });
  });
  
  // 移除标签事件
  document.querySelectorAll("[data-remove-tag]").forEach(button => {
    button.addEventListener("click", () => {
      const tag = button.dataset.removeTag;
      removeTag(movie.path, tag);
    });
  });
}

async function loadCandidates() {
  if (!state.candidateMovie) return;
  state.candidateSearchText = document.getElementById("candidateSearchInput").value.trim();
  state.candidateStatus = { kind: "info", text: "正在搜索候选结果..." };
  renderCandidateModal();

  const payload = await guarded(() =>
    api("/api/movies/search-candidates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        movie_path: state.candidateMovie.path,
        custom_name: state.candidateSearchText || null,
      }),
    })
  );
  if (!payload) {
    state.candidateItems = [];
    state.candidateDiagnostics = [];
    state.candidateSelection = null;
    state.candidateStatus = { kind: "error", text: "这次没有拿到候选结果，试试补上更完整的片名、季数或年份。" };
    renderCandidateModal();
    return;
  }

  state.candidateItems = payload.items || [];
  state.candidateDiagnostics = payload.diagnostics || [];
  state.candidateSelection = state.candidateItems[0] || null;
  state.candidateStatus = state.candidateItems.length
    ? { kind: "success", text: `找到 ${state.candidateItems.length} 个结果，优先看分数、来源、年份和命中搜索词。` }
    : { kind: "error", text: "没有找到可用结果，换一个更完整的搜索词试试。" };
  renderCandidateModal();
}

function renderCandidateModal() {
  const list = document.getElementById("candidateList");
  const applyBtn = document.getElementById("candidateApplyBtn");
  const currentTitle = escapeHtml(state.candidateMovie?.title || state.candidateMovie?.name || "当前条目");
  const status = state.candidateStatus
    ? `<div class="candidate-status ${escapeAttr(state.candidateStatus.kind || "")}">${escapeHtml(state.candidateStatus.text || "")}</div>`
    : "";
  const diagnostics = state.candidateDiagnostics?.length
    ? `
      <div class="candidate-diagnostics">
        ${state.candidateDiagnostics.map((item) => `
          <div class="candidate-diag ${escapeAttr(item.status || "idle")}">
            <strong>${escapeHtml(item.source || "SOURCE")}</strong>
            <span>${escapeHtml(
              item.status === "success"
                ? `${"命中"} ${item.hits || 0} ${"个结果，查询"} ${item.queries || 0} ${"次"}`
                : item.status === "empty"
                  ? `${"没有命中结果，查询"} ${item.queries || 0} ${"次"}`
                  : item.error || "本次未返回结果"
            )}</span>
          </div>
        `).join("")}
      </div>
    `
    : "";

  if (applyBtn) {
    applyBtn.disabled = !state.candidateSelection;
    applyBtn.textContent = state.candidateSelection ? "应用当前候选" : "先选择一个候选";
  }

  if (!state.candidateItems.length) {
    list.innerHTML = `
      <div class="candidate-empty">
        <span class="section-eyebrow">${"手动刮削"}</span>
        <h4>${currentTitle}</h4>
        <p>${"这里会展示 TMDB、豆瓣和 AniBK 的候选结果，优先看分数、年份和命中搜索词。"}</p>
        ${status}
        ${diagnostics}
      </div>
    `;
    return;
  }

  list.innerHTML = `
      <div class="candidate-results-head">
        <div>
          <span class="section-eyebrow">${"手动刮削"}</span>
          <h4>${currentTitle}</h4>
        </div>
      <p>${"优先选择分数更高、年份更近，而且命中搜索词更贴近的结果。"}</p>
      </div>
      ${status}
      ${diagnostics}
      ${state.candidateItems.map((item, index) => `
        <label class="candidate-item ${state.candidateSelection?.url === item.url ? "selected" : ""}">
        <div class="candidate-pick">
          <input type="radio" name="candidateRadio" data-candidate-index="${index}" ${state.candidateSelection?.url === item.url || (!state.candidateSelection && index === 0) ? "checked" : ""}>
        </div>
        <div class="candidate-meta">
          <strong>${escapeHtml(item.title)}</strong>
          <div class="candidate-badges">
            <span class="mini-tag source">${escapeHtml(item.source)}</span>
            <span class="mini-tag">${item.year ? escapeHtml(String(item.year)) : "年份未知"}</span>
            <span class="mini-tag">${typeof item.match_score === "number" ? `${"匹配"} ${Math.round(item.match_score)}` : "待比较"}</span>
            <span class="mini-tag">${index === 0 ? "优先结果" : `${"候选"} ${index + 1}`}</span>
          </div>
          ${item.matched_query ? `<span class="candidate-hint">${"命中搜索词："}${escapeHtml(item.matched_query)}</span>` : ""}
          <span class="candidate-url">${escapeHtml(item.url)}</span>
        </div>
      </label>
    `).join("")}
  `;

  list.querySelectorAll("[data-candidate-index]").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.candidateSelection = state.candidateItems[Number(radio.dataset.candidateIndex)] || null;
      renderCandidateModal();
    });
  });
}

async function playMovie(moviePath, episodeIndex = 0) {
  const payload = await guarded(() =>
    api("/api/movies/play", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath, episode_index: episodeIndex }),
    })
  );
  if (!payload) return;

  showToast("播放器已启动", "success");
  await loadCurrentView();
}

async function savePlaybackProgress(moviePath, progress, duration) {
  const payload = await guarded(() =>
    api(`/api/movies/${encodeURIComponent(moviePath)}/progress`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ progress, duration }),
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
  const payload = await guarded(() =>
    api("/api/recommendations/rate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath, rating }),
    })
  );
  if (!payload) return;
  showToast(`已记录 ${rating} 星偏好`, "success");
  await loadRecommendations();
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

function normalizeRemoteProvider(provider) {
  const value = String(provider || "").trim().toLowerCase();
  return getRemoteProviderOptions().some((item) => item.value === value) ? value : "webdav";
}

function getRemoteProviderPreset(provider) {
  return getRemoteProviderPresets()[normalizeRemoteProvider(provider)] || getRemoteProviderPresets().webdav;
}

function startJobPolling(jobId, source, successMessage) {
  state.activeJobId = jobId;
  jobBanner.classList.remove("hidden");

  const timer = window.setInterval(async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      const total = job.total || 0;
      const current = job.current || 0;
      const isRefresh = String(job.name || "").includes("refresh");
      const sourceLabel = getSourceLabel(source);

      jobTitle.textContent = isRefresh
        ? `${sourceLabel}${"刷新中"}`
        : `${sourceLabel}${"元数据补全中"}`;
      jobMessage.textContent = job.message || "正在处理";
      jobProgressText.textContent = total ? `${current} / ${total}` : "处理中";
      jobProgressBar.style.width = total ? `${Math.min(100, (current / total) * 100)}%` : "25%";

      if (job.status === "completed") {
        window.clearInterval(timer);
        state.activeJobId = null;
        jobBanner.classList.add("hidden");
        jobProgressBar.style.width = "0";
        await loadBootstrap();
        await loadCurrentView();
        if (source === "remote" || source === "combined") {
          await refreshRecommendations(false);
        }
        showToast(successMessage, "success");
      }

      if (job.status === "failed") {
        window.clearInterval(timer);
        state.activeJobId = null;
        jobBanner.classList.add("hidden");
        jobProgressBar.style.width = "0";
        showToast(job.error || "后台任务失败", "error");
      }
    } catch (error) {
      window.clearInterval(timer);
      state.activeJobId = null;
      jobBanner.classList.add("hidden");
      jobProgressBar.style.width = "0";
      showToast(error.message || "读取任务状态失败", "error");
    }
  }, 1000);
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

function renderStats() {
  elements.statsStrip.innerHTML = `
    <article class="stat-chip">
      <strong>${state.stats.all || 0}</strong>
      <span>${"全部条目"}</span>
      <small>${"当前片库总量"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.remote || 0}</strong>
      <span>${"远程条目"}</span>
      <small>${"远程媒体源"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.local || 0}</strong>
      <span>${"本地条目"}</span>
      <small>${"本机挂载目录"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.favorite || 0}</strong>
      <span>${"收藏条目"}</span>
      <small>${"随时可重看"}</small>
    </article>
  `;
}

function showToast(message, kind = "", duration = 2600) {
  const toast = document.createElement("div");
  toast.className = `toast ${kind}`.trim();
  toast.textContent = message;
  
  // 添加动画效果
  toast.style.opacity = "0";
  toast.style.transform = "translateY(20px)";
  toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
  
  elements.toastHost.appendChild(toast);
  
  // 触发动画
  setTimeout(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  }, 10);
  
  window.setTimeout(() => {
    // 淡出动画
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, duration);
}

// 添加加载状态管理
function showLoading(message = null) {
  if (!message) message = "加载中...";
  // 检查是否已存在加载中元素
  let loadingElement = document.getElementById("loadingOverlay");
  if (loadingElement) {
    return; // 已经有加载中状态
  }
  
  loadingElement = document.createElement("div");
  loadingElement.id = "loadingOverlay";
  loadingElement.className = "loading-overlay";
  loadingElement.innerHTML = `
    <div class="loading-content">
      <div class="loading-spinner"></div>
      <p>${message}</p>
    </div>
  `;
  
  document.body.appendChild(loadingElement);
}

function hideLoading() {
  const loadingElement = document.getElementById("loadingOverlay");
  if (loadingElement) {
    loadingElement.style.opacity = "0";
    setTimeout(() => {
      loadingElement.remove();
    }, 300);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function cleanCookie(cookie) {
  if (!cookie) return "";
  let cleaned = cookie.trim();
  // 移除 "Cookie:" 或 "cookie:" 前缀
  cleaned = cleaned.replace(/^cookie:\s*/i, "");
  // 移除首尾的引号
  cleaned = cleaned.replace(/^["']|["']$/g, "");
  // 移除多余的空白字符（保留单个空格）
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  return cleaned;
}

// 解析 OpenList 错误信息，返回用户友好的提示
function parseOpenListError(error, context = "") {
  const msg = error.message || String(error);

  // 登录失败
  if (msg.includes("登录失败") || msg.includes("login")) {
    if (msg.includes("password") || msg.includes("密码")) {
      return "密码错误，请检查管理员密码或点击「重置密码」";
    }
    if (msg.includes("connect") || msg.includes("connection")) {
      return "无法连接到 OpenList 服务，请检查服务是否正常运行";
    }
    return "登录失败，请检查管理员密码是否正确";
  }

  // 存储驱动相关
  if (msg.includes("UNIQUE constraint") || msg.includes("mount_path")) {
    return "挂载路径已存在，请使用不同的路径或直接更新已有驱动";
  }
  if (msg.includes("invalid header field value") || msg.includes("Cookie")) {
    return "Cookie 格式无效，请重新从浏览器复制（不要包含 \"Cookie:\" 前缀）";
  }
  if (msg.includes("token") || msg.includes("refresh_token")) {
    return "Token 无效或已过期，请重新获取";
  }
  if (msg.includes("timeout") || msg.includes("超时")) {
    return "请求超时，请检查网络连接或稍后重试";
  }
  if (msg.includes("net/http") || msg.includes("network")) {
    return "网络请求失败，请检查网络连接";
  }

  // 下载相关
  if (context === "download") {
    if (msg.includes("404") || msg.includes("Not Found")) {
      return "下载链接不存在，请检查版本号是否正确";
    }
    if (msg.includes("proxy") || msg.includes("代理")) {
      return "代理连接失败，请检查代理设置";
    }
    return "下载失败，请检查网络连接或尝试使用代理";
  }

  // 操作失败
  if (context === "toggle") {
    return "切换状态失败，请检查存储驱动配置是否正确";
  }
  if (context === "delete") {
    return "删除失败，请稍后重试";
  }

  // 默认返回原始信息
  return msg;
}

// ---- OpenList 管理函数 ----

let _openlistPollTimer = null;

async function fetchOpenListStatus() {
  try {
    const data = await api("/api/openlist/status");
    state.openlistStatus = data;
    return data;
  } catch (e) {
    state.openlistStatus = { status: "error", error_message: e.message, binary_available: false };
    return state.openlistStatus;
  }
}

async function fetchOpenListStorages() {
  try {
    const data = await api("/api/openlist/storages");
    state.openlistStorages = (data.items || []).map((item) => ({
      ...item,
      mount_path: normalizeRemoteDirectoryPath(item.mount_path),
    }));
  } catch (e) {
    state.openlistStorages = [];
  }
  return state.openlistStorages;
}

async function fetchOpenListDrivers() {
  try {
    const data = await api("/api/openlist/drivers");
    state.openlistDrivers = data.items || [];
  } catch (e) {
    state.openlistDrivers = [];
  }
  return state.openlistDrivers;
}

async function fetchOpenListConfig() {
  try {
    const data = await api("/api/openlist/config");
    if (state.config) {
      state.config.openlist_enabled = data.enabled;
      state.config.openlist_port = data.port;
      state.config.openlist_admin_password = data.admin_password;
      state.config.openlist_auto_start = data.auto_start;
      state.config.openlist_binary_version = data.binary_version;
    }
    return data;
  } catch (e) {
    return null;
  }
}

function startOpenListStatusPolling() {
  stopOpenListStatusPolling();
  _openlistPollTimer = setInterval(async () => {
    if (state.view !== "settings") {
      stopOpenListStatusPolling();
      return;
    }
    await fetchOpenListStatus();
    updateOpenListStatusUI();
  }, 15000);
}

function stopOpenListStatusPolling() {
  if (_openlistPollTimer) {
    clearInterval(_openlistPollTimer);
    _openlistPollTimer = null;
  }
}

function updateOpenListStatusUI() {
  const status = state.openlistStatus;
  if (!status) return;
  const statusText = document.getElementById("openlistStatusText");
  const portText = document.getElementById("openlistPortText");
  const versionText = document.getElementById("openlistVersionText");
  const storageCount = document.getElementById("openlistStorageCount");

  if (statusText) {
    if (!status.binary_available) {
      statusText.textContent = "未安装";
      statusText.style.color = "var(--color-muted, #999)";
    } else {
      const statusMap = {
        stopped: "已停止",
        starting: "启动中...",
        running: "运行中",
        error: "错误",
      };
      statusText.textContent = statusMap[status.status] || status.status;
      statusText.style.color = status.status === "running" ? "var(--color-positive, #4caf50)" : status.status === "error" ? "var(--color-danger, #f44336)" : "";
    }
  }
  if (portText) portText.textContent = status.port || "5244";
  if (versionText) versionText.textContent = status.version || (status.binary_available ? "未知" : "未下载");
  if (storageCount) storageCount.textContent = String(state.openlistStorages.length);
}

function renderOpenListStorageList(storages) {
  if (!storages || storages.length === 0) {
    return `<div class="mount-item empty"><span>${"还没有配置存储驱动"}</span></div>`;
  }
  return storages.map((s) => {
    const statusLabel = s.status === "work" ? "工作中" : s.status === "disabled" ? "已禁用" : s.status;
    const statusColor = s.status === "work" ? "var(--color-positive, #4caf50)" : s.status === "disabled" ? "var(--color-muted, #999)" : "var(--color-danger, #f44336)";
    const statusIcon = s.status === "work" ? "✓" : s.status === "disabled" ? "○" : "✕";
    return `
      <div class="mount-item" style="display:flex; align-items:center; gap:0.75rem; padding:0.75rem 0; border-bottom:1px solid var(--color-border, #eee);">
        <span style="flex:1; font-weight:500;">${escapeHtml(s.mount_path)}</span>
        <span style="color:var(--color-muted); font-size:0.85rem; min-width:80px;">${escapeHtml(s.driver)}</span>
        <span style="color:${statusColor}; font-size:0.85rem; display:flex; align-items:center; gap:0.25rem;">
          <span style="font-size:0.75rem;">${statusIcon}</span>
          ${statusLabel}
        </span>
        <div style="display:flex; gap:0.25rem;">
          <button class="ghost-btn" type="button" data-openlist-edit="${s.id}" data-openlist-driver="${escapeAttr(s.driver)}" data-openlist-mount="${escapeAttr(s.mount_path)}" data-openlist-addition='${escapeAttr(JSON.stringify(s.addition || {}))}'>编辑</button>
          <button class="ghost-btn" type="button" data-openlist-toggle="${s.id}" data-openlist-enable="${s.status !== "work"}">${s.status === "work" ? "禁用" : "启用"}</button>
          <button class="ghost-btn danger-btn" type="button" data-openlist-delete="${s.id}">删除</button>
        </div>
      </div>`;
  }).join("");
}

function renderOpenListDriverForm(drivers, existingData = {}) {
  const selectedDriver = state.openlistDriverForm?.driver || "";
  const driverTemplate = drivers.find((d) => d.driver === selectedDriver);

  let fieldsHtml = "";
  if (driverTemplate) {
    fieldsHtml = driverTemplate.fields.map((f) => {
      const val = escapeAttr(existingData[f.key] || state.openlistDriverForm?.[f.key] || "");
      if (f.type === "hidden") return `<input type="hidden" name="openlist_field_${f.key}" value="${val}">`;
      const inputType = f.type === "textarea" ? "textarea" : f.type === "password" ? "password" : "text";
      const isCookieField = f.key === "cookie";
      const tag = inputType === "textarea"
        ? `<textarea name="openlist_field_${f.key}" rows="${isCookieField ? 4 : 3}" placeholder="${escapeAttr(f.placeholder || "")}" ${isCookieField ? 'class="cookie-input"' : ''}>${escapeHtml(val)}</textarea>`
        : `<input name="openlist_field_${f.key}" type="${inputType}" value="${val}" placeholder="${escapeAttr(f.placeholder || "")}">`;
      const helpText = f.help ? `<small style="color:var(--color-muted); font-size:0.8rem; margin-top:0.25rem; display:block;">${escapeHtml(f.help)}</small>` : "";
      return `<label><span>${escapeHtml(f.label)}${f.required ? " *" : ""}</span>${tag}${helpText}</label>`;
    }).join("");
  }

  const isEdit = !!state.openlistDriverForm?.edit_id;
  const title = isEdit ? "编辑存储驱动" : "添加存储驱动";

  return `
    <div class="settings-card-head" style="margin-bottom:0.75rem;">
      <div><span>${title}</span></div>
    </div>
    <div class="settings-field-grid">
      <label>
        <span>${"驱动类型"}</span>
        <select id="openlistDriverSelect" ${isEdit ? "disabled" : ""}>
          <option value="">${"-- 选择驱动 --"}</option>
          ${drivers.map((d) => `<option value="${d.driver}" ${d.driver === selectedDriver ? "selected" : ""}>${escapeHtml(d.label)}</option>`).join("")}
        </select>
      </label>
      <label>
        <span>${"挂载路径"}</span>
        <input id="openlistMountPath" value="${escapeAttr(state.openlistDriverForm?.mount_path || "")}" placeholder="/quark">
      </label>
      ${fieldsHtml}
    </div>
    <div class="form-actions" style="margin-top:0.75rem; gap:0.5rem;">
      <button class="primary-btn" type="button" id="openlistSaveDriverBtn">${isEdit ? "更新驱动" : "保存驱动"}</button>
      <button class="ghost-btn" type="button" id="openlistCancelDriverBtn">${"取消"}</button>
    </div>`;
}

async function openlistAction(action) {
  try {
    const data = await api(`/api/openlist/${action}`, { method: "POST" });
    showToast(data.message || `${action} 操作完成`, data.success ? "success" : "warning");
    await fetchOpenListStatus();
    updateOpenListStatusUI();
  } catch (e) {
    showToast(`操作失败: ${parseOpenListError(e)}`, "error");
  }
}

async function openlistDownloadBinary() {
  const progressPanel = document.getElementById("openlistDownloadProgress");
  const progressBar = document.getElementById("openlistDownloadProgressBar");
  const progressText = document.getElementById("openlistDownloadProgressText");
  if (progressPanel) progressPanel.classList.remove("hidden");

  try {
    const { job_id } = await api("/api/openlist/download", { method: "POST" });
    const poll = setInterval(async () => {
      try {
        const job = await api(`/api/jobs/${job_id}`);
        if (progressBar) progressBar.style.width = `${job.progress_percent || 0}%`;
        if (progressText) progressText.textContent = job.message || "下载中...";
        if (job.status === "completed" || job.status === "failed") {
          clearInterval(poll);
          if (job.status === "completed") {
            showToast("OpenList 下载完成", "success");
            await fetchOpenListStatus();
            updateOpenListStatusUI();
          } else {
            showToast(`下载失败: ${job.error || "未知错误"}`, "error");
          }
          setTimeout(() => { if (progressPanel) progressPanel.classList.add("hidden"); }, 3000);
        }
      } catch (e) {
        clearInterval(poll);
        if (progressPanel) progressPanel.classList.add("hidden");
      }
    }, 1000);
  } catch (e) {
    showToast(`下载失败: ${parseOpenListError(e, "download")}`, "error");
    if (progressPanel) progressPanel.classList.add("hidden");
  }
}

async function bindOpenListPanel() {
  const startBtn = document.getElementById("openlistStartBtn");
  const stopBtn = document.getElementById("openlistStopBtn");
  const restartBtn = document.getElementById("openlistRestartBtn");
  const downloadBtn = document.getElementById("openlistDownloadBtn");
  const driverSelect = document.getElementById("openlistDriverSelect");
  const saveDriverBtn = document.getElementById("openlistSaveDriverBtn");
  const cancelDriverBtn = document.getElementById("openlistCancelDriverBtn");

  if (startBtn) startBtn.onclick = () => openlistAction("start");
  if (stopBtn) stopBtn.onclick = () => openlistAction("stop");
  if (restartBtn) restartBtn.onclick = () => openlistAction("restart");
  if (downloadBtn) downloadBtn.onclick = () => openlistDownloadBinary();

  // 重置密码
  const resetPasswordBtn = document.getElementById("openlistResetPasswordBtn");
  if (resetPasswordBtn) {
    resetPasswordBtn.onclick = async () => {
      const passwordInput = document.querySelector("[name='openlist_admin_password']");
      const password = passwordInput?.value?.trim();
      if (!password) {
        showToast("请先填写新密码", "warning");
        return;
      }
      try {
        const result = await api("/api/openlist/reset-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        });
        if (result.success) {
          showToast("密码重置成功", "success");
        } else {
          showToast(result.message || "密码重置失败", "error");
        }
      } catch (e) {
        showToast(`密码重置失败: ${parseOpenListError(e)}`, "error");
      }
    };
  }

  // 驱动类型选择
  const defaultMountPaths = {
    Quark: "/quark",
    AliyundriveOpen: "/aliyun",
    "115 Cloud": "/115",
    BaiduNetdisk: "/baidu",
    "AList V3": "/alist",
    WebDav: "/webdav",
  };
  if (driverSelect) {
    driverSelect.onchange = () => {
      const driver = driverSelect.value;
      const defaultPath = defaultMountPaths[driver] || "";
      state.openlistDriverForm = driver ? { driver, mount_path: defaultPath } : null;
      const formEl = document.getElementById("openlistDriverForm");
      if (formEl) formEl.innerHTML = state.openlistDriverForm ? renderOpenListDriverForm(state.openlistDrivers) : "";
      bindOpenListPanel();
    };
  }

  // 保存驱动
  if (saveDriverBtn) {
    saveDriverBtn.onclick = async () => {
      const driver = document.getElementById("openlistDriverSelect")?.value;
      const mountPath = document.getElementById("openlistMountPath")?.value?.trim();
      if (!driver) { showToast("请选择驱动类型", "warning"); return; }
      if (!mountPath) { showToast("请填写挂载路径", "warning"); return; }

      const normalizedPath = normalizeRemoteDirectoryPath(mountPath);
      document.getElementById("openlistMountPath").value = normalizedPath;

      const template = state.openlistDrivers.find((d) => d.driver === driver);
      const addition = {};
      if (template) {
        for (const field of template.fields) {
          const el = document.querySelector(`[name="openlist_field_${field.key}"]`);
          if (el) {
            let value = el.value;
            // 自动清理 Cookie 字段
            if (field.key === "cookie") {
              value = cleanCookie(value);
            }
            addition[field.key] = value;
          }
        }
      }

      if (driver === "Quark" && !String(addition.root_folder_id || "").trim()) {
        addition.root_folder_id = "0";
      }

      try {
        const editId = state.openlistDriverForm?.edit_id;
        const isEdit = !!editId;

        if (isEdit) {
          // 记录编辑前的挂载路径
          const oldStorage = state.openlistStorages.find((s) => String(s.id) === String(editId));
          const oldMountPath = oldStorage?.mount_path;

          // 更新现有驱动
          await api("/api/openlist/storages", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: editId, mount_path: normalizedPath, driver, addition }),
          });
          showToast("存储驱动更新成功", "success");

          // 挂载路径变更时同步扫描目录
          if (oldMountPath && oldMountPath !== normalizedPath && state.webdavDirs.has(oldMountPath)) {
            state.webdavDirs.delete(oldMountPath);
          }
        } else {
          // 添加新驱动
          await api("/api/openlist/storages", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mount_path: normalizedPath, driver, addition }),
          });
          showToast("存储驱动添加成功", "success");
        }

        state.openlistDriverForm = null;
        await fetchOpenListStorages();
        const formEl = document.getElementById("openlistDriverForm");
        if (formEl) formEl.innerHTML = "";
        updateOpenListStatusUI();
        const listEl = document.getElementById("openlistStorageList");
        if (listEl) listEl.innerHTML = renderOpenListStorageList(state.openlistStorages);
        bindOpenListPanel();

        // 自动将挂载路径同步到扫描目录
        if (normalizedPath && !state.webdavDirs.has(normalizedPath)) {
          state.webdavDirs.add(normalizedPath);
          const remoteMountList = document.getElementById("remoteMountList");
          if (remoteMountList) remoteMountList.innerHTML = renderMountList([...state.webdavDirs], "webdav");
          showToast(`已将 ${normalizedPath} 添加到扫描目录`, "success");
        }

        // 新增挂载后自动扫描+刮削
        if (!editId) {
          try {
            await persistSettingsIfNeeded({ silent: true });
            const autoScrape = state.config?.enable_auto_scrape !== false;
            const refreshResp = await api(`/api/library/refresh?source=remote&auto_scrape=${autoScrape}`);
            if (refreshResp?.job_id) {
              startJobPolling(refreshResp.job_id, "remote", "挂载扫描完成");
            }
          } catch (e) {
            console.warn("自动扫描失败:", e);
          }
        }
      } catch (e) {
        showToast(`${state.openlistDriverForm?.edit_id ? "更新" : "添加"}失败: ${parseOpenListError(e)}`, "error");
      }
    };
  }

  // 取消
  if (cancelDriverBtn) {
    cancelDriverBtn.onclick = () => {
      state.openlistDriverForm = null;
      const formEl = document.getElementById("openlistDriverForm");
      if (formEl) formEl.innerHTML = "";
    };
  }

  // 添加驱动按钮（在存储列表下方）
  const addDriverBtn = document.getElementById("openlistAddDriverBtn");
  if (addDriverBtn) {
    addDriverBtn.onclick = async () => {
      if (state.openlistDrivers.length === 0) {
        await fetchOpenListDrivers();
      }
      state.openlistDriverForm = { driver: "", mount_path: "" };
      const formEl = document.getElementById("openlistDriverForm");
      if (formEl) formEl.innerHTML = renderOpenListDriverForm(state.openlistDrivers);
      bindOpenListPanel();
    };
  }

  // 编辑存储驱动
  document.querySelectorAll("[data-openlist-edit]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-openlist-edit");
      const driver = btn.getAttribute("data-openlist-driver");
      const mountPath = btn.getAttribute("data-openlist-mount");
      let addition = {};
      try {
        addition = JSON.parse(btn.getAttribute("data-openlist-addition") || "{}");
      } catch (e) {
        addition = {};
      }

      if (state.openlistDrivers.length === 0) {
        await fetchOpenListDrivers();
      }

      // 设置表单状态为编辑模式
      state.openlistDriverForm = {
        driver: driver,
        mount_path: mountPath,
        edit_id: id,
        ...addition,
      };

      const formEl = document.getElementById("openlistDriverForm");
      if (formEl) {
        formEl.innerHTML = renderOpenListDriverForm(state.openlistDrivers, addition);
        bindOpenListPanel();
        // 滚动到表单位置
        formEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    };
  });

  // 切换启用/禁用
  document.querySelectorAll("[data-openlist-toggle]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-openlist-toggle");
      const enable = btn.getAttribute("data-openlist-enable") === "true";
      try {
        await api(`/api/openlist/storages/${enable ? "enable" : "disable"}?storage_id=${id}`, { method: "POST" });
        showToast(enable ? "已启用" : "已禁用", "success");
        await fetchOpenListStorages();
        const listEl = document.getElementById("openlistStorageList");
        if (listEl) listEl.innerHTML = renderOpenListStorageList(state.openlistStorages);
        updateOpenListStatusUI();
        bindOpenListPanel();
      } catch (e) {
        showToast(`操作失败: ${parseOpenListError(e, "toggle")}`, "error");
      }
    };
  });

  // 删除
  document.querySelectorAll("[data-openlist-delete]").forEach((btn) => {
    btn.onclick = async () => {
      const id = btn.getAttribute("data-openlist-delete");
      if (!confirm("确定要删除此存储驱动吗？")) return;
      try {
        // 记录删除前的挂载路径
        const deletedStorage = state.openlistStorages.find((s) => String(s.id) === String(id));
        const deletedMountPath = deletedStorage?.mount_path;

        await api(`/api/openlist/storages?storage_id=${id}`, { method: "DELETE" });
        showToast("已删除", "success");
        await fetchOpenListStorages();
        const listEl = document.getElementById("openlistStorageList");
        if (listEl) listEl.innerHTML = renderOpenListStorageList(state.openlistStorages);
        updateOpenListStatusUI();
        bindOpenListPanel();

        // 自动从扫描目录中移除已删除的挂载路径
        if (deletedMountPath && state.webdavDirs.has(deletedMountPath)) {
          state.webdavDirs.delete(deletedMountPath);
          const remoteMountList = document.getElementById("remoteMountList");
          if (remoteMountList) remoteMountList.innerHTML = renderMountList([...state.webdavDirs], "webdav");
        }
      } catch (e) {
        showToast(`删除失败: ${parseOpenListError(e, "delete")}`, "error");
      }
    };
  });
}

async function initOpenListPanel() {
  // 只在 OpenList 标签页激活时初始化
  const statusPanel = document.getElementById("openlistStatusPanel");
  if (!statusPanel) return;

  await Promise.all([
    fetchOpenListStatus(),
    fetchOpenListStorages(),
    fetchOpenListConfig(),
  ]);

  // 用获取到的配置更新表单 DOM
  const cfg = state.config || {};
  const enableEl = document.getElementById("openlistEnabledSelect");
  if (enableEl) enableEl.value = cfg.openlist_enabled ? "true" : "false";
  const portEl = document.querySelector("[name='openlist_port']");
  if (portEl) portEl.value = cfg.openlist_port || 5244;
  const autoEl = document.querySelector("[name='openlist_auto_start']");
  if (autoEl) autoEl.value = cfg.openlist_auto_start !== false ? "true" : "false";
  const pwdEl = document.querySelector("[name='openlist_admin_password']");
  if (pwdEl && cfg.openlist_admin_password) pwdEl.value = cfg.openlist_admin_password;

  updateOpenListStatusUI();

  const listEl = document.getElementById("openlistStorageList");
  if (listEl) {
    listEl.innerHTML = `
      <div class="settings-card-head" style="margin-bottom:0.5rem;">
        <div><h4>${"已配置的存储驱动"}</h4></div>
      </div>
      ${renderOpenListStorageList(state.openlistStorages)}
      <button class="ghost-btn" type="button" id="openlistAddDriverBtn" style="margin-top:0.5rem;">${"+ 添加存储驱动"}</button>`;
  }

  bindOpenListPanel();
  startOpenListStatusPolling();
}


// 初始化标签管理事件监听器
document.addEventListener("DOMContentLoaded", () => {
  // 标签管理事件
  document.getElementById("addTagBtn").addEventListener("click", () => {
    const tagInput = document.getElementById("tagInput");
    const tag = tagInput.value.trim();
    if (tag && state.selectedMovie) {
      addTag(state.selectedMovie.path, tag);
      tagInput.value = "";
    }
  });

  // 标签输入框回车事件
  document.getElementById("tagInput").addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      const tag = event.target.value.trim();
      if (tag && state.selectedMovie) {
        addTag(state.selectedMovie.path, tag);
        event.target.value = "";
      }
    }
  });
});
