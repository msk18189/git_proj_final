"""
PDF Report Generator — uses ReportLab + Matplotlib.
Generates a professional multi-page PDF directly from DB data,
no browser / Playwright needed.
"""

import io
import math
import struct
import html
from datetime import datetime
from typing import Optional, List, Dict, Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether, Flowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Brand colours ─────────────────────────────────────────────────────────────
C_NAVY      = colors.HexColor("#0b2f4a")
C_BLUE      = colors.HexColor("#1f6f9f")
C_BLUE100   = colors.HexColor("#e8f3fb")
C_BLUE050   = colors.HexColor("#f5fbff")
C_GREEN     = colors.HexColor("#0f766e")
C_AMBER     = colors.HexColor("#b45309")
C_RED       = colors.HexColor("#b91c1c")
C_GRAY900   = colors.HexColor("#111827")
C_GRAY700   = colors.HexColor("#374151")
C_GRAY500   = colors.HexColor("#6b7280")
C_GRAY300   = colors.HexColor("#d1d5db")
C_GRAY200   = colors.HexColor("#e5e7eb")
C_GRAY100   = colors.HexColor("#f3f4f6")
C_WHITE    = colors.white
PAGE_W, PAGE_H = A4


# ── Style helpers ─────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", fontSize=22, leading=26, fontName="Helvetica-Bold",
                              textColor=C_NAVY, spaceAfter=4,
                              wordWrap='CJK'),
        "h2": ParagraphStyle("h2", fontSize=12, leading=15, fontName="Helvetica-Bold",
                              textColor=C_NAVY, spaceAfter=6, spaceBefore=12,
                              wordWrap='CJK'),
        "h3": ParagraphStyle("h3", fontSize=10, leading=12, fontName="Helvetica-Bold",
                              textColor=C_GRAY700, spaceAfter=4,
                              wordWrap='CJK'),
        "label": ParagraphStyle("label", fontSize=7, leading=9, fontName="Helvetica-Bold",
                                textColor=C_GRAY500, spaceAfter=2,
                                wordWrap='CJK'),
        "value": ParagraphStyle("value", fontSize=18, leading=21, fontName="Helvetica-Bold",
                                textColor=C_GRAY900, wordWrap='CJK'),
        "value_red": ParagraphStyle("value_red", fontSize=18, leading=21, fontName="Helvetica-Bold",
                                    textColor=C_RED, wordWrap='CJK'),
        "body": ParagraphStyle("body", fontSize=9, leading=12, fontName="Helvetica",
                               textColor=C_GRAY700, spaceAfter=4,
                               wordWrap='CJK'),
        "caption": ParagraphStyle("caption", fontSize=7.5, leading=9.5, fontName="Helvetica",
                                  textColor=C_GRAY500, wordWrap='CJK'),
        "th": ParagraphStyle("th", fontSize=8, leading=10, fontName="Helvetica-Bold",
                             textColor=C_NAVY, wordWrap='CJK'),
        "td": ParagraphStyle("td", fontSize=8, leading=10, fontName="Helvetica",
                             textColor=C_GRAY700, wordWrap='CJK'),
    }


def _header_footer(canvas, doc):
    """Draw brand header bar + page number on every page."""
    canvas.saveState()
    # Top bar
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, PAGE_H - 10 * mm, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(C_BLUE)
    canvas.rect(0, PAGE_H - 10 * mm, 44 * mm, 10 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(C_WHITE)
    canvas.drawString(15 * mm, PAGE_H - 6.5 * mm, "PRISM | Engineering Intelligence Report")
    ts = datetime.now().strftime("%d %b %Y  %H:%M")
    canvas.drawRightString(PAGE_W - 15 * mm, PAGE_H - 6.5 * mm, ts)
    # Bottom page number
    canvas.setFillColor(C_GRAY500)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W / 2, 8 * mm,
                             f"Page {doc.page} | Confidential")
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
    
    # Client-report chart colors: blue, teal, neutral gray, amber.
    ax.bar([i - w for i in x], opened, width=w, label="Created", color="#1f6f9f", alpha=0.92, edgecolor="none", zorder=3)
    ax.bar(list(x), merged, width=w, label="Merged", color="#0f766e", alpha=0.92, edgecolor="none", zorder=3)
    ax.bar([i + w for i in x], closed, width=w, label="Closed (not merged)", color="#9ca3af", alpha=0.92, edgecolor="none", zorder=3)
    
    ax.plot(list(x), open_end, marker="o", color="#b45309", linewidth=2.2, markersize=5, label="Open at month end", zorder=4)
    
    ax.set_xticks(list(x))
    ax.set_xticklabels(months, rotation=0, fontsize=8, color="#475569")
    ax.tick_params(axis="y", labelsize=8, colors="#475569")
    
    # Light grid
    ax.grid(axis="y", linestyle="-", linewidth=0.45, color="#e5e7eb", alpha=1, zorder=0)
    
    # Hide top and right spines
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#d1d5db")
    
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
    
    ax.barh([i + height/2 for i in y], opened, height=height, label="Opened", color="#1f6f9f", alpha=0.92, zorder=3)
    ax.barh([i - height/2 for i in y], merged, height=height, label="Merged", color="#0f766e", alpha=0.92, zorder=3)
    
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8, color="#475569")
    ax.tick_params(axis="x", labelsize=8, colors="#475569")
    
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#d1d5db")
    
    # Add count text to the right of the bars
    max_val = max(max(opened) if opened else 1, max(merged) if merged else 1)
    for i, (o, m) in enumerate(zip(opened, merged)):
        ax.text(max_val * 1.05, i, f"{o}/{m}", va="center", ha="left", fontsize=8, fontweight="bold", color="#475569")
        
    ax.set_xlim(0, max_val * 1.18)
    ax.grid(axis="x", linestyle="-", linewidth=0.45, color="#e5e7eb", alpha=1, zorder=0)
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
    ax.spines[["left", "bottom"]].set_color("#d1d5db")
    
    # Add turnaround duration text on the right
    max_val = max(vals) if vals else 1.0
    for i, (v, lbl) in enumerate(zip(vals, labels_list)):
        ax.text(max_val * 1.05, i, lbl, va="center", ha="left", fontsize=8, fontweight="bold", color=colors_list[i])
        
    ax.set_xlim(0, max_val * 1.18)
    ax.grid(axis="x", linestyle="-", linewidth=0.45, color="#e5e7eb", alpha=1, zorder=0)
    
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
        ("BOX", (0, 0), (-1, -1), 0.7, C_GRAY300),
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
    th_row = [Paragraph(html.escape(str(h)), s["th"]) for h in headers]
    data = [th_row]
    for row in rows:
        data.append([Paragraph(str(c) if c is not None else "—", s["td"])
                     for c in row])
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), C_BLUE100),
        ("TEXTCOLOR",    (0, 0), (-1, 0), C_NAVY),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BLUE050]),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, C_GRAY200),
        ("BOX",          (0, 0), (-1, -1), 0.6, C_GRAY300),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


