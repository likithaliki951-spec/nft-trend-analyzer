"""
Convert Markdown documentation files to polished PDF documents using ReportLab Platypus.
"""
import os
import re
import html
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

DOC_DIR = Path(__file__).resolve().parent

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw 'Page X of Y' in footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 11 * inch - 36, "NFT Trend Analyzer — Academic Project Documentation & Viva Guide")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)

        # Footer
        text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 54, 36, text)
        self.drawString(54, 36, "Confidential — Prepared for Academic Examination & Viva Voce")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 46, 8.5 * inch - 54, 46)
        self.restoreState()


def get_styles():
    styles = getSampleStyleSheet()

    # Custom styles
    primary = colors.HexColor("#1e293b")
    brand = colors.HexColor("#0284c7")
    accent = colors.HexColor("#0f172a")

    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=accent,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=brand,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0369a1"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        'H3',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=5,
    ))

    styles.add(ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f8fafc"),
        leftIndent=8,
        rightIndent=8,
        spaceBefore=4,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=12,
        rightIndent=12,
        spaceBefore=4,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1e293b"),
    ))

    styles.add(ParagraphStyle(
        'TableCellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
    ))

    return styles


def format_inline_markdown(text):
    """Escapes html and converts markdown inline styles: code, bold, italic."""
    # First protect existing xml/html entities
    text = html.escape(text)

    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#0369a1"><b>\1</b></font>', text)
    # Bold italic: ***text***
    text = re.sub(r'\*\*\*([^\*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold: **text**
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', text)
    # Italic: *text* or _text_
    text = re.sub(r'(?<!\*)\*([^\*]+)\*(?!\*)', r'<i>\1</i>', text)
    # LaTeX math simplifications for reportlab
    text = re.sub(r'\\(?:le|leq)', '&le;', text)
    text = re.sub(r'\\(?:ge|geq)', '&ge;', text)
    text = re.sub(r'\\times', '&times;', text)
    text = re.sub(r'\\approx', '&approx;', text)
    text = re.sub(r'\\in', '&isin;', text)
    text = re.sub(r'\\ne', '&ne;', text)
    text = re.sub(r'\\mu', '&mu;', text)
    text = re.sub(r'\\sigma', '&sigma;', text)
    text = re.sub(r'\\lambda', '&lambda;', text)
    text = re.sub(r'\\Sigma', '&Sigma;', text)
    text = re.sub(r'\\beta', '&beta;', text)
    text = re.sub(r'\\gamma', '&gamma;', text)
    text = re.sub(r'\\theta', '&theta;', text)
    text = re.sub(r'\\rho', '&rho;', text)
    text = re.sub(r'\\rightarrow', '&rarr;', text)
    text = re.sub(r'\\to', '&rarr;', text)
    text = re.sub(r'\$([^\$]+)\$', r'<font name="Courier-Oblique">\1</font>', text)
    return text


def parse_markdown_to_flowables(md_content, styles):
    flowables = []
    lines = md_content.splitlines()
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []
    first_title = True

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code block fence
        if line.strip().startswith('```'):
            if in_code_block:
                # end of code block
                code_text = html.escape("\n".join(code_lines))
                # wrap in table for nice border
                p = Paragraph(f"<pre>{code_text}</pre>", styles['CodeBlock'])
                t = Table([[p]], colWidths=[7.0 * inch])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                    ('PADDING', (0,0), (-1,-1), 4),
                ]))
                flowables.append(t)
                flowables.append(Spacer(1, 4))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Tables
        if line.strip().startswith('|') and '|' in line.strip()[1:]:
            in_table = True
            table_lines.append(line.strip())
            i += 1
            continue
        elif in_table:
            # End of table
            table_flowable = create_reportlab_table(table_lines, styles)
            if table_flowable:
                flowables.append(table_flowable)
                flowables.append(Spacer(1, 6))
            table_lines = []
            in_table = False
            # do not continue, process current line below

        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=6, spaceAfter=6))
            i += 1
            continue

        # Headings
        if stripped.startswith('# '):
            text = format_inline_markdown(stripped[2:])
            if first_title:
                flowables.append(Paragraph(text, styles['DocTitle']))
                first_title = False
            else:
                flowables.append(Paragraph(text, styles['H1']))
            i += 1
            continue

        if stripped.startswith('## '):
            text = format_inline_markdown(stripped[3:])
            flowables.append(Paragraph(text, styles['H1']))
            i += 1
            continue

        if stripped.startswith('### '):
            text = format_inline_markdown(stripped[4:])
            flowables.append(Paragraph(text, styles['H2']))
            i += 1
            continue

        if stripped.startswith('#### '):
            text = format_inline_markdown(stripped[5:])
            flowables.append(Paragraph(text, styles['H3']))
            i += 1
            continue

        # Blockquote
        if stripped.startswith('> '):
            text = format_inline_markdown(stripped[2:])
            p = Paragraph(text, styles['Callout'])
            t = Table([[p]], colWidths=[7.0 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
                ('LINELEFT', (0,0), (0,-1), 3, colors.HexColor("#0284c7")),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            flowables.append(t)
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Bullet list
        if stripped.startswith('- ') or stripped.startswith('* '):
            text = "&bull; " + format_inline_markdown(stripped[2:])
            flowables.append(Paragraph(text, styles['BulletItem']))
            i += 1
            continue

        # Numbered list
        num_match = re.match(r'^(\d+\.)\s+(.+)', stripped)
        if num_match:
            prefix = num_match.group(1)
            content = format_inline_markdown(num_match.group(2))
            text = f"<b>{prefix}</b> {content}"
            flowables.append(Paragraph(text, styles['BulletItem']))
            i += 1
            continue

        # Standard Body Paragraph
        text = format_inline_markdown(stripped)
        flowables.append(Paragraph(text, styles['Body']))
        i += 1

    # End of file checks
    if in_table and table_lines:
        t = create_reportlab_table(table_lines, styles)
        if t:
            flowables.append(t)

    return flowables


def create_reportlab_table(table_lines, styles):
    """Parse Markdown table lines into a clean ReportLab Table flowable."""
    if len(table_lines) < 2:
        return None

    raw_rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip('|').split('|')]
        # check if it's separator row like |---|:---|
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        raw_rows.append(cells)

    if not raw_rows:
        return None

    num_cols = max(len(r) for r in raw_rows)
    # normalize columns
    for r in raw_rows:
        while len(r) < num_cols:
            r.append('')

    # Calculate column widths to fit ~7 inches
    total_width = 7.0 * inch
    col_width = total_width / num_cols

    # Convert cells to Paragraph flowables
    table_data = []
    for row_idx, row in enumerate(raw_rows):
        row_data = []
        is_header = (row_idx == 0)
        style = styles['TableCellHeader'] if is_header else styles['TableCell']
        for cell_text in row:
            p_text = format_inline_markdown(cell_text)
            row_data.append(Paragraph(p_text, style))
        table_data.append(row_data)

    table = Table(table_data, colWidths=[col_width] * num_cols, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        ('TOPPADDING', (0,0), (-1,0), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,1), (-1,-1), 4),
    ]))
    return table


