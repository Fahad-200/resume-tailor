"""
Resume Parser - Parses resume PDFs into structured data.
Uses pdfplumber for text extraction and Gemini for semantic parsing.
"""

import json
from typing import Dict, Any
from utils.pdf_reader import extract_text_from_pdf
from utils.ai_client import generate_text, GeminiQuotaError


def parse(pdf_filepath: str, max_retries: int = 2) -> Dict[str, Any]:
    """
    Parse a resume PDF into structured data.
    
    Args:
        pdf_filepath: Path to the PDF file
        max_retries: Maximum number of retry attempts for AI calls
        
    Returns:
        Dict containing structured resume data
    """
    # Step 1: Extract text using pdfplumber
    try:
        extracted = extract_text_from_pdf(pdf_filepath)
        full_text = extracted["full_text"]
        page_count = extracted["page_count"]
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")
    
    # Step 2: Use Gemini to parse semantically
    prompt = f"""
You are a resume parsing expert. Parse this resume text into structured JSON.

Respond with ONLY valid JSON. No markdown. No explanation.

{{
    "contact": {{
        "name": "full name",
        "email": "email or null",
        "phone": "phone or null",
        "linkedin": "url or null",
        "location": "city, state or null",
        "github": "url or null",
        "portfolio": "url or null"
    }},
    "summary": "the professional summary/objective text verbatim, or null",
    "experience": [
        {{
            "company": "company name",
            "title": "job title",
            "start_date": "month year or year",
            "end_date": "month year or Present",
            "location": "city or remote or null",
            "bullets": ["bullet point text", "another bullet"]
        }}
    ],
    "education": [
        {{
            "institution": "university/college name",
            "degree": "degree name",
            "field": "field of study",
            "graduation_year": "year or null",
            "gpa": "GPA if mentioned or null",
            "honors": "magna cum laude etc or null"
        }}
    ],
    "skills": {{
        "technical": ["list", "of", "technical", "skills"],
        "soft": ["communication", "leadership", "etc"],
        "tools": ["Jira", "Figma", "etc"],
        "languages": ["Python", "Java", "etc"],
        "certifications": ["AWS Certified", "PMP", "etc"],
        "other": ["anything else that is a skill"]
    }},
    "projects": [
        {{
            "name": "project name",
            "description": "what it does",
            "technologies": ["tech used"],
            "link": "url or null"
        }}
    ],
    "additional_sections": {{
        "section_name": "content"
    }},
    "detected_sections_in_order": ["Summary", "Experience", "Education", "Skills"]
}}

RESUME TEXT:
{full_text}
"""
    
    for attempt in range(max_retries):
        try:
            response_text = generate_text(
                prompt,
                max_retries=1,
                response_mime_type="application/json",
            )

            # Parse JSON
            result = _parse_json_response(response_text)
            
            # Add page count to result
            result["page_count"] = page_count
            
            return result
            
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                prompt = prompt + "\n\nYour previous response was not valid JSON. Respond again with ONLY the JSON object, nothing else."
                continue
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except GeminiQuotaError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise ValueError(f"AI call failed: {e}")
    
    raise ValueError("Failed to parse resume after all retries")


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Parse JSON from AI response, handling markdown code blocks."""
    cleaned = text.strip()
    
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        if lines[0].strip().startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines)
    
    cleaned = cleaned.strip().rstrip('`')
    
    return json.loads(cleaned)


# For testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    import google.generativeai as genai
    
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Test with a resume PDF
    import sys
    if len(sys.argv) > 1:
        result = parse(sys.argv[1])
        print(json.dumps(result, indent=2))
