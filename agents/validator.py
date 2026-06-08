"""
Validator - Validates output and computes ATS match scores.
Pure Python logic, no AI needed.
"""

import json
from typing import Dict, Any, List, Set


def validate(new_content: Dict[str, Any], jd_data: Dict[str, Any],
             original_resume_text: str = "") -> Dict[str, Any]:
    """
    Validate the tailored resume and compute ATS match scores.
    
    Args:
        new_content: The tailored resume content
        jd_data: The analyzed JD data
        original_resume_text: Original resume text for before/after comparison
        
    Returns:
        Dict with ATS scores and keyword analysis
    """
    master_keywords = _build_master_keywords(jd_data)
    
    # Convert new content to searchable text
    new_content_text = _content_to_text(new_content)
    new_content_lower = new_content_text.lower()
    
    keywords_found, keywords_missing = _find_keywords(new_content_lower, master_keywords)
    
    # Calculate scores
    total_keywords = len(master_keywords)
    matched_count = len(keywords_found)
    
    ats_score_after = round((matched_count / total_keywords) * 100) if total_keywords > 0 else 0
    
    # Calculate before score if original text provided
    ats_score_before = 0
    keywords_added: List[str] = []
    
    if original_resume_text:
        original_lower = original_resume_text.lower()
        original_found, _ = _find_keywords(original_lower, master_keywords)
        
        original_count = len(original_found)
        ats_score_before = round((original_count / total_keywords) * 100) if total_keywords > 0 else 0
        
        # Find keywords that were added (in new but not in original)
        original_set = set(original_found)
        keywords_added = [kw for kw in keywords_found if kw not in original_set]
    
    # Compute skills gap - skills required by JD that are not in resume at all
    skills_gap: List[str] = []
    
    # Get all skills from resume
    resume_skills = _get_all_resume_skills(new_content)
    resume_skills_lower = [s.lower() for s in resume_skills]
    
    # Check each required skill
    for skill in required_skills:
        skill_lower = skill.lower()
        if skill_lower not in resume_skills_lower:
            # Check if any variation exists
            found = False
            for rs in resume_skills_lower:
                if skill_lower in rs or rs in skill_lower:
                    found = True
                    break
            if not found:
                skills_gap.append(skill)
    
    # Get JD skills for summary
    jd_skills = set()
    for skill in required_skills:
        jd_skills.add(skill.lower())
    for skill in preferred_skills:
        jd_skills.add(skill.lower())
    
    # Find keywords that are missing from the resume entirely
    fully_missing = []
    for kw in keywords_missing:
        found = False
        for skill in resume_skills_lower:
            if kw in skill or skill in kw:
                found = True
                break
        if not found:
            fully_missing.append(kw)
    
    return {
        "ats_score_before": ats_score_before,
        "ats_score_after": ats_score_after,
        "keywords_added": keywords_added,
        "keywords_missing": keywords_missing[:15],  # Limit for display
        "skills_gap": skills_gap[:10]  # Limit for display
    }


