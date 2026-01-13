import asyncio
import time
from typing import Callable, Optional

try:
    import psutil
except Exception:
    psutil = None


class SquadManager:
    def __init__(
        self,
        set_capacity_cb: Callable[[int], None],
        min_capacity: int = 1,
        max_capacity: int = 4,
        check_interval: float = 2.0,
        idle_threshold_percent: float = 30.0,
        scale_up_step: int = 1,
        scale_down_step: int = 1,
        hysteresis_seconds: float = 5.0,
    ):
        self.set_capacity_cb = set_capacity_cb
        self.min_capacity = max(1, int(min_capacity))
        self.max_capacity = max(self.min_capacity, int(max_capacity))
        self.check_interval = check_interval
        self.idle_threshold_percent = idle_threshold_percent
        self.scale_up_step = max(1, int(scale_up_step))
        self.scale_down_step = max(1, int(scale_down_step))
        self.hysteresis_seconds = hysteresis_seconds

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_change = 0.0
        self._current_capacity = self.min_capacity

    async def start(self):
        if not psutil:
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self):
        while self._running:
            try:
                # psutil.cpu_percent with interval=None returns last interval non-blocking
                usage = psutil.cpu_percent(interval=None)
                idle = max(0.0, 100.0 - usage)
                target = self._capacity_from_idle(idle)
                await self._maybe_apply(target, idle)
            except Exception:
                pass
            await asyncio.sleep(self.check_interval)

    def _capacity_from_idle(self, idle_percent: float) -> int:
        # Map idle percent linearly between min and max
        span = self.max_capacity - self.min_capacity
        if span <= 0:
            return self.min_capacity
        ratio = min(1.0, max(0.0, idle_percent / 100.0))
        target = int(self.min_capacity + round(ratio * span))
        return max(self.min_capacity, min(self.max_capacity, target))

    async def _maybe_apply(self, target: int, idle_percent: float):
        now = time.time()
        if target == self._current_capacity:
            return
        # hysteresis: avoid flapping
        if now - self._last_change < self.hysteresis_seconds:
            return

        self._last_change = now
        self._current_capacity = target

        if asyncio.iscoroutinefunction(self.set_capacity_cb):
            await self.set_capacity_cb(target)
        else:
            # run in loop executor to avoid blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: self.set_capacity_cb(target))

    def get_current_capacity(self) -> int:
        return self._current_capacity
