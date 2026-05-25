async function openTagsModal(movie) {
  state.selectedMovie = movie;
  state.tagInputValue = "";
  await loadTags();
  document.getElementById("tagInput").value = state.tagInputValue;
  renderTagsList();
  openModal("tagsModal");
}

async function loadTags() {
  const payload = await guarded(() => api("/api/tags"));
  if (payload) {
    state.allTags = payload.tags;
  }
}

async function addTag(moviePath, tag) {
  if (!tag.trim()) return;
  
  const payload = await guarded(() => api(`/api/movies/${encodeURIComponent(moviePath)}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag: tag.trim() }),
  }));
  
  if (payload) {
    patchMovie(payload.movie);
    if (state.selectedMovie && state.selectedMovie.path === moviePath) {
      state.selectedMovie = payload.movie;
      renderDetail();
    }
    await loadTags();
    renderTagsList();
    showToast("标签添加成功");
  }
}

async function removeTag(moviePath, tag) {
  const payload = await guarded(() => api(`/api/movies/${encodeURIComponent(moviePath)}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  }));
  
  if (payload) {
    patchMovie(payload.movie);
    if (state.selectedMovie && state.selectedMovie.path === moviePath) {
      state.selectedMovie = payload.movie;
      renderDetail();
    }
    await loadTags();
    renderTagsList();
    showToast("标签移除成功");
  }
}

function renderTagsList() {
  const movie = state.selectedMovie;
  if (!movie) return;
  
  const tagsList = document.getElementById("tagsList");
  
  // 获取电影的标签
  const movieTags = movie.tags || [];
  
  // 获取所有标签
  const allTags = Object.keys(state.allTags);
  
  tagsList.innerHTML = `
    <div class="tags-section">
      <h4>${"电影标签"}</h4>
      ${movieTags.length > 0 ? `
        <div class="tags-grid">
          ${movieTags.map(tag => `
            <div class="tag-item">
              <span class="tag">${escapeHtml(tag)}</span>
              <button class="tag-remove" data-remove-tag="${escapeAttr(tag)}">×</button>
            </div>
          `).join('')}
        </div>
      ` : `<p>${"暂无标签"}</p>`}
    </div>

    ${allTags.length > 0 ? `
    <div class="tags-section">
      <h4>${"所有标签"}</h4>
      <div class="tags-grid">
        ${allTags.map(tag => !movieTags.includes(tag) ? `
          <div class="tag-item">
            <span class="tag">${escapeHtml(tag)}</span>
            <button class="tag-add" data-add-tag="${escapeAttr(tag)}">+</button>
          </div>
        ` : '').join('')}
      </div>
    </div>
    ` : ''}
  `;
  
  // 添加标签事件
  document.querySelectorAll("[data-add-tag]").forEach(button => {
    button.addEventListener("click", () => {
      const tag = button.dataset.addTag;
      addTag(movie.path, tag);
    });
  });
  
  // 移除标签事件
  document.querySelectorAll("[data-remove-tag]").forEach(button => {
    button.addEventListener("click", () => {
      const tag = button.dataset.removeTag;
      removeTag(movie.path, tag);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  // 标签管理事件
  document.getElementById("addTagBtn").addEventListener("click", () => {
    const tagInput = document.getElementById("tagInput");
    const tag = tagInput.value.trim();
    if (tag && state.selectedMovie) {
      addTag(state.selectedMovie.path, tag);
      tagInput.value = "";
    }
  });

  // 标签输入框回车事件
  document.getElementById("tagInput").addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      const tag = event.target.value.trim();
      if (tag && state.selectedMovie) {
        addTag(state.selectedMovie.path, tag);
        event.target.value = "";
      }
    }
  });
});
