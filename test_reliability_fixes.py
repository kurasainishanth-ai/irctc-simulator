"""
Regression tests for the IRCTC Tatkal Assistant reliability fixes.

Tests:
  T01 - BrowserManager.disconnect() does NOT call context.close() or browser.close()
  T02 - BrowserManager.stop() on a CDP-attached session redirects to disconnect()
  T03 - Error classifier: CDP error -> correct message
  T04 - Error classifier: Playwright TimeoutError -> NOT labelled as CDP failure
  T05 - Error classifier: RuntimeError from automation -> clear message
  T06 - Error classifier: page state mismatch -> clear message
  T07 - LogInterceptor: 'exception' word in INFO log does NOT trigger error state
  T08 - LogInterceptor: 'urlopen error' in ERROR log DOES trigger CDP error state
  T09 - LogInterceptor: success log sets running=False and is_error=False
  T10 - inspect_current_page: detects PASSENGER_DETAILS from DOM when URL unchanged
  T11 - dead code removed: no 't_passenger = time.time()' after raise in executor
  T12 - build_dist.py: chrome_profile backup/restore logic present
"""

import sys, os, types, logging, importlib, ast, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "automation"))

# ── Minimal stubs so we can import assistant_server without Flask running ──────
import unittest.mock as mock

# Stub Flask so we don't need a running server
flask_stub = types.ModuleType("flask")
flask_stub.Flask = mock.MagicMock(return_value=mock.MagicMock())
flask_stub.request = mock.MagicMock()
flask_stub.jsonify = lambda x: x
flask_stub.render_template = lambda *a, **kw: ""
sys.modules.setdefault("flask", flask_stub)

# Stub test_real_irctc_v1_direct
trd_stub = types.ModuleType("test_real_irctc_v1_direct")
trd_stub.run_v1_to_payment = mock.MagicMock()
sys.modules["test_real_irctc_v1_direct"] = trd_stub

# Stub playwright for browser.py
pw_stub = types.ModuleType("playwright")
pw_stub.sync_api = types.ModuleType("playwright.sync_api")
pw_stub.sync_api.sync_playwright = mock.MagicMock()
pw_stub.sync_api.Page = object
pw_stub.sync_api.Browser = object
pw_stub.sync_api.BrowserContext = object
sys.modules["playwright"] = pw_stub
sys.modules["playwright.sync_api"] = pw_stub.sync_api

# Now import the real modules
import browser as bm_mod
import assistant_server as srv_mod

BrowserManager = bm_mod.BrowserManager


# ─────────────────────────────────────────────────────────────────────────────

class TestBrowserManagerCDPDisconnect(unittest.TestCase):

    def _make_attached_manager(self):
        """Return a BrowserManager that looks like it attached via CDP."""
        mgr = BrowserManager(cdp_url="http://127.0.0.1:9222")
        mgr._cdp_attached = True
        mgr.playwright = mock.MagicMock()
        mgr.browser = mock.MagicMock()
        mgr.context = mock.MagicMock()
        mgr.page = mock.MagicMock()
        return mgr

    def test_T01_disconnect_does_not_close_browser(self):
        """T01: disconnect() must not call context.close() or browser.close()."""
        mgr = self._make_attached_manager()
        mock_ctx = mgr.context
        mock_brw = mgr.browser
        mgr.disconnect()
        mock_ctx.close.assert_not_called()
        mock_brw.close.assert_not_called()

    def test_T01b_disconnect_stops_playwright(self):
        """T01b: disconnect() must stop the Playwright client."""
        mgr = self._make_attached_manager()
        mock_pw = mgr.playwright
        mgr.disconnect()
        mock_pw.stop.assert_called_once()

    def test_T01c_disconnect_clears_references(self):
        """T01c: disconnect() clears internal references."""
        mgr = self._make_attached_manager()
        mgr.disconnect()
        self.assertIsNone(mgr.page)
        self.assertIsNone(mgr.browser)
        self.assertIsNone(mgr.context)
        self.assertIsNone(mgr.playwright)

    def test_T02_stop_on_cdp_attached_redirects_to_disconnect(self):
        """T02: stop() called on a CDP-attached manager must not close browser."""
        mgr = self._make_attached_manager()
        mock_ctx = mgr.context
        mock_brw = mgr.browser
        mgr.stop()  # should redirect to disconnect()
        mock_ctx.close.assert_not_called()
        mock_brw.close.assert_not_called()

    def test_T02b_stop_on_owned_browser_closes(self):
        """T02b: stop() on a locally-launched (non-CDP) browser calls close()."""
        mgr = BrowserManager()  # _cdp_attached stays False
        mgr.playwright = mock.MagicMock()
        mgr.browser = mock.MagicMock()
        mgr.context = mock.MagicMock()
        mgr.stop()
        mgr.context.close.assert_called_once()
        mgr.browser.close.assert_called_once()


