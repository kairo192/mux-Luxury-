import os
import sys
import threading
import http.server
import socketserver
import urllib.request
import webview

def is_port_in_use(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
        return True
    except Exception:
        return False

def serve_dist(dist_dir, port=1420):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=dist_dir, **kwargs)

        def do_GET(self):
            # SPA fallback: if requested file doesn't exist, serve index.html
            path = self.translate_path(self.path)
            if not os.path.exists(path) and not path.endswith("/"):
                self.path = "/index.html"
            return super().do_GET()

        def end_headers(self):
            # Ensure no caching during local development
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            super().end_headers()

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.serve_forever()

def main():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(repo_root, "apps", "desktop-cms", "dist")

    if not is_port_in_use(1420):
        if os.path.isdir(dist_dir):
            t = threading.Thread(target=serve_dist, args=(dist_dir, 1420), daemon=True)
            t.start()
            print(f"Started internal production server on http://127.0.0.1:1420 serving {dist_dir}")

    window = webview.create_window(
        title="Mus Luxury (LUXE) \u2014 Administration & Inventaire",
        url="http://127.0.0.1:1420",
        width=1440,
        height=900,
        min_size=(1100, 720),
        resizable=True,
    )
    webview.start(debug=True)

if __name__ == "__main__":
    main()
