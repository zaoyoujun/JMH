function getSeasonLabel(movie, fallbackIndex = 0) {
  const specialType = String(movie?.special_type || "").trim();
  if (specialType) return specialType;
  const seasonTitle = String(movie?.season_title || "").trim();
  if (seasonTitle && /^(ova|oad|oav|sp|特别篇|剧场版|外传|前传)$/i.test(seasonTitle)) {
    return seasonTitle;
  }
  const seasonNumber = Number(movie?.season || fallbackIndex + 1 || 1);
  return `\u7b2c ${seasonNumber} \u5b63`;
}

function getSeriesDisplayTitle(movie) {
  const seriesTitle = String(movie?.series_title || "").trim();
  if (seriesTitle) return seriesTitle;
  const seasonNumber = Number(movie?.season || 0);
  const seasonTitle = String(movie?.season_title || "").trim();
  const rawTitle = String(movie?.title || movie?.name || "").trim();
  if (!rawTitle) return "未命名";
  if (seasonTitle && rawTitle.endsWith(seasonTitle)) {
    const trimmed = rawTitle.slice(0, rawTitle.length - seasonTitle.length).trim();
    if (trimmed) return trimmed;
  }
  const seasonMarker = rawTitle.match(/(第\s*[\d一二三四五六七八九十]+\s*季|season\s*\d+|s\d{1,2})/i);
  if (seasonMarker && typeof seasonMarker.index === "number") {
    const prefix = rawTitle.slice(0, seasonMarker.index).trim().replace(/[·:：\-_.\s]+$/g, "");
    const suffix = stripSeasonSegmentMarkers(
      stripSeasonTokenText(rawTitle.slice(seasonMarker.index + seasonMarker[0].length), seasonNumber)
    );
    const normalizedPrefix = normalizeSeriesFolderName(prefix);
    const normalizedSuffix = normalizeSeriesFolderName(suffix);
    if (prefix && suffix && normalizedPrefix && normalizedSuffix && (normalizedSuffix.startsWith(normalizedPrefix) || normalizedPrefix.startsWith(normalizedSuffix))) {
      return prefix.length <= suffix.length ? prefix : suffix;
    }
    if (prefix) return prefix;
  }
  return rawTitle;
}

function stripSeriesPrefix(title, seriesTitle) {
  const rawTitle = String(title || "").trim();
  const baseSeries = String(seriesTitle || "").trim();
  if (!rawTitle || !baseSeries) return rawTitle;
  return rawTitle.replace(new RegExp(`^${escapeRegex(baseSeries)}[\\s:：·\\-_.]*`, "i"), "").trim();
}

function stripSeasonTokenText(value, season = 0) {
  let result = String(value || "").trim();
  if (!result) return "";
  if (season > 0) {
    result = result
      .replace(new RegExp(`第\\s*${season}\\s*季`, "gi"), " ")
      .replace(new RegExp(`Season\\s*${season}`, "gi"), " ")
      .replace(new RegExp(`S0?${season}(?!\\d)`, "gi"), " ");
  }
  result = result
    .replace(/[（(]\s*(第[\d一二三四五六七八九十]+季|season\s*\d+|s\d{1,2})\s*[)）]/gi, " ")
    .replace(/\b(final season|season\s*\d+|s\d{1,2})\b/gi, " ")
    .replace(/第\s*[\d一二三四五六七八九十]+\s*季/gi, " ")
    .replace(/\s+/g, " ")
    .replace(/^[·:：\-_.\s]+|[·:：\-_.\s]+$/g, "")
    .trim();
  return result;
}

function stripSeasonSegmentMarkers(value) {
  return String(value || "")
    // .replace(/[#＃]\s*\d+/g, " ")  // 保留 #1, #2 这样的部分编号
    // .replace(/\bpart\s*\d+\b/gi, " ")  // 保留 Part 标识，用于区分同一季的不同部分
    .replace(/第\s*[\d一二三四五六七八九十]+\s*(部分|篇|章|部)/gi, " ")
    // .replace(/\b(前篇|后篇|後篇|上篇|下篇|前编|后编|後編)\b/gi, " ")  // 保留上下篇标识
    // .replace(/\b([上下前后])\b/g, " ")  // 保留上下标识
    .replace(/\s+/g, " ")
    .replace(/^[·:：\-_.\s]+|[·:：\-_.\s]+$/g, "")
    .trim();
}

