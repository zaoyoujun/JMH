function render() {
  syncHeroCarousel();
  renderTopMeta();
  renderNav();
  renderStats();
  renderToolbarState();
  disposeReportCharts();

  if (state.view === "settings") {
    elements.contentShell.innerHTML = renderSettingsView();
    bindSettingsView();
    if (_currentSettingsTab === "openlist") {
      initOpenListPanel();
    }
    clearRecommendationCarousel();
    return;
  }

  if (state.view === "recommend") {
    elements.contentShell.innerHTML = renderRecommendationView();
    clearRecommendationCarousel();
    return;
  }

  if (state.view === "report") {
    elements.contentShell.innerHTML = renderReportView();
    clearRecommendationCarousel();
    requestAnimationFrame(() => initReportCharts());
    return;
  }

  if (state.view === "all" && !state.config?.has_any_library) {
    elements.contentShell.innerHTML = renderSetupState(
      "还没有接入影视库",
      "接入 WebDAV 或本地目录之后，这里会自动汇总成一个片库。",
      "去设置里接入媒体源"
    );
    clearRecommendationCarousel();
    return;
  }


  const displayItems = getDisplayItems();
  if (!displayItems.length) {
    elements.contentShell.innerHTML = renderEmptyState();
    clearRecommendationCarousel();
    return;
  }

  const heroItems = getHomeHeroItems();
  const featured = heroItems[0] || displayItems[0];
  const groupedLibraryMarkup = !state.search && isListView(state.view)
    ? renderDynamicLibrarySections(displayItems)
    : `
      <section class="library-grid-shell">
        <div class="section-head">
          <div>
            <span class="section-eyebrow">${getCollectionEyebrow()}</span>
            <h3>${getCollectionTitle()}</h3>
          </div>
          <p>${getCollectionSummary()}</p>
        </div>
        <div class="library-grid">
          ${displayItems.map(renderMovieCard).join("")}
        </div>
      </section>
    `;
  elements.contentShell.innerHTML = `
    <div class="library-home">
      ${renderShelfHero(featured, heroItems)}
      ${state.view === "all" ? renderHomeRecommendationSection() : ""}
      ${groupedLibraryMarkup}
    </div>
  `;
  syncRecommendationCarousel();
}

function renderTopMeta() {
  const meta = viewMetaFor(state.view);
  document.getElementById("headlineKicker").textContent = meta.kicker;
  document.getElementById("pageTitle").textContent = meta.title;
  document.getElementById("pageSubtitle").textContent = meta.subtitle;
}

