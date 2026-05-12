from __future__ import annotations

import os
import sys
import time

# allow running as: python sdk_control/uni_test.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # parent of sdk_control = go2_sdk
PARENT = os.path.abspath(os.path.join(ROOT, ".."))  # parent of go2_sdk
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from go2_sdk.sdk_control.uni import Go2LowHybrid  # noqa: E402

a = Go2LowHybrid()
a.mag_start()
a.mag_off(1)
time.sleep(0.005)
a.mag_off(2)
time.sleep(0.005)
a.mag_off(3)
time.sleep(0.005)
a.mag_off(4)
time.sleep(0.005)

# time.sleep(5.0)
