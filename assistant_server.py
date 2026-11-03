import os
import sys
import io

# Explicitly make stdout and stderr UTF-8 safe for Windows (crucial for pythonw)
try:
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

import json
import time
import threading
import logging
from flask import Flask, request, jsonify, render_template

# Ensure imports work from the automation directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation"))
import test_real_irctc_v1_direct

if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__)

CONFIG_FILE = os.path.join(base_dir, "v1_config.json")

current_status = {
    "message": "Ready",
    "is_error": False,
    "running": False,
    "stage": "idle",
}


class LogInterceptor(logging.Handler):
    """Translate automation log messages into GUI status updates.

    Rules:
    - Only match log phrases that are unambiguously from our automation stages.
    - Do NOT treat any word like 'exception' or 'Timeout' as a CDP failure.
      Those are classified by the exception handler in run_thread instead.
    - Never leave running=True after a terminal condition.
    """

    def emit(self, record):
        msg = record.getMessage()
        print(f"INTERCEPTED: {msg}", flush=True)
        msg_lower = msg.lower()

        # --- Terminal: genuine CDP/network connection failures only ---
        _cdp_fail_phrases = (
            "urlopen error", "connection refused", "[errno 10061]",
            "failed to connect to chrome", "could not find a tab",
            "error fetching tabs",
        )
        if any(p in msg_lower for p in _cdp_fail_phrases):
            current_status["message"] = (
                "Cannot connect to Chrome CDP. "
                "Make sure the IRCTC Assistant was launched via Launch_IRCTC_Assistant.exe."
            )
            current_status["is_error"] = True
            current_status["running"] = False
            return

        # --- Terminal: session/login ---
        if "session not logged in" in msg_lower or "session expired" in msg_lower:
            current_status["message"] = "IRCTC session expired. Please log in again."
            current_status["is_error"] = True
            current_status["running"] = False
            return

        # --- Terminal: captcha (log-level WARNING or above only) ---
        if "captcha" in msg_lower and record.levelno >= logging.WARNING:
            current_status["message"] = "CAPTCHA detected — please solve it manually and retry."
            current_status["is_error"] = True
            current_status["running"] = False
            return

        # --- Progress stage advances ---
        if "train" in msg_lower and "located" in msg_lower:
            current_status["message"] = "Train found — locating class..."
            current_status["stage"] = "locating_train"
        elif "expanded class" in msg_lower or "clicking class" in msg_lower:
            current_status["message"] = "Selecting class..."
            current_status["stage"] = "selecting_class"
        elif "clicked book now" in msg_lower or "book now already enabled" in msg_lower:
            current_status["message"] = "Book Now clicked — waiting for passenger form..."
            current_status["stage"] = "booking"
        elif "executing v1 passenger fill" in msg_lower:
            current_status["message"] = "Filling passenger details..."
            current_status["stage"] = "filling_passengers"
        elif "proceeding to review" in msg_lower:
            current_status["message"] = "Opening Review page..."
            current_status["stage"] = "opening_review"
        elif "proceeding to payment" in msg_lower:
            current_status["message"] = "Opening Payment page..."
            current_status["stage"] = "opening_payment"

        # --- Terminal: success ---
        elif "successfully reached payment page" in msg_lower:
            current_status["message"] = (
                "Payment page reached — complete your payment in the IRCTC tab."
            )
            current_status["stage"] = "done"
            current_status["is_error"] = False
            current_status["running"] = False


# Attach interceptor
interceptor = LogInterceptor()
logging.getLogger().addHandler(interceptor)


@app.route("/")
def index():
    return render_template("assistant.html")

@app.route("/api/config", methods=["GET"])
def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({})

@app.route("/api/config", methods=["POST"])
def save_config():
    cfg = request.json
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    return jsonify({"status": "success"})

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(current_status)


run_counter = 0


