
// 应用状态管理
const state = {
  view: "all",
  search: "",
  config: null,
  stats: { all: 0, remote: 0, local: 0, favorite: 0, recent: 0 },
  items: [],
  recommendationItems: [],
  externalRecommendations: [],
  recommendationProfile: null,
  recommendationStats: null,
  recommendationGeneratedAt: 0,
  heroCarouselIndex: 0,
  recommendCarouselPaused: false,
  recommendFilter: { type: "", sort: "score" },
  selectedMovie: null,
  selectedSeasonPath: "",
  selectedEpisode: 0,
  editMovie: null,
  webdavDirs: new Set(),
  localDirs: new Set(),
  directoryScope: "webdav",
  directoryPath: "/",
  directoryItems: [],
  candidateMovie: null,
  candidateSelection: null,
  candidateItems: [],
  candidateDiagnostics: [],
  candidateSearchText: "",
  candidateStatus: null,
  activeJobId: null,
  searchTimer: null,
  allTags: {},
  tagInputValue: "",
  reportData: null,
  analyticsData: null,
  playerRuntime: null,
  scanStatus: null,
  openlistStatus: null,
  openlistStorages: [],
  openlistDrivers: [],
  openlistDriverForm: null,
  inlinePlayer: {
    mode: "",
    moviePath: "",
    resolvedPath: "",
    title: "",
    playUrl: "",
    episodeIndex: 0,
    hasStarted: false,
    lastSavedSecond: 0,
  },
};

// 视图元数据
const elements = {
  contentShell: document.getElementById("contentShell"),
  statsStrip: document.getElementById("statsStrip"),
  navList: document.getElementById("navList"),
  searchInput: document.getElementById("searchInput"),
  refreshBtn: document.getElementById("refreshBtn"),
  toastHost: document.getElementById("toastHost"),
  sidebarStatus: document.getElementById("sidebarStatus"),
  jobBanner: document.getElementById("jobBanner"),
  jobTitle: document.getElementById("jobTitle"),
  jobMessage: document.getElementById("jobMessage"),
  jobProgressText: document.getElementById("jobProgressText"),
  jobProgressBar: document.getElementById("jobProgressBar"),
};

let heroCarouselTimer = null;
let recommendCarouselTimer = null;
let inlinePlayerSaveTimer = null;
let inlinePlayerResumeTimer = null;
let inlinePlayerRecoveredOnce = false;

