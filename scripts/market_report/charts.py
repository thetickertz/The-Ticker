"""Inline SVG charts in The Ticker's style. Colours are CSS variables so the page theme
(and print) controls them. Thin marks, hairline grid, labels in text tokens, no dual axes."""
from __future__ import annotations

from html import escape

from .util import fnum, fpct

FONT = "font-family:var(--mono);"


def _t(x, y, txt, size=11, anchor="start", cls="", fill="var(--muted)", weight=500):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}" style="{FONT}" class="{cls}">{escape(str(txt))}</text>')


def share_bars(items: list[tuple[str, float, str]], width=600, bar_h=18, gap=10, label_w=86, value_w=170) -> str:
    """Horizontal bars for a part-to-whole ranking. items: (label, pct, value_label).
    First bar in the accent hue, the rest in a lighter step; 'Others' in grey."""
    if not items:
        return ""
    n = len(items)
    top = 6
    h = top + n * (bar_h + gap)
    maxp = max(p for _, p, _ in items) or 1
    plot_w = width - label_w - value_w
    out = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" aria-label="Share of turnover by counter" '
           f'style="display:block;max-width:{width}px">']
    for i, (label, pct, vlabel) in enumerate(items):
        y = top + i * (bar_h + gap)
        w = max(2.0, plot_w * (pct / maxp))
        fill = "var(--neutral)" if label == "Others" else ("var(--s1)" if i == 0 else "var(--s1-soft)")
        out.append(_t(label_w - 10, y + bar_h * 0.72, label, 12, "end", fill="var(--ink)", weight=600))
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="0" fill="{fill}"/>')
        # 4px rounded data-end: overlay a rounded cap at the end of the bar
        out.append(f'<rect x="{label_w + w - min(8, w):.1f}" y="{y}" width="{min(8, w):.1f}" height="{bar_h}" rx="4" fill="{fill}"/>')
        out.append(_t(label_w + w + 8, y + bar_h * 0.72, f"{fnum(pct,1)}%  ·  {vlabel}", 11.5, "start", fill="var(--ink2)"))
    out.append("</svg>")
    return "".join(out)


def grouped_columns(groups: list[tuple[str, list[float | None]]], series: list[str], colors: list[str],
                    unit="%", width=360, height=230, ymax=100.0, aria="") -> str:
    """Grouped columns, one axis. groups: [(group label, [v_series0, v_series1...])]."""
    P = {"t": 22, "r": 10, "b": 30, "l": 36}
    pw, ph = width - P["l"] - P["r"], height - P["t"] - P["b"]
    ng, ns = len(groups), len(series)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" style="display:block;max-width:{width}px">']
    # grid
    steps = 4
    for k in range(steps + 1):
        v = ymax * k / steps
        y = P["t"] + ph * (1 - v / ymax)
        out.append(f'<line x1="{P["l"]}" x2="{width-P["r"]}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(_t(P["l"] - 6, y + 3.5, f"{v:.0f}{unit}", 10, "end"))
    slot = pw / ng
    bw = min(26.0, slot * 0.7 / ns)
    for gi, (glabel, vals) in enumerate(groups):
        gx = P["l"] + slot * gi + slot / 2
        total_w = bw * ns + 2 * (ns - 1)
        x0 = gx - total_w / 2
        for si, v in enumerate(vals):
            if v is None:
                continue
            x = x0 + si * (bw + 2)
            hgt = ph * (v / ymax)
            y = P["t"] + ph - hgt
            fill = colors[si % len(colors)]
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="0" fill="{fill}"/>')
            if hgt > 6:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{min(8,hgt):.1f}" rx="4" fill="{fill}"/>')
            out.append(_t(x + bw / 2, y - 5, f"{fnum(v,1)}{unit}", 10.5, "middle", fill="var(--ink2)"))
        out.append(_t(gx, height - 10, glabel, 11.5, "middle", fill="var(--ink)", weight=600))
    out.append("</svg>")
    return "".join(out)


def tenor_columns(by_term: list[dict], key: str, unit: str, dp: int, width=360, height=220, aria="") -> str:
    """One column per tenor for a single measure (WA price or WA yield). Tenors with no trades
    get an empty slot labelled 'no trades' so the x-axis stays comparable day to day."""
    P = {"t": 24, "r": 10, "b": 34, "l": 40}
    pw, ph = width - P["l"] - P["r"], height - P["t"] - P["b"]
    vals = [b.get(key) for b in by_term]
    present = [v for v in vals if v is not None]
    if not present:
        return f'<div class="empty">No bond trades today</div>'
    vmax = max(present)
    vmin = min(present)
    # zero-based axis for price and yield so bar length is honest
    lo, hi = 0.0, vmax * 1.15
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" style="display:block;max-width:{width}px">']
    steps = 4
    import math
    raw = hi / steps
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), raw)
    v = 0.0
    while v <= hi + 1e-9:
        y = P["t"] + ph * (1 - v / hi)
        out.append(f'<line x1="{P["l"]}" x2="{width-P["r"]}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(_t(P["l"] - 6, y + 3.5, fnum(v, 0 if step >= 1 else 1), 10, "end"))
        v += step
    n = len(by_term)
    slot = pw / n
    bw = min(24.0, slot * 0.55)
    for i, b in enumerate(by_term):
        x = P["l"] + slot * i + slot / 2
        val = b.get(key)
        if val is None:
            out.append(_t(x, P["t"] + ph - 6, "no", 9, "middle", fill="var(--muted)"))
            out.append(_t(x, P["t"] + ph + 4, "trades", 9, "middle", fill="var(--muted)"))
        else:
            hgt = ph * (val / hi)
            y = P["t"] + ph - hgt
            out.append(f'<rect x="{x-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="var(--s1)"/>')
            out.append(f'<rect x="{x-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{min(8,hgt):.1f}" rx="4" fill="var(--s1)"/>')
            out.append(_t(x, y - 6, f"{fnum(val,dp)}{unit}", 10.5, "middle", fill="var(--ink)", weight=600))
        out.append(_t(x, height - 12, f"{b['term']}y", 11, "middle", fill="var(--ink2)", weight=600))
    out.append(f'<line x1="{P["l"]}" x2="{width-P["r"]}" y1="{P["t"]+ph:.1f}" y2="{P["t"]+ph:.1f}" stroke="var(--border2)" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)


def sparkline(values: list[float | None], width=150, height=40, color="var(--s1)") -> str:
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    span = (hi - lo) or 1.0
    n = len(values)
    X = lambda i: 4 + (width - 8) * (i / max(1, n - 1))
    Y = lambda v: 4 + (height - 8) * (1 - (v - lo) / span)
    path = " ".join(f"{'M' if k == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for k, (i, v) in enumerate(pts))
    area = f"M{X(pts[0][0]):.1f},{height-4} " + " ".join(f"L{X(i):.1f},{Y(v):.1f}" for i, v in pts) + f" L{X(pts[-1][0]):.1f},{height-4} Z"
    li, lv = pts[-1]
    return (f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true" style="display:block">'
            f'<path d="{area}" fill="{color}" opacity="0.10"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{X(li):.1f}" cy="{Y(lv):.1f}" r="4" fill="{color}" stroke="var(--card)" stroke-width="2"/></svg>')


def legend(items: list[tuple[str, str]]) -> str:
    return '<div class="legend">' + "".join(
        f'<span class="li"><span class="key" style="background:{c}"></span>{escape(n)}</span>' for n, c in items) + "</div>"
