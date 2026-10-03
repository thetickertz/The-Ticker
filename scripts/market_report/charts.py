"""Inline SVG charts in The Ticker's style. Colours are CSS variables so the page theme
(and print) controls them. Thin marks, hairline grid, labels in text tokens, no dual axes."""
from __future__ import annotations

from html import escape

from .util import fnum, fpct

FONT = "font-family:var(--mono);"


def _t(x, y, txt, size=11, anchor="start", cls="", fill="var(--muted)", weight=500):
    c = f' class="{cls}"' if cls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}" style="{FONT}"{c}>{escape(str(txt))}</text>')


def _title(aria: str, desc: str) -> str:
    return f"<title>{escape(aria)}</title><desc>{escape(desc)}</desc>"


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
    desc = "; ".join(f"{g}: " + ", ".join(f"{s_} {fnum(v,1)}{unit}" for s_, v in zip(series, vals) if v is not None) for g, vals in groups)
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" style="display:block;max-width:{width}px">',
           _title(aria, desc)]
    # grid
    steps = 4
    for k in range(steps + 1):
        v = ymax * k / steps
        y = P["t"] + ph * (1 - v / ymax)
        out.append(f'<line x1="{P["l"]}" x2="{width-P["r"]}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(_t(P["l"] - 6, y + 3.5, f"{v:.0f}{unit}", 10, "end"))
    slot = pw / ng
    gap = 12  # wide enough that two value labels never collide
    bw = min(26.0, (slot * 0.7 - gap * (ns - 1)) / ns)
    for gi, (glabel, vals) in enumerate(groups):
        gx = P["l"] + slot * gi + slot / 2
        total_w = bw * ns + gap * (ns - 1)
        x0 = gx - total_w / 2
        for si, v in enumerate(vals):
            if v is None:
                continue
            x = x0 + si * (bw + gap)
            hgt = ph * (v / ymax)
            y = P["t"] + ph - hgt
            fill = colors[si % len(colors)]
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" rx="0" fill="{fill}"><title>{escape(glabel)} · {escape(series[si])}: {fnum(v,1)}{unit}</title></rect>')
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
    present = [v for v in vals if v]  # 0.0 is 'no trade' for a price or a yield
    if not present:
        return '<div class="empty">No bond trades in this session</div>'
    vmax = max(present)
    # zero-based axis for price and yield so bar length is honest
    lo, hi = 0.0, max(vmax, 1e-9) * 1.15
    desc = ", ".join(f"{b['term']}-year {fnum(b.get(key), dp)}{unit}" for b in by_term if b.get(key))
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" style="display:block;max-width:{width}px">',
           _title(aria, desc)]
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
        val = b.get(key) or None
        if val is None:
            out.append(_t(x, P["t"] + ph - 15, "no", 9, "middle", fill="var(--muted)"))
            out.append(_t(x, P["t"] + ph - 5, "trades", 9, "middle", fill="var(--muted)"))
        else:
            hgt = ph * (val / hi)
            y = P["t"] + ph - hgt
            out.append(f'<rect x="{x-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="var(--s1)"><title>{b["term"]}-year: {fnum(val,dp)}{unit} · {fnum(b.get("deals"))} deals · TZS {fnum(b.get("turnover_mln"),1)} m</title></rect>')
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


# ───────────────────────── time-series charts ─────────────────────────
import json as _json
import math as _math


def _ticks(lo, hi, n=4):
    """Clean axis steps (1/2/2.5/5 × 10^k) covering lo..hi."""
    raw = (hi - lo) / n if hi > lo else 1.0
    mag = 10 ** _math.floor(_math.log10(raw)) if raw > 0 else 1
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), raw)
    v = _math.floor(lo / step) * step
    out = []
    while v <= hi + 1e-9:
        out.append(v)
        v += step
    return out, step


def _fmt_axis(v, dp):
    return fnum(v, dp)


