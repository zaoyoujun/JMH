function showToast(message, kind = "", duration = 2600) {
  const toast = document.createElement("div");
  toast.className = `toast ${kind}`.trim();
  toast.textContent = message;
  
  // 添加动画效果
  toast.style.opacity = "0";
  toast.style.transform = "translateY(20px)";
  toast.style.transition = "opacity 0.3s ease, transform 0.3s ease";
  
  elements.toastHost.appendChild(toast);
  
  // 触发动画
  setTimeout(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  }, 10);
  
  window.setTimeout(() => {
    // 淡出动画
    toast.style.opacity = "0";
    toast.style.transform = "translateY(20px)";
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, duration);
}

// 添加加载状态管理
function showLoading(message = null) {
  if (!message) message = "加载中...";
  // 检查是否已存在加载中元素
  let loadingElement = document.getElementById("loadingOverlay");
  if (loadingElement) {
    return; // 已经有加载中状态
  }
  
  loadingElement = document.createElement("div");
  loadingElement.id = "loadingOverlay";
  loadingElement.className = "loading-overlay";
  loadingElement.innerHTML = `
    <div class="loading-content">
      <div class="loading-spinner"></div>
      <p>${message}</p>
    </div>
  `;
  
  document.body.appendChild(loadingElement);
}

function hideLoading() {
  const loadingElement = document.getElementById("loadingOverlay");
  if (loadingElement) {
    loadingElement.style.opacity = "0";
    setTimeout(() => {
      loadingElement.remove();
    }, 300);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function cleanCookie(cookie) {
  if (!cookie) return "";
  let cleaned = cookie.trim();
  // 移除 "Cookie:" 或 "cookie:" 前缀
  cleaned = cleaned.replace(/^cookie:\s*/i, "");
  // 移除首尾的引号
  cleaned = cleaned.replace(/^["']|["']$/g, "");
  // 移除多余的空白字符（保留单个空格）
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  return cleaned;
}

// 解析 OpenList 错误信息，返回用户友好的提示
function parseOpenListError(error, context = "") {
  const msg = error.message || String(error);

  // 登录失败
  if (msg.includes("登录失败") || msg.includes("login")) {
    if (msg.includes("password") || msg.includes("密码")) {
      return "密码错误，请检查管理员密码或点击「重置密码」";
    }
    if (msg.includes("connect") || msg.includes("connection")) {
      return "无法连接到 OpenList 服务，请检查服务是否正常运行";
    }
    return "登录失败，请检查管理员密码是否正确";
  }

  // 存储驱动相关
  if (msg.includes("UNIQUE constraint") || msg.includes("mount_path")) {
    return "挂载路径已存在，请使用不同的路径或直接更新已有驱动";
  }
  if (msg.includes("invalid header field value") || msg.includes("Cookie")) {
    return "Cookie 格式无效，请重新从浏览器复制（不要包含 \"Cookie:\" 前缀）";
  }
  if (msg.includes("token") || msg.includes("refresh_token")) {
    return "Token 无效或已过期，请重新获取";
  }
  if (msg.includes("timeout") || msg.includes("超时")) {
    return "请求超时，请检查网络连接或稍后重试";
  }
  if (msg.includes("net/http") || msg.includes("network")) {
    return "网络请求失败，请检查网络连接";
  }

  // 下载相关
  if (context === "download") {
    if (msg.includes("404") || msg.includes("Not Found")) {
      return "下载链接不存在，请检查版本号是否正确";
    }
    if (msg.includes("proxy") || msg.includes("代理")) {
      return "代理连接失败，请检查代理设置";
    }
    return "下载失败，请检查网络连接或尝试使用代理";
  }

  // 操作失败
  if (context === "toggle") {
    return "切换状态失败，请检查存储驱动配置是否正确";
  }
  if (context === "delete") {
    return "删除失败，请稍后重试";
  }

  // 默认返回原始信息
  return msg;
}

// ---- OpenList 管理函数 ----

