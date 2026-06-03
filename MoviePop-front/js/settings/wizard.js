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
            <p>${"三步完成基础配置"}</p>
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
      <p style="color:var(--text-soft); margin:0;">${"视频资源从哪里来"}</p>
    </div>
    <div class="wizard-source-grid">
      <div class="wizard-source-card ${_wizardSource === "openlist" ? "selected" : ""}" data-wizard-source="openlist">
        <div class="wizard-source-icon">☁️</div>
        <h4>${"OpenList 网盘"}</h4>
        <p>${"夸克、阿里云盘、115、百度网盘等"}</p>
        <span class="wizard-source-badge">${"推荐"}</span>
      </div>
      <div class="wizard-source-card ${_wizardSource === "webdav" ? "selected" : ""}" data-wizard-source="webdav">
        <div class="wizard-source-icon">🌐</div>
        <h4>${"WebDAV"}</h4>
        <p>${"自建 WebDAV、群晖、坚果云等"}</p>
      </div>
    </div>
  `;
}

function renderWizardStep2() {
  if (_wizardSource === "openlist") {
    return `
      <div style="text-align:center; margin-bottom:24px;">
        <h3 style="margin:0 0 8px;">${"配置 OpenList"}</h3>
        <p style="color:var(--text-soft); margin:0;">${"内置网盘聚合服务"}</p>
      </div>
      <div class="settings-card" style="max-width:400px; margin:0 auto;">
        <p style="color:var(--text-soft); font-size:14px; text-align:center;">
          ${"保存后自动下载启动，之后在管理界面添加网盘驱动。"}
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
      <p style="color:var(--text-soft); margin:0;">${"填写 WebDAV 服务器信息"}</p>
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
          <span>${"Cookie（可选）"}</span>
          <textarea name="remote_cookie" rows="2" placeholder="${"支持会话鉴权时可填写"}"></textarea>
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
      <p style="color:var(--text-soft); margin:0;">${"选择要扫描的目录，之后可随时修改"}</p>
    </div>
    <div style="display:grid; gap:16px; max-width:480px; margin:0 auto;">
      <div class="settings-card">
        <div class="settings-card-head">
          <h4>${isOpenlist ? "OpenList 挂载目录" : "远程目录"}</h4>
        </div>
        <div class="mount-list" id="remoteMountList">
          ${renderMountList(remoteDirs, "webdav")}
        </div>
        <button class="primary-btn" type="button" id="browseRemoteDirsBtn" data-browse-dirs="webdav">${isOpenlist ? "浏览目录" : "浏览远程目录"}</button>
      </div>
      <div class="settings-card">
        <div class="settings-card-head">
          <h4>${"本地目录"}</h4>
        </div>
        <div class="mount-list">
          ${renderMountList(localDirs, "local")}
        </div>
        <button class="primary-btn" type="button" data-browse-dirs="local">${"添加目录"}</button>
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
    mpv_path: "",
    default_player: "mpv_desktop",
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

