"""
PDF Reader - Extracts text and tables from PDF resumes using pdfplumber.
"""

import pdfplumber
from typing import Dict, Any, List, Optional


def extract_text_from_pdf(pdf_filepath: str) -> Dict[str, Any]:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_filepath: Path to the PDF file
        
    Returns:
        Dict with 'full_text', 'page_count', 'tables' keys
    """
    full_text = ""
    tables: List[List[List[str]]] = []
    
    with pdfplumber.open(pdf_filepath) as pdf:
        page_count = len(pdf.pages)
        
        for page in pdf.pages:
            # Extract text
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"
            
            # Extract tables
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    
    # Check for scanned/image-based PDF
    if len(full_text.strip()) < 100:
        raise ValueError(
            "This PDF appears to be scanned or image-based. "
            "Please upload a text-based PDF."
        )
    
    return {
        "full_text": full_text.strip(),
        "page_count": page_count,
        "tables": tables
    }


def get_page_count(pdf_filepath: str) -> int:
    """Get the number of pages in a PDF."""
    with pdfplumber.open(pdf_filepath) as pdf:
        return len(pdf.pages)


def extract_page_text(pdf_filepath: str, page_number: int) -> str:
    """Extract text from a specific page (1-indexed)."""
    with pdfplumber.open(pdf_filepath) as pdf:
        if 0 < page_number <= len(pdf.pages):
            return pdf.pages[page_number - 1].extract_text() or ""
        return ""


# For testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = extract_text_from_pdf(sys.argv[1])
        print(f"Pages: {result['page_count']}")
        print(f"Text length: {len(result['full_text'])}")
        print(f"Text preview: {result['full_text'][:500]}...")