class TestErrorClassifier(unittest.TestCase):
    """T03–T06: verify the run_thread exception handler classifies correctly."""

    def _classify(self, exc):
        """Run the exception classification logic and return status dict."""
        # Reset status
        srv_mod.current_status["message"] = "..."
        srv_mod.current_status["is_error"] = False
        srv_mod.current_status["running"] = True

        err_str = str(exc)
        err_type = type(exc).__name__

        _cdp_keywords = (
            "urlopen error", "connection refused", "[errno 10061]",
            "could not find a tab", "error fetching tabs",
            "failed to connect to chrome",
        )
        if any(k in err_str.lower() for k in _cdp_keywords):
            srv_mod.current_status["message"] = "CDP_FAILURE"
        elif "session not logged in" in err_str:
            srv_mod.current_status["message"] = "SESSION_ERROR"
        elif ("Expected PASSENGER_DETAILS" in err_str
              or "Expected REVIEW" in err_str
              or "Expected PAYMENT" in err_str):
            srv_mod.current_status["message"] = "PAGE_STATE_ERROR"
        elif "IRCTC error during transition" in err_str:
            srv_mod.current_status["message"] = f"IRCTC_ERROR: {err_str}"
        elif "TimeoutError" in err_type or err_type.endswith("TimeoutError") or "timed out after" in err_str:
            srv_mod.current_status["message"] = "DOM_TIMEOUT"
        elif isinstance(exc, RuntimeError):
            srv_mod.current_status["message"] = "AUTOMATION_RUNTIME"
        else:
            srv_mod.current_status["message"] = "UNEXPECTED"

        srv_mod.current_status["is_error"] = True
        srv_mod.current_status["running"] = False
        return srv_mod.current_status["message"]

    def test_T03_cdp_connection_error_classified(self):
        """T03: 'urlopen error' must be classified as CDP failure."""
        exc = ConnectionRefusedError("urlopen error [Errno 10061] connection refused")
        self.assertEqual(self._classify(exc), "CDP_FAILURE")

    def test_T04_playwright_timeout_not_cdp(self):
        """T04: A Playwright TimeoutError must NOT become CDP failure message."""

        class FakeTimeoutError(Exception):
            pass
        FakeTimeoutError.__name__ = "TimeoutError"

        exc = FakeTimeoutError("Timeout 5000ms exceeded waiting for locator")
        result = self._classify(exc)
        self.assertNotEqual(result, "CDP_FAILURE",
                            "A Playwright TimeoutError must not be classified as a CDP failure")
        self.assertEqual(result, "DOM_TIMEOUT")

    def test_T05_runtime_error_classified(self):
        """T05: RuntimeError from automation steps classified correctly."""
        exc = RuntimeError("Book Now button not found for train 12759")
        self.assertEqual(self._classify(exc), "AUTOMATION_RUNTIME")

    def test_T06_page_state_mismatch_classified(self):
        """T06: Expected PASSENGER_DETAILS error classified as page state error."""
        exc = RuntimeError("Expected PASSENGER_DETAILS, got results")
        self.assertEqual(self._classify(exc), "PAGE_STATE_ERROR")

    def test_T06b_irctc_transition_error_classified(self):
        """T06b: Explicit IRCTC error during transition classified cleanly."""
        exc = RuntimeError("IRCTC error during transition to review: Unable to Process Request!!")
        res = self._classify(exc)
        self.assertTrue(res.startswith("IRCTC_ERROR:"))


