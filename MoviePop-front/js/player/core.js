function getInlinePlayerElements() {
  return {
    modal: document.getElementById("playerModal"),
    title: document.getElementById("inlinePlayerTitle"),
    meta: document.getElementById("inlinePlayerMeta"),
    status: document.getElementById("inlinePlayerStatus"),
    state: document.getElementById("vlcSessionState"),
    progress: document.getElementById("vlcSessionProgress"),
    bar: document.getElementById("vlcSessionBar"),
    toggle: document.getElementById("vlcToggleBtn"),
  };
}

function resetInlinePlayerState() {
  state.inlinePlayer = {
    mode: "",
    moviePath: "",
    resolvedPath: "",
    title: "",
    playUrl: "",
    episodeIndex: 0,
    hasStarted: false,
    lastSavedSecond: 0,
  };
}

function hydrateInlinePlayerState(session) {
  resetInlinePlayerState();
  state.inlinePlayer.mode = String(session?.player || "");
  state.inlinePlayer.moviePath = String(session?.movie_path || "");
  state.inlinePlayer.resolvedPath = String(session?.resolved_path || "");
  state.inlinePlayer.title = String(session?.display_title || session?.title || "");
  state.inlinePlayer.playUrl = String(session?.play_url || "");
  state.inlinePlayer.episodeIndex = Number(session?.episode_index || 0);
  state.inlinePlayer.hasStarted = !!session?.active;
}

function usesInlinePlayer() {
  return true;
}

function getPreferredInlinePlayerMode() {
  return "mpv_desktop";
}

function getInlinePlayerApiBase(mode = "") {
  return "/api/mpv/session";
}

function getInlinePlayerModeLabel(session) {
  return "内置播放器 mpv";
}

function updateInlinePlayerChrome(session) {
  const { title, meta } = getInlinePlayerElements();
  if (title) title.textContent = session?.display_title || session?.title || "内置播放器 mpv";
  if (meta) meta.textContent = session?.is_series ? `mpv 播放会话 · 第 ${Number(session.episode_index || 0) + 1} 集` : "mpv 播放会话";
}

function usesFloatingMpvPlayer() {
  return false;
}

function getInlinePlayerViewportPayload(visibleOverride = null) {
  const modal = document.getElementById("playerModal");
  const viewport = document.getElementById("inlinePlayerViewport");
  if (!modal || !viewport) return null;
  const rect = viewport.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const visible = visibleOverride !== null
    ? !!visibleOverride
    : !modal.classList.contains("hidden") && rect.width > 0 && rect.height > 0;
  return {
    x: Math.max(0, Math.round(rect.left * dpr)),
    y: Math.max(0, Math.round(rect.top * dpr)),
    width: Math.max(0, Math.round(rect.width * dpr)),
    height: Math.max(0, Math.round(rect.height * dpr)),
    visible,
  };
}

