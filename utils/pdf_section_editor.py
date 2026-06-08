"""
PDF section editor for layout-preserving resume tailoring.

This module detects editable sections in the uploaded PDF and writes updated
content back into those same page regions so the original layout stays intact.
"""

import re
from collections import Counter
from statistics import median
from typing import Any, Dict, List, Tuple

import fitz


SECTION_ALIASES = {
    "objective": {
        "OBJECTIVE",
        "SUMMARY",
        "PROFILE",
        "ABOUT",
        "PROFESSIONAL SUMMARY",
        "CAREER OBJECTIVE",
    },
    "skills": {
        "SKILLS",
        "CORE SKILLS",
        "KEY SKILLS",
        "COMPETENCIES",
        "EXPERTISE",
        "TECHNICAL SKILLS",
    },
}


BOUNDARY_HEADINGS = {
    "OBJECTIVE",
    "SUMMARY",
    "PROFILE",
    "ABOUT",
    "PROFESSIONAL SUMMARY",
    "CAREER OBJECTIVE",
    "EXPERIENCE",
    "WORK EXPERIENCE",
    "PROFESSIONAL EXPERIENCE",
    "EMPLOYMENT",
    "EDUCATION",
    "SKILLS",
    "CORE SKILLS",
    "KEY SKILLS",
    "TECHNICAL SKILLS",
    "COMPETENCIES",
    "EXPERTISE",
    "PROJECTS",
    "PROJECT WORK",
    "CERTIFICATIONS",
    "LANGUAGES",
    "AWARDS",
    "VOLUNTEER",
    "PUBLICATIONS",
}


FONT_FALLBACKS = [
    ("times", "Times-Roman", "Times-Bold"),
    ("arial", "Helvetica", "Helvetica-Bold"),
    ("helvetica", "Helvetica", "Helvetica-Bold"),
    ("calibri", "Helvetica", "Helvetica-Bold"),
    ("courier", "Courier", "Courier-Bold"),
]


def extract_editable_sections(pdf_filepath: str) -> Dict[str, Any]:
    """
    Extract Objective / Summary and Skills sections from a resume PDF.
    """
    doc = fitz.open(pdf_filepath)
    sections: Dict[str, Dict[str, Any]] = {}

    try:
        for page_index, page in enumerate(doc):
            lines = _extract_page_lines(page)
            headings = []

            for idx, line in enumerate(lines):
                heading_text = _normalize_heading(line["text"])
                if heading_text in BOUNDARY_HEADINGS:
                    headings.append((idx, _canonical_section_name(line["text"])))

            for heading_position, (line_index, section_key) in enumerate(headings):
                next_index = (
                    headings[heading_position + 1][0]
                    if heading_position + 1 < len(headings)
                    else len(lines)
                )
                content_lines = [
                    line for line in lines[line_index + 1:next_index] if line["text"].strip()
                ]
                if not section_key or section_key in sections or not content_lines:
                    continue

                sections[section_key] = _build_section_info(
                    section_key,
                    lines[line_index],
                    content_lines,
                    page_index,
                    page.rect,
                )
    finally:
        doc.close()

    return {"sections": sections}


