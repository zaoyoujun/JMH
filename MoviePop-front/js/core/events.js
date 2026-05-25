document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindGlobalEvents();
  const playerCloseBtn = document.querySelector("#playerModal .modal-close");
  if (playerCloseBtn) playerCloseBtn.textContent = "关闭";
  const playerKicker = document.querySelector("#playerModal .section-eyebrow");
  if (playerKicker) playerKicker.textContent = "内置播放器 mpv";
  const playerTitle = document.getElementById("inlinePlayerTitle");
  if (playerTitle) playerTitle.textContent = "正在连接 mpv";
  const playerMeta = document.getElementById("inlinePlayerMeta");
  if (playerMeta) playerMeta.textContent = "由应用接管播放进度、最近播放和观影统计";
  await loadBootstrap();
  await loadAllPlaybackProgress();
  await loadCurrentView();
}

function bindGlobalEvents() {
  window.addEventListener("beforeunload", () => {
    closeInlinePlayer({ refresh: false }).catch(() => {});
  });
  window.addEventListener("resize", () => {
    syncInlinePlayerLayout().catch(() => {});
  });

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
      state.analyticsData = null;
      state.hasAnalyticsData = undefined;
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

    const useIncremental = supportsIncrementalRemoteScan() && (source === "remote" || source === "combined");
    const autoScrape = state.config?.enable_auto_scrape !== false;
    const response = await guarded(() =>
      useIncremental
        ? api(`/api/library/scan-incremental?auto_scrape=${autoScrape}&recent_only=false`, { method: "POST" })
        : api(`/api/library/refresh?source=${encodeURIComponent(source)}&auto_scrape=${autoScrape}`, { method: "POST" })
    );
    if (response) {
      startJobPolling(
        response.job_id,
        source,
        useIncremental ? `${getSourceLabel(source)}新增扫描完成` : `${getSourceLabel(source)}刷新完成`
      );
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

    const vlcCommandBtn = event.target.closest("[data-vlc-command]");
    if (vlcCommandBtn) {
      await sendInlinePlayerCommand(vlcCommandBtn.dataset.vlcCommand);
      return;
    }

    const mpvCommandBtn = event.target.closest("[data-mpv-command]");
    if (mpvCommandBtn) {
      await sendInlinePlayerCommand(mpvCommandBtn.dataset.mpvCommand);
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