# ── Main entry ────────────────────────────────────────────────────────────────

def _data_table(headers, rows, col_widths, s):
    th_row = [Paragraph(html.escape(str(h)), s["th"]) for h in headers]
    data = [th_row]
    for row in rows:
        data.append([
            Paragraph(html.escape(str(c)) if c is not None else "-", s["td"])
            for c in row
        ])
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_BLUE100),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_NAVY),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BLUE050]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GRAY200),
        ("BOX", (0, 0), (-1, -1), 0.6, C_GRAY300),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _display_cell(value):
    if value is None:
        return "-"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_display_cell(v)}" for k, v in list(value.items())[:6])
    if isinstance(value, (list, tuple)):
        return "; ".join(_display_cell(v) for v in value[:6])
    return str(value)


def _append_export_sections(story, export_data, s):
    if not export_data:
        return

    story.append(PageBreak())
    story.append(Paragraph("Complete Dashboard Data Export", s["h1"]))
    story.append(Paragraph(
        "This appendix mirrors the dashboard data available to the export pipeline across pull requests, "
        "issues, branches, forks, CI/CD, discussions, projects, and repository health.",
        s["body"],
    ))
    story.append(Spacer(1, 2 * mm))

    skip_titles = {
        "Repository Snapshot",
        "Sync Coverage",
        "KPI Summary",
        "Monthly PR Flow",
        "Weekly Throughput",
        "Contributors",
        "Oldest Open PRs",
        "Slowest Merged PRs",
        "Stale PR Alerts",
        "PR Risk Panel",
    }

    for section in export_data.get("sections", []):
        title = section.get("title", "Section")
        if title in skip_titles:
            continue
        rows = section.get("rows") or []
        columns = section.get("columns") or []
        story.append(Paragraph(html.escape(str(title)), s["h2"]))
        if not rows:
            story.append(Paragraph("No data available.", s["body"]))
            continue

        chosen_cols = columns[:6] or ["value"]
        table_rows = []
        for row in rows[:18]:
            if not isinstance(row, dict):
                row = {"value": row}
                chosen_cols = ["value"]
            table_rows.append([_display_cell(row.get(col))[:160] for col in chosen_cols])

        avail = PAGE_W - 30 * mm
        col_w = [avail / max(len(chosen_cols), 1)] * max(len(chosen_cols), 1)
        story.append(_data_table(chosen_cols, table_rows, col_w, s))
        if len(rows) > len(table_rows):
            story.append(Paragraph(
                f"{len(rows) - len(table_rows)} additional row(s) are included in the CSV export.",
                s["caption"],
            ))
        story.append(Spacer(1, 3 * mm))


