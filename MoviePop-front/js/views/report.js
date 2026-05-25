const _reportChartInstances = [];
let _reportResizeBound = false;

function disposeReportCharts() {
  _reportChartInstances.forEach((chart) => {
    if (chart && !chart.isDisposed()) chart.dispose();
  });
  _reportChartInstances.length = 0;
}

function _bindReportResize() {
  if (_reportResizeBound) return;
  _reportResizeBound = true;
  window.addEventListener("resize", () => {
    _reportChartInstances.forEach((chart) => {
      if (chart && !chart.isDisposed()) chart.resize();
    });
  });
}

function initReportCharts() {
  disposeReportCharts();
  _bindReportResize();
  const d = state.reportData;
  const analytics = state.analyticsData || {};
  if (!d && !analytics || typeof echarts === "undefined") return;

  const userProfile = analytics.user_profile || {};
  const genrePref = analytics.genre_preference || [];

  // 1. 四维倾向柱状图
  const fourAxisChart = echarts.init(document.getElementById('fourAxisChart'));
  _reportChartInstances.push(fourAxisChart);
  fourAxisChart.setOption({
    tooltip:{trigger:'axis'},
    grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},
    xAxis:{
      type:'category',
      data:['外向E','内向I','现实S','幻想N','情感F','理性T','规划J','随性P']
    },
    yAxis:{type:'value',max:100},
    series:[{
      type:'bar',
      data:[78,22,82,18,85,15,76,24],
      itemStyle:{color:'#e8c872'}
    }]
  });

  // 2. 人格特质雷达图
  const personRadarChart = echarts.init(document.getElementById('personRadarChart'));
  _reportChartInstances.push(personRadarChart);
  personRadarChart.setOption({
    tooltip:{},
    radar:{
      indicator:[
        {name:'怀旧情怀',max:100},
        {name:'情绪共情',max:100},
        {name:'规整整理',max:100},
        {name:'完播执念',max:100},
        {name:'休闲放松',max:100},
        {name:'猎奇探索',max:100}
      ],
      splitArea:{areaStyle:{color:['rgba(232,200,114,0.1)','transparent']}}
    },
    series:[{
      type:'radar',
      data:[{value:[88,92,80,85,79,35],name:'你的观影人格'}],
      lineStyle:{color:'#e8c872'},
      areaStyle:{color:'rgba(232,200,114,0.2)'}
    }]
  });

  // 3. 契合影视类型饼图
  const matchTypeChart = echarts.init(document.getElementById('matchTypeChart'));
  _reportChartInstances.push(matchTypeChart);
  const genreData = genrePref.length ? genrePref.slice(0, 5).map(g => ({
    value: g.count || g.weight || 1,
    name: g.genre || g.name || '其他'
  })) : [
    {value:35,name:'温情生活剧'},
    {value:28,name:'怀旧经典影片'},
    {value:20,name:'治愈动漫'},
    {value:12,name:'人文纪录片'},
    {value:5,name:'热血竞技类'}
  ];
  matchTypeChart.setOption({
    tooltip:{trigger:'item'},
    series:[{
      type:'pie',
      radius:'70%',
      data:genreData,
      itemStyle:{color:function(params){
        const colorList = ['#e8c872','#72a8e8','#e8729c','#72e8b4','#a872e8'];
        return colorList[params.dataIndex]
      }}
    }]
  });

  // 4. 观影行为占比
  const behaviorChart = echarts.init(document.getElementById('behaviorChart'));
  _reportChartInstances.push(behaviorChart);
  behaviorChart.setOption({
    tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:['完整观看','片段快进','二刷重温','新片试水','收藏归档']},
    yAxis:{type:'value'},
    series:[{
      type:'line',
      smooth:true,
      data:[82,15,75,42,70],
      itemStyle:{color:'#e8c872'},
      areaStyle:{color:'rgba(232,200,114,0.15)'}
    }]
  });

  // 5. 折线图：观影时长趋势（行为分析）
  const durationEl = document.getElementById("reportDurationChart");
  if (durationEl) {
    const chart = echarts.init(durationEl);
    _reportChartInstances.push(chart);
    const durationTrend = analytics.watch_duration_trend || [];
    chart.setOption({
      tooltip: { trigger: "axis", formatter: "{b}: {c} 分钟" },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: "category",
        data: durationTrend.map((item) => item.date?.slice(5) || ""),
        axisLabel: { color: "#c6d6f3", fontSize: 11 },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#c6d6f3", fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
      },
      series: [{
        name: "观影时长(分钟)",
        type: "line",
        smooth: true,
        data: durationTrend.map((item) => item.duration_minutes || 0),
        lineStyle: { color: "#10b981", width: 3 },
        itemStyle: { color: "#10b981" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(16,185,129,0.35)" },
            { offset: 1, color: "rgba(16,185,129,0.02)" },
          ]),
        },
      }],
    });
  }

  // 6. 柱状图：观看时段分布（行为分析）
  const timeEl = document.getElementById("reportTimeChart");
  if (timeEl) {
    const chart = echarts.init(timeEl);
    _reportChartInstances.push(chart);
    const timeDist = analytics.time_distribution || [];
    chart.setOption({
      tooltip: { trigger: "axis", formatter: "{b}: {c} 次" },
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: "category",
        data: timeDist.map((item) => item.label || `${item.hour}:00`),
        axisLabel: { color: theme.textColor, fontSize: 10, rotate: 45 },
        axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: theme.textColor, fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
      },
      series: [{
        type: "bar",
        data: timeDist.map((item) => item.count || 0),
        barWidth: "60%",
        itemStyle: {
          borderRadius: 4,
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#8b5cf6" },
            { offset: 1, color: "#3b82f6" },
          ]),
        },
      }],
    });
  }
}

