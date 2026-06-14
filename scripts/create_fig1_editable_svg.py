"""Create an editable vector reconstruction of the locked Figure 1 PNG.

The output is intentionally hand-built as SVG primitives and text. It does not
embed the source PNG, so boxes, arrows, icons, labels, and matrix cells remain
editable in vector editors such as Illustrator, Inkscape, and Affinity Designer.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figure_redraw" / "fig" / "NEW" / "FIG1_editable_vector.svg"

W, H = 1746, 869

NAVY = "#063579"
BLUE = "#1B7FAA"
MID_BLUE = "#2F79B7"
CYAN = "#2586B8"
PURPLE = "#B7A8D7"
PURPLE_D = "#4B3F78"
LAV = "#E9E6F3"
YELLOW = "#FBE99A"
ORANGE = "#E9823B"
GREEN = "#2B8B57"
TEXT = "#161A22"
MUTED = "#5C6975"
STROKE = "#91A8BC"
LIGHT_STROKE = "#C9D4DE"
BG = "#FFFFFF"


class SVG:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, rx=0, fill="none", stroke="none", sw=1, cls="", opacity=None):
        op = "" if opacity is None else f' opacity="{opacity}"'
        klass = "" if not cls else f' class="{cls}"'
        self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{klass}{op}/>'
        )

    def line(self, x1, y1, x2, y2, stroke=NAVY, sw=3, marker=None, dash=None, opacity=None):
        mark = "" if marker is None else f' marker-end="url(#{marker})"'
        d = "" if dash is None else f' stroke-dasharray="{dash}"'
        op = "" if opacity is None else f' opacity="{opacity}"'
        self.add(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round"{mark}{d}{op}/>'
        )

    def path(self, d, fill="none", stroke=NAVY, sw=2, marker=None, dash=None, opacity=None):
        mark = "" if marker is None else f' marker-end="url(#{marker})"'
        das = "" if dash is None else f' stroke-dasharray="{dash}"'
        op = "" if opacity is None else f' opacity="{opacity}"'
        self.add(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round"{mark}{das}{op}/>'
        )

    def circle(self, cx, cy, r, fill="none", stroke=NAVY, sw=2, opacity=None):
        op = "" if opacity is None else f' opacity="{opacity}"'
        self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{op}/>')

    def polygon(self, pts, fill="none", stroke=NAVY, sw=2, opacity=None):
        op = "" if opacity is None else f' opacity="{opacity}"'
        self.add(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"{op}/>')

    def text(
        self,
        x,
        y,
        text,
        size=18,
        fill=TEXT,
        weight="400",
        anchor="middle",
        line_height=1.15,
        italic=False,
        family="Arial, Helvetica, sans-serif",
    ):
        style = "font-style:italic;" if italic else ""
        lines = str(text).split("\n")
        self.add(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}" style="{style}">'
        )
        for i, line in enumerate(lines):
            dy = "0" if i == 0 else f"{size * line_height:.1f}"
            self.add(f'<tspan x="{x}" dy="{dy}">{escape(line)}</tspan>')
        self.add("</text>")


def card(svg: SVG, x, y, w, h, title, header_fill, title_size=24):
    svg.rect(x + 2, y + 5, w, h, rx=10, fill="#000000", stroke="none", opacity=0.10)
    svg.rect(x, y, w, h, rx=10, fill=BG, stroke="#D1D7DE", sw=1.2)
    svg.add(f'<path d="M{x},{y+11} Q{x},{y} {x+11},{y} H{x+w-11} Q{x+w},{y} {x+w},{y+11} V{y+55} H{x} Z" fill="{header_fill}"/>')
    if "\n" in title:
        svg.text(x + w / 2, y + 25, title, size=title_size, fill="#FFFFFF", weight="700", line_height=0.95)
    else:
        svg.text(x + w / 2, y + 37, title, size=title_size, fill="#FFFFFF", weight="700")


def arrow(svg: SVG, x1, y1, x2, y2, color=NAVY, sw=4):
    svg.line(x1, y1, x2, y2, stroke=color, sw=sw, marker="arrow")


def calendar_icon(svg: SVG, x, y, scale=1.0, color=NAVY):
    w, h = 36 * scale, 37 * scale
    svg.rect(x, y, w, h, rx=4 * scale, fill="#FFFDF6", stroke=color, sw=2)
    svg.line(x, y + 9 * scale, x + w, y + 9 * scale, stroke=color, sw=2)
    for dx in (9, 27):
        svg.line(x + dx * scale, y - 4 * scale, x + dx * scale, y + 5 * scale, stroke=color, sw=2)
    for row in range(3):
        for col in range(4):
            svg.circle(x + (9 + col * 6) * scale, y + (18 + row * 6) * scale, 1.0 * scale, fill=color, stroke=color, sw=0)


def file_woman_icon(svg: SVG, x, y, color=NAVY):
    svg.path(f"M{x+8},{y+2} H{x+56} L{x+75},{y+21} V{x*0 + y+78} H{x+8} Z", fill="#FFFFFF", stroke=color, sw=2)
    svg.path(f"M{x+56},{y+2} V{y+22} H{x+75}", stroke=color, sw=2)
    svg.path(
        f"M{x+31},{y+65} C{x+18},{y+55} {x+18},{y+34} {x+34},{y+28} "
        f"C{x+41},{y+38} {x+50},{y+43} {x+58},{y+43} "
        f"C{x+58},{y+59} {x+55},{y+67} {x+48},{y+72} "
        f"C{x+43},{y+68} {x+38},{y+66} {x+31},{y+65} Z",
        fill="none",
        stroke=color,
        sw=3,
    )
    svg.path(f"M{x+23},{y+68} C{x+12},{y+75} {x+4},{y+67} {x+14},{y+58}", stroke=color, sw=3)


def pregnancy_icon(svg: SVG, x, y, color=PURPLE_D):
    svg.path(f"M{x+45},{y+19} C{x+31},{y+19} {x+25},{y+33} {x+31},{y+46}", stroke=color, sw=3)
    svg.path(f"M{x+36},{y+46} C{x+55},{y+43} {x+64},{y+61} {x+50},{y+72}", stroke=color, sw=3)
    svg.path(f"M{x+31},{y+49} C{x+17},{y+63} {x+21},{y+82} {x+45},{y+83} H{x+64}", stroke=color, sw=3)
    svg.path(f"M{x+39},{y+23} C{x+28},{y+35} {x+26},{y+56} {x+45},{y+74}", stroke=color, sw=3)
    svg.circle(x + 48, y + 11, 11, fill="none", stroke=color, sw=3)


def people_icon(svg: SVG, x, y, color=NAVY):
    for dx, dy, r in [(8, 0, 6), (22, 1, 7), (36, 2, 6)]:
        svg.circle(x + dx, y + dy, r, fill=color, stroke=color, sw=0)
    for dx, w in [(0, 16), (12, 22), (30, 16)]:
        svg.rect(x + dx, y + 12, w, 14, rx=7, fill=color, stroke=color, sw=0)


def partnership_icon(svg: SVG, x, y, color=NAVY):
    svg.circle(x + 9, y + 5, 5, fill=color, stroke=color, sw=0)
    svg.circle(x + 27, y + 5, 5, fill=color, stroke=color, sw=0)
    svg.path(f"M{x+9},{y+12} V{y+34} M{x+27},{y+12} V{y+34} M{x+2},{y+22} H{x+34}", stroke=color, sw=3)


def shield_icon(svg: SVG, x, y, color=NAVY):
    svg.path(f"M{x+18},{y} L{x+34},{y+7} V{y+23} C{x+34},{y+34} {x+18},{y+42} {x+18},{y+42} C{x+18},{y+42} {x+2},{y+34} {x+2},{y+23} V{y+7} Z", fill="none", stroke=color, sw=2.4)
    svg.path(f"M{x+13},{y+22} L{x+17},{y+27} L{x+25},{y+16}", stroke=color, sw=2.4)


def hospital_icon(svg: SVG, x, y, color=NAVY):
    svg.rect(x + 5, y + 8, 30, 34, rx=2, fill="none", stroke=color, sw=2)
    svg.rect(x + 12, y + 18, 16, 24, fill="none", stroke=color, sw=2)
    svg.line(x + 20, y + 12, x + 20, y + 22, stroke=color, sw=2)
    svg.line(x + 15, y + 17, x + 25, y + 17, stroke=color, sw=2)
    for dx in (10, 30):
        svg.rect(x + dx, y + 27, 4, 4, fill=color, stroke=color, sw=0)


def scatter_pca(svg: SVG, x, y):
    import math
    pts = [
        (0, 0), (10, 8), (22, -5), (35, 10), (50, -3), (65, 12), (80, 0),
        (110, 20), (126, 10), (142, 32), (156, 22), (173, 35), (190, 25),
        (230, 60), (250, 47), (270, 70), (288, 57), (306, 75), (326, 63),
    ]
    colors = [MID_BLUE] * 7 + ["#A9C6E6"] * 6 + ["#CFC8E0"] * 7
    for i, (px, py) in enumerate(pts):
        svg.circle(x + 28 + px * 0.62, y + 86 + py * 0.62, 5.4, fill=colors[i], stroke=colors[i], sw=0, opacity=0.95)
    svg.line(x + 12, y + 166, x + 156, y + 166, stroke="#111827", sw=1.4, marker="tinyarrow")
    svg.line(x + 12, y + 166, x + 12, y + 18, stroke="#111827", sw=1.4, marker="tinyarrow")
    svg.text(x + 93, y + 189, "PC1", size=17)
    svg.text(x - 3, y + 93, "PC2", size=17, anchor="middle")


def kmeans_clusters(svg: SVG, x, y):
    clusters = [
        (x + 52, y + 52, MID_BLUE, "#C6DDF2"),
        (x + 121, y + 35, PURPLE, "#E8E3F2"),
        (x + 161, y + 92, "#F1D56C", "#FFF3B8"),
    ]
    for cx, cy, c, fill in clusters:
        svg.circle(cx, cy, 36, fill=fill, stroke=c, sw=1.5, opacity=0.55)
        for dx, dy in [(-15, -5), (0, -13), (15, -2), (-5, 9), (11, 14)]:
            svg.circle(cx + dx, cy + dy, 5.5, fill=c, stroke="#FFFFFF", sw=1)


def matrix_cells(svg: SVG, x, y):
    rows = [
        ("Demographics", NAVY, 6),
        ("Partnership", MID_BLUE, 5),
        ("Contraception", MID_BLUE, 5),
        ("Pregnancy history", PURPLE, 5),
        ("Fertility care", PURPLE, 5),
        ("Insurance", PURPLE, 5),
        ("Skip patterns", YELLOW, 5),
    ]
    for r, (_lab, col, n) in enumerate(rows):
        for c in range(n):
            alpha = 1 - c * 0.13
            fill = col
            if c >= 3:
                fill = "#C7D7EA" if col in (NAVY, MID_BLUE) else ("#D8D2E6" if col == PURPLE else "#FFF2B7")
            svg.rect(x + c * 31, y + r * 40, 24, 24, rx=1, fill=fill, stroke="none", opacity=max(alpha, 0.45))
        svg.text(x + n * 31 + 13, y + r * 40 + 18, "…", size=21, anchor="start")


def encoder_tokens(svg: SVG, x, y):
    cols = [NAVY, MID_BLUE, "#6EAAD0", "#A9C6E6", "#C7D7EA", "#FFFFFF"]
    for i, c in enumerate(cols):
        svg.rect(x + i * 26, y, 19, 19, rx=1, fill=c, stroke=NAVY if c == "#FFFFFF" else "none", sw=1)
    svg.text(x + 167, y + 16, "…", size=20, anchor="start")
    for i, c in enumerate([NAVY, "#FFFFFF", "#FFFFFF", "#FFFFFF", PURPLE, "#FFFFFF", "#FFFFFF"]):
        svg.rect(x + i * 25, y + 48, 19, 19, rx=1, fill=c, stroke=NAVY if c == "#FFFFFF" else "none", sw=1)
    for i in (1, 2, 6):
        svg.path(f"M{x+i*25+3},{y+51} L{x+i*25+16},{y+64}", stroke=ORANGE if i in (2, 6) else NAVY, sw=1.4)
        svg.path(f"M{x+i*25+3},{y+64} L{x+i*25+16},{y+51}", stroke=ORANGE if i in (2, 6) else NAVY, sw=1.4)
    svg.text(x + 186, y + 65, "…", size=20, anchor="start")


def main() -> None:
    svg = SVG()
    svg.add(f'<?xml version="1.0" encoding="UTF-8"?>')
    svg.add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="Editable Figure 1 workflow">'
    )
    svg.add(
        """
