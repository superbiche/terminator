#!/usr/bin/env python
# Terminator by Chris Jones <cmsj@tenshu.net>
# GPL v2 only
"""test_tab_close_confirm.py - tests for running-session detection used by
the forced tab-close confirmation."""

import os
import pty
import signal
import time

import pytest

from terminatorlib.util import has_foreground_job


def wait_for_condition(predicate, timeout=5.0, interval=0.1):
    """Poll predicate until it holds or the timeout elapses"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestHasForegroundJob(object):
    def test_self_process_reports_idle(self):
        # The test runner either has no controlling tty or is itself the
        # foreground job of its shell - never a foreign foreground job.
        assert has_foreground_job(os.getpid()) is False

    def test_dead_pid_reports_idle(self):
        assert has_foreground_job(999999) is False

    def test_none_pid_reports_idle(self):
        assert has_foreground_job(None) is False

    def test_zero_and_negative_pids_report_idle(self):
        assert has_foreground_job(0) is False
        assert has_foreground_job(-1) is False

    def test_idle_shell_reports_no_foreground_job(self):
        pid, fd = pty.fork()
        if pid == 0:  # pylint: disable=W0125
            os.execvp('bash', ['bash', '--noprofile', '--norc', '-i'])
        try:
            assert wait_for_condition(
                lambda: not has_foreground_job(pid), timeout=5.0)
        finally:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            os.close(fd)

    def test_running_command_reports_foreground_job(self):
        pid, fd = pty.fork()
        if pid == 0:  # pylint: disable=W0125
            os.execvp('bash', ['bash', '--noprofile', '--norc', '-i'])
        try:
            # Wait for bash to settle at its prompt first, so the transition
            # we assert on is the job starting, not the shell spawning.
            assert wait_for_condition(
                lambda: not has_foreground_job(pid), timeout=5.0)
            os.write(fd, b'sleep 30\n')
            assert wait_for_condition(
                lambda: has_foreground_job(pid), timeout=5.0)
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            os.waitpid(pid, 0)
            os.close(fd)
