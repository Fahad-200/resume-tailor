"""
PDF Generator - Generates PDF resumes using WeasyPrint (HTML to PDF).
Falls back to reportlab if WeasyPrint is unavailable.
"""

import os
import json
from typing import Dict, Any, Optional

# Try to import WeasyPrint, fallback to reportlab if not available
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    pass

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# Font mappings for common resume fonts
FONT_MAPPINGS = {
    "Calibri": "Carlito",
    "Times New Roman": "Liberation Serif",
    "Arial": "Liberation Sans",
    "Helvetica": "Liberation Sans",
    "Georgia": "Georgia",
    "Verdana": "Verdana"
}


def generate(new_content: Dict[str, Any], format_metadata: Dict[str, Any], 
             output_filename: str, output_dir: str = "outputs") -> str:
    """
    Generate a PDF from resume content using extracted format metadata.
    
    Args:
        new_content: The structured resume content
        format_metadata: Format info from original PDF
        output_filename: Output filename (without extension)
        output_dir: Output directory path
        
    Returns:
        Path to generated PDF file
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{output_filename}.pdf")
    
    if WEASYPRINT_AVAILABLE:
        try:
            return _generate_with_weasyprint(new_content, format_metadata, output_path)
        except Exception as e:
            print(f"WeasyPrint failed: {e}, trying reportlab")
    
    if REPORTLAB_AVAILABLE:
        return _generate_with_reportlab(new_content, format_metadata, output_path)
    
    raise RuntimeError("Neither WeasyPrint nor ReportLab is available. Please install one of them.")


def _generate_with_weasyprint(content: Dict[str, Any], metadata: Dict[str, Any], 
                               output_path: str) -> str:
    """Generate PDF using WeasyPrint."""
    
    # Map fonts
    body_font = FONT_MAPPINGS.get(metadata.get("primary_font", "Arial"), "Arial")
    heading_font = FONT_MAPPINGS.get(metadata.get("heading_font", "Georgia"), "Georgia")
    
    # Determine page size
    page_width = metadata.get("page_width", 612)  # Default to letter
    page_height = metadata.get("page_height", 792)
    
    # Convert points to mm for WeasyPrint (1pt = 0.352778mm)
    page_width_mm = page_width * 0.352778
    page_height_mm = page_height * 0.352778
    
    # Get margins
    left_margin = metadata.get("left_margin", 50) * 0.352778
    right_margin = metadata.get("right_margin", 50) * 0.352778
    top_margin = metadata.get("top_margin", 50) * 0.352778
    
    bullet = metadata.get("bullet_style", "•")
    
    # Build HTML
    html = _build_html_content(content, metadata, body_font, heading_font, bullet)
    
    # Create CSS
    css_string = f"""
        @page {{
            size: {page_width_mm}mm {page_height_mm}mm;
            margin: {top_margin}mm {right_margin}mm {top_margin}mm {left_margin}mm;
        }}
        body {{
            font-family: {body_font}, Arial, sans-serif;
            font-size: {metadata.get('body_font_size', 11)}pt;
            color: {metadata.get('primary_color', '#1a1a1a')};
            line-height: 1.4;
        }}
        h1, h2, h3 {{
            font-family: {heading_font}, Georgia, serif;
            color: {metadata.get('accent_color', '#2563eb')};
        }}
        .name {{
            font-size: {metadata.get('name_font_size', 18)}pt;
            font-weight: bold;
        }}
        .section-title {{
            font-size: {metadata.get('heading_font_size', 14)}pt;
            font-weight: bold;
            border-bottom: 1px solid #ccc;
            margin-bottom: 8px;
        }}
        .contact-line {{
            font-size: 10pt;
            color: #666;
        }}
        ul {{
            margin-left: 15px;
            padding-left: 0;
        }}
        li {{
            margin-bottom: 4px;
        }}
    """
    
    HTML(string=html).write_pdf(output_path, stylesheets=[CSS(string=css_string)])
    return output_path


def _build_html_content(content: Dict[str, Any], metadata: Dict[str, Any],
                        body_font: str, heading_font: str, bullet: str) -> str:
    """Build HTML string from resume content."""
    
    layout_type = metadata.get("layout_type", "single_column")
    
    if layout_type == "single_column":
        return _build_single_column_html(content, metadata, bullet)
    elif layout_type in ["two_column", "sidebar_left", "sidebar_right"]:
        return _build_two_column_html(content, metadata, bullet)
    else:
        return _build_single_column_html(content, metadata, bullet)


def _build_single_column_html(content: Dict[str, Any], metadata: Dict[str, Any], 
                               bullet: str) -> str:
    """Build single column layout HTML."""
    
    contact = content.get("contact", {})
    html_parts = []
    
    # Name
    name = contact.get("name", "Your Name")
    html_parts.append(f'<h1 class="name">{name}</h1>')
    
    # Contact info
    contact_parts = []
    if contact.get("email"):
        contact_parts.append(contact["email"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("location"):
        contact_parts.append(contact["location"])
    if contact.get("linkedin"):
        contact_parts.append(contact["linkedin"])
    
    if contact_parts:
        html_parts.append(f'<p class="contact-line">{" | ".join(contact_parts)}</p>')
    
    # Horizontal rule
    if metadata.get("has_horizontal_rule", False):
        html_parts.append('<hr/>')
    
    # Summary
    if content.get("summary"):
        html_parts.append(f'<h2 class="section-title">Summary</h2>')
        html_parts.append(f'<p>{content["summary"]}</p>')
    
    # Experience
    if content.get("experience"):
        html_parts.append(f'<h2 class="section-title">Experience</h2>')
        for exp in content["experience"]:
            title = exp.get("title", "")
            company = exp.get("company", "")
            dates = f"{exp.get('start_date', '')} - {exp.get('end_date', '')}"
            
            html_parts.append(f'<p><strong>{title}</strong> at {company}<br/><em>{dates}</em></p>')
            
            if exp.get("bullets"):
                html_parts.append('<ul>')
                for b in exp["bullets"]:
                    html_parts.append(f'<li>{b}</li>')
                html_parts.append('</ul>')
    
    # Education
    if content.get("education"):
        html_parts.append(f'<h2 class="section-title">Education</h2>')
        for edu in content["education"]:
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            institution = edu.get("institution", "")
            year = edu.get("graduation_year", "")
            
            html_parts.append(f'<p><strong>{degree}{" in " + field if field else ""}</strong><br/>{institution}{", " + year if year else ""}</p>')
    
    # Skills
    if content.get("skills"):
        html_parts.append(f'<h2 class="section-title">Skills</h2>')
        skills = content["skills"]
        
        for skill_type, skill_list in skills.items():
            if skill_list:
                html_parts.append(f'<p><strong>{skill_type.capitalize()}:</strong> {", ".join(skill_list)}</p>')
    
    # Projects
    if content.get("projects"):
        html_parts.append(f'<h2 class="section-title">Projects</h2>')
        for proj in content["projects"]:
            html_parts.append(f'<p><strong>{proj.get("name", "")}</strong>: {proj.get("description", "")}</p>')
            if proj.get("technologies"):
                html_parts.append(f'<p><em>Technologies: {", ".join(proj["technologies"])}</em></p>')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"/></head>
    <body>
    {"".join(html_parts)}
    </body>
    </html>
    """


