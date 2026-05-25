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

  const uninstallBtn = document.getElementById("openlistUninstallBtn");
  if (uninstallBtn) uninstallBtn.onclick = async () => {
    if (!confirm("确定卸载 OpenList？将删除二进制文件和所有数据。")) return;
    try {
      const data = await api("/api/openlist/uninstall", { method: "POST" });
      showToast(data.message || "卸载完成", data.success ? "success" : "warning");
      await fetchOpenListStatus();
      updateOpenListStatusUI();
    } catch (e) {
      showToast(`卸载失败: ${parseOpenListError(e)}`, "error");
    }
  };

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