def build_pdf(md_filename, pdf_filename):
    md_path = DOC_DIR / md_filename
    pdf_path = DOC_DIR / pdf_filename

    if not md_path.exists():
        print(f"Skipping {md_filename} - file not found.")
        return False

    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = get_styles()
    flowables = parse_markdown_to_flowables(md_content, styles)

    try:
        doc.build(flowables, canvasmaker=NumberedCanvas)
        print(f"Successfully generated: {pdf_filename} ({os.path.getsize(pdf_path):,} bytes)")
        return True
    except Exception as e:
        print(f"Error generating {pdf_filename}: {e}")
        return False


def main():
    docs_to_convert = [
        ("Development_and_Deployment_Report.md", "Development_and_Deployment_Report.pdf"),
        ("Project_Architecture_and_Explanation.md", "Project_Architecture_and_Explanation.pdf"),
        ("Viva_Questions_and_Answers.md", "Viva_Questions_and_Answers.pdf"),
        ("Project_Demo_Script.md", "Project_Demo_Script.pdf"),
        ("Last_24_Hours_Quick_Revision.md", "Last_24_Hours_Quick_Revision.pdf"),
    ]

    print("Building polished ReportLab PDFs for NFT Trend Analyzer...")
    success_count = 0
    for md_file, pdf_file in docs_to_convert:
        if build_pdf(md_file, pdf_file):
            success_count += 1

    print(f"\nPDF Generation Complete: {success_count}/{len(docs_to_convert)} files generated successfully.")


if __name__ == '__main__':
    main()