function getCompactSeasonTitle(entry, groupMovie = null) {
  const rawSeasonTitle = String(entry?.season_title || "").trim();
  if (!rawSeasonTitle) return "";
  const seriesTitle = getSeriesDisplayTitle(groupMovie || entry);
  const seasonNumber = Number(entry?.season || 0);
  
  // 先清理系列标题前缀和季数标识，但保留部分编号（如 #1, #2）和上下标识
  let compact = stripSeriesPrefix(rawSeasonTitle, seriesTitle);
  
  // 只移除季数标识（如 S01, 第1季），保留其他信息
  if (seasonNumber > 0) {
    compact = compact
      .replace(new RegExp(`第\\s*${seasonNumber}\\s*季`, "gi"), "")
      .replace(new RegExp(`Season\\s*${seasonNumber}`, "gi"), "")
      .replace(new RegExp(`S0?${seasonNumber}(?!\\d)`, "gi"), "");
  }
  
  // 清理多余空格
  compact = compact.replace(/\s+/g, " ").replace(/^[·:：\-_.\s]+|[·:：\-_.\s]+$/g, "").trim();
  
  // 如果清理后不为空且不等于系列标题，返回它
  // 放宽判断条件，只要不为空就返回
  if (compact && compact.trim()) {
    const normalizedCompact = normalizeSeriesFolderName(compact);
    const normalizedSeries = normalizeSeriesFolderName(seriesTitle);
    // 如果副标题只是数字或简单的季标识，则不显示
    if (!/^\d+$/.test(compact.trim()) && normalizedCompact !== normalizedSeries) {
      return compact;
    }
  }
  return "";
}

function getSeasonEntryLabel(entry, groupMovie = null, fallbackIndex = 0) {
  const seriesTitle = getSeriesDisplayTitle(groupMovie || entry);
  const seasonLabel = getSeasonLabel(entry, fallbackIndex);
  const extras = [];
  const seasonTitle = getCompactSeasonTitle(entry, groupMovie);
  const specialType = String(entry?.special_type || "").trim();
  const seasonNumber = Number(entry?.season || 0);

  // 如果有季标题且不是重复的，添加到 extras
  if (seasonTitle && seasonTitle !== seasonLabel) {
    extras.push(seasonTitle);
  }
  
  // 如果有特殊类型且不是重复的，添加到 extras
  if (specialType && specialType !== seasonLabel) {
    extras.push(specialType);
  }
  
  // 如果有 part 编号且 part > 1，添加 #N（#1 不显示）
  const part = Number(entry?.part || 0);
  if (part > 1) {
    extras.push(`#${part}`);
  }
  
  // 构建最终标签
  if (specialType) {
    // 特别篇格式：系列名·特别篇名
    return `${seriesTitle}·${specialType}`;
  }
  
  if (extras.length > 0) {
    // 正常季格式：系列名·副标题（季数信息）
    // 如果季数大于1，也显示季数
    if (seasonNumber > 1) {
      return `${seriesTitle}·第${seasonNumber}季·${extras.join(" ")}`;
    }
    return `${seriesTitle}·${extras.join(" ")}`;
  }
  
  // 默认格式：系列名（第N季）
  return `${seriesTitle}（第${entry?.season || 1}季）`;
}

