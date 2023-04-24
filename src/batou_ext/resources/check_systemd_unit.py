#!/usr/bin/env python3

import subprocess
import sys

proc = subprocess.run(
    ["systemctl", "show", sys.argv[1], "-P", "ActiveState"],
    capture_output=True,
    text=True,
)

if proc.returncode != 0:
    print(f"ERROR: {proc.stderr}")
    sys.exit(2)

state = proc.stdout.strip()
if state == "failed":
    print(f"ERROR: {state}")
    sys.exit(2)

print(f"OK: {state}")
sys.exit(0)
