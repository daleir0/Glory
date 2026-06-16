"""Record a chart read: save the image, parse defensively, persist to the store."""

import time
from pathlib import Path

from glory_hype.chart.chartread import ChartRead, parse_chart_read
from glory_hype.chart.flags import divergence_flags

_DEFAULT_CHARTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "charts")


def _write_image(path: Path, image_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)


def _apply_flags(store, read: ChartRead) -> None:
    """Set data-integrity flags on the read by checking the chart's price against
    our live Hyperliquid mark. Catches misreads / wrong-instrument / stale charts."""
    ctx = store.latest_ctx()
    live_mark = ctx.get("mark_px") if ctx else None
    read_price = read.current_price
    if read_price is None and read.position:
        read_price = read.position.get("entry")
    read.flags = divergence_flags(read_price, live_mark)


def finalize_chart_read(store, ts: int, data: dict):
    """Finalize a pending chart read: parse the agent's extraction and update
    the existing row. Preserves the pending row's image_path if data omits it."""
    image_path = data.get("image_path")
    if image_path is None:
        for row in store.pending_chart_reads():
            if row["ts"] == ts:
                image_path = row["image_path"]
                break
    read = parse_chart_read(data, ts=ts, image_path=image_path)
    _apply_flags(store, read)
    store.finalize_chart_read(ts, read.to_dict())
    return read


def record_chart_read(store, data: dict, image_bytes: bytes | None = None,
                      charts_dir: str = _DEFAULT_CHARTS_DIR,
                      ts: int | None = None) -> ChartRead:
    if ts is None:
        ts = int(time.time() * 1000)
    image_path = None
    if image_bytes:
        path = Path(charts_dir) / f"hype-{ts}.png"
        try:
            _write_image(path, image_bytes)
            image_path = str(path)
        except Exception:
            image_path = None  # image is a bonus; the read is what matters
    read = parse_chart_read(data, ts=ts, image_path=image_path)
    _apply_flags(store, read)
    store.insert_chart_read(read.to_dict())
    return read
