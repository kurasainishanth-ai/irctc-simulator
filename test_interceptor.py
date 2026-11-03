import logging
current_status = {"message": "Connecting to Chrome...", "is_error": False, "running": True}
class LogInterceptor(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        msg_lower = msg.lower()
        if "session expired" in msg_lower or "captcha" in msg_lower or "runtimeerror" in msg_lower or "exception" in msg_lower or "unexpected error" in msg_lower or "failed to connect" in msg_lower or "could not find a tab" in msg_lower or "error fetching tabs" in msg_lower:
            if "urlopen" in msg_lower or "10061" in msg_lower or "connectionrefused" in msg_lower or "failed to connect" in msg_lower or "error fetching tabs" in msg_lower or "could not find a tab" in msg_lower:
                current_status["message"] = "IRCTC tab not found or Chrome CDP not available. Please open IRCTC and prepare the train results page."
            else:
                current_status["message"] = f"Stopped: {msg}"
            current_status["is_error"] = True
            current_status["running"] = False

interceptor = LogInterceptor()
logging.getLogger().addHandler(interceptor)
logging.error("Failed to connect to Chrome: <urlopen error timed out>")
print(current_status)