function normalizeSeriesFolderName(name) {
  return String(name || "")
    .trim()
    .replace(/\u7b2c\s*[\d\u4e00-\u5341]+\s*\u5b63/gi, " ")
    .replace(/season\s*\d+/gi, " ")
    .replace(/s\d{1,2}/gi, " ")
    // .replace(/[#＃]\d+/g, " ")  // 保留 #1, #2 这样的部分编号
    .replace(/[（(].*?(季|篇|part|final|上|下).*?[)）]/gi, " ")
    .replace(/[._()\[\]-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function getSeriesPathGroupName(movie) {
  const rawPath = String(movie?.path || "");
  if (!rawPath) return "";
  const parts = rawPath.split(/[\\/]+/).filter(Boolean);
  if (parts.length < 4) return "";
  const parent = parts[parts.length - 2];
  const grandparent = parts[parts.length - 3];
  const parentKey = normalizeSeriesFolderName(parent);
  const grandparentKey = normalizeSeriesFolderName(grandparent);
  const parentLooksSeason = /(\u7b2c\s*[\d\u4e00-\u5341]+\s*\u5b63|season\s*\d+|s\d{1,2}|[#＃]\d+|上|下|part)/i.test(parent);
  const genericFolders = new Set([
    "all", "video", "videos", "update", "updates", "webdav", "local", "library", "media",
    "更新中", "动画", "动漫", "剧集", "电视剧", "电影", "综艺", "纪录片", "anime", "shows", "series", "movies"
  ]);
  if (parentLooksSeason && grandparentKey && grandparentKey.length > 1 && !genericFolders.has(grandparentKey)) {
    return grandparentKey;
  }
  return "";
}

function normalizeSeriesKey(movie) {
  const pathBase = getSeriesPathGroupName(movie);
  const titleBase = normalizeSeriesFolderName(movie?.series_title || movie?.title || movie?.name || "");
  let base = pathBase || titleBase;
  if (!pathBase && /[\u4e00-\u9fff]/.test(String(movie?.title || ""))) {
    const collapsed = String(movie?.title || "")
      .replace(/[（(].*?[)）]/g, " ")
      .replace(/\u7b2c\s*\d+\s*\u5b63/gi, " ")
      .replace(/season\s*\d+/gi, " ")
      .replace(/[#＃]\d+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const firstChunk = collapsed.split(" ")[0];
    if (firstChunk && /[\u4e00-\u9fff]/.test(firstChunk)) {
      base = normalizeSeriesFolderName(firstChunk);
    }
  }
  const source = String(movie?.source || movie?.source_label || "");
  return `${base}::${source}`;
}

function buildSeasonBucketKey(entry) {
  const specialType = String(entry?.special_type || "").trim().toLowerCase();
  const seasonNumber = Number(entry?.season || 0);
  if (specialType) {
    return `special::${specialType}::${normalizeSeriesFolderName(getCompactSeasonTitle(entry) || String(entry?.season_title || ""))}`;
  }
  if (seasonNumber > 0) {
    // 包含 season_title 和 part 字段，确保同一季的不同部分正确分开
    const seasonTitle = normalizeSeriesFolderName(getCompactSeasonTitle(entry) || String(entry?.season_title || ""));
    const partNumber = Number(entry?.part || 0);
    let key = `season::${seasonNumber}`;
    if (seasonTitle) key += `::${seasonTitle}`;
    if (partNumber > 0) key += `::part${partNumber}`;
    return key;
  }
  return `path::${entry?.path || ""}`;
}

function mergeSeasonEntries(entries = []) {
  const buckets = new Map();
  for (const entry of entries) {
    const key = buildSeasonBucketKey(entry);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(entry);
  }

  return [...buckets.values()].map((bucket) => {
    if (bucket.length === 1) return bucket[0];
    const ordered = [...bucket].sort((left, right) => String(left.path || "").localeCompare(String(right.path || "")));
    const primary = ordered.find((item) => item.cover_url || item.intro) || ordered[0];
    const latestPlayback = ordered
      .filter((item) => item.playback?.has_progress)
      .sort((left, right) => Number(right.playback?.timestamp || 0) - Number(left.playback?.timestamp || 0))[0] || null;
    const compactTitles = [...new Set(ordered.map((item) => getCompactSeasonTitle(item, primary)).filter(Boolean))];
    const mergedEpisodes = ordered.flatMap((item) => (Array.isArray(item.episodes) ? item.episodes : []));
    const mergedEpisodeFiles = ordered.flatMap((item) => (Array.isArray(item.episode_files) ? item.episode_files : []));
    return {
      ...primary,
      title: getSeriesDisplayTitle(primary),
      name: getSeriesDisplayTitle(primary),
      season_title: compactTitles[0] || getCompactSeasonTitle(primary) || "",
      episode_count: Math.max(
        mergedEpisodes.length,
        mergedEpisodeFiles.length,
        ordered.reduce((sum, item) => sum + Number(item.episode_count || item.episode_files?.length || item.episodes?.length || 0), 0)
      ),
      episodes: mergedEpisodes,
      episode_files: mergedEpisodeFiles,
      playback: latestPlayback?.playback || primary.playback,
      resume_path: latestPlayback?.path || primary.resume_path || primary.path,
      resume_episode_index: Number((latestPlayback?.playback || primary.playback)?.episode_index || 0),
      merged_segment_count: bucket.length,
      source_label: [...new Set(ordered.map((item) => item.source_label).filter(Boolean))].join(" / ") || primary.source_label,
    };
  });
}

function buildGroupedSeries(groupItems) {
  const seasons = mergeSeasonEntries(groupItems).sort((left, right) => {
    // 特别篇（有 special_type）排在最后
    const leftIsSpecial = Boolean(left?.special_type);
    const rightIsSpecial = Boolean(right?.special_type);
    
    if (leftIsSpecial && !rightIsSpecial) return 1;  // 特别篇排后面
    if (!leftIsSpecial && rightIsSpecial) return -1; // 正常季排前面
    
    // 按季数排序
    const seasonGap = Number(left.season || 0) - Number(right.season || 0);
    if (seasonGap !== 0) return seasonGap;
    
    // 同季数按 part 排序
    const partGap = Number(left.part || 0) - Number(right.part || 0);
    if (partGap !== 0) return partGap;
    
    // 同季数同 part 按路径排序
    return String(left.path || "").localeCompare(String(right.path || ""));
  });
  const primary = seasons.find((item) => item.cover_url || item.intro) || seasons[0];
  const tags = [...new Set(seasons.flatMap((item) => (Array.isArray(item.tags) ? item.tags : [])))];
  const inferredTags = [...new Set(seasons.flatMap((item) => (Array.isArray(item.inferred_tags) ? item.inferred_tags : [])))];
  const manualTags = [...new Set(seasons.flatMap((item) => (Array.isArray(item.manual_tags) ? item.manual_tags : [])))];
  const totalEpisodes = seasons.reduce(
    (sum, item) => sum + Number(item.episode_count || item.episode_files?.length || 0),
    0
  );
  const labels = [...new Set(seasons.map((item) => item.source_label).filter(Boolean))];
  const latestPlaybackSeason = seasons
    .filter((item) => item.playback?.has_progress)
    .sort((left, right) => Number(right.playback?.timestamp || 0) - Number(left.playback?.timestamp || 0))[0] || null;
  const playback = latestPlaybackSeason?.playback || {
    progress: 0,
    duration: 0,
    percent: 0,
    timestamp: 0,
    has_progress: false,
  };
  const resumeSeasonLabel = latestPlaybackSeason
    ? getSeasonLabel(latestPlaybackSeason, seasons.indexOf(latestPlaybackSeason))
    : "";
  return {
    ...primary,
    title: getSeriesDisplayTitle(primary),
    name: getSeriesDisplayTitle(primary),
    series_title: getSeriesDisplayTitle(primary),
    seasons,
    season_count: seasons.length,
    episode_count: totalEpisodes,
    is_grouped_series: seasons.length > 1,
    is_favorite: seasons.some((item) => item.is_favorite),
    source_label: labels.join(" / ") || primary.source_label || "媒体库",
    tags,
    manual_tags: manualTags,
    inferred_tags: inferredTags,
    category: primary.category || seasons.find((item) => item.category)?.category || "",
    franchise: primary.franchise || seasons.find((item) => item.franchise)?.franchise || "",
    sort_bucket: Number(primary.sort_bucket || seasons.find((item) => item.sort_bucket)?.sort_bucket || 9),
    sort_title: primary.sort_title || getSeriesDisplayTitle(primary) || primary.title || primary.name || "",
    path: primary.path,
    playback,
    resume_path: latestPlaybackSeason?.path || primary.path,
    resume_episode_index: Number(playback?.episode_index || 0),
    resume_season_label: resumeSeasonLabel,
  };
}

function getDisplayItems(items = state.items) {
  const grouped = new Map();
  for (const item of items) {
    if (!item?.is_series) continue;
    const key = normalizeSeriesKey(item);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  }

  const displayItems = [];
  const seenGroups = new Set();
  for (const item of items) {
    if (!item?.is_series) {
      displayItems.push(item);
      continue;
    }
    const key = normalizeSeriesKey(item);
    if (seenGroups.has(key)) continue;
    seenGroups.add(key);
    const groupItems = grouped.get(key) || [item];
    displayItems.push(buildGroupedSeries(groupItems));
  }
  return displayItems;
}

function getDisplayMovieByPath(moviePath) {
  return getDisplayItems().find((item) => {
    if (item.path === moviePath) return true;
    return Array.isArray(item.seasons) && item.seasons.some((season) => season.path === moviePath);
  });
}

function getActiveSeasonEntry(movie) {
  if (!movie) return null;
  const seasons = Array.isArray(movie.seasons) && movie.seasons.length ? movie.seasons : [movie];
  return seasons.find((item) => item.path === state.selectedSeasonPath) || seasons[0] || null;
}

function syncSelectedMovie() {
  if (!state.selectedMovie) return;
  const lookupPath = state.selectedSeasonPath || state.selectedMovie.path;
  const nextMovie = getDisplayMovieByPath(lookupPath);
  if (nextMovie) {
    state.selectedMovie = nextMovie;
  }
}


