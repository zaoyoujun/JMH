function openCandidateModal(movie) {
  state.candidateMovie = movie;
  state.candidateSelection = null;
  state.candidateItems = [];
  state.candidateDiagnostics = [];
  state.candidateSource = "auto";
  state.candidateSearchText = movie.name || movie.title || "";
  state.candidateStatus = {
    kind: "info",
    text: "输入更准确的片名、季数或年份，可以同时从 Douban、TMDB、Bangumi、AniBK 和 IMDb 拿到更稳的候选结果。"
  };
  const searchInput = document.getElementById("candidateSearchInput");
  if (searchInput) searchInput.value = state.candidateSearchText;
  const sourceSelect = document.getElementById("candidateSourceSelect");
  if (sourceSelect) sourceSelect.value = state.candidateSource;
  renderCandidateModal();
  openModal("candidateModal");
  loadCandidates();
}

async function loadCandidates() {
  if (!state.candidateMovie) return;
  state.candidateSearchText = (document.getElementById("candidateSearchInput")?.value || "").trim();
  state.candidateSource = document.getElementById("candidateSourceSelect")?.value || "auto";
  state.candidateStatus = { kind: "info", text: "正在搜索候选结果..." };
  renderCandidateModal();

  const payload = await guarded(() =>
    api("/api/movies/search-candidates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        movie_path: state.candidateMovie.path,
        custom_name: state.candidateSearchText || null,
        source: state.candidateSource,
      }),
    })
  );
  if (!payload) {
    state.candidateItems = [];
    state.candidateDiagnostics = [];
    state.candidateSelection = null;
    state.candidateStatus = {
      kind: "error",
      text: "这次没有拿到候选结果，试试补上更完整的片名、季数或年份。"
    };
    renderCandidateModal();
    return;
  }

  state.candidateItems = payload.items || [];
  state.candidateDiagnostics = payload.diagnostics || [];
  // 关键修复：搜索后不要自动选中第一条，必须由用户手动点选
  state.candidateSelection = null;
  state.candidateStatus = state.candidateItems.length
    ? { kind: "success", text: `找到 ${state.candidateItems.length} 个结果，请从左侧列表中手动选择一个候选。` }
    : { kind: "error", text: "没有找到可用结果，换一个更完整的搜索词试试。" };
  renderCandidateModal();
}

