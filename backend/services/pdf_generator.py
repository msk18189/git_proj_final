"""
PDF Report Generator — uses ReportLab + Matplotlib.
Generates a professional multi-page PDF directly from DB data,
no browser / Playwright needed.
"""

import io
import math
import struct
from datetime import datetime
from typing import Optional, List, Dict, Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Brand colours ─────────────────────────────────────────────────────────────
C_INDIGO   = colors.HexColor("#6366f1")
C_EMERALD  = colors.HexColor("#10b981")
C_AMBER    = colors.HexColor("#f59e0b")
C_ROSE     = colors.HexColor("#f43f5e")
C_SLATE900 = colors.HexColor("#0f172a")
C_SLATE700 = colors.HexColor("#334155")
C_SLATE400 = colors.HexColor("#94a3b8")
C_SLATE100 = colors.HexColor("#f1f5f9")
C_WHITE    = colors.white
PAGE_W, PAGE_H = A4


# ── Style helpers ─────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", fontSize=22, leading=26, fontName="Helvetica-Bold",
                              textColor=C_SLATE900, spaceAfter=4,
                              wordWrap='CJK'),
        "h2": ParagraphStyle("h2", fontSize=12, leading=15, fontName="Helvetica-Bold",
                              textColor=C_SLATE900, spaceAfter=6, spaceBefore=12,
                              wordWrap='CJK'),
        "h3": ParagraphStyle("h3", fontSize=10, leading=12, fontName="Helvetica-Bold",
                              textColor=C_SLATE700, spaceAfter=4,
                              wordWrap='CJK'),
        "label": ParagraphStyle("label", fontSize=7, leading=9, fontName="Helvetica-Bold",
                                textColor=C_SLATE400, spaceAfter=2,
                                wordWrap='CJK'),
        "value": ParagraphStyle("value", fontSize=18, leading=21, fontName="Helvetica-Bold",
                                textColor=C_SLATE900, wordWrap='CJK'),
        "value_red": ParagraphStyle("value_red", fontSize=18, leading=21, fontName="Helvetica-Bold",
                                    textColor=C_ROSE, wordWrap='CJK'),
        "body": ParagraphStyle("body", fontSize=9, leading=12, fontName="Helvetica",
                               textColor=C_SLATE700, spaceAfter=4,
                               wordWrap='CJK'),
        "caption": ParagraphStyle("caption", fontSize=7.5, leading=9.5, fontName="Helvetica",
                                  textColor=C_SLATE400, wordWrap='CJK'),
        "th": ParagraphStyle("th", fontSize=8, leading=10, fontName="Helvetica-Bold",
                             textColor=C_SLATE700, wordWrap='CJK'),
        "td": ParagraphStyle("td", fontSize=8, leading=10, fontName="Helvetica",
                             textColor=C_SLATE700, wordWrap='CJK'),
    }


def _header_footer(canvas, doc):
    """Draw brand header bar + page number on every page."""
    canvas.saveState()
    # Top bar
    canvas.setFillColor(C_INDIGO)
    canvas.rect(0, PAGE_H - 10 * mm, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(C_WHITE)
    canvas.drawString(15 * mm, PAGE_H - 6.5 * mm, "PRISM — GitHub Engineering Intelligence")
    ts = datetime.now().strftime("%d %b %Y  %H:%M")
    canvas.drawRightString(PAGE_W - 15 * mm, PAGE_H - 6.5 * mm, ts)
    # Bottom page number
    canvas.setFillColor(C_SLATE400)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W / 2, 8 * mm,
                             f"Page {doc.page}  ·  Confidential")
    canvas.restoreState()


# ── Chart helpers (matplotlib → in-memory PNG → RLImage) ─────────────────────

def _get_png_dimensions(png_bytes: bytes):
    """Read width and height from a PNG file's IHDR chunk."""
    try:
        # PNG IHDR starts at byte 16: 4-byte width, 4-byte height (big-endian)
        w, h = struct.unpack('>II', png_bytes[16:24])
        return w, h
    except Exception:
        return None, None