@app.route("/api/start", methods=["POST"])
def start_booking():
    global run_counter
    if current_status["running"]:
        return jsonify({"status": "error", "message": "Already running"}), 400

    run_counter += 1
    run_id = f"RUN {run_counter:03d}"
    print(f"{run_id} START", flush=True)

    current_status["running"] = True
    current_status["message"] = "Connecting to Chrome..."
    current_status["is_error"] = False
    current_status["stage"] = "connecting"

    def run_thread(rid):
        print(f"{rid} config loaded", flush=True)
        try:
            print(f"{rid} connecting to Chrome", flush=True)

            # --- CDP DIAGNOSTICS (stdout only, never shown in GUI) ---
            import urllib.request as _ureq, json as _json
            try:
                _vr = _ureq.urlopen("http://127.0.0.1:9222/json/version", timeout=2)
                _vd = _json.loads(_vr.read().decode())
                print(f"DIAG_VER: {_json.dumps(_vd)}", flush=True)
                _lr = _ureq.urlopen("http://127.0.0.1:9222/json/list", timeout=2)
                _tabs = _json.loads(_lr.read().decode())
                print(f"DIAG_TABS_COUNT: {len(_tabs)}", flush=True)
                for _idx, _t in enumerate(_tabs):
                    print(f"  TARGET {_idx+1}: type={_t.get('type')} url={_t.get('url')}", flush=True)
            except Exception as _e:
                print(f"DIAG_CDP_ERR: {_e}", flush=True)
            # --- END DIAGNOSTICS ---

            test_real_irctc_v1_direct.run_v1_to_payment(
                "http://127.0.0.1:9222", "irctc.co.in", CONFIG_FILE
            )
            print(f"{rid} executor finished normally", flush=True)
            # LogInterceptor sets running=False on success. Only update if it didn't fire.
            if current_status["running"]:
                current_status["message"] = "Automation completed."
                current_status["running"] = False
                current_status["is_error"] = False

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"{rid} EXCEPTION ({type(e).__name__}): {e}", flush=True)
            print(tb, flush=True)

            err_str = str(e)
            err_type = type(e).__name__

            # --- Error classification by actual type/content ---
            # 1. Pure CDP / network failures (port unreachable, no Chrome, etc.)
            _cdp_keywords = (
                "urlopen error", "connection refused", "[errno 10061]",
                "could not find a tab", "error fetching tabs",
                "failed to connect to chrome",
            )
            if any(k in err_str.lower() for k in _cdp_keywords):
                current_status["message"] = (
                    "Cannot reach Chrome CDP (port 9222). "
                    "Make sure the IRCTC Assistant was launched via Launch_IRCTC_Assistant.exe."
                )

            # 2. Session / login gate
            elif "session not logged in" in err_str:
                current_status["message"] = (
                    "IRCTC session is not logged in. Please log in and try again."
                )

            # 3. IRCTC Explicit Server / Navigation Errors
            elif "IRCTC error during transition" in err_str:
                current_status["message"] = f"IRCTC Error: {err_str.replace('IRCTC error during transition to ', '')}"

            # 4. Wrong page state
            elif ("Expected PASSENGER_DETAILS" in err_str
                  or "Expected REVIEW" in err_str
                  or "Expected PAYMENT" in err_str):
                current_status["message"] = (
                    f"Wrong page state detected: {err_str[:200]}. "
                    "Please navigate to the IRCTC train results page and try again."
                )

            # 5. Playwright DOM/navigation timeout or 90s transition timeout
            elif "TimeoutError" in err_type or err_type.endswith("TimeoutError") or "timed out after" in err_str:
                current_status["message"] = (
                    f"Timeout: {err_str[:200]}"
                )

            # 6. Our own RuntimeError from automation steps
            elif isinstance(e, RuntimeError):
                current_status["message"] = f"Automation step failed: {err_str[:300]}"

            # 7. Anything else
            else:
                current_status["message"] = (
                    f"Unexpected error ({err_type}): {err_str[:200]}"
                )

            current_status["is_error"] = True
            current_status["running"] = False

        print(f"{rid} thread ended", flush=True)

    threading.Thread(target=run_thread, args=(run_id,), daemon=True).start()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5005)
