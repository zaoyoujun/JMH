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