def generate_pdf_report(
    repo, kpi, flow, throughput, contributors, stale, slowest, oldest=None, risks=None, export_data=None
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"PRISM Report - {repo.full_name}",
        author="PRISM Analytics",
    )

    s = _styles()
    story = []

    # ── PAGE 1: Header + KPIs + Monthly Flow ──────────────────────────────────
    story.append(Paragraph("GitHub Engineering Intelligence Report", s["h1"]))
    story.append(Paragraph(
        f"<font color='#1f6f9f'>{html.escape(repo.full_name)}</font>  |  "
        f"<font color='#6b7280'>{html.escape(repo.language or 'N/A')}</font>  |  "
        f"{repo.stars or 0} stars",
        s["body"]
    ))
    meta_rows = [
        ["Repository", repo.full_name, "Visibility", getattr(repo, "visibility", "public") or "public"],
        ["Default branch", getattr(repo, "default_branch", None) or "N/A", "Generated", datetime.now().strftime("%d %b %Y %H:%M")],
    ]
    meta_tbl = Table(meta_rows, colWidths=[28 * mm, 62 * mm, 28 * mm, 62 * mm])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_BLUE050),
        ("TEXTCOLOR", (0, 0), (-1, -1), C_GRAY700),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GRAY200),
        ("BOX", (0, 0), (-1, -1), 0.6, C_GRAY300),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=C_GRAY200,
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
                "High Priority" if s_.get("severity") in ("critical", "stale", "high") else "Monitor",
            ])
        story.append(_data_table(
            ["PR Title", "Age", "Author", "Alert Severity"],
            rows_s, cw_s, s
        ))
    else:
        story.append(Paragraph("No stale PRs detected.", s["body"]))

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
             else "Elevated cycle times - review bottleneck PRs."),
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
                "Good" if good else "Needs Attention",
                desc,
            ])
        avail = PAGE_W - 30 * mm
        ins_tbl = Table(ins_data, colWidths=[avail * 0.24, avail * 0.14, avail * 0.22, avail * 0.40])
        ins_tbl.setStyle(TableStyle([
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("BACKGROUND",   (0, 0), (-1, 0), C_BLUE100),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, C_BLUE050]),
            ("INNERGRID",    (0, 0), (-1, -1), 0.25, C_GRAY200),
            ("BOX",          (0, 0), (-1, -1), 0.6, C_GRAY300),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(ins_tbl)
    else:
        story.append(Paragraph("Insufficient data for insights.", s["body"]))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_GRAY200))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Generated by PRISM - GitHub Engineering Intelligence Platform. "
        "This report is confidential and intended for engineering leadership only.",
        s["caption"]
    ))

    _append_export_sections(story, export_data, s)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Client-ready executive report renderer
# ---------------------------------------------------------------------------

REPORT_PAGE = landscape(A4)
REPORT_W, REPORT_H = REPORT_PAGE
MARGIN_X = 14 * mm


def _report_styles():
    return {
        "cover": ParagraphStyle("cover", fontName="Times-Bold", fontSize=28, leading=32, textColor=C_NAVY, alignment=TA_LEFT),
        "h1": ParagraphStyle("report_h1", fontName="Times-Bold", fontSize=18, leading=22, textColor=C_NAVY, spaceAfter=8),
        "h2": ParagraphStyle("report_h2", fontName="Times-Bold", fontSize=14, leading=17, textColor=C_NAVY, spaceAfter=6),
        "body": ParagraphStyle("report_body", fontName="Times-Roman", fontSize=11, leading=14, textColor=C_GRAY700),
        "small": ParagraphStyle("report_small", fontName="Times-Roman", fontSize=9.5, leading=12, textColor=C_GRAY500),
        "table": ParagraphStyle("report_table", fontName="Times-Roman", fontSize=10, leading=12, textColor=C_GRAY700),
        "table_bold": ParagraphStyle("report_table_bold", fontName="Times-Bold", fontSize=10, leading=12, textColor=C_NAVY),
        "card_label": ParagraphStyle("card_label", fontName="Times-Bold", fontSize=9, leading=11, textColor=C_GRAY500),
        "card_value": ParagraphStyle("card_value", fontName="Times-Bold", fontSize=18, leading=21, textColor=C_NAVY),
    }


