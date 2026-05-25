const SETTINGS_TABS = [
  { id: "media", icon: "🌐", label: "媒体源", desc: "WebDAV / OpenList 连接" },
  { id: "player", icon: "▶️", label: "播放与本地", desc: "播放器选择和本地目录" },
  { id: "openlist", icon: "☁️", label: "OpenList", desc: "网盘挂载与管理" },
  { id: "appearance", icon: "🎨", label: "界面与刮削", desc: "主题和自动刮削" },
  { id: "maintenance", icon: "⚙️", label: "维护", desc: "缓存清理与重置" },
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
              <button type="button" class="ghost-btn" id="testConnectionBtnFooter">${"测试连接"}</button>
              <button type="submit" class="primary-btn">${"保存设置"}</button>
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
      hint: config.has_basic_config ? "可测试连接或刷新片库" : "请先配置",
      ready: !!config.has_basic_config,
    },
    {
      label: "本地目录",
      value: config.has_local_config ? `${(config.local_mount_dirs || []).length} 个目录` : "未添加",
      hint: config.has_local_config ? "刷新时一并扫描" : "可添加本地目录",
      ready: !!config.has_local_config,
    },
    {
      label: "默认播放器",
      value: "内置播放器（mpv）",
      hint: "内置播放，支持进度同步和统计",
      ready: true,
    },
    {
      label: "增量扫描",
      value: config.auto_incremental_sync === false ? "已关闭" : "已启用",
      hint: state.scanStatus?.scan_at
        ? `上次检查 ${formatRelativeTime(state.scanStatus.scan_at)}`
        : "尚未执行过增量检查",
      ready: config.auto_incremental_sync !== false,
    },
  ];

  return `
    <section class="settings-overview">
      <div class="settings-overview-copy">
        <span class="section-eyebrow">${"设置中心"}</span>
        <h3>${"接入片库，配置播放"}</h3>
        <p>${"首次使用先完成「媒体源」和「播放与本地」，其余可稍后再配。"}</p>
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
      return "可用";
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
          <h3>${"接入一个媒体源即可开始"}</h3>
          <p>${"可在下方直接配置，也可以跳过稍后再说。"}</p>
        </div>
        <button class="ghost-btn" type="button" id="dismissFirstRunGuideBtn">${"稍后配置"}</button>
      </div>
      <div class="first-run-guide-actions">
        <button class="primary-btn" type="button" data-first-run-source="openlist">${"OpenList 网盘"}</button>
        <button class="ghost-btn" type="button" data-first-run-source="webdav">${"WebDAV"}</button>
        <button class="ghost-btn" type="button" data-browse-dirs="local">${hasLocal ? "管理本地目录" : "添加本地目录"}</button>
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
  const connectButtonLabel = useExternalOpenList ? "验证 OpenList 并选择目录" : "验证并选择目录";
  const hintText = useBuiltinOpenList
    ? "使用内置 OpenList，先启动服务并挂载网盘驱动，再回来选扫描目录。"
    : useExternalOpenList
      ? "填写 OpenList 的 WebDAV 地址（如 http://地址:5244/dav）和账号密码。"
      : remotePreset.help;

  return `
    <div class="settings-section-head">
      <span>${"媒体源"}</span>
      <h3>${"视频从哪里来"}</h3>
      <p>${"网盘用户选 OpenList，已有 WebDAV 服务的选标准 WebDAV。"}</p>
    </div>

    <div class="settings-card settings-tip-card">
      <div class="settings-tip-copy">
        <strong>${isOpenlistProvider ? "OpenList 模式" : "WebDAV 模式"}</strong>
        <p>${isOpenlistProvider ? (useBuiltinOpenList ? "使用内置 OpenList，挂载驱动后即可选择扫描目录。" : "连接你自己的 OpenList，通过 WebDAV 协议浏览目录。") : "适用于群晖、坚果云、Nextcloud、AList 等 WebDAV 服务。"}</p>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"选择媒体源"}</h4>
        </div>
        <p>${"选好方案后验证连接，通过后自动保存并进入目录选择。"}</p>
      </div>
      <div class="source-option-grid">
        <button class="source-option-card ${remoteProvider === "webdav" ? "active" : ""}" type="button" data-select-remote-provider="webdav">
          <strong>${"标准 WebDAV"}</strong>
          <span>${"群晖、坚果云、AList 等已有 WebDAV 服务"}</span>
        </button>
        <button class="source-option-card ${remoteProvider === "openlist" ? "active" : ""}" type="button" data-select-remote-provider="openlist">
          <strong>${"OpenList 网盘"}</strong>
          <span>${"夸克、阿里云盘、115、百度网盘等"}</span>
        </button>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-field-grid">
        <label class="${isOpenlistProvider ? "" : "hidden"}">
          <span>${"部署方式"}</span>
          <select name="openlist_source_mode" id="openlistSourceModeSelect">
            <option value="builtin" ${openlistSourceMode === "builtin" ? "selected" : ""}>${"使用内置 OpenList"}</option>
            <option value="external" ${openlistSourceMode === "external" ? "selected" : ""}>${"使用自己的 OpenList"}</option>
          </select>
        </label>
        <label class="${isOpenlistProvider ? "hidden" : ""}">
          <span>${"方案"}</span>
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
          <span>${"Cookie（可选）"}</span>
          <textarea name="remote_cookie" id="remoteCookieInput" rows="3" placeholder="${"支持会话鉴权的远程源可填写 Cookie"}">${escapeHtml(activeRemoteProfile.remote_cookie || "")}</textarea>
        </label>
        <label>
          <span>${"扫描深度"}</span>
          <input name="scan_max_depth" type="number" min="1" max="8" value="${escapeAttr(String(config.scan_max_depth || 2))}">
        </label>
        <div class="full-width">
          <span>${"说明"}</span>
          <div id="remoteProviderHint" class="settings-inline-note">
            <span>${escapeHtml(hintText)}</span>
          </div>
        </div>
      </div>
      <div class="source-inline-actions">
        ${useBuiltinOpenList
          ? `
            <button class="primary-btn" type="button" id="browseBuiltinOpenListBtn">${builtinReady && hasOpenListStorages ? "浏览目录" : "配置 OpenList"}</button>
            <button class="ghost-btn" type="button" id="openOpenListManagerBtn">${"管理面板"}</button>
          `
          : `
            <button class="primary-btn" type="button" id="connectAndBrowseBtn">${connectButtonLabel}</button>
            <button class="ghost-btn" type="button" id="testConnectionBtn">${"验证连接"}</button>
          `}
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4 id="remoteMountTitle">${isOpenlistProvider ? "扫描目录" : "远程扫描目录"}</h4>
        </div>
        <p id="remoteMountDesc">${"只添加存放影视的目录，扫描更快，识别更准。"}</p>
      </div>
      <div class="mount-list" id="remoteMountList">
        ${renderMountList(webdavDirs, "webdav")}
      </div>
      <button class="primary-btn" type="button" id="browseRemoteDirsBtn">${isOpenlistProvider ? "浏览目录" : "浏览远程目录"}</button>
    </div>
  `;
}

function renderPlayerTab(config) {
  const localDirs = [...state.localDirs];
  const runtime = state.playerRuntime || {};
  const runtimeMode = runtime.desktop_mode ? "桌面模式" : "浏览器模式";
  const runtimeStatusClass = runtime.embed_ready ? "ready" : "pending";
  const runtimeSummary = runtime.desktop_mode
    ? "桌面模式已就绪，可直接启用内置播放器。"
    : (Array.isArray(runtime.reasons) && runtime.reasons.length ? runtime.reasons[0] : "请从桌面模式启动内置 mpv。");
  const runtimeReasonList = Array.isArray(runtime.reasons) ? runtime.reasons : [];

  return `
    <div class="settings-section-head">
      <span>${"播放与扫描"}</span>
      <h3>${"播放器和本地目录"}</h3>
      <p>${"网盘和本地硬盘可以一起配，统一出现在片库中。"}</p>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"内置播放器状态"}</h4>
        </div>
        <p>${"当前运行环境是否支持内置播放器。"}</p>
      </div>
      <div class="runtime-status-grid">
        <article class="runtime-status-card ${runtimeStatusClass}">
          <span>${"当前运行方式"}</span>
          <strong>${escapeHtml(runtimeMode)}</strong>
          <small>${escapeHtml(runtime.runtime === "pywebview" ? "桌面窗口启动" : "浏览器窗口启动")}</small>
        </article>
        <article class="runtime-status-card ${runtime.pywebview_available ? "ready" : "pending"}">
          <span>${"桌面组件"}</span>
          <strong>${runtime.pywebview_available ? "已就绪" : "未安装"}</strong>
          <small>${"桌面窗口依赖此组件。"}</small>
        </article>
        <article class="runtime-status-card ${runtime.mpv_available ? "ready" : "pending"}">
          <span>${"mpv 路径"}</span>
          <strong>${runtime.mpv_available ? "已就绪" : "未配置"}</strong>
          <small>${"内置播放器依赖 mpv.exe。"}</small>
        </article>
      </div>
      <div class="settings-inline-note runtime-note">
        <strong>${runtime.desktop_mode ? "可启用内置播放器" : "暂不支持内置播放器"}</strong>
        <span>${escapeHtml(runtimeSummary)}</span>
      </div>
      ${runtimeReasonList.length ? `
        <div class="runtime-reason-list">
          ${runtimeReasonList.map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}
        </div>
      ` : ""}
    </div>

    <div class="settings-card">
      <div class="settings-field-grid">
        <label>
          <span>${"本地扫描深度"}</span>
          <input name="local_scan_max_depth" type="number" min="1" max="12" value="${escapeAttr(String(config.local_scan_max_depth || 3))}">
        </label>
        <label>
          <span>${"默认播放器"}</span>
          <input value="内置播放器 mpv" disabled>
          <input type="hidden" name="default_player" value="mpv_desktop">
        </label>
        <label class="full-width">
          <span>${"播放模式说明"}</span>
          <div class="settings-inline-note">${"现在仅保留内置 mpv。播放进度、续播和观影统计都会通过应用统一同步。"}</div>
        </label>
        <label class="full-width">
          <span>${"mpv 路径"}</span>
          <div class="path-picker-row">
            <input id="mpvPathInput" name="mpv_path" value="${escapeAttr(config.mpv_path || "")}" placeholder="mpv.exe 路径">
            <button class="ghost-btn" type="button" data-pick-player="mpv">${"浏览…"}</button>
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
          <h4>${"本地扫描目录"}</h4>
        </div>
        <p>${"添加电影盘、剧集盘或 NAS 映射盘，只选放视频的目录。"}</p>
      </div>
      <div class="mount-list">
        ${renderMountList(localDirs, "local")}
      </div>
      <button class="primary-btn" type="button" data-browse-dirs="local">${"添加目录"}</button>
    </div>
  `;
}

function renderOpenListTab(config) {
  return `
    <div class="settings-section-head">
      <span>${"网盘聚合"}</span>
      <h3>${"多网盘统一入口"}</h3>
      <p>${"启用 OpenList 后添加网盘驱动，再回到「媒体源」选择扫描目录。"}</p>
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
          <span>${"内置 OpenList"}</span>
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
          <span>${"开机自启"}</span>
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
        <span style="font-size:13px; color:var(--text-soft);">${"登录失败时使用"}</span>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"服务控制"}</h4>
        </div>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="primary-btn" type="button" id="openlistStartBtn">${"启动"}</button>
        <button class="ghost-btn" type="button" id="openlistStopBtn">${"停止"}</button>
        <button class="ghost-btn" type="button" id="openlistRestartBtn">${"重启"}</button>
        <button class="ghost-btn" type="button" id="openlistDownloadBtn">${"更新"}</button>
        <button class="ghost-btn" type="button" id="openlistUninstallBtn" style="color:var(--danger);">${"卸载"}</button>
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
        <p>${"添加夸克、阿里云盘、115、百度网盘等驱动到 OpenList。"}</p>
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
      <h3>${"主题与刮削设置"}</h3>
      <p>${"不影响片库内容，只改界面外观和封面自动获取。"}</p>
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
        <p>${"新视频自动获取封面和简介，优先 TMDB 和豆瓣。"}</p>
      </div>
      <div class="settings-field-grid">
        <label>
          <span>${"状态"}</span>
          <select name="enable_auto_scrape">
            <option value="true" ${config.enable_auto_scrape ? "selected" : ""}>${"启用"}</option>
            <option value="false" ${!config.enable_auto_scrape ? "selected" : ""}>${"禁用"}</option>
          </select>
        </label>
        <label>
          <span>${"TMDB API Key"}</span>
          <input name="tmdb_api_key" type="password" value="${escapeAttr(config.tmdb_api_key || "")}" placeholder="${"填写你的 TMDB API Key"}">
        </label>
        <label class="full-width">
          <span>${"豆瓣 Cookie"}</span>
          <textarea name="douban_cookie" rows="3" placeholder="${"可填入你自己的豆瓣 Cookie，提升搜索和详情抓取成功率"}">${escapeHtml(config.douban_cookie || "")}</textarea>
        </label>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"增量扫描"}</h4>
        </div>
        <p>${"软件启动后会在后台检查 OpenList 更新，只扫描新增或变更的目录。"}</p>
      </div>
      <div class="settings-field-grid">
        <label>
          <span>${"后台自动检查"}</span>
          <select name="auto_incremental_sync">
            <option value="true" ${config.auto_incremental_sync !== false ? "selected" : ""}>${"启用"}</option>
            <option value="false" ${config.auto_incremental_sync === false ? "selected" : ""}>${"禁用"}</option>
          </select>
        </label>
        <label>
          <span>${"检查间隔（分钟）"}</span>
          <input name="auto_incremental_sync_interval_minutes" type="number" min="5" max="720" value="${escapeAttr(String(config.auto_incremental_sync_interval_minutes || 30))}">
        </label>
        <label>
          <span>${"快速扫描范围（天）"}</span>
          <input name="incremental_recent_days" type="number" min="1" max="30" value="${escapeAttr(String(config.incremental_recent_days || 7))}">
        </label>
      </div>
    </div>
  `;
}

function renderMaintenanceTab() {
  const scanStatus = state.scanStatus || {};
  return `
    <div class="settings-section-head">
      <span>${"维护"}</span>
      <h3>${"缓存清理与重置"}</h3>
      <p>${"一般清缓存即可，配置异常时才需要重置全部数据。"}</p>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"OpenList 增量同步"}</h4>
        </div>
        <p>${scanStatus.scan_at ? `上次检查 ${formatRelativeTime(scanStatus.scan_at)}，新增 ${scanStatus.new_files || 0}，更新 ${scanStatus.updated_files || 0}` : "还没有执行过增量检查。"}</p>
      </div>
      <div class="maintenance-grid">
        <button class="primary-btn" type="button" id="scanIncrementalBtn">${"扫描新增"}</button>
        <button class="ghost-btn" type="button" id="scanRecentBtn">${"快速扫描（近 ${Number(state.config?.incremental_recent_days || 7)} 天）"}</button>
        <button class="ghost-btn" type="button" id="rebuildRemoteLibraryBtn">${"全量重建远程片库"}</button>
      </div>
    </div>

    <div class="settings-card">
      <div class="settings-card-head">
        <div>
          <h4>${"缓存管理"}</h4>
        </div>
        <p>${"清缓存不影响配置和收藏。"}</p>
      </div>
      <div class="maintenance-grid">
        <button class="ghost-btn" type="button" id="clearRemoteCacheBtn">${"远程缓存"}</button>
        <button class="ghost-btn" type="button" id="clearLocalCacheBtn">${"本地缓存"}</button>
        <button class="ghost-btn" type="button" id="clearAllCacheBtn">${"全部缓存"}</button>
      </div>
    </div>

    <div class="settings-card" style="border-color: rgba(240, 113, 120, 0.3);">
      <div class="settings-card-head">
        <div>
          <h4 style="color: var(--danger);">${"危险区域"}</h4>
        </div>
        <p>${"操作不可恢复，请谨慎。"}</p>
      </div>
      <button class="ghost-btn danger-btn" type="button" id="clearAllDataBtn">${"重置全部数据"}</button>
    </div>
  `;
}

// 首次配置向导
