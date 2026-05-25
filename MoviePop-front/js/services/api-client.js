async function api(url, options = {}) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒超时
    
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (!response.ok) {
      let message = "请求失败";
      try {
        const payload = await response.json();
        message = payload.detail || payload.message || message;
      } catch (error) {
        message = response.statusText || message;
      }
      throw new Error(message);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('请求超时，请检查网络连接');
    } else if (!navigator.onLine) {
      throw new Error('网络连接已断开，请检查网络设置');
    }
    throw error;
  }
}

async function guarded(task, showLoadingFlag = false, loadingMessage = null) {
  if (!loadingMessage) loadingMessage = "加载中...";
  if (showLoadingFlag) {
    showLoading(loadingMessage);
  }
  
  try {
    const result = await task();
    if (showLoadingFlag) {
      hideLoading();
    }
    return result;
  } catch (error) {
    if (showLoadingFlag) {
      hideLoading();
    }
    showToast(error.message || "发生了未知错误", "error");
    return null;
  }
}

