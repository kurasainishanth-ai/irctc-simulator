import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation"))
import test_real_irctc_v1_direct

try:
    test_real_irctc_v1_direct.run_v1_to_payment("http://127.0.0.1:9222", "irctc.co.in", "v1_config.json")
except Exception as e:
    print("CAUGHT:", type(e), str(e))
