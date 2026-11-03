import sys
import io

if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

print("=== V1 Phase 1 & 2: RESULTS → PAYMENT ===")
import logging
logging.basicConfig(level=logging.INFO)
logging.info("=== V1 Phase 1 & 2: RESULTS → PAYMENT ===")

with open("test_stdout2.txt", "w") as f:
    f.write("OK!")
