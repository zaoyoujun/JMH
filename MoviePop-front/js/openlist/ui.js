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

