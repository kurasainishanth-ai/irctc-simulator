from automation.browser import BrowserManager
import traceback

print('Testing connect_to_tab and stop...')
try:
    bm = BrowserManager(cdp_url='http://127.0.0.1:9222')
    p = bm.connect_to_tab('irctc.co.in')
    print('Connected to:', p.url)
    bm.stop()
    print('Stopped successfully.')
except Exception as e:
    print('Exception:')
    traceback.print_exc()
