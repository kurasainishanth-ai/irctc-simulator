import os
import sys
import time
import urllib.request
import subprocess
import winreg
import ctypes
import json

def get_chrome_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        path, _ = winreg.QueryValueEx(key, "")
        return path
    except Exception:
        pass
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        path, _ = winreg.QueryValueEx(key, "")
        return path
    except Exception:
        pass
    return None

def show_error(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Startup Error", 0x10)
    sys.exit(1)

def main():
    base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    
    chrome_path = get_chrome_path()
    if not chrome_path or not os.path.exists(chrome_path):
        show_error("Google Chrome is required to run IRCTC Tatkal Assistant.\nPlease install Chrome and try again.")
    
    # Check if assistant_server.exe is running via tasklist
    try:
        tasks = subprocess.check_output('tasklist /FI "IMAGENAME eq assistant_server.exe"', shell=True, text=True)
        server_running = "assistant_server.exe" in tasks
    except Exception:
        server_running = False

    if not server_running:
        server_exe = os.path.join(base_dir, "assistant_server.exe")
        if not os.path.exists(server_exe):
            show_error(f"Cannot find backend server at: {server_exe}")
        subprocess.Popen([server_exe], creationflags=subprocess.CREATE_NO_WINDOW, cwd=base_dir)

    # Check if chrome is running with CDP
    cdp_up = False
    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1)
        if req.status == 200:
            cdp_up = True
    except Exception:
        pass

    chrome_profile = os.path.join(base_dir, "chrome_profile")
    
    if not cdp_up:
        chrome_cmd = [
            chrome_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={chrome_profile}",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        subprocess.Popen(chrome_cmd)

    cdp_ready = False
    for _ in range(20):
        try:
            req = urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1)
            if req.status == 200:
                cdp_ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    
    if not cdp_ready:
        show_error("Failed to start Chrome CDP on port 9222. Please ensure no other Chrome instance is blocking the port.")

    backend_ready = False
    for _ in range(20):
        try:
            req = urllib.request.urlopen("http://127.0.0.1:5005/api/status", timeout=1)
            if req.status == 200:
                backend_ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not backend_ready:
        show_error("Failed to start the local backend server on port 5005.")

    try:
        req = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=2)
        tabs = json.loads(req.read().decode('utf-8'))
        has_irctc = any("irctc.co.in" in t.get("url", "") for t in tabs)
    except Exception:
        has_irctc = False
    
    urls = []
    if not has_irctc:
        urls.append("https://www.irctc.co.in/nget/")
    urls.append("http://127.0.0.1:5005")

    open_cmd = [chrome_path, f"--user-data-dir={chrome_profile}"] + urls
    subprocess.Popen(open_cmd)

if __name__ == "__main__":
    main()