def _build_two_column_html(content: Dict[str, Any], metadata: Dict[str, Any],
                           bullet: str) -> str:
    """Build two column layout HTML."""
    # For now, treat two-column as single column with wider margins
    # A full implementation would use CSS Grid
    return _build_single_column_html(content, metadata, bullet)


def _generate_with_reportlab(content: Dict[str, Any], metadata: Dict[str, Any],
                              output_path: str) -> str:
    """Generate PDF using ReportLab as fallback."""
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor(metadata.get('accent_color', '#2563eb'))
    )
    
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor(metadata.get('accent_color', '#2563eb')),
        spaceAfter=6
    )
    
    # Name
    contact = content.get("contact", {})
    name = contact.get("name", "Your Name")
    story.append(Paragraph(name, title_style))
    
    # Contact
    contact_parts = []
    for key in ["email", "phone", "location", "linkedin"]:
        if contact.get(key):
            contact_parts.append(contact[key])
    
    if contact_parts:
        story.append(Paragraph(" | ".join(contact_parts), styles['Normal']))
    
    story.append(Spacer(1, 12))
    
    # Summary
    if content.get("summary"):
        story.append(Paragraph("Summary", section_style))
        story.append(Paragraph(content["summary"], styles['Normal']))
        story.append(Spacer(1, 6))
    
    # Experience
    if content.get("experience"):
        story.append(Paragraph("Experience", section_style))
        for exp in content["experience"]:
            title_text = f"<b>{exp.get('title', '')}</b> at {exp.get('company', '')}"
            story.append(Paragraph(title_text, styles['Normal']))
            
            dates = f"{exp.get('start_date', '')} - {exp.get('end_date', '')}"
            story.append(Paragraph(f"<i>{dates}</i>", styles['Normal']))
            
            if exp.get("bullets"):
                for bullet_text in exp["bullets"]:
                    story.append(Paragraph(f"• {bullet_text}", styles['Normal']))
            story.append(Spacer(1, 6))
    
    # Education
    if content.get("education"):
        story.append(Paragraph("Education", section_style))
        for edu in content["education"]:
            edu_text = f"<b>{edu.get('degree', '')}</b> in {edu.get('field', '')}"
            story.append(Paragraph(edu_text, styles['Normal']))
            story.append(Paragraph(edu.get('institution', ''), styles['Normal']))
            story.append(Spacer(1, 6))
    
    # Skills
    if content.get("skills"):
        story.append(Paragraph("Skills", section_style))
        skills = content["skills"]
        for skill_type, skill_list in skills.items():
            if skill_list:
                story.append(Paragraph(
                    f"<b>{skill_type.capitalize()}:</b> {', '.join(skill_list)}",
                    styles['Normal']
                ))
    
    doc.build(story)
    return output_path


# For testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'r') as f:
            content = json.load(f)
        with open(sys.argv[3], 'r') as f:
            metadata = json.load(f)
        result = generate(content, metadata, sys.argv[1])
        print(f"Generated: {result}")
