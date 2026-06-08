"""
Format Extractor - Extracts visual format information from PDF resumes.
Uses PyMuPDF (fitz) to analyze fonts, colors, layout, and spacing.
"""

import fitz
import json
from collections import Counter
from typing import Dict, Any


def extract_format_metadata(pdf_filepath: str) -> Dict[str, Any]:
    """
    Extract visual format metadata from a PDF file.
    
    Args:
        pdf_filepath: Path to the PDF file
        
    Returns:
        Dict containing format metadata including fonts, colors, margins, layout
    """
    doc = fitz.open(pdf_filepath)
    
    if len(doc) == 0:
        raise ValueError("PDF has no pages")
    
    # Get first page for primary formatting
    first_page = doc[0]
    page_width = first_page.rect.width
    page_height = first_page.rect.height
    
    # Extract text with font information
    text_dict = first_page.get_text("dict")
    
    fonts_info = []
    colors_info = []
    text_blocks = []
    
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    fonts_info.append({
                        "font": span.get("font", "unknown"),
                        "size": span.get("size", 0),
                        "flags": span.get("flags", 0),
                        "color": span.get("color", 0)
                    })
                    colors_info.append(span.get("color", 0))
                    text_blocks.append({
                        "text": span.get("text", "").strip(),
                        "font": span.get("font", "unknown"),
                        "size": span.get("size", 0),
                        "bbox": span.get("bbox", [0, 0, 0, 0])
                    })
    
    # Analyze fonts
    font_sizes = Counter([f["size"] for f in fonts_info])
    most_common_size = font_sizes.most_common(1)[0][0] if font_sizes else 11
    
    # Find heading and body fonts
    heading_fonts = []
    body_fonts = []
    name_fonts = []
    
    for info in fonts_info:
        if info["size"] >= 14:
            heading_fonts.append(info["font"])
        elif info["size"] >= 10:
            body_fonts.append(info["font"])
        if info["size"] >= 16:
            name_fonts.append(info["font"])
    
    primary_font = Counter(body_fonts).most_common(1)[0][0] if body_fonts else "Arial"
    heading_font = Counter(heading_fonts).most_common(1)[0][0] if heading_fonts else primary_font
    name_font = Counter(name_fonts).most_common(1)[0][0] if name_fonts else heading_font
    
    # Analyze layout - detect columns
    x_positions = [b["bbox"][0] for b in text_blocks if b["text"]]
    is_two_column = _detect_columns(x_positions, page_width)
    
    # Detect margins
    left_margin = min([b["bbox"][0] for b in text_blocks if b["text"] and b["bbox"][0] > 0]) if x_positions else 50
    right_margin = page_width - max([b["bbox"][2] for b in text_blocks if b["text"]]) if x_positions else 50
    top_margin = min([b["bbox"][1] for b in text_blocks if b["text"] and b["bbox"][1] > 0]) if text_blocks else 50
    
    # Detect colors
    primary_color = _int_to_hex(Counter(colors_info).most_common(1)[0][0]) if colors_info else "#1a1a1a"
    accent_color = _int_to_hex(Counter(colors_info).most_common(3)[0][0]) if len(Counter(colors_info).most_common(3)) > 0 else "#2563eb"
    
    # Detect bullet style
    bullet_style = _detect_bullet_style(text_blocks)
    
    # Detect sections
    sections_detected = _detect_sections(text_blocks)
    
    # Check for horizontal rules and sidebar
    has_horizontal_rule = _check_horizontal_rule(first_page)
    has_sidebar = is_two_column and left_margin > 100
    
    # Determine layout type
    if has_sidebar:
        layout_type = "sidebar_left" if left_margin < page_width / 3 else "sidebar_right"
    elif is_two_column:
        layout_type = "two_column"
    else:
        layout_type = "single_column"
    
    doc.close()
    
    return {
        "page_width": page_width,
        "page_height": page_height,
        "is_two_column": is_two_column,
        "primary_font": primary_font,
        "heading_font": heading_font,
        "name_font": name_font,
        "body_font_size": most_common_size,
        "heading_font_size": 14.0,
        "name_font_size": 18.0,
        "primary_color": primary_color,
        "accent_color": accent_color,
        "background_color": "#ffffff",
        "left_margin": left_margin,
        "right_margin": right_margin,
        "top_margin": top_margin,
        "section_spacing": 20.0,
        "bullet_style": bullet_style,
        "sections_detected": sections_detected,
        "has_horizontal_rule": has_horizontal_rule,
        "has_sidebar": has_sidebar,
        "layout_type": layout_type
    }


def _detect_columns(x_positions: list, page_width: float) -> bool:
    """Detect if the page has two columns based on x positions."""
    if not x_positions:
        return False
    
    # Group x positions into clusters
    min_x = min(x_positions)
    max_x = max(x_positions)
    width = max_x - min_x
    
    if width < page_width * 0.5:
        return False
    
    # Use a simple heuristic: if there's a significant gap in the middle
    mid = page_width / 2
    left_count = sum(1 for x in x_positions if x < mid - 50)
    right_count = sum(1 for x in x_positions if x > mid + 50)
    
    return left_count > 10 and right_count > 10


def _int_to_hex(color_int: int) -> str:
    """Convert integer color to hex string."""
    if color_int == 0:
        return "#000000"
    try:
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except:
        return "#1a1a1a"


def _detect_bullet_style(text_blocks: list) -> str:
    """Detect the bullet style used in the resume."""
    bullet_chars = ["•", "-", "▪", "–", "○", "●"]
    
    for block in text_blocks:
        text = block.get("text", "")
        if text:
            first_char = text[0].strip()
            if first_char in bullet_chars:
                return first_char
            if text.startswith("  ") and len(text) > 2:
                return "•"
    
    return "•"


def _detect_sections(text_blocks: list) -> list:
    """Detect common resume sections from text blocks."""
    section_keywords = {
        "summary": ["summary", "objective", "profile", "about"],
        "experience": ["experience", "employment", "work history", "professional experience"],
        "education": ["education", "academic", "qualification"],
        "skills": ["skills", "technical skills", "competencies", "expertise"],
        "projects": ["projects", "project"],
        "certifications": ["certifications", "certificates", "credentials"],
        "additional": ["publications", "awards", "volunteer", "languages"]
    }
    
    detected = []
    text_lower = " ".join([b.get("text", "").lower() for b in text_blocks])
    
    for section, keywords in section_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                detected.append(section.capitalize())
                break
    
    # Ensure order
    order = ["Summary", "Experience", "Education", "Skills", "Projects", "Certifications"]
    result = []
    for s in order:
        if s in detected:
            result.append(s)
    for s in detected:
        if s not in result:
            result.append(s)
    
    return result if result else ["Summary", "Experience", "Education", "Skills"]


def _check_horizontal_rule(page) -> bool:
    """Check if page has horizontal rules."""
    try:
        annots = page.annots()
        if annots:
            return True
        # Check for lines in drawings
        drawings = page.get_drawings()
        for drawing in drawings:
            if drawing.get("type") == "line":
                return True
    except:
        pass
    return False


# For testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        metadata = extract_format_metadata(sys.argv[1])
        print(json.dumps(metadata, indent=2))