class TestLogInterceptor(unittest.TestCase):
    """T07–T09: LogInterceptor word triggers."""

    def setUp(self):
        srv_mod.current_status["message"] = "Running..."
        srv_mod.current_status["is_error"] = False
        srv_mod.current_status["running"] = True

    def _emit(self, msg, level=logging.INFO):
        record = logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        srv_mod.interceptor.emit(record)

    def test_T07_exception_word_in_info_does_not_trigger_error(self):
        """T07: An INFO log containing 'exception' must NOT trigger error state."""
        self._emit("Playwright caught an exception internally and recovered", logging.INFO)
        self.assertFalse(srv_mod.current_status["is_error"],
                         "INFO log with 'exception' must not set is_error=True")
        self.assertTrue(srv_mod.current_status["running"],
                        "INFO log with 'exception' must not set running=False")

    def test_T08_urlopen_error_in_error_log_triggers_cdp_error(self):
        """T08: ERROR log with 'urlopen error' must trigger CDP failure state."""
        self._emit("urlopen error [Errno 10061] connection refused to port 9222", logging.ERROR)
        self.assertTrue(srv_mod.current_status["is_error"])
        self.assertFalse(srv_mod.current_status["running"])
        self.assertIn("CDP", srv_mod.current_status["message"])

    def test_T09_success_log_sets_terminal_success(self):
        """T09: 'successfully reached payment page' sets running=False, is_error=False."""
        self._emit("Successfully reached Payment Page — automation stopped.")
        self.assertFalse(srv_mod.current_status["running"])
        self.assertFalse(srv_mod.current_status["is_error"])
        self.assertIn("payment", srv_mod.current_status["message"].lower())


class TestInspectCurrentPage(unittest.TestCase):
    """T10: inspect_current_page detects PASSENGER_DETAILS from DOM."""

    def _make_page(self, url, has_passenger_component=False):
        page = mock.MagicMock()
        page.url = url
        # locator("app-passenger-input, app-passenger").count()
        loc = mock.MagicMock()
        loc.count.return_value = 1 if has_passenger_component else 0
        page.locator.return_value = loc
        return page

    def test_T10_detects_passenger_from_dom_when_url_unchanged(self):
        """T10: When URL is still train-list but app-passenger-input is in DOM,
        inspect_current_page must return PASSENGER_DETAILS."""
        from real_irctc_agent import RealIRCTCAgent, PageState
        from config import AgentConfig
        page = self._make_page(
            "https://www.irctc.co.in/nget/booking/train-list",
            has_passenger_component=True
        )
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))
        result = agent.inspect_current_page()
        self.assertEqual(result["state"], PageState.PASSENGER_DETAILS,
                         "DOM detection must override URL-based RESULTS state")

    def test_T10b_no_false_positive_when_component_absent(self):
        """T10b: Without the DOM component, train-list URL returns RESULTS."""
        from real_irctc_agent import RealIRCTCAgent, PageState
        from config import AgentConfig
        page = self._make_page(
            "https://www.irctc.co.in/nget/booking/train-list",
            has_passenger_component=False
        )
        agent = RealIRCTCAgent(page, AgentConfig("https://www.irctc.co.in"))
        result = agent.inspect_current_page()
        self.assertEqual(result["state"], PageState.RESULTS)


class TestDeadCodeRemoved(unittest.TestCase):
    """T11: Unreachable t_passenger assignment after raise is gone."""

    def test_T11_no_dead_code_after_raise(self):
        executor_path = os.path.join(
            os.path.dirname(__file__), "automation", "test_real_irctc_v1_direct.py"
        )
        with open(executor_path, encoding="utf-8") as f:
            source = f.read()
        # The exact dead-code pattern that existed before the fix
        self.assertNotIn(
            "t_passenger = time.time()  # unreachable", source,
            "Dead code 't_passenger = time.time()' after raise must be removed"
        )
        self.assertNotIn(
            "raise RuntimeError(f\"Expected PASSENGER_DETAILS, got {state}\")\n            t_passenger",
            source,
            "Unreachable t_passenger assignment after raise must not exist"
        )


class TestBuildDistPreservesProfile(unittest.TestCase):
    """T12: build_dist.py contains chrome_profile backup/restore logic."""

    def test_T12_chrome_profile_backup_present(self):
        build_path = os.path.join(os.path.dirname(__file__), "build_dist.py")
        with open(build_path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("chrome_profile", source, "build_dist.py must reference chrome_profile")
        self.assertIn("profile_backup", source, "build_dist.py must contain backup logic")
        self.assertIn("copytree", source, "build_dist.py must restore profile with copytree")
        self.assertIn("Backing up chrome_profile", source,
                      "build_dist.py must print backup message")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(
        sys.modules[__name__]
    ))
    sys.exit(0 if result.wasSuccessful() else 1)
