# SPDX-License-Identifier: Apache-2.0
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BashLifecycleTests(unittest.TestCase):
    def run_bash(self, body):
        with tempfile.TemporaryDirectory() as runtime:
            return subprocess.run(
                ["bash", "-c", 'set -euo pipefail; source "$1/scripts/common.sh"; RUNTIME="$2"; ' + body,
                 "test", str(ROOT), runtime], capture_output=True, text=True, timeout=15, check=True,
            )

    def test_start_reuses_owned_process_and_stop_terminates_it(self):
        result = self.run_bash('''
            trap 'stop_managed fixture >/dev/null' EXIT
            start_managed fixture sleep 60
            managed_running fixture
            before="$(cat "$RUNTIME/fixture.pid")"
            start_managed fixture sleep 60
            [[ "$(cat "$RUNTIME/fixture.pid")" == "$before" ]]
            stop_managed fixture
            ! managed_running fixture
        ''')
        self.assertIn("already managed", result.stdout)
        self.assertIn("Stopped fixture", result.stdout)

    def test_stale_pid_file_does_not_target_unrelated_process(self):
        self.run_bash('''
            printf '%s\\n%s\\n' "$$" 'wrong start time' > "$RUNTIME/fixture.pid"
            ! managed_running fixture
            stop_managed fixture
            kill -0 "$$"
        ''')
