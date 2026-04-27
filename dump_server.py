"""
Local HTTP server for browser fingerprint gathering.

This script launches a simple web server that serves an HTML page designed to
collect various client-side browser fingerprints (e.g., User-Agent, Client Hints,
WebGL renderer info, Canvas noise). The collected data is sent back to the server
via a POST request and logged to the console.
"""
import http.server
import socketserver
import json

PORT = 8080

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Fingerprint Dump</title>
</head>
<body>
    <h2>Сбор отпечатков...</h2>
    <pre id="output"></pre>
    <script>
        async function collectFingerprint() {
            let fp = {};
            
            // 1. Навигатор
            fp.userAgent = navigator.userAgent;
            fp.webdriver = navigator.webdriver;
            fp.hardwareConcurrency = navigator.hardwareConcurrency;
            fp.deviceMemory = navigator.deviceMemory;
            fp.platform = navigator.platform;
            fp.languages = navigator.languages;
            
            // 2. Client Hints
            if (navigator.userAgentData) {
                try {
                    let uaData = await navigator.userAgentData.getHighEntropyValues(["architecture", "model", "platform", "platformVersion", "uaFullVersion"]);
                    fp.userAgentData = uaData;
                } catch(e) { fp.userAgentData = "Error"; }
            }
            
            // 3. WebGL
            try {
                let canvas = document.createElement('canvas');
                let gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    let ext = gl.getExtension('WEBGL_debug_renderer_info');
                    fp.webgl_vendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : "N/A";
                    fp.webgl_renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "N/A";
                }
            } catch(e) { fp.webgl_vendor = "Error"; }

            // 4. Canvas Noise
            try {
                let canvas = document.createElement('canvas');
                canvas.width = 100; canvas.height = 100;
                let ctx = canvas.getContext('2d');
                ctx.fillStyle = "blue";
                ctx.fillRect(0,0,100,100);
                let data = canvas.toDataURL();
                // берем последние 50 символов чтобы увидеть шум
                fp.canvas_end = data.substring(data.length - 50);
            } catch(e) { fp.canvas_end = "Error"; }

            // 5. Window & Chrome
            fp.has_window_chrome = !!window.chrome;
            fp.has_chrome_app = window.chrome ? !!window.chrome.app : false;
            
            // Вывод и отправка
            document.getElementById('output').innerText = JSON.stringify(fp, null, 2);
            
            fetch('/dump', {
                method: 'POST',
                body: JSON.stringify(fp)
            }).then(() => document.body.innerHTML += "<h3>Данные отправлены! Проверьте консоль сервера.</h3>");
        }
        
        collectFingerprint();
    </script>
</body>
</html>
"""

class DumpHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print("\n" + "="*50)
        print(f"[GET] {self.path}")
        print("--- HTTP HEADERS ---")
        for key, value in self.headers.items():
            print(f"{key}: {value}")
        print("-" * 20)
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode('utf-8'))

    def do_POST(self):
        if self.path == '/dump':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            print("\n--- JAVASCRIPT FINGERPRINT ---")
            try:
                data = json.loads(post_data.decode('utf-8'))
                print(json.dumps(data, indent=4, ensure_ascii=False))
            except Exception as e:
                print("RAW DATA:", post_data.decode('utf-8'))
            print("==================================================\n")
            
            self.send_response(200)
            self.end_headers()

with socketserver.TCPServer(("", PORT), DumpHandler) as httpd:
    print(f"Сервер запущен на http://localhost:{PORT}")
    print("Откройте этот адрес в Playwright или обычном браузере.")
    httpd.serve_forever()
