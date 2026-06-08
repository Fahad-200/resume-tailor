# Resume Tailor — AI-Powered Resume Customization Engine

> **I built this tool because I hate editing resumes.** Every job application deserves a tailored resume, but manually tweaking formatting, rewording bullet points, and matching keywords for each application is tedious and error-prone. So I automated it — an AI-powered engine that takes your resume PDF and a job description, then produces a perfectly tailored, formatted PDF — all while preserving the original design.

> **⚠ IMPORTANT: This is a DEVELOPMENT SERVER.** It is designed for local use only (`127.0.0.1`). Do not deploy this in a production environment without adding authentication, rate limiting, and security hardening.

---

## What It Does

Upload your resume (PDF), paste a job description, and the system:

1. **Parses** your resume — extracts text, sections, fonts, colors, layout, and styling metadata
2. **Analyzes** the job description — identifies required skills, qualifications, keywords, and role requirements
3. **Rewrites** your Objective and Skills sections using AI (Google Gemini) to align with the job, **without fabricating information**
4. **Edits the PDF in-place** — updates only the text, keeping your original fonts, colors, layout, and design intact
5. **Scores ATS keyword match** before and after — see the improvement
6. **Shows a diff view** — exactly what changed, side-by-side
7. **Generates a cover letter** (optional)
8. **Cleans up** — your uploaded file is removed automatically after generation

All in ~15–30 seconds.

---

## Why This Exists (The Story)

I was applying to software development roles and found myself spending way too much time tailoring resumes. Every job description has different keywords, different priorities, and different tone expectations. I wanted a tool that:

