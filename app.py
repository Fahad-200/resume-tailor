"""
Resume Tailor - AI-Powered Resume Tailoring Web Application
Main Flask Application
"""

import os
import json
import uuid
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE_MB', 10)) * 1024 * 1024

# Configure CORS
CORS(app)

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Directories
UPLOAD_DIR = os.getenv('UPLOAD_DIR', 'uploads')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'outputs')
HISTORY_DIR = os.getenv('HISTORY_DIR', 'history')
FORMAT_CACHE_DIR = os.getenv('FORMAT_CACHE_DIR', 'format_cache')
SYSTEM_STATUS_PASSWORD = os.getenv('SYSTEM_STATUS_PASSWORD', 'zxc')
RESUME_SESSION_TTL_SECONDS = int(os.getenv('RESUME_SESSION_TTL_SECONDS', 2 * 60 * 60))

# Create directories
for directory in [UPLOAD_DIR, OUTPUT_DIR, HISTORY_DIR, FORMAT_CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)

ACTIVE_RESUME_SESSIONS = {}
RUNTIME_STATUS = {
    'last_generate_status': 'idle',
    'last_generate_message': 'No generation has been run in this app session yet.',
    'last_generate_time': None,
    'last_ai_error': None,
    'last_cleanup_time': None,
}

# Import agents and utils
from agents.jd_analyzer import analyze as analyze_jd
from agents.content_rewriter import tailor_resume_sections, generate_cover_letter_from_text
from agents.validator import validate_resume_text
from utils.pdf_reader import extract_text_from_pdf
from utils.format_extractor import extract_format_metadata
from utils.diff_generator import generate_section_diff, generate_html_diff
from utils.history_manager import save as save_history, get_all, get, delete as delete_history
from utils.ai_client import GeminiQuotaError, get_primary_model, get_fallback_models, generate_text
from utils.pdf_section_editor import (
    apply_section_updates,
    build_searchable_resume_text,
    build_uploaded_style_profile,
    extract_editable_sections,
)


def cleanup_old_uploads():
    """Clean up uploads older than 24 hours."""
    import time
    current_time = time.time()
    max_age = 24 * 60 * 60  # 24 hours
    
    try:
        for filename in os.listdir(UPLOAD_DIR):
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age:
                    os.remove(filepath)
    except Exception as e:
        print(f"Cleanup error: {e}")


def cleanup_expired_resume_sessions():
    """Drop one-time resume sessions and stale source files."""
    current_time = time.time()
    expired_file_ids = []

    for file_id, session_data in list(ACTIVE_RESUME_SESSIONS.items()):
        uploaded_at = session_data.get('uploaded_at', current_time)
        if current_time - uploaded_at > RESUME_SESSION_TTL_SECONDS:
            expired_file_ids.append(file_id)

    for file_id in expired_file_ids:
        _cleanup_resume_source(file_id)

    RUNTIME_STATUS['last_cleanup_time'] = datetime.now().isoformat()


def _cleanup_resume_source(file_id: str):
    """Delete one-time source artifacts after a successful run or session expiry."""
    session_data = ACTIVE_RESUME_SESSIONS.pop(file_id, None) or {}
    filepath = session_data.get('filepath')
    cache_path = os.path.join(FORMAT_CACHE_DIR, f"{file_id}.json")

    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as e:
            print(f"Source cleanup error: {e}")

    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
        except OSError as e:
            print(f"Cache cleanup error: {e}")


def _remember_resume_session(file_id: str, session_data: dict):
    ACTIVE_RESUME_SESSIONS[file_id] = {
        **session_data,
        'uploaded_at': time.time(),
    }


def _set_runtime_status(status: str, message: str, ai_error: str | None = None):
    RUNTIME_STATUS['last_generate_status'] = status
    RUNTIME_STATUS['last_generate_message'] = message
    RUNTIME_STATUS['last_generate_time'] = datetime.now().isoformat()
    RUNTIME_STATUS['last_ai_error'] = ai_error


