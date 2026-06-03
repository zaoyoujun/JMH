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

