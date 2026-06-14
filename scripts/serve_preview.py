import http.server
import socketserver
import os
import json
import webbrowser
import threading
import sys
import time

PORT = 8000
README_PATH = "README.md"

# HTML Template with premium UI and live-reload
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" data-color-mode="dark" data-dark-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub README Live Preview</title>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- GitHub Markdown CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css">
    <style>
        :root {
            --bg-gradient: linear-gradient(135deg, #090d16 0%, #110e29 100%);
            --panel-bg: rgba(22, 27, 43, 0.7);
            --panel-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-purple: #a78bfa;
            --accent-purple-hover: #c4b5fd;
            --accent-green: #34d399;
            --accent-green-glow: rgba(52, 211, 153, 0.4);
            --sidebar-width: 320px;
        }

        /* Light Mode Variables Override */
        html[data-color-mode="light"] {
            --bg-gradient: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
            --panel-bg: rgba(255, 255, 255, 0.85);
            --panel-border: rgba(0, 0, 0, 0.08);
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --accent-purple: #6366f1;
            --accent-purple-hover: #4f46e5;
        }

        * {
            box-sizing: border-box;
            transition: background-color 0.3s ease, border-color 0.3s ease, color 0.2s ease;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: var(--bg-gradient);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            background: rgba(13, 17, 28, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--panel-border);
            padding: 14px 28px;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        html[data-color-mode="light"] header {
            background: rgba(255, 255, 255, 0.85);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo i {
            font-size: 26px;
            background: linear-gradient(135deg, var(--accent-purple) 0%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo h1 {
            margin: 0;
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }

        .status-bar {
            display: flex;
            align-items: center;
            gap: 18px;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(52, 211, 153, 0.08);
            border: 1px solid rgba(52, 211, 153, 0.2);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 500;
            color: var(--accent-green);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--accent-green-glow);
            animation: pulse 2s infinite;
        }

        .update-flash {
            animation: flashGreen 1s ease-out;
        }

        @keyframes flashGreen {
            0% { background-color: rgba(52, 211, 153, 0.4); transform: scale(1.05); }
            100% { background-color: rgba(52, 211, 153, 0.08); transform: scale(1); }
        }

        @keyframes pulse {
            0% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7);
            }
            70% {
                transform: scale(1);
                box-shadow: 0 0 0 8px rgba(52, 211, 153, 0);
            }
            100% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(52, 211, 153, 0);
            }
        }

        .main-container {
            display: flex;
            flex: 1;
            max-width: 1400px;
            margin: 28px auto;
            width: 100%;
            padding: 0 24px;
            gap: 28px;
        }

        .preview-panel {
            flex: 1;
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 20px;
            padding: 48px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.2);
            overflow-x: auto;
            position: relative;
        }

        .markdown-body {
            box-sizing: border-box;
            min-width: 200px;
            max-width: 920px;
            margin: 0 auto;
            background: transparent !important;
        }

        .sidebar {
            width: var(--sidebar-width);
            display: flex;
            flex-direction: column;
            gap: 24px;
            flex-shrink: 0;
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--panel-border);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.15);
        }

        .card-title {
            font-family: 'Outfit', sans-serif;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
            margin-top: 0;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-title i {
            color: var(--accent-purple);
        }

        .info-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .info-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            padding-bottom: 8px;
        }

        .info-label {
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .info-value {
            font-weight: 600;
            font-family: 'Fira Code', monospace;
            color: var(--text-primary);
        }

        .action-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--panel-border);
            color: var(--text-primary);
            padding: 10px 16px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            width: 100%;
            justify-content: center;
            outline: none;
        }

        .btn:hover {
            background: rgba(255, 255, 255, 0.09);
            border-color: rgba(255, 255, 255, 0.18);
            transform: translateY(-2px);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--accent-purple) 0%, #7c3aed 100%);
            border: none;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.25);
        }

        .btn-primary:hover {
            background: linear-gradient(135deg, var(--accent-purple-hover) 0%, #6d28d9 100%);
            box-shadow: 0 6px 16px rgba(124, 58, 237, 0.4);
            color: #ffffff;
        }

        .notification {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: rgba(16, 24, 48, 0.95);
            border: 1px solid var(--accent-green);
            color: #ffffff;
            padding: 14px 20px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 1000;
        }

        .notification.show {
            transform: translateY(0);
            opacity: 1;
        }

        .notification i {
            color: var(--accent-green);
            font-size: 18px;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.05);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.12);
            border-radius: 5px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.22);
        }

        /* Responsive */
        @media (max-width: 992px) {
            .main-container {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <i class="fab fa-github"></i>
            <h1>README Live Preview</h1>
        </div>
        <div class="status-bar">
            <span class="status-badge" id="statusBadge">
                <span class="status-dot"></span>
                <span id="statusText">Syncing Live</span>
            </span>
        </div>
    </header>

    <div class="main-container">
        <div class="preview-panel">
            <div class="markdown-body" id="previewArea">
                <div style="display: flex; justify-content: center; align-items: center; min-height: 200px; flex-direction: column; gap: 16px; color: var(--text-secondary);">
                    <i class="fas fa-spinner fa-spin" style="font-size: 28px; color: var(--accent-purple);"></i>
                    <p>Loading README.md and preparing preview...</p>
                </div>
            </div>
        </div>

        <div class="sidebar">
            <div class="card">
                <h3 class="card-title"><i class="fas fa-info-circle"></i> File Information</h3>
                <div class="info-list">
                    <div class="info-item">
                        <span class="info-label"><i class="far fa-file-alt"></i> File</span>
                        <span class="info-value">README.md</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-hdd"></i> Size</span>
                        <span class="info-value" id="fileSize">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label"><i class="fas fa-file-signature"></i> Words</span>
                        <span class="info-value" id="wordCount">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label"><i class="far fa-clock"></i> Last Saved</span>
                        <span class="info-value" id="lastSaved">-</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3 class="card-title"><i class="fas fa-sliders-h"></i> Controls</h3>
                <div class="action-group">
                    <button class="btn btn-primary" id="btnUpdateReadme">
                        <i class="fas fa-sync-alt"></i> Update Metrics Now
                    </button>
                    <button class="btn" id="btnToggleTheme">
                        <i class="fas fa-adjust"></i> Toggle Color Mode
                    </button>
                    <button class="btn" id="btnReload">
                        <i class="fas fa-redo"></i> Force Reload File
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="notification" id="toast">
        <i class="fas fa-check-circle"></i>
        <span id="toastMsg">README updated successfully!</span>
    </div>

    <!-- Script imports -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
        let lastMtime = 0;
        let isFetching = false;
        
        // Use default marked configuration
        // (latest marked.js version compatibility)

        async function fetchReadme() {
            if (isFetching) return;
            isFetching = true;
            try {
                const response = await fetch('/api/readme');
                if (response.ok) {
                    const data = await response.json();
                    
                    // If mtime is updated
                    if (data.mtime !== lastMtime) {
                        const parsed = marked.parse(data.content);
                        document.getElementById('previewArea').innerHTML = parsed;
                        
                        // Flash status badge to indicate update
                        const badge = document.getElementById('statusBadge');
                        badge.classList.add('update-flash');
                        setTimeout(() => badge.classList.remove('update-flash'), 1000);
                        
                        // Update file info
                        updateFileInfo(data.content, data.mtime);
                        
                        if (lastMtime !== 0) {
                            showToast("README.md updated & live reloaded!");
                        }
                        lastMtime = data.mtime;
                    }
                }
            } catch (err) {
                console.error("Error fetching README:", err);
                document.getElementById('statusText').innerText = "Error: " + err.message;
                document.getElementById('statusBadge').style.borderColor = "rgba(239, 68, 68, 0.4)";
                document.getElementById('statusBadge').style.backgroundColor = "rgba(239, 68, 68, 0.08)";
                document.getElementById('statusBadge').style.color = "#ef4444";
            } finally {
                isFetching = false;
            }
        }

        function updateFileInfo(content, mtime) {
            // Size
            const bytes = new Blob([content]).size;
            let sizeStr = bytes + " B";
            if (bytes > 1024) sizeStr = (bytes / 1024).toFixed(2) + " KB";
            document.getElementById('fileSize').innerText = sizeStr;

            // Word Count
            const words = content.trim().split(/\\s+/).filter(w => w.length > 0).length;
            document.getElementById('wordCount').innerText = words.toLocaleString();

            // Last Saved
            const date = new Date(mtime * 1000);
            document.getElementById('lastSaved').innerText = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            
            // Restore status indicator styles just in case
            document.getElementById('statusText').innerText = "Syncing Live";
            document.getElementById('statusBadge').style.borderColor = "";
            document.getElementById('statusBadge').style.backgroundColor = "";
            document.getElementById('statusBadge').style.color = "";
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            document.getElementById('toastMsg').innerText = msg;
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // Toggle theme
        const btnToggleTheme = document.getElementById('btnToggleTheme');
        btnToggleTheme.addEventListener('click', () => {
            const currentMode = document.documentElement.getAttribute('data-color-mode');
            const newMode = currentMode === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-color-mode', newMode);
            document.documentElement.setAttribute('data-dark-theme', newMode);
        });

        // Force reload
        document.getElementById('btnReload').addEventListener('click', () => {
            lastMtime = 0; // force redraw
            fetchReadme();
            showToast("Force reloaded README.md!");
        });

        // Run update metrics script via API
        document.getElementById('btnUpdateReadme').addEventListener('click', async () => {
            const btn = document.getElementById('btnUpdateReadme');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            try {
                showToast("Running scripts/update_readme.py... please wait");
                const resp = await fetch('/api/update-readme', { method: 'POST' });
                const result = await resp.json();
                if (resp.ok && result.success) {
                    showToast("Metrics updated successfully!");
                    lastMtime = 0; // force redraw
                    fetchReadme();
                } else {
                    showToast("Update failed: " + (result.error || "Unknown error"));
                }
            } catch (err) {
                showToast("Error executing script: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-sync-alt"></i> Update Metrics Now';
            }
        });

        // Poll every 800ms
        setInterval(fetchReadme, 800);
        
        // Initial fetch
        fetchReadme();
    </script>
</body>
</html>
"""

class ReadmePreviewHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif self.path == "/api/readme":
            if os.path.exists(README_PATH):
                mtime = os.path.getmtime(README_PATH)
                try:
                    with open(README_PATH, "r", encoding="utf-8") as f:
                        content = f.read()
                    data = {
                        "content": content,
                        "mtime": mtime
                    }
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(data).encode("utf-8"))
                except Exception as e:
                    self.send_error(500, f"Error reading README.md: {str(e)}")
            else:
                self.send_error(404, "README.md not found")
        else:
            # Serve other static files (like images, css, svgs in profile-3d-contrib/)
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/update-readme":
            # Run the update_readme.py script
            import subprocess
            try:
                # Execute scripts/update_readme.py
                script_path = os.path.join("scripts", "update_readme.py")
                
                # Run with python interpreter
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    response_data = {"success": True, "output": result.stdout}
                    self.send_response(200)
                else:
                    response_data = {"success": False, "error": result.stderr or result.stdout}
                    self.send_response(500)
                
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # Mute API logging to keep server console clean
        if args and isinstance(args[0], str) and "/api/" in args[0]:
            return
        super().log_message(format, *args)

def run_server():
    # Configure the socket reuse option
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ReadmePreviewHandler) as httpd:
        print("\n=======================================================")
        print(" [RUNNING] README Live Preview Server is active!")
        print(f" > Local URL: http://localhost:{PORT}")
        print(f" > Watching file: {README_PATH}")
        print(" > Edit README.md and save to see it update live!")
        print("=======================================================\n")
        
        # Open in browser after a short delay to let server start
        def open_browser():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{PORT}")
            
        threading.Thread(target=open_browser, daemon=True).start()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer shutting down. Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    # Ensure workspace root contains README.md
    if not os.path.exists(README_PATH):
        # If run from scripts directory, change to parent directory
        if os.path.basename(os.getcwd()) == "scripts":
            os.chdir("..")
            
        if not os.path.exists(README_PATH):
            print(f"Error: Could not find {README_PATH} in current directory.")
            sys.exit(1)
            
    run_server()