def _build_resume_session_from_file(file_id: str, filepath: str, original_name: str | None = None) -> dict:
    format_metadata = extract_format_metadata(filepath)
    original_extracted = extract_text_from_pdf(filepath)
    editable_sections = extract_editable_sections(filepath).get('sections', {})
    style_profile = build_uploaded_style_profile(editable_sections, format_metadata)

    return {
        'file_id': file_id,
        'filepath': filepath,
        'filename': original_name or os.path.basename(filepath),
        'page_count': original_extracted['page_count'],
        'original_resume_text': original_extracted['full_text'],
        'format_metadata': format_metadata,
        'editable_sections': editable_sections,
        'style_profile': style_profile,
    }


def _get_resume_session(file_id: str) -> dict | None:
    cleanup_expired_resume_sessions()

    session_data = ACTIVE_RESUME_SESSIONS.get(file_id)
    if session_data:
        return session_data

    upload_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
    if not upload_files:
        return None

    filepath = os.path.join(UPLOAD_DIR, upload_files[0])
    if not os.path.exists(filepath):
        return None

    rebuilt_session = _build_resume_session_from_file(file_id, filepath, upload_files[0].split('_', 1)[-1])
    _remember_resume_session(file_id, rebuilt_session)
    return rebuilt_session


def _directory_is_writable(directory: str) -> bool:
    probe_path = os.path.join(directory, f".status_probe_{uuid.uuid4().hex}")
    try:
        with open(probe_path, 'w', encoding='utf-8') as probe_file:
            probe_file.write('ok')
        os.remove(probe_path)
        return True
    except OSError:
        return False


def _probe_ai_service() -> dict:
    if not GEMINI_API_KEY:
        return {
            'status': 'warning',
            'message': 'Gemini API key is not configured.',
        }

    started = time.time()
    try:
        response = generate_text(
            "Reply with only OK.",
            max_retries=1,
            temperature=0.0,
        )
        duration_ms = round((time.time() - started) * 1000)
        return {
            'status': 'ok',
            'message': f"Gemini responded in {duration_ms} ms using {get_primary_model()}",
            'response': response[:20],
        }
    except GeminiQuotaError as exc:
        return {
            'status': 'degraded',
            'message': str(exc),
        }
    except Exception as exc:
        return {
            'status': 'outage',
            'message': f"Live Gemini probe failed: {exc}",
        }


# Run cleanup on startup
cleanup_old_uploads()
cleanup_expired_resume_sessions()


@app.route('/')
def index():
    """Main page - upload and JD input."""
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'gemini_configured': bool(GEMINI_API_KEY),
        'gemini_model': get_primary_model(),
        'gemini_fallback_models': get_fallback_models()
    })