def _report_canvas(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(C_NAVY)
    canvas.setLineWidth(0.8)
    canvas.rect(8 * mm, 8 * mm, REPORT_W - 16 * mm, REPORT_H - 16 * mm, stroke=1, fill=0)
    canvas.setFillColor(C_NAVY)
    canvas.rect(8 * mm, REPORT_H - 18 * mm, REPORT_W - 16 * mm, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(C_WHITE)
    canvas.setFont("Times-Bold", 12)
    canvas.drawString(14 * mm, REPORT_H - 14.5 * mm, "PRISM")
    canvas.setFont("Times-Roman", 9)
    canvas.drawString(31 * mm, REPORT_H - 14.5 * mm, "Engineering Intelligence")
    canvas.drawRightString(REPORT_W - 14 * mm, REPORT_H - 14.5 * mm, datetime.now().strftime("%d %b %Y"))
    canvas.setFillColor(colors.Color(0.15, 0.23, 0.35, alpha=0.05))
    canvas.setFont("Times-Bold", 54)
    canvas.translate(REPORT_W / 2, REPORT_H / 2)
    canvas.rotate(28)
    canvas.drawCentredString(0, 0, "CONFIDENTIAL")
    canvas.rotate(-28)
    canvas.translate(-REPORT_W / 2, -REPORT_H / 2)
    canvas.setFillColor(C_GRAY500)
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(REPORT_W / 2, 11 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _as_num(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _fmt(value, suffix=""):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        value = round(value, 1)
    return f"{value}{suffix}"


def _section_rows(export_data, title):
    if not export_data:
        return []
    for section in export_data.get("sections", []):
        if section.get("title") == title:
            return section.get("rows") or []
    return []


def _section_first(export_data, title):
    rows = _section_rows(export_data, title)
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def _duration_hours(display, fallback_days=None):
    if isinstance(display, dict):
        value = _as_num(display.get("value"), None)
        unit = str(display.get("unit", "")).lower()
        if value is not None:
            if unit.startswith("d"):
                return value * 24
            if unit.startswith("h"):
                return value
            return value
    if fallback_days is not None:
        return _as_num(fallback_days) * 24
    return 0


def _status_color(value, good_at=75, warn_at=50, inverse=False):
    v = _as_num(value)
    if inverse:
        if v <= good_at:
            return C_GREEN
        if v <= warn_at:
            return C_AMBER
        return C_RED
    if v >= good_at:
        return C_GREEN
    if v >= warn_at:
        return C_AMBER
    return C_RED


class DonutFlowable(Flowable):
    def __init__(self, value, width=52 * mm, height=42 * mm, label="Score"):
        super().__init__()
        self.value = max(0, min(100, _as_num(value)))
        self.width = width
        self.height = height
        self.label = label

    def draw(self):
        c = self.canv
        cx, cy = self.width / 2, self.height / 2 + 2
        r = min(self.width, self.height) / 2 - 5
        c.setStrokeColor(C_GRAY200)
        c.setLineWidth(9)
        c.circle(cx, cy, r, stroke=1, fill=0)
        if self.value >= 100:
            c.setStrokeColor(_status_color(self.value))
            c.setLineWidth(9)
            c.circle(cx, cy, r, stroke=1, fill=0)
        elif self.value > 0:
            c.setStrokeColor(_status_color(self.value))
            c.setLineWidth(9)
            c.arc(cx - r, cy - r, cx + r, cy + r, 90, -(self.value / 100) * 360)
        c.setFillColor(C_NAVY)

        c.setFont("Times-Bold", 17)
        c.drawCentredString(cx, cy - 3, f"{int(round(self.value))}")
        c.setFillColor(C_GRAY500)
        c.setFont("Times-Roman", 9)
        c.drawCentredString(cx, cy - 16, self.label)


class BarsFlowable(Flowable):
    def __init__(self, items, width=95 * mm, height=42 * mm, max_value=None):
        super().__init__()
        self.items = items[:6]
        self.width = width
        self.height = height
        self.max_value = max_value or max([_as_num(v) for _, v, _ in self.items] + [1])

    def draw(self):
        c = self.canv
        y = self.height - 8
        for label, value, color in self.items:
            v = _as_num(value)
            c.setFont("Times-Roman", 8.5)
            c.setFillColor(C_GRAY700)
            c.drawString(0, y, str(label)[:22])
            c.setFillColor(C_GRAY200)
            c.rect(34 * mm, y - 1, self.width - 42 * mm, 5, fill=1, stroke=0)
            c.setFillColor(color)
            c.rect(34 * mm, y - 1, (self.width - 42 * mm) * (v / self.max_value), 5, fill=1, stroke=0)
            c.setFillColor(C_NAVY)
            c.drawRightString(self.width, y, _fmt(int(v)))
            y -= 8


class RadarFlowable(Flowable):
    def __init__(self, scores, width=78 * mm, height=60 * mm):
        super().__init__()
        self.scores = scores
        self.width = width
        self.height = height

    def draw(self):
        import math
        c = self.canv
        cx, cy = self.width / 2, self.height / 2
        r = min(self.width, self.height) / 2 - 12
        labels = list(self.scores.keys())[:5]
        points = []
        for i, label in enumerate(labels):
            ang = math.pi / 2 + 2 * math.pi * i / len(labels)
            c.setStrokeColor(C_GRAY200)
            c.line(cx, cy, cx + math.cos(ang) * r, cy + math.sin(ang) * r)
            c.setFillColor(C_GRAY700)
            c.setFont("Times-Roman", 7.5)
            c.drawCentredString(cx + math.cos(ang) * (r + 8), cy + math.sin(ang) * (r + 8), label[:12])
            val_r = r * max(0, min(100, _as_num(self.scores[label]))) / 100
            points.append((cx + math.cos(ang) * val_r, cy + math.sin(ang) * val_r))
        for ring in (0.33, 0.66, 1):
            ring_pts = []
            for i in range(len(labels)):
                ang = math.pi / 2 + 2 * math.pi * i / len(labels)
                ring_pts.append((cx + math.cos(ang) * r * ring, cy + math.sin(ang) * r * ring))
            c.setStrokeColor(C_GRAY200)
            c.lines([(ring_pts[i][0], ring_pts[i][1], ring_pts[(i + 1) % len(labels)][0], ring_pts[(i + 1) % len(labels)][1]) for i in range(len(labels))])
        if points:
            p = c.beginPath()
            p.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                p.lineTo(x, y)
            p.close()
            c.setFillColor(colors.Color(0.14, 0.39, 0.92, alpha=0.18))
            c.setStrokeColor(C_BLUE)
            c.drawPath(p, stroke=1, fill=1)


class HeatmapFlowable(Flowable):
    def __init__(self, values, width=90 * mm, height=38 * mm):
        super().__init__()
        self.values = values[:40]
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        cols = 10
        cell = min(self.width / cols, self.height / 4)
        for idx, value in enumerate(self.values):
            x = (idx % cols) * cell
            y = self.height - ((idx // cols) + 1) * cell
            v = _as_num(value)
            color = C_GREEN if v < 30 else C_AMBER if v < 70 else C_RED
            c.setFillColor(color)
            c.rect(x, y, cell - 1, cell - 1, fill=1, stroke=0)


class TreemapFlowable(Flowable):
    def __init__(self, items, width=90 * mm, height=42 * mm):
        super().__init__()
        self.items = items[:5]
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        total = sum(max(1, _as_num(v)) for _, v, _ in self.items) or 1
        x = 0
        for label, value, color in self.items:
            w = self.width * max(1, _as_num(value)) / total
            c.setFillColor(color)
            c.rect(x, 0, w - 1, self.height, fill=1, stroke=0)
            c.setFillColor(C_WHITE)
            c.setFont("Times-Bold", 8)
            c.drawString(x + 3, self.height - 12, str(label)[:14])
            c.setFont("Times-Roman", 8)
            c.drawString(x + 3, self.height - 23, _fmt(int(_as_num(value))))
            x += w


def _card(title, value, subtitle="", color=C_BLUE, width=50 * mm):
    s = _report_styles()
    dot = Table([[""]], colWidths=[4 * mm], rowHeights=[4 * mm])
    dot.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color), ("BOX", (0, 0), (-1, -1), 0, color)]))
    inner = Table([
        [Paragraph(title, s["card_label"]), dot],
        [Paragraph(str(value), s["card_value"]), ""],
        [Paragraph(subtitle, s["small"]), ""],
    ], colWidths=[width - 12 * mm, 5 * mm])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
        ("BOX", (0, 0), (-1, -1), 0.6, C_GRAY300),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return inner


def _std_table(headers, rows, widths=None):
    s = _report_styles()
    data = [[Paragraph(str(h), s["table_bold"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(html.escape(str(cell)) if cell is not None else "N/A", s["table"]) for cell in row])
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_BLUE100),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_BLUE050]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GRAY200),
        ("BOX", (0, 0), (-1, -1), 0.6, C_GRAY300),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _page_title(story, title, subtitle=None):
    s = _report_styles()
    story.append(Paragraph(title, s["h1"]))
    if subtitle:
        story.append(Paragraph(subtitle, s["body"]))
    story.append(Spacer(1, 5 * mm))


def _recommendations(kpi, health, stale, risks, cicd):
    recs = []
    if _as_num(kpi.get("stale_prs")) > 0:
        recs.append(("Critical Action", "Reduce stale pull requests through weekly ownership review.", C_RED))
    if _duration_hours(kpi.get("avg_wait_for_review_display"), kpi.get("avg_wait_for_review")) > 24:
        recs.append(("Priority 1", "Introduce reviewer SLA and automated escalation for delayed reviews.", C_AMBER))
    if _as_num(kpi.get("merge_rate")) < 75:
        recs.append(("Priority 2", "Analyze rejected or abandoned PRs to reduce rework.", C_AMBER))
    if _as_num(cicd.get("success_rate")) < 80:
        recs.append(("Priority 3", "Stabilize failing CI workflows before scaling delivery throughput.", C_RED))
    if _as_num(health.get("score")) >= 80:
        recs.append(("Long-Term", "Maintain current engineering controls and monitor trend degradation.", C_GREEN))
    if not recs:
        recs.append(("Short-Term", "Continue routine backlog, CI, and review governance.", C_GREEN))
    return recs[:6]


def generate_pdf_report(
    repo, kpi, flow, throughput, contributors, stale, slowest, oldest=None, risks=None, export_data=None
) -> bytes:
    s = _report_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=REPORT_PAGE,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=24 * mm,
        bottomMargin=18 * mm,
        title=f"PRISM Executive Report - {repo.full_name}",
        author="PRISM Analytics",
    )
    story = []

    repo_info = _section_first(export_data, "Repository Snapshot")
    issue_summary = _section_first(export_data, "Issue Summary")
    branch_summary = _section_first(export_data, "Branch Summary")
    fork_summary = _section_first(export_data, "Fork Summary")
    cicd_summary = _section_first(export_data, "CI/CD Summary")
    discussion_summary = _section_first(export_data, "Discussion Summary")
    project_summary = _section_first(export_data, "Project Summary")
    health = _section_first(export_data, "Repository Health") or {"score": 0, "components": {}}
    issues = _section_rows(export_data, "Issues")
    branches = _section_rows(export_data, "Branches")
    forks = _section_rows(export_data, "Forks")
    workflow_runs = _section_rows(export_data, "Workflow Runs")
    workflow_breakdown = _section_rows(export_data, "Workflow Breakdown")
    issue_velocity = _section_rows(export_data, "Issue Resolution Velocity")
    issue_priority = _section_rows(export_data, "Issue Priority Distribution")
    projects = _section_rows(export_data, "Projects")
    discussions = _section_rows(export_data, "Discussions")
    stale = stale or []
    risks = risks or []
    oldest = oldest or []
    slowest = slowest or []
    contributors = contributors or []
    flow = flow or []

    health_score = _as_num(health.get("score"))
    wait_hours = _duration_hours(kpi.get("avg_wait_for_review_display"), kpi.get("avg_wait_for_review"))
    cycle_hours = _duration_hours(kpi.get("avg_cycle_time_display"), kpi.get("avg_cycle_time"))

    # Page 1
    _page_title(story, "Executive Summary Dashboard", f"{repo.full_name} | Confidential Engineering Intelligence Report")
    cards = [
        _card("Open PRs", _fmt(kpi.get("open_prs")), "Active development queue", _status_color(kpi.get("open_prs"), 10, 25, inverse=True)),
        _card("Merge Rate", _fmt(kpi.get("merge_rate"), "%"), "Closed PRs merged", _status_color(kpi.get("merge_rate"))),
        _card("Avg Cycle Time", _fmt(round(cycle_hours, 1), " hrs"), "PR open to merge", _status_color(cycle_hours, 48, 96, inverse=True)),
        _card("Review Wait Time", _fmt(round(wait_hours, 1), " hrs"), "Time to first review", _status_color(wait_hours, 24, 48, inverse=True)),
        _card("Repository Health", f"{int(round(health_score))}/100", "Aggregate maturity signal", _status_color(health_score)),
    ]
    story.append(Table([cards], colWidths=[(REPORT_W - 2 * MARGIN_X) / 5] * 5, style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 7 * mm))
    status_items = [
        ("Open", kpi.get("open_prs", 0), C_AMBER),
        ("Merged", kpi.get("merged_prs", 0), C_GREEN),
        ("Closed", kpi.get("closed_not_merged_prs", 0), C_GRAY500),
        ("Stale", kpi.get("stale_prs", 0), C_RED),
    ]
    summary = (
        "Repository demonstrates strong development activity with measurable delivery throughput. "
        "Review responsiveness, stale work, and CI stability should be managed as leading indicators of execution risk."
    )
    story.append(Table([
        [DonutFlowable(health_score, label="Health"), BarsFlowable(status_items), Paragraph(summary, s["body"])],
    ], colWidths=[62 * mm, 105 * mm, 92 * mm], style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(PageBreak())

    # Page 2
    _page_title(story, "Repository Overview")
    overview_cards = [
        _card("Repository", repo.full_name, "Name"),
        _card("Stars", _fmt(repo_info.get("stars", getattr(repo, "stars", 0))), "Popularity"),
        _card("Forks", _fmt(repo_info.get("forks_count", fork_summary.get("total_forks", 0))), "Adoption"),
        _card("Contributors", _fmt(len(contributors)), "Observed contributors"),
        _card("Language", repo_info.get("language") or getattr(repo, "language", "N/A"), "Primary stack"),
    ]
    story.append(Table([overview_cards], colWidths=[(REPORT_W - 2 * MARGIN_X) / 5] * 5))
    story.append(Spacer(1, 8 * mm))
    tech = [repo_info.get("language") or getattr(repo, "language", None), "GitHub Actions" if workflow_runs else None, "Projects" if projects else None, "Discussions" if discussions else None, "CI/CD" if workflow_breakdown else None]
    tech = [t for t in tech if t] or ["Repository Metadata", "Pull Requests", "Issues"]
    badge_rows = [[Paragraph(t, s["table_bold"]) for t in tech[:5]]]
    story.append(_std_table(["Technology Stack Signals"], [[", ".join(tech)]], [240 * mm]))
    story.append(Spacer(1, 7 * mm))
    arch = [[_card("Source Control", "GitHub", "Repository and collaboration", C_BLUE), _card("Delivery", f"{cicd_summary.get('success_rate', 0)}%", "CI success rate", _status_color(cicd_summary.get("success_rate"))), _card("Governance", _fmt(branch_summary.get("protected_branches", 0)), "Protected branches", C_NAVY)]]
    story.append(Table(arch, colWidths=[82 * mm] * 3))
    story.append(PageBreak())

    # Page 3
    _page_title(story, "Pull Request Analytics")
    funnel_rows = [["Created", kpi.get("total_prs", 0)], ["Reviewed", int(_as_num(kpi.get("total_prs")) * max(_as_num(kpi.get("avg_reviews_per_pr")), 0) > 0)], ["Merged", kpi.get("merged_prs", 0)], ["Open", kpi.get("open_prs", 0)]]
    trend_items = [(f.get("month", ""), f.get("created", 0), C_BLUE) for f in flow[-6:]]
    merge_items = [(f.get("month", ""), f.get("merged", 0), C_GREEN) for f in flow[-6:]]
    open_items = [(f.get("month", ""), f.get("open_at_end", 0), C_AMBER) for f in flow[-6:]]
    story.append(Table([
        [_std_table(["Lifecycle Stage", "Count"], funnel_rows, [55 * mm, 30 * mm]), BarsFlowable(trend_items, 72 * mm), BarsFlowable(merge_items, 72 * mm), BarsFlowable(open_items, 72 * mm)]
    ], colWidths=[95 * mm, 78 * mm, 78 * mm, 78 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(PageBreak())

    # Page 4
    _page_title(story, "Developer Productivity Analysis")
    top = sorted(contributors, key=lambda c: (_as_num(c.get("merged_prs")), _as_num(c.get("total_prs"))), reverse=True)[:5]
    rows = []
    medals = ["Gold", "Silver", "Bronze", "Top Performer", "Top Performer"]
    for idx, c in enumerate(top):
        rows.append([medals[idx], c.get("username"), c.get("total_prs", 0), c.get("merged_prs", 0), f"{c.get('merge_rate', 0)}%", _fmt(c.get("avg_wait_for_review"), " d")])
    story.append(_std_table(["Rank", "Contributor", "PR Count", "Merged", "Success Rate", "Avg Review Time"], rows or [["N/A", "No contributor data", 0, 0, "N/A", "N/A"]], [38 * mm, 60 * mm, 32 * mm, 32 * mm, 35 * mm, 45 * mm]))
    story.append(Spacer(1, 6 * mm))
    perf_items = [(c.get("username", "N/A"), c.get("merge_rate", 0), _status_color(c.get("merge_rate"))) for c in top]
    story.append(BarsFlowable(perf_items, 150 * mm, 50 * mm, max_value=100))
    story.append(PageBreak())

    # Page 5
    _page_title(story, "Risk Intelligence")
    low = [r for r in risks if _as_num(r.get("risk_score")) < 40]
    med = [r for r in risks if 40 <= _as_num(r.get("risk_score")) < 70]
    high = [r for r in risks if _as_num(r.get("risk_score")) >= 70]
    matrix = [
        ["Low Risk", "\n".join([f"#{r.get('number')} {r.get('title', '')[:36]}" for r in low[:4]]) or "None"],
        ["Medium Risk", "\n".join([f"#{r.get('number')} {r.get('title', '')[:36]}" for r in med[:4]]) or "None"],
        ["High Risk", "\n".join([f"#{r.get('number')} {r.get('title', '')[:36]}" for r in high[:4]]) or "None"],
    ]
    insight = f"{len([r for r in risks if _as_num(r.get('predicted_delay_days')) > 1])} PRs are likely to experience review delays due to prolonged inactivity or complexity."
    story.append(Table([[_std_table(["Risk Band", "Pull Requests"], matrix, [36 * mm, 118 * mm]), DonutFlowable((len(high) / max(len(risks), 1)) * 100, label="High Risk"), Paragraph(insight, s["body"])]], colWidths=[165 * mm, 62 * mm, 80 * mm]))
    story.append(PageBreak())

    # Page 6
    _page_title(story, "Backlog Analysis")
    bucket_vals = {"0-7 Days": 0, "7-30 Days": 0, "30-90 Days": 0, "90+ Days": 0}
    for item in oldest:
        age = _as_num(item.get("age_days"))
        if age <= 7: bucket_vals["0-7 Days"] += 1
        elif age <= 30: bucket_vals["7-30 Days"] += 1
        elif age <= 90: bucket_vals["30-90 Days"] += 1
        else: bucket_vals["90+ Days"] += 1
    story.append(Table([[BarsFlowable([(k, v, C_GREEN if i == 0 else C_AMBER if i < 3 else C_RED) for i, (k, v) in enumerate(bucket_vals.items())], 100 * mm, 42 * mm), TreemapFlowable([(k, v, C_GREEN if i == 0 else C_AMBER if i < 3 else C_RED) for i, (k, v) in enumerate(bucket_vals.items())], 100 * mm), _std_table(["Oldest PR", "Age", "Author"], [[f"#{o.get('number')} {o.get('title', '')[:30]}", f"{o.get('age_days', 0)}d", o.get("author", "N/A")] for o in oldest[:10]], [80 * mm, 24 * mm, 40 * mm])]], colWidths=[105 * mm, 105 * mm, 145 * mm]))
    story.append(PageBreak())

    # Page 7
    _page_title(story, "CI/CD Performance")
    ci_cards = [[_card("Success Rate", _fmt(cicd_summary.get("success_rate"), "%"), "Workflow health", _status_color(cicd_summary.get("success_rate"))), _card("Total Runs", _fmt(cicd_summary.get("total_runs", 0)), "Observed runs", C_BLUE), _card("Failed Runs", _fmt(cicd_summary.get("failed_runs", 0)), "Failure volume", _status_color(cicd_summary.get("failed_runs"), 3, 10, inverse=True))]]
    story.append(Table(ci_cards, colWidths=[80 * mm] * 3))
    story.append(Spacer(1, 7 * mm))
    wf_rows = [[w.get("name"), w.get("total_runs"), f"{w.get('success_rate', 0)}%", w.get("avg_duration_minutes", 0)] for w in workflow_breakdown[:8]]
    story.append(_std_table(["Workflow", "Runs", "Success", "Avg Duration Min"], wf_rows or [["N/A", 0, "N/A", "N/A"]], [95 * mm, 30 * mm, 35 * mm, 45 * mm]))
    story.append(PageBreak())

    # Page 8
    _page_title(story, "Issue Analytics")
    issue_cards = [[_card("Open Issues", issue_summary.get("open_issues", 0), "Current issue queue", C_AMBER), _card("Closure Rate", _fmt(issue_summary.get("closure_rate"), "%"), "Resolution effectiveness", _status_color(issue_summary.get("closure_rate"))), _card("Bug Count", issue_summary.get("bug_count", 0), "Quality signal", C_RED)]]
    priority_items = [(p.get("name") or p.get("priority", "N/A"), p.get("value") or p.get("count", 0), C_RED if p.get("name") == "Critical" else C_AMBER if p.get("name") == "High" else C_BLUE) for p in issue_priority]
    velocity_items = [(v.get("month"), v.get("closed", 0), C_GREEN) for v in issue_velocity[-6:]]
    story.append(Table(issue_cards, colWidths=[80 * mm] * 3))
    story.append(Spacer(1, 7 * mm))
    story.append(Table([[BarsFlowable(priority_items, 105 * mm), BarsFlowable(velocity_items, 105 * mm), _std_table(["Top Issue", "State", "Age"], [[i.get("title", "")[:36], i.get("state"), i.get("age_days", 0)] for i in issues[:10]], [80 * mm, 28 * mm, 25 * mm])]], colWidths=[110 * mm, 110 * mm, 140 * mm]))
    story.append(PageBreak())

    # Page 9
    _page_title(story, "Branch Management")
    branch_cards = [[_card("Active Branches", branch_summary.get("active_branches", 0), "Recently updated", C_GREEN), _card("Stale Branches", branch_summary.get("stale_branches", 0), "Cleanup candidates", C_RED), _card("Protected Branches", branch_summary.get("protected_branches", 0), "Governance", C_BLUE)]]
    heat_values = [b.get("staleness_days", 0) for b in branches]
    story.append(Table(branch_cards, colWidths=[80 * mm] * 3))
    story.append(Spacer(1, 7 * mm))
    story.append(Table([[HeatmapFlowable(heat_values), _std_table(["Branch", "Protected", "Age Days"], [[b.get("name"), b.get("protected"), b.get("staleness_days")] for b in branches[:10]], [95 * mm, 35 * mm, 35 * mm])]], colWidths=[110 * mm, 175 * mm]))
    story.append(PageBreak())

    # Page 10
    _page_title(story, "Community & Adoption")
    adoption_cards = [[_card("Stars", repo_info.get("stars", getattr(repo, "stars", 0)), "Popularity", C_BLUE), _card("Forks", fork_summary.get("total_forks", len(forks)), "Adoption", C_GREEN), _card("Discussions", discussion_summary.get("total_discussions", 0), "Community", C_AMBER), _card("Projects", project_summary.get("total_projects", 0), "Planning", C_NAVY)]]
    story.append(Table(adoption_cards, colWidths=[65 * mm] * 4))
    story.append(Spacer(1, 8 * mm))
    fork_items = [(f.get("full_name", "fork")[:18], f.get("stars", 0), C_BLUE) for f in forks[:6]]
    story.append(BarsFlowable(fork_items or [("No fork data", 1, C_GRAY500)], 150 * mm, 48 * mm))
    story.append(PageBreak())

    # Page 11
    _page_title(story, "Repository Health Scorecard")
    components = health.get("components") if isinstance(health.get("components"), dict) else {}
    scores = {
        "PR Mgmt": _as_num(components.get("pull_requests", health_score * 0.2)) * 5 if components else health_score,
        "CI/CD": _as_num(components.get("cicd", cicd_summary.get("success_rate", 0))),
        "Quality": 100 - min(100, _as_num(issue_summary.get("bug_count", 0)) * 5),
        "Collab": min(100, _as_num(kpi.get("avg_reviews_per_pr", 0)) * 30),
        "Docs": 70 if repo_info.get("url") else 40,
    }
    score_rows = [[k, int(max(0, min(100, v)))] for k, v in scores.items()]
    story.append(Table([[_std_table(["Category", "Score"], score_rows, [60 * mm, 35 * mm]), RadarFlowable(scores, 95 * mm, 70 * mm)]], colWidths=[110 * mm, 105 * mm]))
    story.append(PageBreak())

    # Page 12
    _page_title(story, "Engineering Recommendations")
    recs = _recommendations(kpi, health, stale, risks, cicd_summary)
    rec_tables = []
    for title, text, color in recs:
        rec_tables.append(_card(title, text, "Recommended management action", color, width=82 * mm))
    rows = [rec_tables[i:i + 3] for i in range(0, len(rec_tables), 3)]
    story.append(Table(rows, colWidths=[86 * mm] * 3, style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Risk Mitigation Plan: assign ownership for stale work, review workflow failure patterns weekly, and track health score movement after remediation.", s["body"]))
    story.append(PageBreak())

    # Final Page
    _page_title(story, "Executive Conclusion")
    maturity = 1
    if health_score >= 85:
        maturity = 5
    elif health_score >= 70:
        maturity = 4
    elif health_score >= 50:
        maturity = 3
    elif health_score >= 30:
        maturity = 2
    findings = [
        ["Key Finding", "Repository has measurable engineering activity and collaboration signals."],
        ["Strategic Recommendation", "Focus management attention on review latency, stale backlog, and CI predictability."],
        ["Engineering Maturity", f"Level {maturity} - " + ["Initial", "Managed", "Defined", "Measured", "Optimized"][maturity - 1]],
    ]
    story.append(_std_table(["Area", "Assessment"], findings, [65 * mm, 190 * mm]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Final assessment is generated dynamically from repository health, PR throughput, review responsiveness, CI/CD performance, and collaboration metrics available in the analyzed dashboard data.", s["body"]))

    doc.build(story, onFirstPage=_report_canvas, onLaterPages=_report_canvas)
    return buf.getvalue()