def _fig_to_image(fig, width_mm=170):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    w = width_mm * mm
    # Compute actual aspect ratio from the rendered PNG
    png_data = buf.getvalue()
    img_w, img_h = _get_png_dimensions(png_data)
    if img_w and img_h:
        aspect = img_h / img_w
    else:
        aspect = 0.50  # safe fallback
    buf.seek(0)
    return RLImage(buf, width=w, height=w * aspect)


def _chart_monthly_flow(flow_data):
    months = [d.get("month", "") for d in flow_data]
    opened = [d.get("created", 0) for d in flow_data]
    merged = [d.get("merged", 0) for d in flow_data]
    closed = [d.get("closed", 0) for d in flow_data]
    open_end = [d.get("open_at_end", 0) for d in flow_data]

    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor="#ffffff")
    ax.set_facecolor("#ffffff")
    x = range(len(months))
    w = 0.22
    
    # Colors: Created (blue #3b82f6), Merged (green #10b981), Closed (gray #94a3b8), Open end (orange #f59e0b)
    ax.bar([i - w for i in x], opened, width=w, label="Created", color="#3b82f6", alpha=0.9, edgecolor="none", zorder=3)
    ax.bar(list(x), merged, width=w, label="Merged", color="#10b981", alpha=0.9, edgecolor="none", zorder=3)
    ax.bar([i + w for i in x], closed, width=w, label="Closed (not merged)", color="#94a3b8", alpha=0.9, edgecolor="none", zorder=3)
    
    ax.plot(list(x), open_end, marker="o", color="#f59e0b", linewidth=2.5, markersize=6, label="Open at month end", zorder=4)
    
    ax.set_xticks(list(x))
    ax.set_xticklabels(months, rotation=0, fontsize=8, color="#475569")
    ax.tick_params(axis="y", labelsize=8, colors="#475569")
    
    # Light grid
    ax.grid(axis="y", linestyle="--", linewidth=0.5, color="#cbd5e1", alpha=0.7, zorder=0)
    
    # Hide top and right spines
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cbd5e1")
    
    # Legend at bottom
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4, frameon=False)
    ax.set_title("PRS CREATED • MERGED • CLOSED WITHOUT MERGE • OPEN AT END OF MONTH", fontsize=8.5, fontweight="bold", pad=12, loc="left", color="#475569")
    
    fig.tight_layout()
    return _fig_to_image(fig, 170)


def _chart_author_activity(contributors):
    top = contributors[:8]
    names = [c.get("username", "?") for c in top]
    opened = [c.get("total_prs", 0) for c in top]
    merged = [c.get("merged_prs", 0) for c in top]
    
    fig, ax = plt.subplots(figsize=(6, 4.5), facecolor="#ffffff")
    ax.set_facecolor("#ffffff")
    
    y = range(len(names))
    height = 0.3
    
    ax.barh([i + height/2 for i in y], opened, height=height, label="Opened", color="#3b82f6", alpha=0.9, zorder=3)
    ax.barh([i - height/2 for i in y], merged, height=height, label="Merged", color="#10b981", alpha=0.9, zorder=3)
    
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8, color="#475569")
    ax.tick_params(axis="x", labelsize=8, colors="#475569")
    
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cbd5e1")
    
    # Add count text to the right of the bars
    max_val = max(max(opened) if opened else 1, max(merged) if merged else 1)
    for i, (o, m) in enumerate(zip(opened, merged)):
        ax.text(max_val * 1.05, i, f"{o}/{m}", va="center", ha="left", fontsize=8, fontweight="bold", color="#475569")
        
    ax.set_xlim(0, max_val * 1.18)
    ax.grid(axis="x", linestyle="--", linewidth=0.5, color="#cbd5e1", alpha=0.7, zorder=0)
    ax.legend(fontsize=8, loc="lower right", frameon=False)
    ax.set_title("AUTHOR ACTIVITY — PRS OPENED / MERGED", fontsize=8.5, fontweight="bold", pad=12, loc="left", color="#475569")
    
    fig.tight_layout()
    return _fig_to_image(fig, 82)


