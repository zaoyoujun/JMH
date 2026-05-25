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

function supportsIncrementalRemoteScan() {
  return false;
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

function escapeRegex(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeRemoteProvider(provider) {
  const value = String(provider || "").trim().toLowerCase();
  return getRemoteProviderOptions().some((item) => item.value === value) ? value : "webdav";
}

function getRemoteProviderPreset(provider) {
  return getRemoteProviderPresets()[normalizeRemoteProvider(provider)] || getRemoteProviderPresets().webdav;
}

