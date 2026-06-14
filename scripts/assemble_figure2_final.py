"""Assemble final Figure 2 from source-rendered panel PDFs.

The panel contents remain source-code-first renders from the project data:
- F2A/F2B/F2C: scripts/prism_panelwise_redraw_20260605.py
- F2D: figure_redraw/figure2D_endpoint_prevalence_20260606/scripts/

This script only performs the final-size layout step and synchronizes the
assembled Figure 2 to results/figures, manuscript/latex/figures, and
figure_redraw/fig.
"""

from __future__ import annotations

from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
PANEL_ROOT = ROOT / "figure_redraw" / "panelwise_persist_prism_20260605" / "outputs"
F2D_ROOT = ROOT / "figure_redraw" / "figure2D_endpoint_prevalence_20260606" / "outputs" / "F2D"
RESULT_FIGURES = ROOT / "results" / "figures"
LATEX_FIGURES = ROOT / "manuscript" / "latex" / "figures"
FINAL_FIG_DIR = ROOT / "figure_redraw" / "fig"

PANEL_PDFS = {
    "A": PANEL_ROOT / "F2A" / "F2A__v1__HF191_2026-04-18_e0fa957a.pdf",
    "B": PANEL_ROOT / "F2B" / "F2B__v1__native_prism_domain_missingness_matrix.pdf",
    "C": PANEL_ROOT / "F2C" / "F2C__v1__HF052_2025-08-05_47ae15c2.pdf",
    "D": F2D_ROOT / "F2D__v1__native_prism_endpoint_prevalence_matrix.pdf",
}

INK_RGB = (31 / 255, 36 / 255, 48 / 255)
PT_PER_MM = 72 / 25.4
PAGE_W = 180 * PT_PER_MM
PAGE_H = 116 * PT_PER_MM


def show_panel(page: fitz.Page, label: str, pdf_path: Path, rect: fitz.Rect, add_label: bool = True) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    src = fitz.open(str(pdf_path))
    content = fitz.Rect(rect)
    if add_label:
        page.insert_text(
            fitz.Point(rect.x0, rect.y0 + 9.0),
            label,
            fontsize=8.5,
            fontname="helv",
            color=INK_RGB,
        )
        content.x0 += 14
    page.show_pdf_page(content, src, 0, keep_proportion=True)
    src.close()


def render_png(pdf_path: Path, png_path: Path) -> None:
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=360, alpha=False)
    pix.save(str(png_path))
    doc.close()


def render_svg(pdf_path: Path, svg_path: Path) -> None:
    doc = fitz.open(str(pdf_path))
    svg_path.write_text(doc[0].get_svg_image(text_as_path=False), encoding="utf-8")
    doc.close()


def main() -> None:
    for directory in [RESULT_FIGURES, LATEX_FIGURES, FINAL_FIG_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, PAGE_H), color=None, fill=(1, 1, 1))

    slots = {
        "A": fitz.Rect(14, 14, 226, 146),
        "B": fitz.Rect(246, 14, 503, 146),
        "C": fitz.Rect(14, 151, 226, 316),
        "D": fitz.Rect(235, 147, 503, 319),
    }
    show_panel(page, "A", PANEL_PDFS["A"], slots["A"], add_label=True)
    show_panel(page, "B", PANEL_PDFS["B"], slots["B"], add_label=True)
    show_panel(page, "C", PANEL_PDFS["C"], slots["C"], add_label=True)
    page.insert_text(
        fitz.Point(slots["D"].x0, slots["D"].y0 + 9.0),
        "D",
        fontsize=8.5,
        fontname="helv",
        color=INK_RGB,
    )
    show_panel(page, "D", PANEL_PDFS["D"], slots["D"], add_label=False)

    pdf_out = RESULT_FIGURES / "figure2_matrix_missingness.pdf"
    doc.save(str(pdf_out), garbage=4, deflate=True)
    doc.close()

    render_png(pdf_out, RESULT_FIGURES / "figure2_matrix_missingness.png")
    render_svg(pdf_out, RESULT_FIGURES / "figure2_matrix_missingness.svg")

    for ext in [".pdf", ".png", ".svg"]:
        src = RESULT_FIGURES / f"figure2_matrix_missingness{ext}"
        (LATEX_FIGURES / src.name).write_bytes(src.read_bytes())
    for ext in [".pdf", ".png"]:
        src = RESULT_FIGURES / f"figure2_matrix_missingness{ext}"
        (FINAL_FIG_DIR / f"fig2{ext}").write_bytes(src.read_bytes())

    print(
        {
            "figure2_pdf": str(pdf_out),
            "latex_pdf": str(LATEX_FIGURES / "figure2_matrix_missingness.pdf"),
            "page_size_pt": [round(PAGE_W, 2), round(PAGE_H, 2)],
        }
    )


if __name__ == "__main__":
    main()