function renderCandidateModal() {
  const list = document.getElementById("candidateList");
  const applyBtn = document.getElementById("candidateApplyBtn");
  const currentTitle = escapeHtml(state.candidateMovie?.title || state.candidateMovie?.name || "当前条目");
  const currentPoster = state.candidateMovie?.cover_url || "";
  const status = state.candidateStatus
    ? `<div class="candidate-status ${escapeAttr(state.candidateStatus.kind || "")}">${escapeHtml(state.candidateStatus.text || "")}</div>`
    : "";
  const diagnostics = state.candidateDiagnostics?.length
    ? `
      <div class="candidate-diagnostics">
        ${state.candidateDiagnostics.map((item) => `
          <div class="candidate-diag ${escapeAttr(item.status || "idle")}">
            <strong>${escapeHtml(item.source || "SOURCE")}</strong>
            <span>${escapeHtml(
              item.status === "success"
                ? `命中 ${item.hits || 0} 个结果，查询 ${item.queries || 0} 次`
                : item.status === "empty"
                  ? `没有命中结果，查询 ${item.queries || 0} 次`
                  : item.error || "本次未返回结果"
            )}</span>
          </div>
        `).join("")}
      </div>
    `
    : "";

  if (applyBtn) {
    applyBtn.disabled = !state.candidateSelection;
    applyBtn.textContent = state.candidateSelection ? "确认入库" : "请先选择候选";
  }

  // 未选择时显示明确的占位，绝不回退到当前电影封面（避免误以为已自动下载）
  const hasSelection = !!state.candidateSelection;
  const previewPoster = hasSelection ? state.candidateSelection.cover_url || "" : "";
  const previewTitle = hasSelection ? state.candidateSelection.title : "请选择一个候选";
  const previewMeta = hasSelection
    ? [
        state.candidateSelection.source,
        state.candidateSelection.year ? `${state.candidateSelection.year}` : "年份未知",
        typeof state.candidateSelection.match_score === "number" ? `匹配 ${Math.round(state.candidateSelection.match_score)}` : "待比较"
      ].filter(Boolean).join(" · ")
    : "尚未选择候选结果";
  const previewDesc = hasSelection
    ? (state.candidateSelection.intro || "暂无简介")
    : "请从左侧候选列表中点击你想要应用的那一项，选中后这里会显示完整的海报与简介预览。";

  const preview = `
    <div class="candidate-preview">
      <div class="candidate-preview-poster">
        ${previewPoster
          ? `<img src="${escapeAttr(previewPoster)}" alt="海报预览" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">`
          : ""}
        <div class="candidate-preview-poster-fallback" ${previewPoster ? 'style="display:none;"' : ''}>无封面</div>
      </div>
      <div class="candidate-preview-info">
        <div class="candidate-preview-title">${escapeHtml(previewTitle)}</div>
        <div class="candidate-preview-meta">${escapeHtml(previewMeta)}</div>
        <div class="candidate-preview-desc">${escapeHtml(previewDesc)}</div>
        ${state.candidateSelection ? `
          <div class="candidate-preview-actions">
            <button class="ghost-btn candidate-preview-detail" type="button">查看详情</button>
          </div>
        ` : ""}
      </div>
    </div>
  `;

  if (!state.candidateItems.length) {
    list.innerHTML = `
      <div class="candidate-empty">
        ${preview}
        <div class="candidate-empty-text">
          <span class="section-eyebrow">手动刮削</span>
          <h4>${currentTitle}</h4>
          <p>这里会展示 Douban、TMDB 和 AniBK 的候选结果，优先看分数、年份和命中搜索词。</p>
        </div>
        ${status}
        ${diagnostics}
      </div>
    `;
    return;
  }

  list.innerHTML = `
    <div class="candidate-results">
      <div class="candidate-results-list">
        <div class="candidate-results-head">
          <span class="section-eyebrow">手动刮削</span>
          <h4>${currentTitle}</h4>
          <p>优先选择分数更高、年份更近，而且命中搜索词更贴近的结果。</p>
        </div>
        ${status}
        ${diagnostics}
        <div class="candidate-items">
          ${state.candidateItems.map((item, index) => `
            <div class="candidate-item ${state.candidateSelection?.url === item.url ? "selected" : ""}" data-candidate-index="${index}">
              <div class="candidate-item-poster">
                ${item.cover_url
                  ? `<img src="${escapeAttr(item.cover_url)}" alt="${escapeAttr(item.title)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">`
                  : ""}
                <div class="candidate-item-poster-fallback" ${item.cover_url ? 'style="display:none;"' : ''}>无图</div>
              </div>
              <div class="candidate-item-body">
                <div class="candidate-item-title">
                  ${escapeHtml(item.title)}
                  <span class="candidate-source source-${escapeAttr((item.source || "unknown").toLowerCase())}">${escapeHtml(item.source || "未知来源")}</span>
                </div>
                <div class="candidate-item-meta">
                  ${item.year ? `<span>${escapeHtml(String(item.year))}</span>` : '<span>年份未知</span>'}
                  ${typeof item.match_score === "number" ? `<span>匹配 ${Math.round(item.match_score)}</span>` : '<span>待比较</span>'}
                  ${item.matched_query ? `<span>命中: ${escapeHtml(item.matched_query)}</span>` : ""}
                </div>
                <div class="candidate-item-desc">${escapeHtml(item.intro || "暂无简介")}</div>
                <div class="candidate-item-footer">
                  <span class="candidate-item-index">候选 ${index + 1}</span>
                </div>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
      ${preview}
    </div>
  `;

  list.querySelectorAll("[data-candidate-index]").forEach((row) => {
    row.addEventListener("click", () => {
      const index = Number(row.dataset.candidateIndex);
      state.candidateSelection = state.candidateItems[index] || null;
      renderCandidateModal();
    });
  });

  const detailBtn = list.querySelector(".candidate-preview-detail");
  if (detailBtn && state.candidateSelection?.url) {
    detailBtn.addEventListener("click", () => {
      window.open(state.candidateSelection.url, "_blank", "noopener");
    });
  }
}