def validate_resume_text(
    new_resume_text: str,
    jd_data: Dict[str, Any],
    original_resume_text: str = "",
    resume_skills: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Validate ATS coverage when only specific PDF sections were edited.
    """
    master_keywords = _build_master_keywords(jd_data)
    required_skills = jd_data.get("required_skills", [])

    new_resume_lower = new_resume_text.lower()
    keywords_found, keywords_missing = _find_keywords(new_resume_lower, master_keywords)

    total_keywords = len(master_keywords)
    matched_count = len(keywords_found)
    ats_score_after = round((matched_count / total_keywords) * 100) if total_keywords > 0 else 0

    ats_score_before = 0
    keywords_added: List[str] = []
    if original_resume_text:
        original_lower = original_resume_text.lower()
        original_found, _ = _find_keywords(original_lower, master_keywords)
        original_count = len(original_found)
        ats_score_before = round((original_count / total_keywords) * 100) if total_keywords > 0 else 0
        original_set = set(original_found)
        keywords_added = [kw for kw in keywords_found if kw not in original_set]

    normalized_resume_skills = [skill.lower() for skill in (resume_skills or [])]
    skills_gap: List[str] = []
    for skill in required_skills:
        skill_lower = skill.lower()
        if not any(skill_lower in existing or existing in skill_lower for existing in normalized_resume_skills):
            skills_gap.append(skill)

    return {
        "ats_score_before": ats_score_before,
        "ats_score_after": ats_score_after,
        "keywords_added": keywords_added,
        "keywords_missing": keywords_missing[:15],
        "skills_gap": skills_gap[:10],
    }


def _content_to_text(content: Dict[str, Any]) -> str:
    """Convert resume content dict to searchable text."""
    text_parts = []
    
    # Contact info
    contact = content.get("contact", {})
    for key, value in contact.items():
        if value:
            text_parts.append(str(value))
    
    # Summary
    if content.get("summary"):
        text_parts.append(content["summary"])
    
    # Experience
    for exp in content.get("experience", []):
        text_parts.append(exp.get("title", ""))
        text_parts.append(exp.get("company", ""))
        for bullet in exp.get("bullets", []):
            text_parts.append(bullet)
    
    # Education
    for edu in content.get("education", []):
        for key, value in edu.items():
            if value:
                text_parts.append(str(value))
    
    # Skills
    skills = content.get("skills", {})
    for category, skill_list in skills.items():
        if skill_list and isinstance(skill_list, list):
            text_parts.extend([str(s) for s in skill_list])
    
    # Projects
    for proj in content.get("projects", []):
        text_parts.append(proj.get("name", ""))
        text_parts.append(proj.get("description", ""))
        for tech in proj.get("technologies", []):
            text_parts.append(tech)
    
    # Additional sections
    for section_content in content.get("additional_sections", {}).values():
        text_parts.append(str(section_content))
    
    return " ".join(text_parts)


def _get_all_resume_skills(content: Dict[str, Any]) -> List[str]:
    """Extract all skills from resume content."""
    all_skills = []
    
    skills = content.get("skills", {})
    for category, skill_list in skills.items():
        if skill_list and isinstance(skill_list, list):
            all_skills.extend([str(s) for s in skill_list])
    
    # Also extract from experience bullets
    for exp in content.get("experience", []):
        for bullet in exp.get("bullets", []):
            # Look for technology mentions in bullets
            words = bullet.split()
            for word in words:
                # Common tech patterns
                if any(x in word.lower() for x in ['python', 'java', 'aws', 'azure', 'docker', 'sql', 'html', 'css', 'js', 'react', 'node', 'git']):
                    all_skills.append(word)
    
    return all_skills


def _build_master_keywords(jd_data: Dict[str, Any]) -> List[str]:
    all_keywords: List[str] = []
    all_keywords.extend(jd_data.get("required_skills", []))
    all_keywords.extend(jd_data.get("ats_keywords", []))
    all_keywords.extend(jd_data.get("preferred_skills", []))
    all_keywords.extend(jd_data.get("domain_specific_terms", []))

    keyword_set: Set[str] = set()
    for keyword in all_keywords:
        if keyword and len(keyword) > 1:
            keyword_set.add(keyword.lower().strip())

    return list(keyword_set)


def _find_keywords(search_text: str, master_keywords: List[str]) -> tuple[List[str], List[str]]:
    keywords_found: List[str] = []
    keywords_missing: List[str] = []

    for keyword in master_keywords:
        if keyword in search_text:
            keywords_found.append(keyword)
        else:
            keywords_missing.append(keyword)

    return keywords_found, keywords_missing


# For testing
if __name__ == "__main__":
    # Test with sample data
    sample_jd = {
        "required_skills": ["Python", "AWS", "Docker", "Kubernetes"],
        "preferred_skills": ["Machine Learning", "TensorFlow"],
        "ats_keywords": ["Python", "AWS", "Docker", "Kubernetes", "REST API", "CI/CD"],
        "domain_specific_terms": ["microservices", "agile"],
        "summary_keywords": ["Python", "AWS", "experience"]
    }
    
    sample_resume = {
        "contact": {"name": "John Doe"},
        "summary": "Software engineer with experience in Python and AWS.",
        "experience": [
            {
                "company": "Tech Corp",
                "title": "Developer",
                "bullets": ["Built APIs using Python", "Deployed to AWS"]
            }
        ],
        "skills": {
            "technical": ["Python", "Java", "AWS", "Docker"],
            "soft": ["Communication"]
        }
    }
    
    original_text = "John Doe - Software Engineer - Python, Java - Tech Corp"
    
    result = validate(sample_resume, sample_jd, original_text)
    print(json.dumps(result, indent=2))
