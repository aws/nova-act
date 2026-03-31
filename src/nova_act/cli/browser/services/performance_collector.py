# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Performance metrics collection via browser Performance API."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from playwright.sync_api import Page


class NavigationTiming(TypedDict, total=False):
    requestStart: float
    responseStart: float
    domInteractive: float
    domComplete: float
    loadEventEnd: float


class ResourceTiming(TypedDict, total=False):
    name: str
    duration: float
    transferSize: int


class PaintTiming(TypedDict):
    name: str
    startTime: float


class MemoryInfo(TypedDict):
    usedJSHeapSize: int
    totalJSHeapSize: int
    jsHeapSizeLimit: int


class VitalsInfo(TypedDict):
    lcp: float | None
    cls: float


class PerfData(TypedDict):
    navigation: NavigationTiming | None
    resources: list[ResourceTiming]
    paint: list[PaintTiming]
    memory: MemoryInfo | None
    vitals: NotRequired[VitalsInfo]


# JavaScript to collect Navigation Timing, Resource Timing, Paint Timing, and Memory
PERF_COLLECT_JS = """
() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const resources = performance.getEntriesByType('resource');
    const paint = performance.getEntriesByType('paint');
    const memory = performance.memory ? {
        usedJSHeapSize: performance.memory.usedJSHeapSize,
        totalJSHeapSize: performance.memory.totalJSHeapSize,
        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
    } : null;
    return {
        navigation: nav ? nav.toJSON() : null,
        resources: resources.map(r => r.toJSON()),
        paint: paint.map(p => p.toJSON()),
        memory: memory,
    };
}
"""

# JavaScript to collect Core Web Vitals (LCP, CLS) via PerformanceObserver with buffered:true
VITALS_COLLECT_JS = """
() => new Promise((resolve) => {
    const vitals = { lcp: null, cls: 0 };
    try {
        new PerformanceObserver((list) => {
            const entries = list.getEntries();
            if (entries.length > 0) {
                vitals.lcp = entries[entries.length - 1].startTime;
            }
        }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {}
    try {
        new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) vitals.cls += entry.value;
            }
        }).observe({ type: 'layout-shift', buffered: true });
    } catch (e) {}
    setTimeout(() => resolve(vitals), 100);
})
"""


class PerformanceCollector:
    """Collects performance metrics from a browser page via Performance API."""

    def __init__(self, page: Page) -> None:
        self._page = page

    def _collect_perf(self) -> PerfData:
        """Execute PERF_COLLECT_JS once and return the result."""
        return self._page.evaluate(PERF_COLLECT_JS)  # type: ignore[no-any-return]

    def collect_all(self) -> PerfData:
        """Collect all available performance metrics."""
        base = self._collect_perf()
        base["vitals"] = self._page.evaluate(VITALS_COLLECT_JS)
        return base

    def collect_navigation(self) -> NavigationTiming | None:
        """Collect navigation timing metrics."""
        return self._collect_perf()["navigation"]

    def collect_resources(self) -> list[ResourceTiming]:
        """Collect resource timing entries."""
        return self._collect_perf()["resources"]

    def collect_vitals(self) -> VitalsInfo:
        """Collect Core Web Vitals (LCP, CLS)."""
        return self._page.evaluate(VITALS_COLLECT_JS)  # type: ignore[no-any-return]

    def collect_memory(self) -> MemoryInfo | None:
        """Collect memory usage (Chrome-only)."""
        return self._collect_perf()["memory"]


def format_navigation(nav: NavigationTiming | None) -> list[str]:
    """Format navigation timing as human-readable lines."""
    if not nav:
        return ["  (no navigation data)"]
    lines: list[str] = []
    ttfb = nav.get("responseStart", 0) - nav.get("requestStart", 0)
    dom_interactive = nav.get("domInteractive", 0)
    dom_complete = nav.get("domComplete", 0)
    load_event = nav.get("loadEventEnd", 0)
    lines.append(f"  TTFB ................ {ttfb:.0f} ms")
    lines.append(f"  DOM Interactive ..... {dom_interactive:.0f} ms")
    lines.append(f"  DOM Complete ........ {dom_complete:.0f} ms")
    lines.append(f"  Page Load ........... {load_event:.0f} ms")
    return lines


def format_resources(resources: list[ResourceTiming]) -> list[str]:
    """Format resource timing summary as human-readable lines."""
    if not resources:
        return ["  (no resources)"]
    total_size = sum(r.get("transferSize", 0) for r in resources)
    sorted_by_duration = sorted(resources, key=lambda r: r.get("duration", 0), reverse=True)
    top5 = sorted_by_duration[:5]
    lines = [f"  Resources: {len(resources)} loaded ({_format_bytes(total_size)} total)"]
    if top5:
        slowest = ", ".join(f"{_short_url(r.get('name', '?'))} ({r.get('duration', 0):.0f}ms)" for r in top5)
        lines.append(f"  Slowest: {slowest}")
    return lines


def format_vitals(vitals: VitalsInfo) -> list[str]:
    """Format Core Web Vitals as human-readable lines."""
    lines: list[str] = []
    lcp = vitals.get("lcp")
    cls_val = vitals.get("cls", 0)
    lcp_str = f"{lcp:.0f} ms" if lcp is not None else "N/A"
    lines.append(f"  LCP ................. {lcp_str}")
    lines.append(f"  CLS ................. {cls_val:.3f}")
    return lines


def format_memory(memory: MemoryInfo | None) -> list[str]:
    """Format memory usage as human-readable lines."""
    if not memory:
        return ["  (not available)"]
    used = memory.get("usedJSHeapSize", 0)
    total = memory.get("totalJSHeapSize", 0)
    return [f"  JS Heap Used ........ {_format_bytes(used)} / {_format_bytes(total)}"]


def format_paint(paint: list[PaintTiming]) -> list[str]:
    """Format paint timing as human-readable lines."""
    if not paint:
        return ["  (no paint data)"]
    lines: list[str] = []
    for entry in paint:
        name = entry.get("name", "unknown")
        start = entry.get("startTime", 0)
        label = (
            "First Paint"
            if name == "first-paint"
            else "First Contentful Paint" if name == "first-contentful-paint" else name
        )
        lines.append(f"  {label} .. {start:.0f} ms")
    return lines


def _format_bytes(n: int | float) -> str:
    """Format byte count as human-readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _short_url(url: str) -> str:
    """Extract path from URL for display."""
    if "/" in url:
        parts = url.split("/")
        return "/" + parts[-1] if parts[-1] else url
    return url