- **Doesn't fabricate** — it only rewrites existing content to be more relevant, it never adds fake experience
- **Preserves formatting** — recruiters can tell when you paste plain text into a template
- **Gives me a score** — so I know if my resume actually matches before I submit
- **Is local and private** — my resume data never hits a third-party server (except Google's Gemini API for AI processing)

So I built this. It started as a weekend project and grew into a full-stack AI application with a modular agent architecture, PDF engineering, and a clean web UI.

---

## What I Learned Building This

Working on this project taught me a ton across the full stack:

| Area | What I Learned |
|------|---------------|
| **Backend (Python/Flask)** | REST API design, request validation, error handling, session management, file upload/download, CORS configuration |
| **AI/ML Integration** | Working with Google Gemini API, prompt engineering, structured output parsing, fallback model handling, rate limit handling, quota management |
| **PDF Engineering** | PyMuPDF (fitz) for in-place PDF text editing, pdfplumber for text extraction, WeasyPrint + ReportLab for PDF generation, font/style metadata extraction |
| **Agent Architecture** | Modular agent system — JD analyzer, resume parser, content rewriter, validator — each with single responsibility, composable pipeline |
| **Frontend (HTML/CSS/JS)** | Jinja2 templating, diff view rendering (side-by-side HTML diff), PDF.js preview, responsive UI, drag-and-drop upload |
| **Security Best Practices** | One-time session cleanup, input validation, file type restrictions, no secrets in code, environment-based configuration |
| **Tools & Workflow** | Git version control, Python virtual environments, dependency management, cross-platform Windows/Linux support |
| **Architecture Patterns** | Pipeline processing, multi-agent orchestration, caching (format cache), history management, cleanup daemons |

---

## Architecture

```
                    ┌─────────────────────┐
                    │   Browser (Client)   │
                    │  HTML / CSS / JS     │
                    └──────────┬──────────┘
                               │ HTTP (Flask)
                    ┌──────────▼──────────┐
                    │   Flask App (app.py) │
                    │  Routes, Sessions,   │
                    │  Error Handling      │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
  ┌───────▼───────┐  ┌────────▼────────┐  ┌───────▼───────┐
  │  JD Analyzer  │  │ Content Rewriter│  │   Validator   │
  │  (agent/)     │  │  (agent/)       │  │  (agent/)     │
  └───────────────┘  └─────────────────┘  └───────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Google Gemini    │
                    │    (AI Service)     │
                    └─────────────────────┘

  ┌─────────────────── Storage Layer ───────────────────┐
  │  uploads/  →  outputs/  →  history/  →  format_cache/ │
  └──────────────────────────────────────────────────────┘
```

### Key Modules

| Module | File | Purpose |
|--------|------|---------|
| **Flask App** | `app.py` | Main server — routes, session management, pipeline orchestration, error handling, health/status endpoints |
| **JD Analyzer** | `agents/jd_analyzer.py` | Extracts job title, required skills, qualifications, responsibilities, keywords from job descriptions using Gemini |
| **Content Rewriter** | `agents/content_rewriter.py` | Rewrites Objective and Skills sections to match the JD; generates cover letters |
| **Validator** | `agents/validator.py` | ATS keyword scoring — compares resume keywords against JD keywords, shows before/after scores |
| **PDF Reader** | `utils/pdf_reader.py` | Extracts text and page count from PDFs using pdfplumber |
| **Format Extractor** | `utils/format_extractor.py` | Extracts font families, sizes, colors, text positions, and layout metadata from the original PDF |
| **PDF Section Editor** | `utils/pdf_section_editor.py` | **Core innovation** — edits only the Objective and Skills text in the original PDF using PyMuPDF, preserving every visual element |
| **Diff Generator** | `utils/diff_generator.py` | Creates structured diff data and HTML diff view showing line-by-line changes |
| **AI Client** | `utils/ai_client.py` | Gemini API client with retries, fallback models, quota error handling, token management |
| **History Manager** | `utils/history_manager.py` | Stores generation history as JSON with metadata, manages cleanup of old entries |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | Flask 3.0 (Python) |
| **AI Service** | Google Gemini (gemini-2.5-flash, with fallback models) |
| **PDF Reading** | pdfplumber |
| **PDF Editing** | PyMuPDF (fitz) |
| **PDF Generation** | WeasyPrint (with GTK) / ReportLab fallback |
| **Frontend** | HTML5, CSS3, JavaScript (vanilla), Jinja2 |
| **PDF Preview** | PDF.js |
| **Configuration** | python-dotenv |
| **Platform** | Cross-platform (Windows, Linux, macOS) |

---

## Project Structure

```
resume_tailor/
├── app.py                    # Main Flask application server
├── .env.example              # Environment configuration template
├── requirements.txt          # Python package dependencies
├── .gitignore                # Git ignore rules
├── agents/                   # AI agent modules (orchestration layer)
│   ├── jd_analyzer.py       # Job description analysis & keyword extraction
│   ├── content_rewriter.py  # AI-powered resume section rewriting
│   ├── validator.py         # ATS score computation & skills gap analysis
│   └── resume_parser.py     # Resume text parsing & section detection
├── utils/                    # Utility modules (service layer)
│   ├── ai_client.py         # Gemini API client with retry & fallback logic
│   ├── pdf_reader.py        # PDF text extraction & page analysis
│   ├── pdf_section_editor.py # In-place PDF text editing engine
│   ├── format_extractor.py  # Font, color & layout metadata extraction
│   ├── diff_generator.py    # Structured diff & HTML diff rendering
│   └── history_manager.py   # Generation history JSON persistence
├── templates/                # Jinja2 HTML templates
│   ├── base.html            # Base layout with Bootstrap-like styling
│   ├── index.html           # Main upload & generation interface
│   ├── history.html         # Generation history viewer
│   └── result.html          # Results display page
├── static/                   # Static assets
│   ├── css/style.css        # Application stylesheet
│   └── js/                  # Client-side JavaScript modules
│       ├── main.js          # Core application logic
│       ├── diff_view.js     # Diff view rendering
│       ├── pdf_preview.js   # PDF preview (PDF.js integration)
│       └── system_status.js # Admin diagnostics UI
├── uploads/                  # Uploaded resume PDFs (auto-cleaned)
├── outputs/                  # Generated tailored resume PDFs
├── history/                  # Generation history JSON files
└── format_cache/            # Cached formatting metadata
```

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Google Gemini API key** — get one free at [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Git** (to clone)

### Installation

```bash
# Clone
git clone https://github.com/Fahad-200/resume-tailor.git
cd resume-tailor

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# → Edit .env and set GEMINI_API_KEY=your_key_here

# Run (development server)
python app.py
```

### Usage

1. Open **http://localhost:5000**
2. Upload your **text-based PDF resume** (drag-and-drop supported)
3. Paste a **job description** (at least 50 characters)
4. (Optional) Toggle cover letter generation, select tone
5. Click **"Tailor My Resume"**
6. Wait ~15–30 seconds
7. Download the tailored PDF + see ATS scores, diff, and cover letter

---

## Features in Detail

### Smart Resume Tailoring
The AI rewrites your Objective/Summary and Skills sections to emphasize experience relevant to the target role. It never adds fake experience — it only rephrases and re-prioritizes existing content.

### Format Preservation
Unlike other resume tools that output plain text or template-based PDFs, this tool edits the **original PDF in-place**. Your fonts, colors, layout, bullet styles, margins — everything stays exactly as designed. Only the text content of editable sections changes.

### ATS Score Analysis
Before-and-after keyword matching scores. The system extracts all keywords from the job description and checks your resume for matches, showing exactly which skills were added and which are still missing.

### Diff View
See exactly what changed — a side-by-side HTML diff of the original vs. tailored content for each section.

### Cover Letter Generation
Optional AI-generated cover letter tailored to the job, based on your resume content and the job description.

### Clean Architecture
- **One-time session model** — uploaded files are deleted after successful generation
- **Expiry-based cleanup** — stale sessions auto-expire after 2 hours
- **History retention** — last 10 generations saved with metadata
- **Health/status endpoints** — diagnostics for system monitoring

---

## System Status & Diagnostics

The app includes a protected `/api/system-status` endpoint for diagnostics:

```bash
curl -X POST http://localhost:5000/api/system-status \
  -H "Content-Type: application/json" \
  -d '{"password": "zxc"}'
```

Returns status for: Web app health, Gemini configuration, live AI probe, PDF pipeline, session storage, storage paths, and recent runtime history.

---

## Security

- **Local-only** — binds to `127.0.0.1` by default, not exposed to network
- **One-time file cleanup** — uploaded resumes deleted after generation
- **No secrets in code** — all configuration via `.env` (excluded from git)
- **File type validation** — only PDFs accepted
- **Session expiry** — idle sessions auto-clean after 2 hours
- **No data persistence** — history is local JSON, no database required

---

## About This Project

This was built as a **personal productivity tool** — I wanted to stop manually editing resumes and focus on actually applying. It's also been an incredible learning experience in:

- Building production-quality Flask applications
- Integrating and orchestrating AI services
- PDF engineering and manipulation at the binary level
- Designing modular, testable agent architectures
- Writing clean, maintainable Python

This is one of several projects I'm building and sharing. More to come.

> *Built with the assistance of coding agentic AI tools — learned immensely about prompt engineering, agent orchestration, and AI-assisted software development in the process.*

---

## License

MIT — Use freely for personal projects.

---

## Connect

**[GitHub: @Fahad-200](https://github.com/Fahad-200)**