def format_days_turnaround(days_val):
    if days_val is None:
        return "—", "#64748b"
    hours = days_val * 24
    if hours < 24:
        return f"{round(hours)}h", "#10b981"
    elif hours <= 48:
        return f"{round(days_val, 1)}d", "#f59e0b"
    else:
        return f"{round(days_val, 1)}d", "#f43f5e"


def _chart_review_turnaround(contributors):
    has_wait = [c for c in contributors if c.get("avg_wait_for_review") is not None]
    if not has_wait:
        has_wait = contributors[:8]
        
    top = has_wait[:8]
    names = [c.get("username", "?") for c in top]
    vals = [c.get("avg_wait_for_review") or 0.0 for c in top] # in days
    
    colors_list = []
    labels_list = []
    for v in vals:
        label, color = format_days_turnaround(v)
        colors_list.append(color)
        labels_list.append(label)
        
    fig, ax = plt.subplots(figsize=(6, 4.5), facecolor="#ffffff")
    ax.set_facecolor("#ffffff")
    
    y = range(len(names))
    height = 0.4
    
    ax.barh(y, vals, height=height, color=colors_list, alpha=0.9, zorder=3)
    
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8, color="#475569")
    ax.tick_params(axis="x", labelsize=8, colors="#475569")
    
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cbd5e1")
    
    # Add turnaround duration text on the right
    max_val = max(vals) if vals else 1.0
    for i, (v, lbl) in enumerate(zip(vals, labels_list)):
        ax.text(max_val * 1.05, i, lbl, va="center", ha="left", fontsize=8, fontweight="bold", color=colors_list[i])
        
    ax.set_xlim(0, max_val * 1.18)
    ax.grid(axis="x", linestyle="--", linewidth=0.5, color="#cbd5e1", alpha=0.7, zorder=0)
    
    ax.set_xlabel("Green <24h • Amber 24–48h • Red >48h", fontsize=7.5, color="#64748b", fontweight="bold", labelpad=8)
    ax.set_title("REVIEW TURNAROUND — AVG WAIT FOR FIRST REVIEW", fontsize=8.5, fontweight="bold", pad=12, loc="left", color="#475569")
    
    fig.tight_layout()
    return _fig_to_image(fig, 82)


# ── KPI card grid ─────────────────────────────────────────────────────────────

