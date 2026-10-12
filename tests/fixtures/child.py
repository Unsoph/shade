"""Scripted engine stand-in for supervisor integration tests.

Behaviour is chosen by the attempt number kept in $SHADE_TEST_STATE:
  1 -> beat briefly then crash (exit 3)
  2 -> beat once then hang forever
  3+ -> beat briefly then exit 0
Every launch appends its argv to $SHADE_TEST_STATE.argv.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.watchdog.heartbeat import Heartbeat  # noqa: E402

state = os.environ["SHADE_TEST_STATE"]
attempt = int(open(state).read() or 0) + 1 if os.path.exists(state) else 1
open(state, "w").write(str(attempt))
with open(state + ".argv", "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")

hb_path = sys.argv[sys.argv.index("--heartbeat") + 1]
hb = Heartbeat(hb_path, interval_s=0.0)
if attempt == 2:
    hb.beat(1)
    time.sleep(60)
for i in range(6):
    hb.beat(i)
    time.sleep(0.05)
sys.exit(3 if attempt == 1 else 0)
