function openCandidateModal(movie) {
  state.candidateMovie = movie;
  state.candidateSelection = null;
  state.candidateItems = [];
  state.candidateDiagnostics = [];
  state.candidateSearchText = movie.name || movie.title || "";
  state.candidateStatus = { kind: "info", text: "输入更准确的片名、季数或年份，可以同时从 Douban、TMDB、Bangumi、AniBK 和 IMDb 拿到更稳的候选结果。" };
  document.getElementById("candidateSearchInput").value = state.candidateSearchText;
  renderCandidateModal();
  openModal("candidateModal");
  loadCandidates();
}

async function loadCandidates() {
  if (!state.candidateMovie) return;
  state.candidateSearchText = document.getElementById("candidateSearchInput").value.trim();
  state.candidateStatus = { kind: "info", text: "正在搜索候选结果..." };
  renderCandidateModal();

  const payload = await guarded(() =>
    api("/api/movies/search-candidates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        movie_path: state.candidateMovie.path,
        custom_name: state.candidateSearchText || null,
      }),
    })
  );
  if (!payload) {
    state.candidateItems = [];
    state.candidateDiagnostics = [];
    state.candidateSelection = null;
    state.candidateStatus = { kind: "error", text: "这次没有拿到候选结果，试试补上更完整的片名、季数或年份。" };
    renderCandidateModal();
    return;
  }

  state.candidateItems = payload.items || [];
  state.candidateDiagnostics = payload.diagnostics || [];
  state.candidateSelection = state.candidateItems[0] || null;
  state.candidateStatus = state.candidateItems.length
    ? { kind: "success", text: `找到 ${state.candidateItems.length} 个结果，优先看分数、来源、年份和命中搜索词。` }
    : { kind: "error", text: "没有找到可用结果，换一个更完整的搜索词试试。" };
  renderCandidateModal();
}

function renderCandidateModal() {
  const list = document.getElementById("candidateList");
  const applyBtn = document.getElementById("candidateApplyBtn");
  const currentTitle = escapeHtml(state.candidateMovie?.title || state.candidateMovie?.name || "当前条目");
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
                ? `${"命中"} ${item.hits || 0} ${"个结果，查询"} ${item.queries || 0} ${"次"}`
                : item.status === "empty"
                  ? `${"没有命中结果，查询"} ${item.queries || 0} ${"次"}`
                  : item.error || "本次未返回结果"
            )}</span>
          </div>
        `).join("")}
      </div>
    `
    : "";

  if (applyBtn) {
    applyBtn.disabled = !state.candidateSelection;
    applyBtn.textContent = state.candidateSelection ? "应用当前候选" : "先选择一个候选";
  }

  if (!state.candidateItems.length) {
    list.innerHTML = `
      <div class="candidate-empty">
        <span class="section-eyebrow">${"手动刮削"}</span>
        <h4>${currentTitle}</h4>
        <p>${"这里会展示 Douban、TMDB、Bangumi、AniBK 和 IMDb 的候选结果，优先看分数、年份和命中搜索词。"}</p>
        ${status}
        ${diagnostics}
      </div>
    `;
    return;
  }

  list.innerHTML = `
      <div class="candidate-results-head">
        <div>
          <span class="section-eyebrow">${"手动刮削"}</span>
          <h4>${currentTitle}</h4>
        </div>
      <p>${"优先选择分数更高、年份更近，而且命中搜索词更贴近的结果。"}</p>
      </div>
      ${status}
      ${diagnostics}
      ${state.candidateItems.map((item, index) => `
        <label class="candidate-item ${state.candidateSelection?.url === item.url ? "selected" : ""}">
        <div class="candidate-pick">
          <input type="radio" name="candidateRadio" data-candidate-index="${index}" ${state.candidateSelection?.url === item.url || (!state.candidateSelection && index === 0) ? "checked" : ""}>
        </div>
        <div class="candidate-meta">
          <strong>${escapeHtml(item.title)}</strong>
          <div class="candidate-badges">
            <span class="mini-tag source">${escapeHtml(item.source)}</span>
            <span class="mini-tag">${item.year ? escapeHtml(String(item.year)) : "年份未知"}</span>
            <span class="mini-tag">${typeof item.match_score === "number" ? `${"匹配"} ${Math.round(item.match_score)}` : "待比较"}</span>
            <span class="mini-tag">${index === 0 ? "优先结果" : `${"候选"} ${index + 1}`}</span>
          </div>
          ${item.matched_query ? `<span class="candidate-hint">${"命中搜索词："}${escapeHtml(item.matched_query)}</span>` : ""}
          <span class="candidate-url">${escapeHtml(item.url)}</span>
        </div>
      </label>
    `).join("")}
  `;

  list.querySelectorAll("[data-candidate-index]").forEach((radio) => {
    radio.addEventListener("change", () => {
      state.candidateSelection = state.candidateItems[Number(radio.dataset.candidateIndex)] || null;
      renderCandidateModal();
    });
  });
}