@app.route('/upload-template', methods=['POST'])
def upload_template():
    """Handle resume PDF upload."""
    try:
        cleanup_expired_resume_sessions()

        if 'resume_pdf' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['resume_pdf']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Only PDF files are allowed'}), 400
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        original_name = file.filename
        safe_name = f"{file_id}_{original_name}"
        filepath = os.path.join(UPLOAD_DIR, safe_name)
        
        # Save file
        file.save(filepath)
        
        try:
            session_data = _build_resume_session_from_file(file_id, filepath, original_name)
            _remember_resume_session(file_id, session_data)
        except Exception as e:
            # Clean up file if extraction fails
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'success': False, 'error': f'Failed to process PDF: {str(e)}'}), 400
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': original_name,
            'page_count': session_data['page_count'],
            'sections_detected': session_data['format_metadata'].get('sections_detected', []),
            'style_mode_available': True,
            'session_mode': 'one_time_upload_style'
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Generate tailored resume."""
    try:
        cleanup_expired_resume_sessions()
        data = request.get_json()
        
        # Validate input
        file_id = data.get('file_id')
        job_description = data.get('job_description', '')
        options = data.get('options', {})
        
        if not file_id:
            return jsonify({'success': False, 'error': 'No resume file uploaded'}), 400
        
        if not job_description or len(job_description) < 50:
            return jsonify({'success': False, 'error': 'Job description must be at least 50 characters'}), 400
        
        session_data = _get_resume_session(file_id)
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Resume session not found. Upload the PDF again before generating.'
            }), 400

        filepath = session_data['filepath']
        original_resume_text = session_data['original_resume_text']
        editable_sections = session_data['editable_sections']
        if not editable_sections:
            return jsonify({
                'success': False,
                'error': 'Could not find editable Objective or Skills sections in this PDF.'
            }), 400

        # Step 1: Analyze JD
        jd_data = analyze_jd(job_description)

        # Step 2: Tailor only the editable sections
        tailoring_result = tailor_resume_sections(
            original_resume_text,
            editable_sections,
            jd_data,
            {
                **options,
                'uploaded_style_profile': session_data.get('style_profile', ''),
            },
        )
        section_updates = tailoring_result.get('updates', {})
        if not section_updates:
            return jsonify({
                'success': False,
                'error': 'No editable resume sections were updated. Make sure the PDF contains Objective/Summary and Skills headings.'
            }), 400

        # Step 3: Generate a real PDF by editing the original in place
        output_file_id = str(uuid.uuid4())
        output_path = os.path.join(OUTPUT_DIR, f"{output_file_id}.pdf")
        apply_section_updates(filepath, editable_sections, section_updates, output_path)

        # Step 4: Validate and get ATS scores
        searchable_resume_text = build_searchable_resume_text(original_resume_text, section_updates)
        updated_skills = []
        if section_updates.get('skills'):
            for category in section_updates['skills'].get('categories', []):
                updated_skills.extend(category.get('items', []))

        validation_result = validate_resume_text(
            searchable_resume_text,
            jd_data,
            original_resume_text,
            updated_skills,
        )

        # Step 5: Generate cover letter if requested
        cover_letter = None
        if options.get('generate_cover_letter', False):
            try:
                cover_letter = generate_cover_letter_from_text(original_resume_text, jd_data)
            except Exception as e:
                print(f"Cover letter generation error: {e}")
        
        # Step 6: Generate diff
        diff_data = generate_section_diff(editable_sections, section_updates)
        
        # Step 7: Save to history
        changed_sections = diff_data.get('changed_sections', [])
        changes_summary = (
            ", ".join(tailoring_result.get('changes_made', []))
            or (f"Updated {', '.join(changed_sections)}" if changed_sections else "Updated resume sections")
        )
        history_entry = {
            'job_title': jd_data.get('job_title', 'Unknown'),
            'company_name': jd_data.get('company_name'),
            'ats_score_before': validation_result['ats_score_before'],
            'ats_score_after': validation_result['ats_score_after'],
            'output_file_id': output_file_id,
            'file_id': file_id,
            'keywords_added': validation_result['keywords_added'],
            'keywords_missing': validation_result['keywords_missing'],
            'changes_summary': changes_summary
        }
        history_id = save_history(history_entry, HISTORY_DIR, OUTPUT_DIR)
        
        # Generate diff HTML
        diff_html = generate_html_diff(diff_data)

        # One-time upload style/session: clear source resume after successful generation
        _cleanup_resume_source(file_id)
        _set_runtime_status(
            'ok',
            'Generation completed successfully. Source upload was cleared after the run.',
        )
        
        # Build response
        return jsonify({
            'success': True,
            'output_file_id': output_file_id,
            'ats_score_before': validation_result['ats_score_before'],
            'ats_score_after': validation_result['ats_score_after'],
            'keywords_added': validation_result['keywords_added'][:10],
            'keywords_missing': validation_result['keywords_missing'][:10],
            'cover_letter': cover_letter,
            'diff_html': diff_html,
            'skills_gap': validation_result['skills_gap'][:10],
            'changes_summary': history_entry['changes_summary'],
            'history_id': history_id,
            'job_title': jd_data.get('job_title', 'tailored'),
            'source_session_cleared': True,
        })
        
    except GeminiQuotaError as e:
        _set_runtime_status('degraded', 'Generation failed because Gemini quota was unavailable.', str(e))
        return jsonify({'success': False, 'error': str(e)}), 429
    except google_exceptions.ResourceExhausted:
        _set_runtime_status('degraded', 'Generation failed because the AI rate limit was reached.', 'AI rate limit reached')
        return jsonify({'success': False, 'error': 'AI rate limit reached. Please wait 60 seconds and try again, or switch the app to a billed Gemini project.'}), 429
    except google_exceptions.InvalidArgument as e:
        _set_runtime_status('outage', 'Generation failed because the AI request was invalid.', str(e))
        return jsonify({'success': False, 'error': 'Invalid request to AI service. Please check your API key.'}), 400
    except Exception as e:
        print(f"Generation error: {e}")
        _set_runtime_status('outage', 'Generation failed because of a backend error.', str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system-status', methods=['POST'])
def api_system_status():
    """Protected system diagnostics endpoint."""
    payload = request.get_json(silent=True) or {}
    if payload.get('password') != SYSTEM_STATUS_PASSWORD:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    cleanup_expired_resume_sessions()
    ai_probe = _probe_ai_service()

    systems = [
        {
            'name': 'Web App',
            'status': 'ok',
            'details': 'Flask server is responding.',
        },
        {
            'name': 'Gemini Configuration',
            'status': 'ok' if GEMINI_API_KEY else 'warning',
            'details': f"Primary model: {get_primary_model()}" if GEMINI_API_KEY else 'Gemini API key is not configured.',
        },
        {
            'name': 'Live AI Probe',
            'status': ai_probe['status'],
            'details': ai_probe['message'],
        },
        {
            'name': 'PDF Editing Pipeline',
            'status': 'ok',
            'details': 'PyMuPDF in-place PDF editing is active for Objective and Skills updates.',
        },
        {
            'name': 'Temporary Resume Session Mode',
            'status': 'ok',
            'details': f"One-time source cleanup is active. Active uploaded resume sessions: {len(ACTIVE_RESUME_SESSIONS)}.",
        },
        {
            'name': 'Storage Paths',
            'status': 'ok' if all(_directory_is_writable(path) for path in [UPLOAD_DIR, OUTPUT_DIR, HISTORY_DIR]) else 'warning',
            'details': f"Uploads: {UPLOAD_DIR} | Outputs: {OUTPUT_DIR} | History: {HISTORY_DIR}",
        },
        {
            'name': 'Recent Runtime',
            'status': RUNTIME_STATUS['last_generate_status'],
            'details': RUNTIME_STATUS['last_generate_message'],
        },
    ]

    severity_order = {'ok': 0, 'idle': 0, 'warning': 1, 'degraded': 2, 'outage': 3}
    worst_status = max(systems, key=lambda item: severity_order.get(item['status'], 1))['status']
    overall_status = {
        'ok': 'All systems look operational.',
        'idle': 'All systems look operational.',
        'warning': 'System is usable with warnings.',
        'degraded': 'System is up but partially degraded.',
        'outage': 'One or more critical systems look down.',
    }.get(worst_status, 'System status unavailable.')

    return jsonify({
        'success': True,
        'checked_at': datetime.now().isoformat(),
        'overall_status': worst_status,
        'overall_message': overall_status,
        'systems': systems,
        'recent_runtime': RUNTIME_STATUS,
    })


@app.route('/download/<output_file_id>')
def download(output_file_id):
    """Download generated PDF."""
    filepath = os.path.join(OUTPUT_DIR, f"{output_file_id}.pdf")
    
    if not os.path.exists(filepath):
        txt_path = os.path.join(OUTPUT_DIR, f"{output_file_id}.txt")
        if os.path.exists(txt_path):
            return jsonify({
                'error': 'This older generation only created a text fallback. Please regenerate the resume to get a real PDF.'
            }), 409
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f'tailored_resume.pdf',
        mimetype='application/pdf'
    )


@app.route('/preview/<file_id>')
def preview(file_id):
    """Preview a PDF file (original or output)."""
    cleanup_expired_resume_sessions()
    # Check uploads first
    upload_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
    if upload_files:
        filepath = os.path.join(UPLOAD_DIR, upload_files[0])
        if os.path.exists(filepath):
            response = make_response(send_file(filepath, mimetype='application/pdf'))
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
    
    # Check outputs
    output_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
    if os.path.exists(output_path):
        response = make_response(send_file(output_path, mimetype='application/pdf'))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    
    return jsonify({'error': 'File not found'}), 404


@app.route('/history')
def history():
    """History page."""
    return render_template('history.html')


@app.route('/api/history')
def api_history():
    """Get all history entries."""
    entries = get_all(HISTORY_DIR)
    return jsonify(entries)


@app.route('/api/history/<history_id>', methods=['DELETE'])
def api_delete_history(history_id):
    """Delete a history entry."""
    success = delete_history(history_id, HISTORY_DIR, OUTPUT_DIR)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Failed to delete'}), 500


@app.route('/result')
def result_page():
    """Result page (optional - can also show inline)."""
    return render_template('result.html')


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_enabled = os.getenv('FLASK_DEBUG', 'false').strip().lower() == 'true'
    app.run(host='127.0.0.1', port=port, debug=debug_enabled)
