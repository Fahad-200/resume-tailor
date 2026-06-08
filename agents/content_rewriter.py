"""
Content Rewriter - Rewrites resume content to match a job description.
Uses Gemini AI to intelligently tailor content without fabrication.
"""

import json
from difflib import SequenceMatcher
from typing import Dict, Any
from utils.ai_client import generate_text, GeminiQuotaError
from utils.pdf_section_editor import extract_skill_categories, categories_to_text


def rewrite(resume_data: Dict[str, Any], jd_data: Dict[str, Any], 
            options: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """
    Rewrite resume content to match job description.
    
    CRITICAL: This function must NOT fabricate skills, experiences, or 
    qualifications the candidate doesn't have. It only reframes, emphasizes,
    reorders, and rewrites what already exists.
    
    Args:
        resume_data: Parsed resume data from resume_parser
        jd_data: Analyzed JD data from jd_analyzer
        options: Options including 'tone' preference
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dict containing rewritten resume content
    """
    tone = options.get('tone', 'professional')
    
    prompt = f"""
You are an expert resume writer and career coach. Your job is to tailor 
a candidate's resume for a specific job WITHOUT fabricating anything.

STRICT RULES — NEVER VIOLATE THESE:
1. Do NOT add skills, technologies, or experiences the candidate does not have
2. Do NOT change dates, company names, job titles, or educational institutions
3. Do NOT invent metrics or numbers that are not in the original
4. You MAY reorder bullet points to put the most relevant ones first
5. You MAY reword bullet points to use stronger action verbs and JD-aligned language
6. You MAY add context or expand on a bullet if the information exists elsewhere 
   in the resume (e.g. a skill from the skills section can be woven into a bullet)
7. You MAY rewrite the summary completely — it's meant to be tailored
8. You MAY reorder skills to put the most JD-relevant ones first
9. Use the exact terminology and keywords from the JD where applicable
10. Use action verbs that the JD itself uses where possible

TARGET JOB:
{json.dumps(jd_data, indent=2)}

CANDIDATE'S CURRENT RESUME:
{json.dumps(resume_data, indent=2)}

TONE PREFERENCE: {tone}

Respond with ONLY valid JSON matching this exact structure:
{{
    "contact": (same as input — do not change),
    "summary": "NEW tailored summary — 2 to 4 sentences. Must mention: job title, 
                 top 2-3 relevant skills from candidate's background that match JD, 
                 years of experience, and 1-2 summary_keywords from the JD",
    "experience": [
        {{
            "company": (same as input),
            "title": (same as input),
            "start_date": (same as input),
            "end_date": (same as input),
            "location": (same as input),
            "bullets": ["REWRITTEN bullet 1 — lead with action verb from JD", 
                        "REWRITTEN bullet 2", ...],
            "bullets_original": ["original bullet 1", "original bullet 2", ...]
        }}
    ],
    "education": (same as input — do not change),
    "skills": {{
        "technical": [most JD-relevant first, then rest],
        "soft": [most JD-relevant first, then rest],
        "tools": [...],
        "languages": [...],
        "certifications": [...],
        "other": [...]
    }},
    "projects": (same as input or with reworded descriptions if relevant to JD),
    "additional_sections": (same as input),
    "detected_sections_in_order": (same as input),
    "changes_made": [
        "Rewrote summary to emphasize Python and ML background",
        "Reordered Experience bullets to highlight data pipeline work",
        "Moved AWS to top of technical skills"
    ]
}}
"""
    
    for attempt in range(max_retries):
        try:
            response_text = generate_text(
                prompt,
                max_retries=1,
                response_mime_type="application/json",
            )

            result = _parse_json_response(response_text)
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
    
    raise ValueError("Failed to rewrite resume after all retries")


def generate_cover_letter(resume_data: Dict[str, Any], jd_data: Dict[str, Any],
                          max_retries: int = 2) -> str:
    """
    Generate a cover letter for the candidate and job.
    
    Args:
        resume_data: Parsed resume data
        jd_data: Analyzed JD data
        max_retries: Maximum number of retry attempts
        
    Returns:
        Cover letter text
    """
    job_title = jd_data.get("job_title", "the position")
    company_name = jd_data.get("company_name", "the company")
    tone = jd_data.get("tone", "professional")
    
    prompt = f"""
Write a professional cover letter for this candidate applying to this job.

Candidate info: {json.dumps(resume_data.get('contact', {}))}
Job: {job_title} at {company_name}
Tone: {tone}

Rules:
- 3 paragraphs: opening (why this role), middle (top 2-3 relevant achievements), 
  closing (call to action)
- Use the candidate's ACTUAL experience only
- Under 350 words
- Match the tone of the job (formal/casual/startup)
- Do NOT use clichés like "I am writing to express my interest"
- Start with a strong hook

Candidate Resume Data: {json.dumps(resume_data, indent=2)}
Job Data: {json.dumps(jd_data, indent=2)}

Respond with only the cover letter text. No subject line. No headers.
"""
    
    for attempt in range(max_retries):
        try:
            return generate_text(prompt, max_retries=1, temperature=0.4)
        except GeminiQuotaError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise ValueError(f"AI call failed: {e}")
    
    raise ValueError("Failed to generate cover letter after all retries")


def tailor_resume_sections(
    original_resume_text: str,
    editable_sections: Dict[str, Dict[str, Any]],
    jd_data: Dict[str, Any],
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Tailor only the editable Objective / Summary and Skills sections.
    """
    requested_sections = options.get("target_sections") or ["objective", "skills"]
    normalized_targets = [_normalize_target_section(section) for section in requested_sections]
    normalized_targets = [section for section in normalized_targets if section]

    updates: Dict[str, Dict[str, Any]] = {}
    changes_made = []

    if "objective" in normalized_targets and editable_sections.get("objective"):
        original_objective = editable_sections["objective"]["text"]
        updated_objective = _rewrite_objective(
            original_resume_text,
            original_objective,
            jd_data,
            options,
        )
        updates["objective"] = {"text": updated_objective}
        if updated_objective.strip() != original_objective.strip():
            changes_made.append("Updated Objective to align with the job description")

    if "skills" in normalized_targets and editable_sections.get("skills"):
        original_categories = extract_skill_categories(editable_sections["skills"])
        reordered_categories = _tailor_skills_categories(original_categories, jd_data, options)
        updates["skills"] = {
            "categories": reordered_categories,
            "text": categories_to_text(reordered_categories),
        }
        if categories_to_text(reordered_categories).strip() != editable_sections["skills"]["text"].strip():
            changes_made.append("Reordered Skills to surface the strongest JD-relevant and transferable strengths first")

    return {
        "updates": updates,
        "changes_made": changes_made,
    }


def generate_cover_letter_from_text(
    resume_text: str,
    jd_data: Dict[str, Any],
    max_retries: int = 2,
) -> str:
    """
    Generate a cover letter using raw resume text when structured parsing is skipped.
    """
    job_title = jd_data.get("job_title", "the position")
    company_name = jd_data.get("company_name", "the company")
    tone = jd_data.get("tone", "professional")

    prompt = f"""
Write a professional cover letter for this candidate applying to this job.

Job: {job_title} at {company_name}
Tone: {tone}

Rules:
- 3 paragraphs only
- Under 320 words
- Use ONLY experience, skills, and achievements already present in the resume text
- Do NOT invent companies, years, numbers, or responsibilities
- Start directly with a strong, natural opening
- No subject line or heading

RESUME TEXT:
{resume_text}

JOB DATA:
{json.dumps(jd_data, indent=2)}

Respond with only the cover letter text.
"""

    for attempt in range(max_retries):
        try:
            return generate_text(prompt, max_retries=1, temperature=0.4)
        except GeminiQuotaError:
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise ValueError(f"AI call failed: {e}")

    raise ValueError("Failed to generate cover letter after all retries")


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


def _rewrite_objective(
    original_resume_text: str,
    original_objective: str,
    jd_data: Dict[str, Any],
    options: Dict[str, Any],
) -> str:
    tone = options.get("tone", "professional")
    style_profile = options.get("uploaded_style_profile", "").strip()
    original_word_count = len(original_objective.split())
    min_words = max(35, original_word_count - 12)
    max_words = min(original_word_count + 12, 105)
    tone_instruction = _build_tone_instruction(tone, style_profile)

    prompt = f"""
You are tailoring only the Objective / Summary section of a resume.

STRICT RULES:
1. Use ONLY facts, skills, tools, and qualifications that already appear in the resume
2. Do NOT invent years of experience, job titles, companies, metrics, or certifications
3. Keep the rewrite close to the original length so it fits in the same PDF section
4. Focus on JD-relevant strengths already present in the resume
5. Return plain text only, with no heading and no quotation marks
6. If the JD is in a different domain, emphasize truthful transferable strengths from the resume instead of forcing fake alignment
7. The rewrite must clearly sound targeted to the JD, not like a generic paraphrase

Tone / style direction:
{tone_instruction}

Target word count: between {min_words} and {max_words}

CURRENT OBJECTIVE:
{original_objective}

FULL RESUME TEXT:
{original_resume_text}

JOB DATA:
{json.dumps(jd_data, indent=2)}
"""

    response = generate_text(prompt, max_retries=1, temperature=0.3)
    cleaned = " ".join(response.replace("\n", " ").split()).strip()
    cleaned = cleaned.removeprefix("Objective:").removeprefix("Summary:").strip()
    rewritten = cleaned or original_objective

    similarity_ratio = SequenceMatcher(
        None,
        original_objective.lower(),
        rewritten.lower(),
    ).ratio()
    if similarity_ratio > 0.88:
        strengthened_prompt = prompt + """

Your previous rewrite stayed too close to the original.
Try again with stronger JD targeting while remaining 100% truthful:
- swap generic phrases for role-specific phrasing from the JD
- foreground the candidate's most transferable existing strengths
- make the target role explicit in the first sentence
"""
        stronger_response = generate_text(strengthened_prompt, max_retries=1, temperature=0.45)
        stronger_cleaned = " ".join(stronger_response.replace("\n", " ").split()).strip()
        stronger_cleaned = stronger_cleaned.removeprefix("Objective:").removeprefix("Summary:").strip()
        if stronger_cleaned:
            rewritten = stronger_cleaned

    return rewritten


def _normalize_target_section(section_name: str) -> str:
    lowered = (section_name or "").strip().lower()
    if lowered in {"objective", "summary", "profile"}:
        return "objective"
    if lowered in {"skills", "technical skills", "core skills"}:
        return "skills"
    return ""


def _reorder_skill_categories(
    categories: list[Dict[str, Any]],
    jd_data: Dict[str, Any],
) -> list[Dict[str, Any]]:
    jd_terms = _build_jd_term_set(jd_data)
    reordered = []

    for category in categories:
        original_items = category.get("items", [])
        indexed_items = list(enumerate(original_items))
        indexed_items.sort(
            key=lambda item: (
                -_score_skill_item(item[1], jd_terms),
                item[0],
            )
        )
        reordered.append(
            {
                "label": category.get("label", "Skills"),
                "items": [item for _, item in indexed_items],
            }
        )

    reordered.sort(
        key=lambda category: (
            -sum(_score_skill_item(item, jd_terms) for item in category.get("items", [])),
            category.get("label", ""),
        )
    )

    return reordered


def _tailor_skills_categories(
    categories: list[Dict[str, Any]],
    jd_data: Dict[str, Any],
    options: Dict[str, Any],
) -> list[Dict[str, Any]]:
    jd_skill_candidates = _build_jd_skill_candidates(jd_data)

    ai_reordered = _reorder_skill_categories_with_ai(
        categories,
        jd_data,
        options,
        jd_skill_candidates,
    )
    if ai_reordered:
        return ai_reordered

    return _augment_skills_with_jd_terms(categories, jd_data, jd_skill_candidates)


def _build_jd_term_set(jd_data: Dict[str, Any]) -> set[str]:
    candidates = []
    for key in [
        "required_skills",
        "preferred_skills",
        "ats_keywords",
        "domain_specific_terms",
        "summary_keywords",
        "action_verbs_preferred",
    ]:
        value = jd_data.get(key, [])
        if isinstance(value, list):
            candidates.extend(value)

    normalized = set()
    for term in candidates:
        cleaned = " ".join(str(term).lower().split())
        if cleaned:
            normalized.add(cleaned)
    return normalized


def _score_skill_item(skill_item: str, jd_terms: set[str]) -> int:
    candidate = " ".join(str(skill_item).lower().split())
    candidate_tokens = set(candidate.replace("/", " ").replace("-", " ").split())
    score = 0

    for jd_term in jd_terms:
        jd_tokens = set(jd_term.replace("/", " ").replace("-", " ").split())
        if candidate == jd_term:
            score += 10
        elif candidate in jd_term or jd_term in candidate:
            score += 7
        else:
            score += len(candidate_tokens & jd_tokens)

    return score


def _build_tone_instruction(tone: str, style_profile: str) -> str:
    if tone == "uploaded_pdf_style":
        if style_profile:
            return (
                "Match the uploaded resume's existing writing style and density while still targeting the JD.\n"
                f"{style_profile}"
            )
        return "Match the uploaded resume's existing writing style and density while still targeting the JD."

    tone_map = {
        "professional": "Use a polished, business-ready tone with direct JD alignment.",
        "enthusiastic": "Use an energetic, confident tone without sounding exaggerated.",
        "conservative": "Use a formal, restrained, low-risk tone.",
    }
    return tone_map.get(tone, "Use a clear, direct professional tone.")


def _reorder_skill_categories_with_ai(
    categories: list[Dict[str, Any]],
    jd_data: Dict[str, Any],
    options: Dict[str, Any],
    jd_skill_candidates: list[str],
) -> list[Dict[str, Any]] | None:
    tone = options.get("tone", "professional")
    style_profile = options.get("uploaded_style_profile", "").strip()
    original_total_items = sum(len(category.get("items", [])) for category in categories)
    max_total_items = min(original_total_items + 6, max(original_total_items, 8) + 8)
    prompt = f"""
You are tailoring the Skills section of a resume for a job description.

STRICT RULES:
1. Keep the same category labels that already exist in the resume
2. You MAY reorder categories and items
3. You MAY keep, replace, or add skills to better match the JD
4. Any new added skill must come from the allowed JD skill candidates list below
5. Do NOT invent new terms that are not already in the resume or in the allowed JD skill candidates list
6. Keep the final section close to the original density so it still fits in a one-page PDF
7. Favor the strongest JD-specific skills and transferable terms first
8. If the JD is from a different field, blend in relevant JD terms while keeping some original strengths
9. Total final skill items across all categories must stay at or below {max_total_items}

Tone / style direction:
{_build_tone_instruction(tone, style_profile)}

CURRENT SKILLS CATEGORIES:
{json.dumps(categories, indent=2)}

ALLOWED JD SKILL CANDIDATES:
{json.dumps(jd_skill_candidates, indent=2)}

JOB DATA:
{json.dumps(jd_data, indent=2)}

Return ONLY JSON with this shape:
{{
  "ordered_categories": [
    {{"label": "existing label", "items": ["existing item 1", "existing item 2"]}}
  ]
}}
"""

    try:
        response_text = generate_text(
            prompt,
            max_retries=1,
            response_mime_type="application/json",
            temperature=0.2,
        )
        parsed = _parse_json_response(response_text)
        candidate = parsed.get("ordered_categories")
        if not isinstance(candidate, list):
            return None
        return _validate_ai_skill_reorder(categories, candidate, jd_skill_candidates)
    except Exception:
        return None


def _validate_ai_skill_reorder(
    original_categories: list[Dict[str, Any]],
    candidate_categories: list[Dict[str, Any]],
    jd_skill_candidates: list[str],
) -> list[Dict[str, Any]] | None:
    original_map = {
        category["label"]: list(category.get("items", []))
        for category in original_categories
    }
    allowed_items_map = {}
    for item in jd_skill_candidates:
        allowed_items_map[_normalize_skill_text(item)] = item
    for items in original_map.values():
        for item in items:
            allowed_items_map[_normalize_skill_text(item)] = item

    candidate_labels = [category.get("label") for category in candidate_categories]
    if set(candidate_labels) != set(original_map.keys()) or len(candidate_labels) != len(original_map):
        return None

    total_items = 0
    validated = []
    for category in candidate_categories:
        label = category.get("label")
        candidate_items = []
        seen_items = set()
        for raw_item in list(category.get("items", [])):
            normalized = _normalize_skill_text(raw_item)
            canonical = allowed_items_map.get(normalized)
            if not canonical or normalized in seen_items:
                continue
            candidate_items.append(canonical)
            seen_items.add(normalized)

        if not candidate_items:
            return None

        total_items += len(candidate_items)

        validated.append(
            {
                "label": label,
                "items": candidate_items,
            }
        )

    original_total_items = sum(len(items) for items in original_map.values())
    if total_items > min(original_total_items + 6, max(original_total_items, 8) + 8):
        return None

    return validated


def _augment_skills_with_jd_terms(
    categories: list[Dict[str, Any]],
    jd_data: Dict[str, Any],
    jd_skill_candidates: list[str],
) -> list[Dict[str, Any]]:
    jd_terms = _build_jd_term_set(jd_data)
    original_total_items = sum(len(category.get("items", [])) for category in categories)
    max_total_items = min(original_total_items + 6, max(original_total_items, 8) + 8)
    max_items_per_category = {
        category["label"]: max(len(category.get("items", [])) + 2, len(category.get("items", [])))
        for category in categories
    }

    working_categories = []
    all_existing_items = {
        _normalize_skill_text(item)
        for category in categories
        for item in category.get("items", [])
    }

    remaining_slots = max_total_items - original_total_items
    candidate_queue = [
        term for term in jd_skill_candidates
        if _normalize_skill_text(term) not in all_existing_items
    ]

    additions_by_category = {category["label"]: [] for category in categories}

    while candidate_queue and remaining_slots > 0:
        term = candidate_queue.pop(0)
        target_label = _guess_skill_category(term, [category["label"] for category in categories])
        if not target_label:
            continue

        if len(additions_by_category[target_label]) >= 2:
            continue

        additions_by_category[target_label].append(term)
        remaining_slots -= 1

    for category in categories:
        label = category["label"]
        original_items = list(category.get("items", []))
        added_items = additions_by_category.get(label, [])

        combined_items = added_items + original_items
        deduped_items = []
        seen = set()
        for item in combined_items:
            normalized = _normalize_skill_text(item)
            if normalized in seen:
                continue
            deduped_items.append(item)
            seen.add(normalized)

        indexed_items = list(enumerate(deduped_items))
        indexed_items.sort(
            key=lambda item: (
                -_score_skill_item(item[1], jd_terms),
                item[0],
            )
        )

        trimmed_items = [item for _, item in indexed_items[:max_items_per_category[label]]]
        working_categories.append(
            {
                "label": label,
                "items": trimmed_items,
            }
        )

    working_categories.sort(
        key=lambda category: (
            -sum(_score_skill_item(item, jd_terms) for item in category.get("items", [])),
            category.get("label", ""),
        )
    )

    return working_categories


def _build_jd_skill_candidates(jd_data: Dict[str, Any]) -> list[str]:
    candidates = []
    for key in [
        "required_skills",
        "preferred_skills",
        "ats_keywords",
        "domain_specific_terms",
        "summary_keywords",
    ]:
        value = jd_data.get(key, [])
        if isinstance(value, list):
            candidates.extend(value)

    ranked = []
    seen = set()
    for term in candidates:
        cleaned = _clean_jd_skill_candidate(term)
        normalized = _normalize_skill_text(cleaned)
        if not cleaned or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ranked.append(cleaned)

    ranked.sort(key=_jd_skill_priority_key)
    return ranked[:14]


def _clean_jd_skill_candidate(term: Any) -> str:
    cleaned = " ".join(str(term).replace("|", " ").split()).strip(" ,.;:-")
    if not cleaned:
        return ""
    if len(cleaned.split()) > 5:
        return ""
    if len(cleaned) < 2:
        return ""
    return cleaned


def _jd_skill_priority_key(term: str) -> tuple[int, int]:
    normalized = _normalize_skill_text(term)
    negative_terms = ["experience", "years", "degree", "required", "preferred", "must", "ability"]
    generic_terms = ["team", "leadership", "role", "business", "projects"]

    penalty = 0
    if any(token in normalized for token in negative_terms):
        penalty += 4
    if any(token in normalized for token in generic_terms):
        penalty += 2

    return (penalty, len(normalized.split()))


def _normalize_skill_text(value: Any) -> str:
    normalized = " ".join(str(value).lower().replace("&", " and ").split())
    normalized = normalized.replace(",", "")
    return normalized


def _guess_skill_category(term: str, available_labels: list[str]) -> str:
    normalized_term = _normalize_skill_text(term)
    normalized_labels = {label.lower(): label for label in available_labels}
    term_tokens = set(normalized_term.replace("/", " ").replace("-", " ").split())

    language_tokens = {"python", "java", "c", "c++", "c#", "sql", "javascript", "typescript", "ruby", "go"}
    tool_tokens = {
        "excel", "tableau", "power bi", "git", "github", "flask", "tensorflow", "opencv",
        "seo", "sem", "google analytics", "analytics", "crm", "figma", "canva"
    }
    interpersonal_tokens = {
        "communication", "collaboration", "presentation", "leadership", "storytelling",
        "problem solving", "negotiation", "stakeholder management"
    }

    if _matches_skill_token(normalized_term, term_tokens, language_tokens):
        for label in available_labels:
            if "language" in label.lower():
                return label

    if _matches_skill_token(normalized_term, term_tokens, tool_tokens):
        for label in available_labels:
            label_lower = label.lower()
            if "tool" in label_lower or "platform" in label_lower:
                return label

    if _matches_skill_token(normalized_term, term_tokens, interpersonal_tokens):
        for label in available_labels:
            label_lower = label.lower()
            if "interpersonal" in label_lower or "soft" in label_lower:
                return label

    for label in available_labels:
        label_lower = label.lower()
        if "technical" in label_lower or "skill" in label_lower:
            return label

    return normalized_labels.get("skills", available_labels[0] if available_labels else "")


def _matches_skill_token(normalized_term: str, term_tokens: set[str], candidates: set[str]) -> bool:
    for candidate in candidates:
        candidate_normalized = _normalize_skill_text(candidate)
        if " " in candidate_normalized:
            if candidate_normalized in normalized_term:
                return True
        elif candidate_normalized in term_tokens:
            return True
    return False


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    import google.generativeai as genai
    
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    sample_resume = {
        "contact": {"name": "John Doe", "email": "john@example.com"},
        "summary": "Experienced software engineer with 5 years in Python development.",
        "experience": [
            {
                "company": "Tech Corp",
                "title": "Software Engineer",
                "start_date": "2020",
                "end_date": "Present",
                "bullets": ["Developed web applications", "Worked with team"]
            }
        ],
        "education": [{"institution": "State University", "degree": "BS", "field": "Computer Science"}],
        "skills": {"technical": ["Python", "Java", "AWS"], "soft": ["Communication"]}
    }
    
    sample_jd = {
        "job_title": "Senior Python Developer",
        "company_name": "Startup Inc",
        "ats_keywords": ["Python", "Django", "AWS", "REST API"],
        "action_verbs_preferred": ["orchestrate", "design", "lead"],
        "tone": "startup"
    }
    
    result = rewrite(sample_resume, sample_jd, {"tone": "professional"})
    print(json.dumps(result, indent=2))
