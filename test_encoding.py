import sys
import logging
try:
    logging.basicConfig(level=logging.INFO)
    logging.info("=== V1 Phase 1 & 2: RESULTS → PAYMENT ===")
except Exception as e:
    with open("test_out.txt", "w", encoding="utf-8") as f:
        f.write(f"CAUGHT BY SCRIPT: {type(e)} {e}")