def _kpi_card(label, value, subtitle, alert, col_w, s):
    lbl = Paragraph(label.upper(), s["label"])
    val_style = s["value_red"] if alert else s["value"]
    val = Paragraph(value or "—", val_style)
    sub = Paragraph(subtitle or "", s["caption"])
    
    card_table = Table([[lbl], [Spacer(1, 1*mm)], [val], [Spacer(1, 1*mm)], [sub]], colWidths=[col_w - 6])
    card_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    
    outer = Table([[card_table]], colWidths=[col_w])
    outer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ("ROUNDEDCORNERS", [6]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return outer


def _kpi_table(kpi, repo, s):
    def _v(disp):
        if not disp:
            return "—"
        val = disp.get("value", "—")
        unit = disp.get("unit", "")
        return f"{val}{unit}"

    avg_ct = _v(kpi.get("avg_cycle_time_display"))
    med_ct = _v(kpi.get("median_cycle_time_display"))
    avg_wt = _v(kpi.get("avg_wait_for_review_display"))
    avg_rd = _v(kpi.get("avg_review_duration_display"))

    # 4 columns on page width
    col_w = (PAGE_W - 30 * mm - 12 * mm) / 4

    cards = [
        _kpi_card("OPEN PRS", str(kpi.get("open_prs", "—")), "all currently open", False, col_w, s),
        _kpi_card("STALE OPEN (>30D)", str(kpi.get("stale_prs", "—")), "need attention", (kpi.get("stale_prs", 0) or 0) > 5, col_w, s),
        _kpi_card("AVG CYCLE TIME", avg_ct, "open → merged", False, col_w, s),
        _kpi_card("MEDIAN CYCLE TIME", med_ct, "p50 of merged PRs", False, col_w, s),
        _kpi_card("AVG WAIT FOR REVIEW", avg_wt, "time to first review", False, col_w, s),
        _kpi_card("AVG REVIEW DURATION", avg_rd, "first → last review", False, col_w, s),
        _kpi_card("MERGE RATE", f"{kpi.get('merge_rate', 0)}%", "of closed PRs that merged", False, col_w, s),
        _kpi_card("AVG REVIEWS / PR", str(kpi.get("avg_reviews_per_pr", "—")), repo.full_name if repo else "", False, col_w, s),
    ]

    row1 = [cards[0], cards[1], cards[2], cards[3]]
    row2 = [cards[4], cards[5], cards[6], cards[7]]
    
    grid = Table([
        row1,
        [Spacer(1, 4*mm)] * 4,
        row2
    ], colWidths=[col_w + 4*mm] * 4)
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4*mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return grid


# ── Table helpers ─────────────────────────────────────────────────────────────

def _data_table(headers, rows, col_widths, s):
    th_row = [Paragraph(h, s["th"]) for h in headers]
    data = [th_row]
    for row in rows:
        data.append([Paragraph(str(c) if c is not None else "—", s["td"])
                     for c in row])
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), C_SLATE100),
        ("TEXTCOLOR",    (0, 0), (-1, 0), C_SLATE700),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("INNERGRID",    (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("BOX",          (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Main entry ────────────────────────────────────────────────────────────────

def generate_pdf_report(
    repo, kpi, flow, throughput, contributors, stale, slowest, oldest=None, risks=None
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"PRISM Report — {repo.full_name}",
        author="PRISM Analytics",
    )

    s = _styles()
    story = []

    # ── PAGE 1: Header + KPIs + Monthly Flow ──────────────────────────────────
    story.append(Paragraph("GitHub PR Metrics Dashboard", s["h1"]))
    story.append(Paragraph(
        f"<font color='#6366f1'>{repo.full_name}</font>  ·  "
        f"<font color='#94a3b8'>{repo.language or 'N/A'}</font>  ·  "
        f"⭐ {repo.stars or 0}",
        s["body"]
    ))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#e2e8f0"),
                             spaceAfter=6))

    story.append(Paragraph("SUMMARY", s["h2"]))
    if kpi:
        story.append(_kpi_table(kpi, repo, s))
    else:
        story.append(Paragraph("No KPI data available.", s["body"]))

    story.append(Spacer(1, 4 * mm))

    # Monthly Flow (Full Page Width)
    story.append(Paragraph("MONTHLY PR FLOW", s["h2"]))
    flow_list = flow if isinstance(flow, list) else []
    if flow_list:
        chart_flow = _chart_monthly_flow(flow_list)
        story.append(chart_flow)
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "<b>Open at month end (orange line)</b> = PRs created on or before the last day of the month "
            "that had not yet been closed or merged by that date. For the current month this equals the live open count.",
            s["caption"]
        ))
    else:
        story.append(Paragraph("No monthly flow data available.", s["body"]))

    story.append(PageBreak())

    # ── PAGE 2: Author Activity & Review Turnaround ───────────────────────────
    story.append(Paragraph("Developer Productivity & Responsiveness", s["h1"]))
    story.append(Spacer(1, 2 * mm))
    
    contrib_list = contributors if isinstance(contributors, list) else []
    if contrib_list:
        chart_author = _chart_author_activity(contrib_list)
        chart_review = _chart_review_turnaround(contrib_list)
        
        half_w = (PAGE_W - 30 * mm) / 2
        charts_row = Table([[chart_author, chart_review]], colWidths=[half_w, half_w])
        charts_row.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(charts_row)
    else:
        story.append(Paragraph("No contributor analytics available to draw charts.", s["body"]))
        
    story.append(Spacer(1, 4 * mm))

    # Contributors detailed table
    story.append(Paragraph("Top Contributors Performance", s["h2"]))
    if contrib_list:
        avail = PAGE_W - 30 * mm
        cw = [avail * 0.28, avail * 0.12, avail * 0.12, avail * 0.10, avail * 0.22, avail * 0.16]
        rows = []
        for c in contrib_list[:10]:
            ct = c.get("avg_cycle_time_display") or {}
            rows.append([
                c.get("username", "—"),
                str(c.get("total_prs", 0)),
                str(c.get("merged_prs", 0)),
                str(c.get("open_prs", 0)),
                f"{ct.get('value', '—')} {ct.get('unit', '')}",
                f"{c.get('merge_rate', 0) or 0}%",
            ])
        story.append(_data_table(
            ["Username", "Total PRs", "Merged", "Open", "Avg Cycle Time", "Merge Rate"],
            rows, cw, s
        ))
    else:
        story.append(Paragraph("No contributor data available.", s["body"]))

    story.append(PageBreak())

    # ── PAGE 3: ML PR Risks & Oldest Open PRs ─────────────────────────────────
    story.append(Paragraph("Risk & Backlog Management", s["h1"]))
    story.append(Spacer(1, 2 * mm))
    
    # ML PR Risk Panel Table
    story.append(Paragraph("PR Risk & Delay Predictions (ML Powered)", s["h2"]))
    risks_list = risks if isinstance(risks, list) else []
    if risks_list:
        avail = PAGE_W - 30 * mm
        cw_r = [avail * 0.40, avail * 0.16, avail * 0.14, avail * 0.16, avail * 0.14]
        rows_r = []
        for r in risks_list[:10]:
            title = (r.get("title") or "")[:80]
            prob = r.get("bottleneck_probability")
            prob_str = f"{prob}%" if prob is not None else "—"
            delay = r.get("predicted_delay_display") or "—"
            score = r.get("risk_score")
            score_str = f"{score}" if score is not None else "—"
            
            rows_r.append([
                f"#{r.get('number', '?')} {title}",
                r.get("author", "—"),
                score_str,
                prob_str,
                delay
            ])
            
        story.append(_data_table(
            ["PR Title", "Author", "Risk Score", "Bottleneck Prob.", "Est. Delay"],
            rows_r, cw_r, s
        ))
    else:
        story.append(Paragraph("No ML predictions stored yet. Run training or refresh ML from settings.", s["body"]))

    story.append(Spacer(1, 4 * mm))

    # Oldest Open PRs Table
    story.append(Paragraph("Oldest Open PRs (Backlog Review)", s["h2"]))
    oldest_list = oldest if isinstance(oldest, list) else []
    if oldest_list:
        avail = PAGE_W - 30 * mm
        cw_o = [avail * 0.46, avail * 0.12, avail * 0.22, avail * 0.20]
        rows_o = []
        for o in oldest_list[:10]:
            title = (o.get("title") or "")[:90]
            rows_o.append([
                f"#{o.get('number', '?')} {title}",
                f"{o.get('age_days', 0)}d",
                o.get("author", "—"),
                str(o.get("review_count", 0)),
            ])
        story.append(_data_table(
            ["PR Title", "Backlog Age", "Author", "Reviews Received"],
            rows_o, cw_o, s
        ))
    else:
        story.append(Paragraph("No open PR backlog found.", s["body"]))

    story.append(PageBreak())

    # ── PAGE 4: Bottleneck Analysis & Operational Insights ─────────────────────
    story.append(Paragraph("Bottleneck Analysis & Operational Insights", s["h1"]))
    story.append(Spacer(1, 2 * mm))

    # Slowest merged PRs (bottleneck analysis)
    story.append(Paragraph("Slowest Merged PRs (Cycle Time Bottlenecks)", s["h2"]))
    slow_list = slowest if isinstance(slowest, list) else []
    if slow_list:
        avail = PAGE_W - 30 * mm
        cw_sl = [avail * 0.46, avail * 0.18, avail * 0.22, avail * 0.14]
        rows_sl = []
        for sl in slow_list[:10]:
            ct = sl.get("cycle_time_display") or {}
            title = (sl.get("title") or "")[:100]
            rows_sl.append([
                f"#{sl.get('number', '?')} {title}",
                f"{ct.get('value', '—')} {ct.get('unit', '')}",
                sl.get("author", "—"),
                str(sl.get("review_count", 0)),
            ])
        story.append(_data_table(
            ["PR Title", "Cycle Time", "Author", "Reviews"],
            rows_sl, cw_sl, s
        ))
    else:
        story.append(Paragraph("No merged PR bottleneck data available.", s["body"]))

    story.append(Spacer(1, 4 * mm))

    # Stale PR Alerts
    story.append(Paragraph("Stale PR Alerts (Needs Attention)", s["h2"]))
    stale_list = stale if isinstance(stale, list) else []
    if stale_list:
        avail = PAGE_W - 30 * mm
        cw_s = [avail * 0.46, avail * 0.12, avail * 0.22, avail * 0.20]
        rows_s = []
        for s_ in stale_list[:10]:
            title = (s_.get("title") or "")[:90]
            rows_s.append([
                f"#{s_.get('number', '?')} {title}",
                f"{s_.get('age_days', 0)}d",
                s_.get("author", "—"),
                "⚠ Stale" if s_.get("severity") == "high" else "Medium Alert",
            ])
        story.append(_data_table(
            ["PR Title", "Age", "Author", "Alert Severity"],
            rows_s, cw_s, s
        ))
    else:
        story.append(Paragraph("No stale PRs detected! 🎉", s["body"]))

    story.append(Spacer(1, 4 * mm))

    # Operational Insights Table
    story.append(Paragraph("Operational Assessment", s["h2"]))
    if kpi:
        avg_ct  = kpi.get("avg_cycle_time", 0) or 0
        merge_r = kpi.get("merge_rate", 0) or 0
        stale_c = len(stale_list)
        insights = [
            ("Cycle Time Health",
             kpi.get("avg_cycle_time_display", {}).get("value", "N/A"),
             avg_ct < 3, # Less than 3 days
             "Cycle time is within healthy limits." if avg_ct < 3
             else "Elevated cycle times — review bottleneck PRs."),
            ("Merge Efficiency",
             f"{merge_r:.0f}%",
             merge_r > 75,
             "Strong merge rate indicates high quality submissions." if merge_r > 75
             else "Low merge rate — high PR churn or abandoned work."),
            ("Stale Accumulation",
             f"{stale_c} PRs",
             stale_c < 5,
             "Minimal stale PRs in the backlog." if stale_c < 5
             else "High stale volume — backlog grooming needed."),
        ]
        ins_data = [["Metric", "Value", "Status", "Finding / Action"]]
        for title_i, metric, good, desc in insights:
            ins_data.append([
                title_i, metric,
                "✓ Good" if good else "⚠ Needs Attention",
                desc,
            ])
        avail = PAGE_W - 30 * mm
        ins_tbl = Table(ins_data, colWidths=[avail * 0.24, avail * 0.14, avail * 0.22, avail * 0.40])
        ins_tbl.setStyle(TableStyle([
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("BACKGROUND",   (0, 0), (-1, 0), C_SLATE100),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f8fafc")]),
            ("INNERGRID",    (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("BOX",          (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(ins_tbl)
    else:
        story.append(Paragraph("Insufficient data for insights.", s["body"]))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Generated by PRISM — GitHub Engineering Intelligence Platform. "
        "This report is confidential and intended for engineering leadership only.",
        s["caption"]
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
