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

