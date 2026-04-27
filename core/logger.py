"""
Manages session logging and browser tracing.

Records console messages, network requests, and optionally saves Playwright
traces to help with debugging automation sessions.
"""
import os
import shutil

class SessionLogger:
    def __init__(self, session_name, base_path=None):
        # Если путь не задан, используем logs/sessions от корня проекта
        if base_path is None:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            base_path = os.path.join(root, "logs", "sessions")
            
        self.session_name = session_name
        self.log_path = os.path.join(base_path, session_name)
        
    def prepare(self):
        """Очищает и создает папку для логов сессии."""
        if os.path.exists(self.log_path):
            shutil.rmtree(self.log_path)
        os.makedirs(self.log_path, exist_ok=True)
        return self.log_path

    def setup_page_logging(self, page):
        """Подключает логирование консоли и запросов."""
        console_log = os.path.join(self.log_path, "console.log")
        requests_log = os.path.join(self.log_path, "requests.log")

        page.on("console", lambda msg: self._write_to_file(console_log, f"[{msg.type}] {msg.text}\n"))
        page.on("request", lambda req: self._write_to_file(requests_log, f"{req.method} {req.url}\n"))
        # В Python Playwright req.failure - это строка или None
        page.on("requestfailed", lambda req: self._write_to_file(requests_log, f"FAILED: {req.method} {req.url} - {req.failure if req.failure else 'Unknown'}\n"))

    def _write_to_file(self, path, text):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text)
        except: pass

    def stop_tracing(self, context, filename="trace.zip"):
        """Сохраняет архив трассировки."""
        trace_path = os.path.join(self.log_path, filename)
        context.tracing.stop(path=trace_path)
        return trace_path