function renderReportView() {
  const d = state.reportData;
  const analytics = state.analyticsData || {};
  const userProfile = analytics.user_profile || {};
  const durationTrend = analytics.watch_duration_trend || [];
  const genrePref = analytics.genre_preference || [];
  const timeDist = analytics.time_distribution || [];
  const completionRate = analytics.completion_rate || {};

  // 检查是否有有效的行为数据
  const hasValidData = state.hasAnalyticsData === true;
  
  if (!hasValidData) {
    return renderSetupState(
      "暂无足够的观影数据",
      "观看影片至少5分钟或完成3次观看后，系统将为您生成专属观影人格报告。",
      ""
    );
  }

  if (!d && !analytics) {
    return renderSetupState(
      "暂无观影数据",
      "开始收藏和播放影片后，这里会生成你的观影报告。",
      ""
    );
  }

  const overview = d?.overview || {};
  const typeDist = d?.type_distribution || [];
  const genres = d?.genre_preferences || [];
  const completion = d?.completion_stats || {};
  const activity = d?.recent_activity || [];

  const totalCompletion = (completion.completed || completionRate.completed || 0) + (completion.in_progress || completionRate.in_progress || 0) + (completion.not_started || completionRate.not_started || 0) || 1;
  const completedPct = Math.round(((completion.completed || completionRate.completed || 0) / totalCompletion) * 100);
  const inProgressPct = Math.round(((completion.in_progress || completionRate.in_progress || 0) / totalCompletion) * 100);
  const notStartedPct = 100 - completedPct - inProgressPct;

  const mbtiCode = userProfile.mbti_code || "ESFJ";
  const mbtiName = userProfile.mbti_name || "剧情共情家";

  const personalityTags = [
    userProfile.most_watched_genre ? `偏爱${userProfile.most_watched_genre}` : "偏爱温情叙事",
    completionRate.completion_rate > 60 ? "高完播爱好者" : "随性观影者",
    userProfile.preferred_decade ? `偏爱${userProfile.preferred_decade}年代` : "偏爱经典老片",
    userProfile.most_active_period ? `${userProfile.most_active_period}活跃` : "定时规律观影"
  ];

  return `
    <div class="report-shell">
      <div class="person-title">
        <h1>你的专属观影人格</h1>
        <p>基于网盘影视观看行为 · 类MBTI四维人格判定</p>
        <div class="person-code">
          ${mbtiCode.split('').map(c => `<div class="code-item">${c}</div>`).join('')}
        </div>
        <p style="font-size:20px;color:#fff;">${mbtiName} ${mbtiCode}</p>
      </div>

      <div class="row-box">
        <div class="card">
          <h3>观影四维人格倾向</h3>
          <div class="chart-box" id="fourAxisChart"></div>
          <div class="desc-text">
            外向追剧E/独处观影I | 现实写实S/脑洞幻想N<br>
            情感共情F/理性观影T | 规整规划J/随性随缘P
          </div>
        </div>

        <div class="card">
          <h3>观影人格特质雷达</h3>
          <div class="chart-box" id="personRadarChart"></div>
          <div class="tag-wrap">
            ${personalityTags.map(tag => `<span class="tag">${tag}</span>`).join('')}
          </div>
        </div>
      </div>

      <div class="row-box">
        <div class="card full-card">
          <h3>${mbtiCode} ${mbtiName} · 人格深度解读</h3>
          <p class="desc-text">
            你是极具共情力的观影爱好者，偏爱贴近现实、情感饱满的影视内容，很少追无脑爽片与硬核烧脑题材。日常观影习惯规律有序，会主动整理网盘影视资源，分类清晰，偏爱完整看完整部剧集与电影，完播率远高于普通用户。
            <br><br>
            更倾向在休闲时段陪伴式观影，喜欢温情、生活、怀旧向内容，热衷收藏高分口碑影视，偏爱90-00年代经典影视，对影视剧情情绪感知极强，容易代入角色情绪。极少碎片化快进观看，注重完整的观影体验，网盘内资源整理规整，观影计划清晰。
          </p>
        </div>
      </div>

      <div class="row-box">
        <div class="card">
          <h3>最契合你的影视类型</h3>
          <div class="chart-box" id="matchTypeChart"></div>
        </div>

        <div class="card">
          <h3>专属观影行为特征</h3>
          <div class="chart-box" id="behaviorChart"></div>
        </div>
      </div>

      <div class="row-box">
        <div class="card">
          <h3>观影时长趋势</h3>
          <div class="chart-box" id="reportDurationChart"></div>
        </div>

        <div class="card">
          <h3>观看时段分布</h3>
          <div class="chart-box" id="reportTimeChart"></div>
        </div>
      </div>

      <div class="row-box">
        <div class="card full-card">
          <h3>观影概览</h3>
          <div class="report-overview-simple">
            <article class="report-kpi-card-simple">
              <small>总片数</small>
              <strong>${overview.total_movies || 0}</strong>
            </article>
            <article class="report-kpi-card-simple">
              <small>已观看</small>
              <strong>${overview.watched || userProfile.total_movies_watched || 0}</strong>
            </article>
            <article class="report-kpi-card-simple">
              <small>观影时长</small>
              <strong>${overview.total_watch_hours || userProfile.total_watch_hours || 0} 小时</strong>
            </article>
            <article class="report-kpi-card-simple">
              <small>完播率</small>
              <strong>${completionRate.completion_rate || completedPct}%</strong>
            </article>
          </div>
        </div>
      </div>
    </div>
  `;
}