async function syncInlinePlayerLayout(visibleOverride = null) {
  if ((state.inlinePlayer.mode || "").toLowerCase() !== "mpv_desktop") return;
  const payload = getInlinePlayerViewportPayload(visibleOverride);
  if (!payload) return;
  try {
    await api("/api/mpv/session/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    // ignore transient layout sync failures
  }
}

function stopInlinePlayerPolling() {
  window.clearInterval(inlinePlayerSaveTimer);
  inlinePlayerSaveTimer = null;
}

function startInlinePlayerPolling() {
  stopInlinePlayerPolling();
  inlinePlayerSaveTimer = window.setInterval(() => {
    pollInlinePlayerSession().catch(() => {});
  }, 2500);
}

function formatVlcStateLabel(rawState) {
  const value = String(rawState || "").trim().toLowerCase();
  if (value === "playing") return "正在播放";
  if (value === "paused") return "已暂停";
  if (value === "opening") return "正在打开媒体";
  if (value === "stopped") return "已停止";
  return "等待 mpv 响应";
}

function renderInlinePlayerSession(session) {
  const { title, meta, status, state: stateEl, progress, bar, toggle } = getInlinePlayerElements();
  const active = !!session?.active;
  const duration = Number(session?.duration_seconds || 0);
  const current = Number(session?.progress_seconds || 0);
  const percent = duration > 0 ? Math.max(0, Math.min(100, (current / duration) * 100)) : 0;
  if (title) title.textContent = session?.display_title || session?.title || "内置播放器 mpv";
  if (meta) meta.textContent = session?.is_series ? `mpv 播放会话 · 第 ${Number(session.episode_index || 0) + 1} 集` : "mpv 播放会话";
  if (status) status.textContent = active ? "应用正在同步 mpv 的状态、进度和观影统计。" : "当前没有正在运行的 mpv 会话。";
  if (stateEl) stateEl.textContent = formatVlcStateLabel(session?.state);
  if (progress) progress.textContent = `${formatDuration(current)} / ${formatDuration(duration)}`;
  if (bar) bar.style.width = `${percent}%`;
  if (toggle) toggle.textContent = String(session?.state || "").toLowerCase() === "paused" ? "继续播放" : "暂停播放";
}

async function refreshPlaybackUiAfterSessionEnd({ closePlayerModal = true } = {}) {
  const detailModal = document.getElementById("detailModal");
  const playerModal = document.getElementById("playerModal");
  const detailOpen = !!detailModal && !detailModal.classList.contains("hidden");
  const selectedRootPath = state.selectedMovie?.path || "";
  const selectedSeasonPath = state.selectedSeasonPath || "";

  stopInlinePlayerPolling();
  resetInlinePlayerState();

  if (closePlayerModal && playerModal && !playerModal.classList.contains("hidden")) {
    playerModal.classList.add("hidden");
  }

  await loadBootstrap();
  await loadCurrentView();

  if (detailOpen) {
    const nextSelectedMovie =
      getDisplayMovieByPath(selectedSeasonPath) ||
      getDisplayMovieByPath(selectedRootPath);
    if (nextSelectedMovie) {
      state.selectedMovie = nextSelectedMovie;
      if (Array.isArray(nextSelectedMovie.seasons) && nextSelectedMovie.seasons.some((season) => season.path === selectedSeasonPath)) {
        state.selectedSeasonPath = selectedSeasonPath;
      } else {
        state.selectedSeasonPath = nextSelectedMovie.path;
      }
      syncSelectedMovie();
      renderDetail();
    }
  }
}

async function pollInlinePlayerSession() {
  try {
    const payload = await api(getInlinePlayerApiBase());
    if (!payload?.result) return;
    renderInlinePlayerSession(payload.result);
    await syncInlinePlayerLayout();
    if (!payload.result.active) {
      await refreshPlaybackUiAfterSessionEnd({ closePlayerModal: true });
    }
  } catch (error) {
    await refreshPlaybackUiAfterSessionEnd({ closePlayerModal: true });
  }
}

async function sendInlinePlayerCommand(action, value = null) {
  const payload = await guarded(() =>
    api(`${getInlinePlayerApiBase()}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, value }),
    })
  );
  if (payload?.result) {
    renderInlinePlayerSession(payload.result);
    if (action === "stop") {
      await refreshPlaybackUiAfterSessionEnd({ closePlayerModal: true });
    }
  }
}

async function recoverInlinePlayerSession({ silent = true } = {}) {
  try {
    let session = null;
    const primary = getPreferredInlinePlayerMode();
    const payload = await api(getInlinePlayerApiBase(primary));
    if (payload?.result?.active) {
      session = payload.result;
    }
    if (!session?.active) {
      stopInlinePlayerPolling();
      resetInlinePlayerState();
      return null;
    }
    hydrateInlinePlayerState(session);
    if (usesFloatingMpvPlayer()) {
      startInlinePlayerPolling();
    } else if (document.getElementById("playerModal") && !document.getElementById("playerModal").classList.contains("hidden")) {
      renderInlinePlayerSession(session);
      startInlinePlayerPolling();
      await syncInlinePlayerLayout();
    }
    if (!silent && !inlinePlayerRecoveredOnce) {
      showToast("已恢复播放器会话，进度统计会继续同步", "info");
      inlinePlayerRecoveredOnce = true;
    }
    return session;
  } catch (error) {
    stopInlinePlayerPolling();
    return null;
  }
}

async function openInlinePlayer(moviePath, episodeIndex = 0) {
  const preferredMode = getPreferredInlinePlayerMode();
  try {
    const current = await api(getInlinePlayerApiBase(preferredMode));
    if (current?.result?.active && current.result.movie_path === moviePath && Number(current.result.episode_index || 0) === Number(episodeIndex || 0)) {
      hydrateInlinePlayerState(current.result);
      startInlinePlayerPolling();
      return;
    }
  } catch (error) {
    // ignore and fall through to start a new controlled session
  }

  const payload = await guarded(() =>
    api(`${getInlinePlayerApiBase(preferredMode)}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_path: moviePath, episode_index: episodeIndex }),
    })
  );
  if (!payload?.result) return;

  hydrateInlinePlayerState(payload.result);
  startInlinePlayerPolling();
  if (payload?.stats) {
    state.stats = payload.stats;
    renderStats();
  }
  showToast(
    payload.result.resume_applied
      ? `已从 ${formatDuration(payload.result.resume_seconds || 0)} 继续播放`
      : "已打开内置 mpv 播放窗口",
    "success"
  );
}

async function closeInlinePlayer({ refresh = true } = {}) {
  const { status } = getInlinePlayerElements();
  stopInlinePlayerPolling();
  window.clearTimeout(inlinePlayerResumeTimer);
  inlinePlayerResumeTimer = null;
  await syncInlinePlayerLayout(false);
  if (status) status.textContent = "";
  resetInlinePlayerState();
  if (refresh) {
    await loadCurrentView();
  }
}

