function renderStats() {
  if (state.view === "recommend") {
    const stats = state.recommendationStats || {};
    elements.statsStrip.innerHTML = `
      <article class="stat-chip">
        <strong>${stats.library_recommendations || 0}</strong>
        <span>${"库内推荐"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.external_recommendations || 0}</strong>
        <span>${"站外发现"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.profile_tags || 0}</strong>
        <span>${"偏好标签"}</span>
      </article>
      <article class="stat-chip">
        <strong>${stats.seed_count || 0}</strong>
        <span>${"画像样本"}</span>
      </article>
    `;
    return;
  }
  elements.statsStrip.innerHTML = `
    <article class="stat-chip">
      <strong>${state.stats.all || 0}</strong>
      <span>${"全部条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.remote || 0}</strong>
      <span>${"远程条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.local || 0}</strong>
      <span>${"本地条目"}</span>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.favorite || 0}</strong>
      <span>${"收藏条目"}</span>
    </article>
  `;
}

function startJobPolling(jobId, source, successMessage) {
  state.activeJobId = jobId;
  jobBanner.classList.remove("hidden");

  const timer = window.setInterval(async () => {
    try {
      const job = await api(`/api/jobs/${jobId}`);
      const total = job.total || 0;
      const current = job.current || 0;
      const isRefresh = String(job.name || "").includes("refresh");
      const sourceLabel = getSourceLabel(source);

      jobTitle.textContent = isRefresh
        ? `${sourceLabel}${"刷新中"}`
        : `${sourceLabel}${"元数据补全中"}`;
      jobMessage.textContent = job.message || "正在处理";
      jobProgressText.textContent = total ? `${current} / ${total}` : "处理中";
      jobProgressBar.style.width = total ? `${Math.min(100, (current / total) * 100)}%` : "25%";

      if (job.status === "completed") {
        window.clearInterval(timer);
        state.activeJobId = null;
        jobBanner.classList.add("hidden");
        jobProgressBar.style.width = "0";
        await loadBootstrap();
        await loadCurrentView();
        if (source === "remote" || source === "combined") {
          await refreshRecommendations(false);
        }
        showToast(successMessage, "success");
      }

      if (job.status === "failed") {
        window.clearInterval(timer);
        state.activeJobId = null;
        jobBanner.classList.add("hidden");
        jobProgressBar.style.width = "0";
        showToast(job.error || "后台任务失败", "error");
      }
    } catch (error) {
      window.clearInterval(timer);
      state.activeJobId = null;
      jobBanner.classList.add("hidden");
      jobProgressBar.style.width = "0";
      showToast(error.message || "读取任务状态失败", "error");
    }
  }, 1000);
}

function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  if (id === "playerModal") closeInlinePlayer({ refresh: false }).catch(() => {});
  document.getElementById(id).classList.add("hidden");
}

function renderStats() {
  elements.statsStrip.innerHTML = `
    <article class="stat-chip">
      <strong>${state.stats.all || 0}</strong>
      <span>${"全部条目"}</span>
      <small>${"当前片库总量"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.remote || 0}</strong>
      <span>${"远程条目"}</span>
      <small>${"远程媒体源"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.local || 0}</strong>
      <span>${"本地条目"}</span>
      <small>${"本机挂载目录"}</small>
    </article>
    <article class="stat-chip">
      <strong>${state.stats.favorite || 0}</strong>
      <span>${"收藏条目"}</span>
      <small>${"随时可重看"}</small>
    </article>
  `;
}

