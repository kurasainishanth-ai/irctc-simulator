# IRCTC Tatkal Assistant & Simulator

A desktop assistant and deterministic testing environment for IRCTC booking flows, powered by Python, Flask, Playwright, and Chrome DevTools Protocol (CDP).

---

## Architecture Overview

```
Launch_IRCTC_Assistant.exe  (Launcher)
  │
  ├─ Starts backend server (assistant_server.exe on port 5005)
  ├─ Launches dedicated Chrome instance (--remote-debugging-port=9222)
  └─ Opens IRCTC portal & Assistant Web UI in adjacent tabs
```

1. **Launcher (`launcher.py` / `Launch_IRCTC_Assistant.exe`)**:
   - Detects local Google Chrome installation.
   - Automatically initializes the local backend and dedicated Chrome profile with remote debugging enabled.
   - Opens the Assistant interface (`http://127.0.0.1:5005`) and IRCTC.

2. **Web GUI & Backend (`assistant_server.py`)**:
   - Web GUI served locally in Chrome.
   - Configurable journey details (train number, class, passenger list, insurance, payment preference).
   - Real-time progress monitoring through event-driven log interception and stage progression.

3. **Automation Engine (`automation/`)**:
   - **`browser.py`**: Connects over CDP to the active Chrome tab without spawning secondary browser instances or closing tabs upon completion.
   - **`real_irctc_agent.py`**: Handles deterministic train card lookup, class expansion, date selection, passenger input, insurance/payment choice, and transition monitoring.
   - **`test_real_irctc_v1_direct.py`**: Direct V1 automation flow from Results → Passenger Details → Review → Payment.

---

## Safety & Boundaries

- **No payment automation**: Stops strictly at the Payment page (`/payment/bkgPaymentOptions`) for the user to select and authorize payment manually.
- **No credential / OTP / CAPTCHA bypass**: User handles login, CAPTCHA solving, and two-factor authentication manually.
- **Session Preservation**: Disconnecting Playwright leaves the user's Chrome session and tabs completely intact for repeated runs.
- **Hard Transitions & Error Detection**: 90-second timeout on transitions with real-time detection of server errors (e.g., *"Unable to Process Request!!"* or session timeouts).

---

## Project Structure

```
irctc-simulator/
├── app.py                         # Standalone Flask IRCTC simulator (mock state machine)
├── assistant_server.py            # Local assistant backend server
├── launcher.py                    # Process manager & Chrome CDP launcher
├── build_dist.py                  # PyInstaller build & packaging script
├── v1_config.json                 # Booking & journey configuration
├── templates/                     # Web UI templates (Assistant & Simulator)
├── static/                        # Stylesheets and frontend assets
├── automation/
│   ├── browser.py                 # BrowserManager (CDP connection & tab manager)
│   ├── real_irctc_agent.py        # IRCTC DOM automation agent
│   ├── test_real_irctc_v1_direct.py# Direct V1 flow execution script
│   └── config.py                  # Configuration models
├── test_reliability_fixes.py      # Unit & error classification regression tests
└── test_v1_mock.py                # Mock end-to-end flow tests
```

---

## Running the Application

### Option 1: Packaged Executable (Recommended)
Double-click `Launch_IRCTC_Assistant.exe` in the `IRCTC_Tatkal_Assistant` distribution directory:
1. Chrome and the Assistant web interface open automatically.
2. Prepare the train search/results on IRCTC.
3. Save journey configuration and click **START BOOKING**.

### Option 2: Running from Source
```powershell
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Launch the Assistant backend
python assistant_server.py

# Launch Chrome with CDP
chrome.exe --remote-debugging-port=9222 --user-data-dir=".\chrome_profile"
```

---

## Running Regression Tests

```powershell
python test_reliability_fixes.py
python test_v1_mock.py
```
