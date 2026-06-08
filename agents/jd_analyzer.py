"""
JD Analyzer - Analyzes job descriptions to extract structured information.
Uses Gemini AI to parse job postings.
"""

import json
from typing import Dict, Any
from utils.ai_client import generate_text, GeminiQuotaError


def analyze(job_description: str, max_retries: int = 2) -> Dict[str, Any]:
    """
    Analyze a job description and extract structured information.
    
    Args:
        job_description: The raw job description text
        max_retries: Maximum number of retry attempts for AI calls
        
    Returns:
        Dict containing structured JD analysis
    """
    # Build the prompt
    prompt = f"""
You are an expert recruiter and ATS (Applicant Tracking System) specialist.
Analyze the following job description and extract structured information.

Respond with ONLY a valid JSON object. No markdown. No explanation. Just JSON.

Extract these fields:
{{
    "job_title": "exact job title from the posting",
    "company_name": "company name if mentioned, else null",
    "seniority_level": "junior/mid/senior/lead/manager/director/vp/c-level",
    "industry": "e.g. fintech, healthcare, saas, e-commerce, etc.",
    "required_skills": ["list", "of", "explicitly", "required", "skills"],
    "preferred_skills": ["list", "of", "nice-to-have", "skills"],
    "required_qualifications": ["e.g. 5+ years Python", "Bachelor's degree"],
    "key_responsibilities": ["top 5 responsibilities as concise phrases"],
    "ats_keywords": ["every important keyword that ATS would scan for — 15 to 25 words"],
    "action_verbs_preferred": ["verbs the JD itself uses, e.g. 'orchestrate', 'drive', 'collaborate'"],
    "tone": "formal/casual/startup/corporate/technical",
    "employment_type": "full-time/part-time/contract/remote/hybrid/on-site",
    "domain_specific_terms": ["technical acronyms or domain terms the employer uses"],
    "red_flags_to_address": ["things a candidate must mention to not be filtered out"],
    "summary_keywords": ["5 to 8 keywords that must appear in a resume summary for this role"]
}}

JOB DESCRIPTION:
{job_description}
"""
    
    for attempt in range(max_retries):
        try:
            response_text = generate_text(
                prompt,
                max_retries=1,
                response_mime_type="application/json",
            )

            # Parse JSON from response
            result = _parse_json_response(response_text)
            return result
            
        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                # Retry with explicit JSON request
                prompt = prompt + "\n\nYour previous response was not valid JSON. Respond again with ONLY the JSON object, nothing else."
                continue
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except GeminiQuotaError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise ValueError(f"AI call failed: {e}")
    
    raise ValueError("Failed to analyze job description after all retries")


def _parse_json_response(text: str) -> Dict[str, Any]:
    """
    Parse JSON from AI response, handling markdown code blocks.
    
    Args:
        text: The raw response text from AI
        
    Returns:
        Parsed JSON dict
    """
    # Strip markdown code fences if present
    cleaned = text.strip()
    
    if cleaned.startswith('```'):
        # Handle ```json or ``` blocks
        lines = cleaned.split('\n')
        # Remove first line (```json or ```)
        if lines[0].strip().startswith('```'):
            lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines)
    
    # Remove any trailing backticks
    cleaned = cleaned.strip().rstrip('`')
    
    return json.loads(cleaned)


# For testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    import google.generativeai as genai
    
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Test with sample JD
    sample_jd = """
    Software Engineer
    
    We are looking for a Software Engineer to join our team.
    
    Requirements:
    - 3+ years of Python experience
    - Experience with cloud services (AWS)
    - Bachelor's degree in Computer Science
    
    Preferred:
    - Experience with machine learning
    - Docker and Kubernetes
    
    Skills: Python, AWS, Docker, Kubernetes, Machine Learning
    """
    
    result = analyze(sample_jd)
    print(json.dumps(result, indent=2))