<defs>
  <linearGradient id="grad_navy" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#06256D"/><stop offset="100%" stop-color="#073B87"/></linearGradient>
  <linearGradient id="grad_blue" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#176B9A"/><stop offset="100%" stop-color="#1D8CBC"/></linearGradient>
  <linearGradient id="grad_blue2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#2275B0"/><stop offset="100%" stop-color="#2C8AC1"/></linearGradient>
  <linearGradient id="grad_purple" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#B6A7DA"/><stop offset="100%" stop-color="#A897C9"/></linearGradient>
  <linearGradient id="grad_yellow" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#FFF8C9"/><stop offset="100%" stop-color="#FFF0A5"/></linearGradient>
  <marker id="arrow" markerWidth="16" markerHeight="16" refX="14" refY="8" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L16,8 L0,16 Z" fill="#063579"/></marker>
  <marker id="tinyarrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L7,3.5 L0,7 Z" fill="#111827"/></marker>
</defs>
"""
    )
    svg.rect(0, 0, W, H, fill="#FFFFFF")

    # Top row cards
    card(svg, 18, 26, 329, 398, "NSFG public-use files", "url(#grad_navy)")
    svg.rect(47, 109, 268, 120, rx=8, fill="#FFFFFF", stroke=STROKE, sw=1)
    svg.rect(47, 253, 268, 122, rx=8, fill="#FFFFFF", stroke=STROKE, sw=1)
    file_woman_icon(svg, 75, 130, NAVY)
    pregnancy_icon(svg, 78, 279, PURPLE_D)
    svg.text(214, 173, "Female\nrespondent file", size=23, anchor="middle")
    svg.text(214, 318, "Female\npregnancy file", size=23, anchor="middle")

    card(svg, 393, 26, 308, 398, "Cycle harmonization", "url(#grad_blue)", title_size=23)
    years = ["2011–2013", "2013–2015", "2015–2017", "2017–2019", "2022–2023"]
    for i, yr in enumerate(years):
        yy = 123 + i * 60
        if i == 4:
            svg.rect(418, yy - 22, 198, 46, rx=8, fill="#FFF7C8", stroke="none", opacity=0.75)
        calendar_icon(svg, 433, yy - 19, scale=0.92)
        svg.text(492, yy + 6, yr, size=23, anchor="start")
    svg.path("M632,128 H647 Q650,128 650,132 V368 Q650,371 647,371 H632", stroke="#54718C", sw=2.6)
    svg.line(650, 238, 666, 238, stroke="#54718C", sw=2.6)

    card(svg, 746, 26, 417, 398, "Respondent-level\nlife-course matrix", "url(#grad_blue)", title_size=22)
    domain_y = [113, 154, 194, 234, 274, 314, 354]
    domain_text = ["Demographics", "Partnership", "Contraception", "Pregnancy history", "Fertility care", "Insurance", "Skip patterns"]
    for yy, lab in zip(domain_y, domain_text):
        if lab == "Demographics":
            people_icon(svg, 773, yy - 9)
        elif lab == "Partnership":
            partnership_icon(svg, 773, yy - 12)
        elif lab == "Contraception":
            svg.path(f"M772,{yy+4} L812,{yy-9} L816,{yy+5} L776,{yy+18} Z", fill="none", stroke=NAVY, sw=2)
            for j in range(4):
                svg.circle(781 + j * 8, yy + 3 - j * 2, 1.2, fill=NAVY, stroke=NAVY, sw=0)
        elif lab == "Pregnancy history":
            pregnancy_icon(svg, 770, yy - 25, NAVY)
        elif lab == "Fertility care":
            hospital_icon(svg, 773, yy - 21)
        elif lab == "Insurance":
            shield_icon(svg, 775, yy - 22)
        else:
            svg.path(f"M773,{yy} H810", stroke="#111111", sw=2.2, dash="5 5", marker="arrow")
        svg.text(853, yy + 7, lab, size=16, anchor="start")
    matrix_cells(svg, 967, 102)
    svg.text(955, 402, "Mixed types, with missingness", size=17, anchor="middle")

    card(svg, 1202, 26, 508, 398, "Masked tabular\nSSL encoder", "url(#grad_blue)", title_size=22)
    svg.text(1234, 123, "Feature tokens", size=17, anchor="start")
    svg.text(1234, 171, "Mixed masking", size=17, anchor="start")
    encoder_tokens(svg, 1360, 109)
    arrow(svg, 1418, 190, 1418, 218, color=NAVY, sw=3)
    svg.rect(1235, 229, 315, 95, rx=8, fill="#F1EFF8", stroke="#7486B3", sw=1.2)
    # neural network
    nodes = [(1271, 261), (1271, 292), (1307, 246), (1307, 308), (1343, 261), (1343, 292)]
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            if abs(nodes[a][0] - nodes[b][0]) <= 40:
                svg.line(nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1], stroke="#7C86B5", sw=1)
    for nx, ny in nodes:
        svg.circle(nx, ny, 7, fill="#FFFFFF", stroke=NAVY, sw=1.8)
    svg.text(1415, 280, "Transformer\nencoder", size=22)
    arrow(svg, 1418, 329, 1418, 354, color=NAVY, sw=3)
    svg.rect(1235, 357, 315, 44, rx=7, fill="#F1EFF8", stroke="#7486B3", sw=1)
    svg.text(1393, 385, "Reconstruction loss", size=21)
    arrow(svg, 1569, 276, 1614, 276, color=NAVY, sw=4)
    svg.text(1638, 157, "48-d\nembedding", size=16)
    svg.rect(1636, 193, 41, 196, rx=8, fill="#FFFFFF", stroke=STROKE, sw=1)
    for i, c in enumerate([NAVY, "#0A4C99", "#176BA9", "#DCEAF7", "#C6B9DD", "#B5A8D7"]):
        svg.circle(1656, 210 + i * 27, 8, fill=c, stroke=c, sw=0)
    svg.text(1656, 312, "⋮", size=28)

    # Inter-card arrows
    arrow(svg, 349, 223, 389, 223)
    arrow(svg, 703, 223, 743, 223)
    arrow(svg, 1166, 223, 1200, 223)

    # Long connector from SSL card to phenotype discovery
    svg.path("M1434,425 V458 H236 Q236,458 236,474 V481", stroke=NAVY, sw=2.8, marker="arrow")

    # Bottom cards
    card(svg, 19, 486, 508, 281, "Phenotype discovery", "url(#grad_purple)", title_size=24)
    svg.text(121, 571, "PCA", size=18)
    scatter_pca(svg, 40, 560)
    svg.text(283, 571, "k-means clustering", size=18)
    kmeans_clusters(svg, 219, 585)
    svg.text(446, 571, "Phenotypes", size=18)
    svg.rect(415, 592, 72, 39, rx=7, fill="#BFD4EC", stroke="#88A7C7", sw=1)
    svg.rect(415, 640, 72, 39, rx=7, fill="#D8D0E8", stroke="#B6A8D3", sw=1)
    svg.rect(415, 688, 72, 39, rx=7, fill="#FFF1A7", stroke="#E9D269", sw=1)
    svg.text(451, 617, "P0", size=20)
    svg.text(451, 665, "P1", size=20)
    svg.text(451, 713, "P2", size=20)
    arrow(svg, 197, 649, 225, 649, sw=3)
    arrow(svg, 361, 649, 396, 649, sw=3)

    card(svg, 574, 486, 486, 281, "Temporal survey validation", "url(#grad_blue)", title_size=24)
    svg.rect(597, 588, 111, 134, rx=8, fill="#FFF4B5", stroke="#E5D27A", sw=1)
    calendar_icon(svg, 634, 608, scale=0.95)
    svg.text(653, 677, "2022–2023\nhold-out cycle", size=17)
    svg.text(777, 570, "Endpoints", size=18, fill=NAVY, weight="700")
    endpoints = [
        ("Contraceptive vulnerability", "shield"),
        ("Fertility / loss help", "plus"),
        ("Mistimed / unwanted pregnancy", "clock"),
        ("Adverse pregnancy history", "warning"),
        ("Fecundity limitation / infertility", "uterus"),
    ]
    for i, (txt, kind) in enumerate(endpoints):
        yy = 596 + i * 35
        if kind == "shield":
            shield_icon(svg, 752, yy - 16, NAVY)
        elif kind == "plus":
            svg.rect(753, yy - 15, 22, 22, rx=2, fill="none", stroke=NAVY, sw=2)
            svg.line(764, yy - 11, 764, yy + 3, stroke=NAVY, sw=2)
            svg.line(757, yy - 4, 771, yy - 4, stroke=NAVY, sw=2)
        elif kind == "clock":
            svg.circle(764, yy - 4, 12, fill="none", stroke=NAVY, sw=2)
            svg.line(764, yy - 4, 764, yy - 12, stroke=NAVY, sw=2)
            svg.line(764, yy - 4, 771, yy + 1, stroke=NAVY, sw=2)
        elif kind == "warning":
            svg.polygon(f"764,{yy-20} 779,{yy+7} 749,{yy+7}", fill="none", stroke=NAVY, sw=2)
            svg.line(764, yy - 10, 764, yy - 1, stroke=NAVY, sw=2)
            svg.circle(764, yy + 3, 1.5, fill=NAVY, stroke=NAVY, sw=0)
        else:
            svg.path(f"M753,{yy-14} C760,{yy-22} 768,{yy-22} 775,{yy-14} M764,{yy-13} V{yy+10} M753,{yy+4} C755,{yy-1} 773,{yy-1} 775,{yy+4}", stroke=NAVY, sw=2)
        svg.text(798, yy + 1, txt, size=17, anchor="start")

    card(svg, 1107, 486, 618, 281, "Robustness checks", "url(#grad_blue2)", title_size=24)
    separators = [1253, 1420, 1578]
    for xx in separators:
        svg.line(xx, 561, xx, 740, stroke="#B9C5D0", sw=1.2, dash="3 6")
    # Adjusted models
    svg.line(1156, 595, 1188, 595, stroke=NAVY, sw=2)
    svg.polygon("1159,595 1172,565 1185,595", fill="none", stroke=NAVY, sw=2)
    svg.line(1135, 610, 1182, 610, stroke=NAVY, sw=2)
    svg.polygon("1138,610 1153,579 1168,610", fill="none", stroke=NAVY, sw=2)
    svg.text(1179, 643, "Adjusted\nmodels", size=17, weight="700")
    svg.text(1179, 699, "Survey-weighted\nlogistic models", size=15)
    # Ever-pregnant
    svg.circle(1334, 580, 17, fill="none", stroke=NAVY, sw=2)
    svg.path("M1334,598 V628 M1310,615 C1320,605 1348,605 1358,615", stroke=NAVY, sw=2)
    svg.path("M1321,580 C1322,558 1351,558 1352,580", stroke=NAVY, sw=2)
    svg.text(1335, 643, "Ever-pregnant\nstratum", size=17, weight="700")
    svg.text(1335, 704, "Restrict to\nrespondents with\nany pregnancy", size=14)
    # Age sensitivity
    svg.circle(1499, 581, 17, fill="none", stroke=NAVY, sw=2)
    svg.path("M1499,598 V628 M1478,615 C1489,604 1510,604 1521,615", stroke=NAVY, sw=2)
    svg.path("M1514,563 Q1527,555 1519,574", stroke=NAVY, sw=2)
    svg.text(1500, 643, "Age 15–49\nsensitivity", size=17, weight="700")
    svg.text(1500, 704, "Alternate age\nrange analysis", size=14)
    # Baseline methods
    bars = [(1630, 592, 20), (1643, 574, 38), (1656, 557, 55), (1669, 584, 28)]
    for bx, by, bh in bars:
        svg.rect(bx, by, 9, bh, fill=NAVY, stroke=NAVY, sw=0)
    svg.text(1650, 643, "Baseline\nmethods", size=17, weight="700")
    svg.text(1650, 704, "PCA, MCA, LCA,\nElastic-net,\nLightGBM", size=14)

    arrow(svg, 528, 622, 571, 622)
    arrow(svg, 1062, 622, 1104, 622)

    # Legend
    legend = [
        (250, NAVY, "NSFG data & harmonization"),
        (541, BLUE, "Data representation"),
        (782, PURPLE, "Representation learning & phenotyping"),
        (1161, YELLOW, "Temporal validation"),
        (1390, "#FFFFFF", "Masked elements"),
    ]
    for x, col, label in legend:
        if label == "Masked elements":
            svg.rect(x, 822, 23, 23, rx=2, fill="#FFF7EB", stroke=ORANGE, sw=2)
            for off in range(-18, 30, 8):
                svg.line(x + off, 845, x + off + 22, 823, stroke=ORANGE, sw=1.2)
        else:
            svg.rect(x, 822, 23, 23, rx=2, fill=col, stroke=col, sw=1)
        svg.text(x + 35, 840, label, size=16, anchor="start")

    svg.add("</svg>")
    OUT.write_text("\n".join(svg.parts), encoding="utf-8")
    ET.parse(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