function renderNav() {
  navList.querySelector('[data-view="local"]')?.remove();
  navList.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

function renderToolbarState() {
  const source = getMaintenanceSource();
  const searchEnabled = isListView(state.view);
  elements.searchInput.disabled = !searchEnabled;
  elements.searchInput.placeholder = "按标题、别名、简介筛选";

  if (state.view === "recommend") {
    elements.refreshBtn.textContent = "刷新推荐";
    elements.refreshBtn.disabled = false;
    return;
  }

  if (state.view === "report") {
    elements.refreshBtn.textContent = "刷新报告";
    elements.refreshBtn.disabled = false;
    return;
  }

  if (state.view === "recent") {
    elements.refreshBtn.textContent = "清除最近播放";
    elements.refreshBtn.disabled = false;
    return;
  }

  const label = getSourceLabel(source);
  elements.refreshBtn.textContent = supportsIncrementalRemoteScan() ? "扫描新增" + label : "扫描并更新" + label;
  elements.refreshBtn.disabled = !Boolean(source);
}

function getCollectionEyebrow() {
  if (state.search) return `${"搜索结果"} ${state.items.length}`;
  if (state.view === "favorite") return "收藏片单";
  if (state.view === "recent") return "继续观看";
  return "整库浏览";
}

function getCollectionTitle() {
  if (state.search) return `"${escapeHtml(state.search)}" ${"的结果"}`;
  if (state.view === "favorite") return "你最常回看的内容";
  if (state.view === "recent") return "上次看到这里";
  return "整合后的影视库";
}

function getCollectionSummary() {
  const total = state.items.length;
  if (state.search) return `共找到 ${total} 个匹配项。`;
  if (state.view === "all") return "本地与远程内容会统一陈列，播放、收藏和补全都在同一个视图里完成。";
  if (state.view === "favorite") return "把常看和舍不得删的作品留在手边。";
  return "从最近打开的内容继续往下看。";
}

function getPrimaryLibraryGroup(movie) {
  const tags = Array.isArray(movie?.tags) ? movie.tags : [];
  const category = String(movie?.category || "").trim();
  if (tags.includes("合集")) return "合集系列";
  if (category === "动漫") return "动漫";
  if (category === "电视剧") return "电视剧";
  if (category === "电影") return "电影";
  return "其他整理";
}

function getGroupSortWeight(name) {
  const weights = {
    "合集系列": 0,
    "动漫": 1,
    "电视剧": 2,
    "电影": 3,
    "其他整理": 9,
  };
  return weights[name] ?? 99;
}

function buildDynamicLibrarySections(items = []) {
  const groups = new Map();
  for (const item of items) {
    const groupName = getPrimaryLibraryGroup(item);
    if (!groups.has(groupName)) groups.set(groupName, []);
    groups.get(groupName).push(item);
  }

  return [...groups.entries()]
    .sort((left, right) => {
      const [leftName, leftItems] = left;
      const [rightName, rightItems] = right;
      const weightGap = getGroupSortWeight(leftName) - getGroupSortWeight(rightName);
      if (weightGap !== 0) return weightGap;
      return rightItems.length - leftItems.length;
    })
    .map(([name, sectionItems]) => {
      const franchiseCounter = new Map();
      const tagCounter = new Map();
      for (const item of sectionItems) {
        const franchise = String(item?.franchise || "").trim();
        if (franchise) franchiseCounter.set(franchise, (franchiseCounter.get(franchise) || 0) + 1);
        for (const tag of Array.isArray(item?.inferred_tags) ? item.inferred_tags : []) {
          if (["动漫", "电视剧", "电影", "单片", "多集", "动漫库", "电视剧库", "电影库"].includes(tag)) continue;
          tagCounter.set(tag, (tagCounter.get(tag) || 0) + 1);
        }
      }
      const topFranchise = [...franchiseCounter.entries()].sort((a, b) => b[1] - a[1])[0];
      const topTags = [...tagCounter.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([tag]) => tag);

      let summary = `当前分组共 ${sectionItems.length} 个条目。`;
      if (topFranchise && topFranchise[1] >= 2) {
        summary = `当前以 ${topFranchise[0]} 等系列为主，共 ${sectionItems.length} 个条目。`;
      } else if (topTags.length) {
        summary = `当前更多集中在 ${topTags.join(" / ")} 这类内容，共 ${sectionItems.length} 个条目。`;
      }

      return {
        key: `${name}-${sectionItems.length}`,
        title: name,
        eyebrow: `${name} ${sectionItems.length}`,
        summary,
        items: sectionItems,
      };
    });
}

function renderDynamicLibrarySections(items = []) {
  const sections = buildDynamicLibrarySections(items);
  if (!sections.length) return "";
  return `
    <div class="library-group-stack">
      ${sections.map((section) => `
        <section class="library-grid-shell library-group-shell" data-library-group="${escapeAttr(section.title)}">
          <div class="section-head">
            <div>
              <span class="section-eyebrow">${escapeHtml(section.eyebrow)}</span>
              <h3>${escapeHtml(section.title)}</h3>
            </div>
            <p>${escapeHtml(section.summary)}</p>
          </div>
          <div class="library-grid">
            ${section.items.map(renderMovieCard).join("")}
          </div>
        </section>
      `).join("")}
    </div>
  `;
}

function renderSetupState(title, description, actionLabel) {
  return `
    <div class="empty-state">
      <div class="empty-state-inner">
        <span class="section-eyebrow">${"开始接入"}</span>
        <h3>${title}</h3>
        <p>${description}</p>
        <div class="form-actions centered-actions">
          <button class="primary-btn" onclick="window.__openSettingsFromInline && window.__openSettingsFromInline()">${actionLabel}</button>
        </div>
      </div>
    </div>
  `;
}

function renderEmptyState() {
  const copy =
    state.search
      ? "换个关键词再试试，或者清空搜索条件。"
      : "先刷新片库，或者检查当前媒体源配置是否正确。";

  return `
    <div class="empty-state">
      <div class="empty-state-inner">
        <span class="section-eyebrow">${state.search ? "没有结果" : "片库为空"}</span>
        <h3>${state.search ? "没有匹配结果" : "这里暂时还是空的"}</h3>
        <p>${copy}</p>
      </div>
    </div>
  `;
}

window.__openSettingsFromInline = () => {
  state.view = "settings";
  render();
};

