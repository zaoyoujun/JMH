import threading
import time
import webview
import uvicorn

from backend.app import app


def start_server(port: int):
    """在后台线程启动API服务器"""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    port = 8088

    # 后台启动API服务器
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # 等待服务器启动
    time.sleep(1.5)

    # 创建桌面窗口
    window = webview.create_window(
        title="鸡米花 - 家庭影视库",
        url=f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        min_size=(800, 600),
        resizable=True,
        text_select=True,
    )
    webview.start(debug=False)
