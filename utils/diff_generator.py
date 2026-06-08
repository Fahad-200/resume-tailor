"""
Diff Generator - Generates unified diffs between original and tailored resume content.
Uses Python's built-in difflib.
"""

import difflib
from typing import Dict, Any, List


def generate_diff(original_resume: Dict[str, Any], new_resume: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate unified diffs between original and tailored resume.
    
    Args:
        original_resume: Original resume data
        new_resume: Tailored resume data with bullets_original field
        
    Returns:
        Dict with diff sections and change summaries
    """
    diffs = {}
    total_changes = 0
    changed_sections = []
    
    # Summary diff
    original_summary = original_resume.get("summary", "") or ""
    new_summary = new_resume.get("summary", "") or ""
    
    if original_summary != new_summary:
        summary_diff = _create_unified_diff(
            "Summary",
            original_summary.split('\n'),
            new_summary.split('\n')
        )
        diffs["summary_diff"] = summary_diff
        if summary_diff:
            total_changes += 1
            changed_sections.append("Summary")
    
    # Experience diffs
    original_exp = original_resume.get("experience", [])
    new_exp = new_resume.get("experience", [])
    
    experience_diffs = []
    for i, (orig_exp, new_exp_item) in enumerate(zip(original_exp, new_exp)):
        company = new_exp_item.get("company", f"Position {i+1}")
        
        # Compare bullets - use bullets_original if available
        orig_bullets = orig_exp.get("bullets", [])
        new_bullets = new_exp_item.get("bullets", [])
        
        if new_exp_item.get("bullets_original"):
            orig_bullets = new_exp_item.get("bullets_original", [])
        
        if orig_bullets != new_bullets:
            exp_diff = _create_unified_diff(
                f"Experience at {company}",
                orig_bullets,
                new_bullets
            )
            experience_diffs.append({
                "company": company,
                "diff": exp_diff
            })
            if exp_diff:
                total_changes += 1
                changed_sections.append(f"Experience at {company}")
    
    diffs["experience_diffs"] = experience_diffs
    
    # Skills diff
    original_skills = _flatten_skills(original_resume.get("skills", {}))
    new_skills = _flatten_skills(new_resume.get("skills", {}))
    
    if original_skills != new_skills:
        skills_diff = _create_unified_diff(
            "Skills",
            original_skills.split(', '),
            new_skills.split(', ')
        )
        diffs["skills_diff"] = skills_diff
        if skills_diff:
            total_changes += 1
            changed_sections.append("Skills")
    
    # Education diff (usually minimal changes)
    original_edu = str(original_resume.get("education", []))
    new_edu = str(new_resume.get("education", []))
    
    if original_edu != new_edu:
        diffs["education_diff"] = _create_unified_diff(
            "Education",
            [original_edu],
            [new_edu]
        )
    
    # Projects diff
    original_projects = original_resume.get("projects", [])
    new_projects = new_resume.get("projects", [])
    
    if original_projects != new_projects:
        diffs["projects_diff"] = _create_unified_diff(
            "Projects",
            [str(p) for p in original_projects],
            [str(p) for p in new_projects]
        )
        if diffs.get("projects_diff"):
            total_changes += 1
            changed_sections.append("Projects")
    
    diffs["total_changes"] = total_changes
    diffs["changed_sections"] = changed_sections
    
    return diffs


def generate_section_diff(
    original_sections: Dict[str, Dict[str, Any]],
    updated_sections: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generate diffs for section-only tailoring workflows.
    """
    section_diffs = []
    changed_sections = []

    section_labels = {
        "objective": "Objective",
        "skills": "Skills",
    }

    for section_key, label in section_labels.items():
        original_text = original_sections.get(section_key, {}).get("text", "") or ""
        updated_text = updated_sections.get(section_key, {}).get("text", "") or ""
        if original_text.strip() == updated_text.strip():
            continue

        diff = _create_unified_diff(
            label,
            original_text.split("\n"),
            updated_text.split("\n"),
        )
        if not diff:
            continue

        section_diffs.append(
            {
                "section": label,
                "diff": diff,
            }
        )
        changed_sections.append(label)

    return {
        "section_diffs": section_diffs,
        "total_changes": len(section_diffs),
        "changed_sections": changed_sections,
    }


def _flatten_skills(skills: Dict[str, List[str]]) -> str:
    """Flatten skills dict to a single string."""
    all_skills = []
    for category, skill_list in skills.items():
        if skill_list and isinstance(skill_list, list):
            all_skills.extend(skill_list)
    return ", ".join(all_skills)


def _create_unified_diff(title: str, original_lines: List[str], 
                         new_lines: List[str]) -> str:
    """Create a unified diff string."""
    # Filter empty lines
    original_lines = [l for l in original_lines if l]
    new_lines = [l for l in new_lines if l]
    
    if not original_lines and not new_lines:
        return ""
    
    # Use difflib to generate unified diff
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"Original {title}",
        tofile=f"Tailored {title}",
        lineterm=""
    )
    
    diff_lines = list(diff)
    
    if not diff_lines:
        return ""
    
    return '\n'.join(diff_lines)


def generate_html_diff(diff_data: Dict[str, Any]) -> str:
    """
    Generate HTML diff view for display in frontend.
    
    Args:
        diff_data: Output from generate_diff()
        
    Returns:
        HTML string for diff2html
    """
    html_parts = []

    if diff_data.get("section_diffs"):
        for section_diff in diff_data["section_diffs"]:
            html_parts.append(f"""
            <div class="diff-section">
                <h3 class="text-lg font-semibold mb-2">{section_diff['section']}</h3>
                <pre class="diff-content">{_escape_html(section_diff['diff'])}</pre>
            </div>
            """)
        return '\n'.join(html_parts)
    
    # Summary diff
    if diff_data.get("summary_diff"):
        html_parts.append(f"""
        <div class="diff-section">
            <h3 class="text-lg font-semibold mb-2">Summary</h3>
            <pre class="diff-content">{_escape_html(diff_data['summary_diff'])}</pre>
        </div>
        """)
    
    # Experience diffs
    for exp_diff in diff_data.get("experience_diffs", []):
        html_parts.append(f"""
        <div class="diff-section">
            <h3 class="text-lg font-semibold mb-2">Experience at {exp_diff['company']}</h3>
            <pre class="diff-content">{_escape_html(exp_diff['diff'])}</pre>
        </div>
        """)
    
    # Skills diff
    if diff_data.get("skills_diff"):
        html_parts.append(f"""
        <div class="diff-section">
            <h3 class="text-lg font-semibold mb-2">Skills</h3>
            <pre class="diff-content">{_escape_html(diff_data['skills_diff'])}</pre>
        </div>
        """)
    
    return '\n'.join(html_parts)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


# For testing
if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 2:
        with open(sys.argv[1], 'r') as f:
            original = json.load(f)
        with open(sys.argv[2], 'r') as f:
            new = json.load(f)
        
        diff = generate_diff(original, new)
        print(json.dumps(diff, indent=2))
