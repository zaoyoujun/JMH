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

  document.getElementById("scanIncrementalBtn")?.addEventListener("click", async () => {
    const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
    if (persisted === null) return;
    const autoScrape = state.config?.enable_auto_scrape !== false;
    const response = await guarded(() =>
      api(`/api/library/scan-incremental?auto_scrape=${autoScrape}&recent_only=false`, { method: "POST" })
    );
    if (response?.job_id) {
      startJobPolling(response.job_id, "remote", "新增扫描完成");
    }
  });

  document.getElementById("scanRecentBtn")?.addEventListener("click", async () => {
    const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
    if (persisted === null) return;
    const autoScrape = state.config?.enable_auto_scrape !== false;
    const days = Number(state.config?.incremental_recent_days || 7);
    const response = await guarded(() =>
      api(`/api/library/scan-incremental?auto_scrape=${autoScrape}&recent_only=true&recent_days=${days}`, { method: "POST" })
    );
    if (response?.job_id) {
      startJobPolling(response.job_id, "remote", "快速扫描完成");
    }
  });

  document.getElementById("rebuildRemoteLibraryBtn")?.addEventListener("click", async () => {
    const confirmed = window.confirm("这会重新扫描整个 OpenList 远程片库，耗时会比增量扫描长。确定继续吗？");
    if (!confirmed) return;
    const persisted = await persistSettingsIfNeeded({ force: true, silent: true });
    if (persisted === null) return;
    const autoScrape = state.config?.enable_auto_scrape !== false;
    const response = await guarded(() =>
      api(`/api/library/rebuild-remote?auto_scrape=${autoScrape}`, { method: "POST" })
    );
    if (response?.job_id) {
      startJobPolling(response.job_id, "remote", "远程片库重建完成");
    }
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
      const player = button.dataset.pickPlayer || "mpv";
      const targetInput = document.getElementById("mpvPathInput");
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
    syncRemoteDraftToState();
    await persistSettingsIfNeeded({ force: true, silent: true });
    await Promise.all([fetchOpenListConfig(), fetchOpenListStatus(), fetchOpenListStorages()]);
    const status = state.openlistStatus || {};
    if (!status.binary_available || !state.config?.openlist_enabled || status.status !== "running" || !state.openlistStorages.length) {
      showToast("请先在下方 OpenList 面板中完成配置（下载→启动→添加驱动）", "info", 4000);
      return false;
    }
    await openDirectoryModal("webdav", getRemoteRootPath());
    return true;
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
      mpv_path: state.config?.mpv_path || "",
      default_player: "mpv_desktop",
      video_formats: state.config?.video_formats || [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".rmvb", ".ts"],
      enable_auto_scrape: state.config?.enable_auto_scrape !== false,
      auto_incremental_sync: state.config?.auto_incremental_sync !== false,
      auto_incremental_sync_interval_minutes: Number(state.config?.auto_incremental_sync_interval_minutes || 30),
      incremental_recent_days: Number(state.config?.incremental_recent_days || 7),
      scrape_source: state.config?.scrape_source || "auto",
      tmdb_api_key: state.config?.tmdb_api_key || "",
      douban_cookie: state.config?.douban_cookie || "",
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
    mpv_path: String(formData.get("mpv_path") || "").trim(),
    default_player: "mpv_desktop",
    video_formats: videoFormats,
    enable_auto_scrape: formData.get("enable_auto_scrape") === "true",
    auto_incremental_sync: formData.get("auto_incremental_sync") !== "false",
    auto_incremental_sync_interval_minutes: Number(formData.get("auto_incremental_sync_interval_minutes") || 30),
    incremental_recent_days: Number(formData.get("incremental_recent_days") || 7),
    scrape_source: "auto",
    tmdb_api_key: String(formData.get("tmdb_api_key") || "").trim(),
    douban_cookie: String(formData.get("douban_cookie") || "").trim(),
    tmdb_api_base: String(formData.get("tmdb_api_base") || "https://api.themoviedb.org/3").trim(),
    tmdb_web_base: String(formData.get("tmdb_web_base") || "https://www.themoviedb.org").trim(),
    tmdb_image_base: String(formData.get("tmdb_image_base") || "https://image.tmdb.org/t/p/w500").trim(),
    ui_theme: normalizeTheme(formData.get("ui_theme")),
    interface_theme: normalizeTheme(formData.get("ui_theme")),
  };
}

