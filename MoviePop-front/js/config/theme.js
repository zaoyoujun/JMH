const _viewMetaZH = {
  all: { kicker: "媒体库", title: "我的片库", subtitle: "集中浏览本地与 WebDAV 的影视内容。" },
  recommend: { kicker: "推荐", title: "为你推荐", subtitle: "根据收藏、播放进度、标签和评分生成个性化推荐。" },
  favorite: { kicker: "收藏", title: "我的收藏", subtitle: "保留你想长期留着的影片和剧集。" },
  recent: { kicker: "最近播放", title: "最近播放", subtitle: "回到最近看过的内容，接着播放。" },
  settings: { kicker: "设置", title: "应用设置", subtitle: "管理片库来源、播放器和扫描目录。" },
  report: { kicker: "报告", title: "观影报告", subtitle: "基于你的收藏、播放和评分生成可视化观影分析。" },
};
function viewMetaFor(key) {
  const m = _viewMetaZH[key];
  return { kicker: m.kicker, title: m.title, subtitle: m.subtitle };
}

// DOM 元素引用
const _themeOptionsBase = [
  { value: "amber", label: "暖光" },
  { value: "graphite", label: "石墨" },
  { value: "forest", label: "森绿" },
  { value: "coast", label: "海岸" },
];
function getThemeOptions() { return _themeOptionsBase; }

function formatRelativeTime(timestamp) {
  const value = Number(timestamp || 0);
  if (!value) return "未执行";
  const diff = Math.max(0, Math.floor(Date.now() / 1000) - value);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

function normalizeTheme(theme) {
  const value = String(theme || "").trim().toLowerCase();
  return getThemeOptions().some((item) => item.value === value) ? value : "amber";
}

function applyTheme(theme) {
  const nextTheme = normalizeTheme(theme);
  document.documentElement.dataset.theme = nextTheme;
  if (state.config) {
    state.config.ui_theme = nextTheme;
    state.config.interface_theme = nextTheme;
  }
}

function getThemeColor(theme) {
  const colors = {
    amber: "linear-gradient(135deg, #ff9248, #ffb347)",
    graphite: "linear-gradient(135deg, #6b7280, #9ca3af)",
    forest: "linear-gradient(135deg, #22c55e, #4ade80)",
    coast: "linear-gradient(135deg, #06b6d4, #67e8f9)",
  };
  return colors[theme] || colors.amber;
}

function getThemeEmoji(theme) {
  const emojis = { amber: "🌅", graphite: "🪨", forest: "🌲", coast: "🌊" };
  return emojis[theme] || emojis.amber;
}

