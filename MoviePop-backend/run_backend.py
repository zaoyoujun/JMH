from backend.server import find_free_port
import uvicorn

from backend.app import app


if __name__ == "__main__":
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"MoviePop backend running at {url}")
    import webbrowser
    webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info", access_log=False)
