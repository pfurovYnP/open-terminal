import asyncio
import os

import pytest

from open_terminal.utils.runner import PtyRunner, _PTY_AVAILABLE


class MemoryLog:
    def __init__(self):
        self.records = []

    async def write(self, data: str) -> None:
        self.records.append(data)


def test_pty_runner_reads_without_default_executor(monkeypatch):
    if not _PTY_AVAILABLE:
        pytest.skip("Unix PTY support is not available on this platform")

    log = MemoryLog()
    runner = PtyRunner("printf quick-win", cwd=None, env=os.environ.copy())

    async def exercise_runner() -> None:
        loop = asyncio.get_running_loop()

        def fail_run_in_executor(*args, **kwargs):
            raise AssertionError("PTY output reader should not use the default executor")

        monkeypatch.setattr(loop, "run_in_executor", fail_run_in_executor)
        await runner.read_output(log)

    try:
        asyncio.run(exercise_runner())
        assert any("quick-win" in record for record in log.records)
    finally:
        runner._process.wait(timeout=5)
        runner.close()


def test_pty_runner_finishes_when_background_child_keeps_pty_open():
    if not _PTY_AVAILABLE:
        pytest.skip("Unix PTY support is not available on this platform")

    log = MemoryLog()
    runner = PtyRunner("sleep 30 & printf parent-done", cwd=None, env=os.environ.copy())

    async def exercise_runner() -> None:
        await asyncio.wait_for(runner.read_output(log), timeout=1.0)
        assert await runner.wait() == 0

    try:
        asyncio.run(exercise_runner())
        assert any("parent-done" in record for record in log.records)
    finally:
        runner.kill(force=True)
        runner.close()