def line_chart(x_labels: list[str], series: list[dict], width=760, height=300, unit="", dp=1,
               aria="", x_fmt=None, rebase=False, chart_id="") -> str:
    """Multi-series line chart with hairline grid, end markers and end labels. series:
    [{"name", "color", "values": [v or None per x]}]. The data rides along in data-* attributes so
    the page's tooltip script can show the exact values on hover / keyboard."""
    S = [s for s in series if any(v is not None for v in s["values"])]
    if not S or len(x_labels) < 2:
        return '<div class="empty">Not enough history yet — the trend appears after a few sessions.</div>'
    if rebase:
        for s in S:
            base = next((v for v in s["values"] if v), None)
            s["values"] = [(v / base * 100.0) if (v is not None and base) else None for v in s["values"]]
    P = {"t": 16, "r": 64, "b": 32, "l": 54}
    pw, ph = width - P["l"] - P["r"], height - P["t"] - P["b"]
    allv = [v for s in S for v in s["values"] if v is not None]
    lo, hi = min(allv), max(allv)
    pad = (hi - lo) * 0.12 or (abs(hi) * 0.02 or 1.0)
    lo, hi = lo - pad, hi + pad
    ticks, _ = _ticks(lo, hi)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
    n = len(x_labels)
    X = lambda i: P["l"] + pw * (i / (n - 1))
    Y = lambda v: P["t"] + ph * (1 - (v - lo) / (hi - lo))
    desc = "; ".join(f"{s['name']}: latest {fnum(next((v for v in reversed(s['values']) if v is not None), None), dp)}{unit}" for s in S)
    data = {"x": x_labels, "series": [{"name": s["name"], "color": s["color"], "values": [None if v is None else round(v, 4) for v in s["values"]]} for s in S],
            "plot": [P["l"], P["t"], pw, ph], "unit": unit, "dp": dp, "lo": lo, "hi": hi}
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" tabindex="0" class="tschart" '
           f'data-chart=\'{escape(_json.dumps(data), quote=True)}\' style="display:block">', _title(aria, desc)]
    for v in ticks:
        if v < lo or v > hi:
            continue
        y = Y(v)
        out.append(f'<line x1="{P["l"]}" x2="{width - P["r"]}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(_t(P["l"] - 8, y + 3.5, f"{_fmt_axis(v, dp)}{unit if unit == '%' else ''}", 10.5, "end"))
    every = max(1, _math.ceil(n / 6))
    for i in range(n):
        if i % every and i != n - 1:
            continue
        if i != n - 1 and every > 1 and n - 1 - i < every * 0.6:
            continue
        anchor = "end" if X(i) > width - P["r"] - 30 else "start" if X(i) < P["l"] + 24 else "middle"
        out.append(_t(X(i), height - 10, x_fmt(x_labels[i]) if x_fmt else x_labels[i], 10.5, anchor))
    if len(S) == 1:  # single series: 10% area wash
        pts = [(i, v) for i, v in enumerate(S[0]["values"]) if v is not None]
        area = f"M{X(pts[0][0]):.1f},{P['t'] + ph:.1f} " + " ".join(f"L{X(i):.1f},{Y(v):.1f}" for i, v in pts) + f" L{X(pts[-1][0]):.1f},{P['t'] + ph:.1f} Z"
        out.append(f'<path d="{area}" fill="{S[0]["color"]}" opacity="0.10"/>')
    end_labels = []
    for s in S:
        pts = [(i, v) for i, v in enumerate(s["values"]) if v is not None]
        path = " ".join(f"{'M' if k == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for k, (i, v) in enumerate(pts))
        out.append(f'<path d="{path}" fill="none" stroke="{s["color"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        li, lv = pts[-1]
        out.append(f'<circle cx="{X(li):.1f}" cy="{Y(lv):.1f}" r="4" fill="{s["color"]}" stroke="var(--card)" stroke-width="2"/>')
        end_labels.append((Y(lv), s["name"], lv, s["color"]))
    # end labels: nudge apart if they collide
    end_labels.sort()
    placed = []
    for y, name, v, color in end_labels:
        if placed and y - placed[-1] < 14:
            y = placed[-1] + 14
        placed.append(y)
        out.append(f'<rect x="{width - P["r"] + 8}" y="{y - 5:.1f}" width="8" height="3" rx="1.5" fill="{color}"/>')
        out.append(_t(width - P["r"] + 20, y + 3.5, f"{fnum(v, dp)}{unit}", 11, "start", fill="var(--ink)", weight=600))
    out.append(f'<line class="xh" x1="0" x2="0" y1="{P["t"]}" y2="{P["t"] + ph}" stroke="var(--border2)" stroke-width="1" opacity="0"/>')
    out.append("</svg>")
    return "".join(out)


def column_series(x_labels: list[str], values: list[float | None], width=760, height=230, unit="", dp=2,
                  scale=1.0, aria="", x_fmt=None, value_fmt=None, chart_id="") -> str:
    """One column per session; the latest column in the accent hue, the rest in a lighter step."""
    vals = [None if v is None else v / scale for v in values]
    present = [v for v in vals if v is not None]
    if len(present) < 2:
        return '<div class="empty">Not enough history yet — the trend appears after a few sessions.</div>'
    P = {"t": 22, "r": 14, "b": 32, "l": 54}
    pw, ph = width - P["l"] - P["r"], height - P["t"] - P["b"]
    hi = max(present) * 1.12 or 1.0
    ticks, _ = _ticks(0, hi)
    hi = max(hi, ticks[-1])
    n = len(vals)
    slot = pw / n
    bw = min(24.0, slot * 0.62)
    X = lambda i: P["l"] + slot * i + slot / 2
    Y = lambda v: P["t"] + ph * (1 - v / hi)
    last_i = max(i for i, v in enumerate(vals) if v is not None)
    desc = f"latest {value_fmt(present[-1]) if value_fmt else fnum(present[-1], dp)}; average {value_fmt(sum(present)/len(present)) if value_fmt else fnum(sum(present)/len(present), dp)}"
    data = {"x": x_labels, "series": [{"name": aria or "value", "color": "var(--s1)", "values": [None if v is None else round(v, 4) for v in vals]}],
            "plot": [P["l"], P["t"], pw, ph], "unit": unit, "dp": dp, "lo": 0, "hi": hi, "columns": True}
    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{escape(aria)}" tabindex="0" class="tschart" '
           f'data-chart=\'{escape(_json.dumps(data), quote=True)}\' style="display:block">', _title(aria, desc)]
    for v in ticks:
        if v > hi:
            continue
        y = Y(v)
        out.append(f'<line x1="{P["l"]}" x2="{width - P["r"]}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(_t(P["l"] - 8, y + 3.5, _fmt_axis(v, 0 if v >= 10 or v == 0 else dp), 10.5, "end"))
    every = max(1, _math.ceil(n / 6))
    for i in range(n):
        if i % every and i != n - 1:
            continue
        if i != n - 1 and every > 1 and n - 1 - i < every * 0.6:
            continue
        anchor = "end" if X(i) > width - P["r"] - 30 else "start" if X(i) < P["l"] + 24 else "middle"
        out.append(_t(X(i), height - 10, x_fmt(x_labels[i]) if x_fmt else x_labels[i], 10.5, anchor))
    avg = sum(present) / len(present)
    out.append(f'<line x1="{P["l"]}" x2="{width - P["r"]}" y1="{Y(avg):.1f}" y2="{Y(avg):.1f}" stroke="var(--s2)" stroke-width="1.5" stroke-dasharray="3 4"/>')
    out.append(_t(P["l"] + 4, Y(avg) - 5, f"30-session average {value_fmt(avg) if value_fmt else fnum(avg, dp)}", 10, "start", fill="var(--ink2)"))
    for i, v in enumerate(vals):
        if v is None:
            continue
        h = max(1.5, ph * v / hi)
        y = P["t"] + ph - h
        fill = "var(--s1)" if i == last_i else "var(--s1-soft)"
        out.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{fill}"><title>{escape(x_labels[i])}: {escape(value_fmt(v) if value_fmt else fnum(v, dp))}</title></rect>')
        if h > 8:
            out.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="8" rx="4" fill="{fill}"/>')
    lv = vals[last_i]
    out.append(_t(X(last_i), Y(lv) - 7, value_fmt(lv) if value_fmt else fnum(lv, dp), 10.5, "end" if X(last_i) > width - P["r"] - 40 else "middle", fill="var(--ink)", weight=600))
    out.append(f'<line x1="{P["l"]}" x2="{width - P["r"]}" y1="{P["t"] + ph:.1f}" y2="{P["t"] + ph:.1f}" stroke="var(--border2)" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)