def extract_skill_categories(section_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse the visual skills block into ordered categories and items.
    """
    categories: List[Dict[str, Any]] = []
    current_category: Dict[str, Any] | None = None

    for line in section_info.get("content_lines", []):
        text = line.get("text", "").strip()
        if not text:
            continue

        if ":" in text and text.index(":") < 40:
            label, remainder = text.split(":", 1)
            current_category = {
                "label": label.strip(),
                "text": remainder.strip(),
            }
            categories.append(current_category)
            continue

        if current_category is None:
            current_category = {"label": "Skills", "text": text}
            categories.append(current_category)
            continue

        current_category["text"] = f"{current_category['text']} {text}".strip()

    normalized_categories: List[Dict[str, Any]] = []
    for category in categories:
        items = [
            item.strip()
            for item in re.split(r"\s*,\s*", category.get("text", ""))
            if item.strip()
        ]
        normalized_categories.append(
            {
                "label": category["label"],
                "items": items,
            }
        )

    return normalized_categories


def categories_to_text(categories: List[Dict[str, Any]]) -> str:
    """Convert skills categories back into plain text for diffs and validation."""
    return "\n".join(
        f"{category['label']}: {', '.join(category.get('items', []))}".strip()
        for category in categories
        if category.get("label")
    )


def build_uploaded_style_profile(
    editable_sections: Dict[str, Dict[str, Any]],
    format_metadata: Dict[str, Any],
) -> str:
    """
    Build a compact writing / layout style hint from the uploaded PDF.
    """
    objective_text = editable_sections.get("objective", {}).get("text", "").strip()
    skills_text = editable_sections.get("skills", {}).get("text", "").strip()

    objective_sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", objective_text)
        if sentence.strip()
    ]
    sentence_lengths = [len(sentence.split()) for sentence in objective_sentences]
    average_sentence_length = round(sum(sentence_lengths) / len(sentence_lengths), 1) if sentence_lengths else 0

    bullet_style = format_metadata.get("bullet_style", "none")
    body_font_size = round(float(format_metadata.get("body_font_size", 10)), 1)
    heading_font = format_metadata.get("heading_font", "unknown")
    layout_type = format_metadata.get("layout_type", "single_column")

    style_notes = [
        f"Layout: {layout_type}",
        f"Heading font family: {heading_font}",
        f"Body font size: {body_font_size}pt",
        f"Objective sentence count: {len(objective_sentences)}",
        f"Average objective sentence length: {average_sentence_length} words",
        f"Skills format: comma-separated category lines",
        f"Bullet style observed: {bullet_style}",
    ]

    if objective_text:
        style_notes.append(f"Objective voice sample: {objective_text}")
    if skills_text:
        style_notes.append(f"Skills formatting sample: {skills_text}")

    return "\n".join(style_notes)


def build_searchable_resume_text(
    original_resume_text: str,
    section_updates: Dict[str, Dict[str, Any]],
) -> str:
    """
    Build searchable text for ATS scoring after section-only updates.
    """
    updated_parts = [original_resume_text.strip()]

    for section_key in ["objective", "skills"]:
        update = section_updates.get(section_key)
        if not update:
            continue
        updated_text = update.get("text", "").strip()
        if updated_text:
            updated_parts.append(updated_text)

    return "\n\n".join(part for part in updated_parts if part)


def apply_section_updates(
    source_pdf_path: str,
    editable_sections: Dict[str, Dict[str, Any]],
    section_updates: Dict[str, Dict[str, Any]],
    output_path: str,
) -> str:
    """
    Apply section updates directly to the original PDF and save a real PDF.
    """
    doc = fitz.open(source_pdf_path)

    try:
        pages_with_redactions = set()

        for section_key, update in section_updates.items():
            section_info = editable_sections.get(section_key)
            if not section_info or not update:
                continue

            page = doc[section_info["page_index"]]
            rect = fitz.Rect(section_info["content_rect"])
            page.add_redact_annot(rect, fill=(1, 1, 1))
            pages_with_redactions.add(section_info["page_index"])

        for page_index in pages_with_redactions:
            doc[page_index].apply_redactions()

        for section_key, update in section_updates.items():
            section_info = editable_sections.get(section_key)
            if not section_info or not update:
                continue

            page = doc[section_info["page_index"]]
            if section_key == "objective":
                _render_objective(page, section_info, update.get("text", ""))
            elif section_key == "skills":
                _render_skills(page, section_info, update.get("categories", []))

        doc.save(output_path)
    finally:
        doc.close()

    return output_path


def _extract_page_lines(page: fitz.Page) -> List[Dict[str, Any]]:
    data = page.get_text("dict")
    lines: List[Dict[str, Any]] = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue

            font_names = [span.get("font", "") for span in spans if span.get("font")]
            font_sizes = [span.get("size", 0) for span in spans if span.get("size")]
            color_values = [span.get("color", 0) for span in spans]

            lines.append(
                {
                    "text": text,
                    "bbox": list(line.get("bbox", [0, 0, 0, 0])),
                    "font": Counter(font_names).most_common(1)[0][0] if font_names else "",
                    "size": median(font_sizes) if font_sizes else 10.0,
                    "color": Counter(color_values).most_common(1)[0][0] if color_values else 0,
                    "is_bold": any("bold" in font.lower() for font in font_names),
                }
            )

    lines.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    return lines


def _canonical_section_name(text: str) -> str | None:
    normalized = _normalize_heading(text)
    for section_key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section_key
    return None


def _normalize_heading(text: str) -> str:
    normalized = re.sub(r"[^A-Za-z ]+", " ", text or "")
    normalized = " ".join(normalized.upper().split())
    return normalized


def _build_section_info(
    section_key: str,
    heading_line: Dict[str, Any],
    content_lines: List[Dict[str, Any]],
    page_index: int,
    page_rect: fitz.Rect,
) -> Dict[str, Any]:
    x0 = min(line["bbox"][0] for line in content_lines)
    y0 = min(line["bbox"][1] for line in content_lines)
    x1 = max(line["bbox"][2] for line in content_lines)
    y1 = max(line["bbox"][3] for line in content_lines)

    font_sizes = [line["size"] for line in content_lines if line.get("size")]
    font_names = [line["font"] for line in content_lines if line.get("font")]
    colors = [line["color"] for line in content_lines]

    regular_font = _map_font_name(
        Counter(font_names).most_common(1)[0][0] if font_names else "Times-Roman",
        bold=False,
    )
    bold_font = _map_font_name(
        heading_line.get("font") or (font_names[0] if font_names else "Times-Bold"),
        bold=True,
    )

    padded_rect = fitz.Rect(
        max(page_rect.x0 + 2, x0 - 2),
        max(page_rect.y0 + 1, y0 - 1),
        min(page_rect.x1 - 2, x1 + 2),
        min(page_rect.y1 - 2, y1 + 1),
    )

    return {
        "page_index": page_index,
        "heading_text": heading_line["text"],
        "heading_rect": heading_line["bbox"],
        "content_rect": list(padded_rect),
        "content_lines": content_lines,
        "text": _section_lines_to_text(section_key, content_lines),
        "style": {
            "font_name": regular_font,
            "bold_font_name": bold_font,
            "font_size": float(median(font_sizes) if font_sizes else 10.0),
            "color": _color_to_rgb(Counter(colors).most_common(1)[0][0] if colors else 0),
            "line_height": _estimate_line_height(content_lines),
        },
    }


def _section_lines_to_text(section_key: str, content_lines: List[Dict[str, Any]]) -> str:
    texts = [line["text"].strip() for line in content_lines if line["text"].strip()]
    if section_key == "objective":
        return " ".join(texts)
    return "\n".join(texts)


def _estimate_line_height(content_lines: List[Dict[str, Any]]) -> float:
    if len(content_lines) > 1:
        sorted_lines = sorted(content_lines, key=lambda item: item["bbox"][1])
        gaps = []
        for previous, current in zip(sorted_lines, sorted_lines[1:]):
            gap = current["bbox"][1] - previous["bbox"][1]
            if gap > 0:
                gaps.append(gap)
        if gaps:
            return float(median(gaps))

    sizes = [line["size"] for line in content_lines if line.get("size")]
    return float((median(sizes) if sizes else 10.0) * 1.3)


def _map_font_name(source_font: str, bold: bool) -> str:
    font_lower = (source_font or "").lower()
    for needle, regular_font, bold_font in FONT_FALLBACKS:
        if needle in font_lower:
            return bold_font if bold else regular_font
    return "Times-Bold" if bold else "Times-Roman"


def _color_to_rgb(color_int: int) -> Tuple[float, float, float]:
    if not color_int:
        return (0, 0, 0)
    r = ((color_int >> 16) & 0xFF) / 255
    g = ((color_int >> 8) & 0xFF) / 255
    b = (color_int & 0xFF) / 255
    return (r, g, b)


def _render_objective(page: fitz.Page, section_info: Dict[str, Any], text: str) -> None:
    rect = fitz.Rect(section_info["content_rect"])
    style = section_info["style"]
    font_size = style["font_size"]
    min_font_size = max(7.5, font_size - 2.0)

    cleaned_text = " ".join((text or "").split())
    while font_size >= min_font_size:
        remaining = page.insert_textbox(
            rect,
            cleaned_text,
            fontname=style["font_name"],
            fontsize=font_size,
            color=style["color"],
            align=0,
        )
        if remaining >= 0:
            return
        font_size -= 0.2

    raise ValueError("Tailored objective text did not fit inside the original PDF section.")


def _render_skills(
    page: fitz.Page,
    section_info: Dict[str, Any],
    categories: List[Dict[str, Any]],
) -> None:
    if not categories:
        return

    rect = fitz.Rect(section_info["content_rect"])
    style = section_info["style"]
    font_size = style["font_size"]
    min_font_size = max(7.5, font_size - 1.5)

    while font_size >= min_font_size:
        lines = _build_skills_render_lines(
            categories,
            rect.width,
            style["font_name"],
            style["bold_font_name"],
            font_size,
        )
        line_height = max(style["line_height"] * (font_size / style["font_size"]), font_size * 1.18)
        if len(lines) * line_height <= rect.height + 1:
            current_y = rect.y0
            for line in lines:
                page.insert_text(
                    (rect.x0, current_y + font_size),
                    line["text"],
                    fontname=style["bold_font_name"] if line["bold"] else style["font_name"],
                    fontsize=font_size,
                    color=style["color"],
                )
                current_y += line_height
            return
        font_size -= 0.2

    raise ValueError("Tailored skills text did not fit inside the original PDF section.")


def _build_skills_render_lines(
    categories: List[Dict[str, Any]],
    max_width: float,
    regular_font: str,
    bold_font: str,
    font_size: float,
) -> List[Dict[str, Any]]:
    rendered_lines: List[Dict[str, Any]] = []

    for category in categories:
        label = f"{category['label']}:"
        items_text = ", ".join(category.get("items", []))
        first_line_source = f"{label} {items_text}".strip()
        first_line, remainder = _take_line(first_line_source, max_width, bold_font, font_size)
        rendered_lines.append({"text": first_line, "bold": True})

        if remainder:
            for continuation_line in _wrap_text(remainder, max_width, regular_font, font_size):
                rendered_lines.append({"text": continuation_line, "bold": False})

    return rendered_lines


def _wrap_text(text: str, max_width: float, font_name: str, font_size: float) -> List[str]:
    remaining = " ".join(text.split())
    lines: List[str] = []

    while remaining:
        line, next_remaining = _take_line(remaining, max_width, font_name, font_size)
        lines.append(line)
        remaining = next_remaining

    return lines


def _take_line(
    text: str,
    max_width: float,
    font_name: str,
    font_size: float,
) -> Tuple[str, str]:
    words = text.split()
    if not words:
        return "", ""

    current_words = [words[0]]
    remaining_words = words[1:]

    for word in remaining_words:
        candidate = " ".join(current_words + [word])
        width = fitz.get_text_length(candidate, fontname=font_name, fontsize=font_size)
        if width <= max_width:
            current_words.append(word)
            continue
        break

    consumed = len(current_words)
    line_text = " ".join(current_words)
    leftover = " ".join(words[consumed:]).strip()
    return line_text, leftover
