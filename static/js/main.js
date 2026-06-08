// Main application JavaScript

// Global state
let uploadedFileId = null;
let currentResultData = null;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initUploadArea();
    initJDInput();
    initTabs();
    initGenerateButton();
});

// Initialize upload area with drag and drop
function initUploadArea() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('resume-file');
    const uploadAgain = document.getElementById('upload-again');
    const retryUpload = document.getElementById('retry-upload');
    
    if (!uploadArea || !fileInput) return;
    
    // Click to browse
    uploadArea.addEventListener('click', function(e) {
        if (e.target.id !== 'upload-again' && e.target.id !== 'retry-upload') {
            fileInput.click();
        }
    });
    
    // File input change
    fileInput.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            uploadFile(this.files[0]);
        }
    });
    
    // Drag and drop
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.type === 'application/pdf') {
                uploadFile(file);
            } else {
                showUploadError('Only PDF files are allowed');
            }
        }
    });
    
    // Retry upload
    if (retryUpload) {
        retryUpload.addEventListener('click', function(e) {
            e.stopPropagation();
            resetUploadArea();
        });
    }
    
    // Upload again button
    if (uploadAgain) {
        uploadAgain.addEventListener('click', function(e) {
            e.stopPropagation();
            resetUploadArea();
        });
    }
}

// Upload file to server
function uploadFile(file) {
    // Validate file
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showUploadError('Only PDF files are allowed');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
        showUploadError('File size must be less than 10MB');
        return;
    }
    
    const formData = new FormData();
    formData.append('resume_pdf', file);
    
    // Show loading state
    showUploadLoading();
    
    fetch('/upload-template', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            uploadedFileId = data.file_id;
            showUploadSuccess(data);
            
            // Render PDF preview
            if (window.renderPDFPreview) {
                renderPDFPreview(data.file_id, 'pdf-preview-canvas', false);
            }
        } else {
            showUploadError(data.error || 'Upload failed');
        }
    })
    .catch(err => {
        console.error('Upload error:', err);
        showUploadError('Failed to upload file');
    });
}

// Show upload loading state
function showUploadLoading() {
    const placeholder = document.getElementById('upload-placeholder');
    const success = document.getElementById('upload-success');
    const error = document.getElementById('upload-error');
    
    if (placeholder) placeholder.classList.add('hidden');
    if (success) success.classList.add('hidden');
    if (error) error.classList.remove('hidden');
    
    // Show a simple loading state in placeholder
    if (placeholder) {
        placeholder.innerHTML = '<div class="loading-spinner mx-auto"></div><p class="text-slate-400 mt-4">Uploading...</p>';
        placeholder.classList.remove('hidden');
    }
}

// Show upload success state
function showUploadSuccess(data) {
    const placeholder = document.getElementById('upload-placeholder');
    const success = document.getElementById('upload-success');
    const error = document.getElementById('upload-error');
    const sectionsDetected = document.getElementById('sections-detected');
    const sectionsList = document.getElementById('sections-list');
    
    if (placeholder) placeholder.classList.add('hidden');
    if (error) error.classList.add('hidden');
    if (success) success.classList.remove('hidden');
    
    // Update filename and page info
    const filename = document.getElementById('filename');
    const pageInfo = document.getElementById('page-info');
    const styleSessionNote = document.getElementById('style-session-note');
    
    if (filename) filename.textContent = data.filename;
    if (pageInfo) pageInfo.textContent = `${data.page_count} page(s)`;
    if (styleSessionNote && data.style_mode_available) {
        styleSessionNote.textContent = 'Uploaded PDF style is captured for this run only. After generation, the source resume is cleared and you will upload again for a new JD.';
    }
    
    // Show detected sections
    if (sectionsDetected && data.sections_detected) {
        sectionsList.innerHTML = data.sections_detected.map(s => 
            `<span class="px-2 py-1 bg-slate-700 rounded text-xs">${s}</span>`
        ).join('');
        sectionsDetected.classList.remove('hidden');
    }
    
    // Check if we can enable generate button
    checkGenerateButton();
}

// Show upload error
function showUploadError(message) {
    const placeholder = document.getElementById('upload-placeholder');
    const success = document.getElementById('upload-success');
    const error = document.getElementById('upload-error');
    const errorMessage = document.getElementById('error-message');
    
    if (placeholder) placeholder.classList.add('hidden');
    if (success) success.classList.add('hidden');
    if (error) error.classList.remove('hidden');
    if (errorMessage) errorMessage.textContent = message;
}

// Reset upload area
function resetUploadArea() {
    uploadedFileId = null;
    
    const placeholder = document.getElementById('upload-placeholder');
    const success = document.getElementById('upload-success');
    const error = document.getElementById('upload-error');
    const sectionsDetected = document.getElementById('sections-detected');
    const fileInput = document.getElementById('resume-file');
    
    if (fileInput) fileInput.value = '';
    
    if (placeholder) {
        placeholder.innerHTML = `
            <svg class="w-16 h-16 mx-auto text-slate-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
            <p class="text-slate-400 mb-2">Drag & drop your PDF resume here</p>
            <p class="text-slate-500 text-sm">or click to browse</p>
        `;
        placeholder.classList.remove('hidden');
    }
    
    if (success) success.classList.add('hidden');
    if (error) error.classList.add('hidden');
    if (sectionsDetected) sectionsDetected.classList.add('hidden');
    
    checkGenerateButton();
}

// Initialize JD textarea
function initJDInput() {
    const jdTextarea = document.getElementById('job-description');
    const charCount = document.getElementById('char-count');
    
    if (!jdTextarea) return;
    
    jdTextarea.addEventListener('input', function() {
        const length = this.value.length;
        if (charCount) {
            charCount.textContent = `${length} characters`;
            
            if (length < 50) {
                charCount.className = 'text-sm text-rose-400';
            } else if (length < 200) {
                charCount.className = 'text-sm text-amber-400';
            } else {
                charCount.className = 'text-sm text-emerald-400';
            }
        }
        
        checkGenerateButton();
    });
}

// Check if generate button should be enabled
function checkGenerateButton() {
    const generateBtn = document.getElementById('generate-btn');
    const jdTextarea = document.getElementById('job-description');
    
    if (!generateBtn) return;
    
    const hasFile = uploadedFileId !== null;
    const hasJD = jdTextarea && jdTextarea.value.length >= 50;
    
    generateBtn.disabled = !(hasFile && hasJD);
}

// Initialize tabs
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchTab(tabName);
        });
    });
}

// Switch tabs
function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('text-indigo-400', 'border-b-2', 'border-indigo-500');
            btn.classList.remove('text-slate-400');
        } else {
            btn.classList.remove('text-indigo-400', 'border-b-2', 'border-indigo-500');
            btn.classList.add('text-slate-400');
        }
    });
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    
    const targetContent = document.getElementById(`tab-${tabName}`);
    if (targetContent) {
        targetContent.classList.remove('hidden');
    }
}

// Initialize generate button
function initGenerateButton() {
    const generateBtn = document.getElementById('generate-btn');
    const generateCoverLetter = document.getElementById('generate-cover-letter');
    const toneSelect = document.getElementById('tone-select');
    
    if (!generateBtn) return;
    
    generateBtn.addEventListener('click', generateResume);
}

// Generate resume
function generateResume() {
    const jdTextarea = document.getElementById('job-description');
    const generateCoverLetter = document.getElementById('generate-cover-letter');
    const toneSelect = document.getElementById('tone-select');
    const generateBtn = document.getElementById('generate-btn');
    const loadingState = document.getElementById('loading-state');
    const loadingText = document.getElementById('loading-text');
    const progressBar = document.getElementById('progress-bar');
    
    // Validate
    if (!uploadedFileId) {
        showFlashMessage('Please upload a resume first', 'error');
        return;
    }
    
    if (!jdTextarea || jdTextarea.value.length < 50) {
        showFlashMessage('Please enter a job description (at least 50 characters)', 'error');
        return;
    }
    
    // Prepare request
    const requestData = {
        file_id: uploadedFileId,
        job_description: jdTextarea.value,
        options: {
            generate_cover_letter: generateCoverLetter ? generateCoverLetter.checked : false,
            tone: toneSelect ? toneSelect.value : 'professional'
        }
    };
    
    // Show loading state
    generateBtn.disabled = true;
    loadingState.classList.remove('hidden');
    
    // Animate progress
    let progress = 0;
    const progressMessages = [
        'Analyzing Job Description...',
        'Observing Uploaded PDF Style...',
        'Tailoring Objective and Skills...',
        'Generating PDF...',
        'Finalizing...'
    ];
    
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 95) progress = 95;
        
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        
        const msgIndex = Math.min(Math.floor(progress / 20), progressMessages.length - 1);
        if (loadingText) {
            loadingText.textContent = progressMessages[msgIndex];
        }
    }, 800);
    
    // Send request
    fetch('/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(res => res.json())
    .then(data => {
        clearInterval(progressInterval);
        
        if (data.success) {
            currentResultData = data;
            
            // Complete progress
            if (progressBar) progressBar.style.width = '100%';
            if (loadingText) loadingText.textContent = 'Complete!';
            
            setTimeout(() => {
                loadingState.classList.add('hidden');
                showResults(data);
                if (data.source_session_cleared) {
                    resetUploadArea();
                    showFlashMessage('Source resume session cleared after generation. Upload again for the next JD.', 'warning');
                }
            }, 500);
        } else {
            clearInterval(progressInterval);
            loadingState.classList.add('hidden');
            generateBtn.disabled = false;
            showFlashMessage(data.error || 'Generation failed', 'error');
        }
    })
    .catch(err => {
        clearInterval(progressInterval);
        console.error('Generation error:', err);
        loadingState.classList.add('hidden');
        generateBtn.disabled = false;
        showFlashMessage('Failed to generate resume', 'error');
    });
}

// Show results
function showResults(data) {
    const resultsSection = document.getElementById('results-section');
    
    if (resultsSection) {
        resultsSection.classList.remove('hidden');
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Populate resume preview
    if (window.renderPDFPreview && data.output_file_id) {
        renderPDFPreview(data.output_file_id, 'result-pdf-canvas', true);
    }
    
    // Update download button
    const downloadBtn = document.getElementById('download-pdf');
    if (downloadBtn && data.output_file_id) {
        downloadBtn.onclick = function() {
            window.location.href = `/download/${data.output_file_id}`;
        };
    }
    
    // Populate ATS scores
    renderATSScore(data.ats_score_before, data.ats_score_after);
    
    // Populate keywords
    populateKeywords(data);
    
    // Populate diff
    const diffContent = document.getElementById('diff-content');
    const changesSummary = document.getElementById('changes-summary');
    if (diffContent && data.diff_html) {
        diffContent.innerHTML = data.diff_html;
    }
    if (changesSummary && data.changes_summary) {
        changesSummary.textContent = data.changes_summary;
    }
    
    // Show cover letter tab if available
    if (data.cover_letter) {
        const coverTab = document.querySelector('[data-tab="cover"]');
        if (coverTab) {
            coverTab.classList.remove('hidden');
        }
        
        const coverContent = document.getElementById('cover-letter-content');
        if (coverContent) {
            coverContent.innerHTML = data.cover_letter.replace(/\n/g, '<br>');
        }
        
        const downloadCoverBtn = document.getElementById('download-cover');
        if (downloadCoverBtn) {
            downloadCoverBtn.classList.remove('hidden');
            downloadCoverBtn.onclick = function() {
                const blob = new Blob([data.cover_letter], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'cover_letter.txt';
                a.click();
            };
        }
    }
    
    // Switch to first tab
    switchTab('resume');
}

// Render ATS score gauges
function renderATSScore(before, after) {
    const beforeScore = document.getElementById('score-before');
    const afterScore = document.getElementById('score-after');
    const beforeCircle = document.getElementById('score-before-circle');
    const afterCircle = document.getElementById('score-after-circle');
    
    const circumference = 2 * Math.PI * 56; // 351.86
    
    // Animate before score
    animateValue(beforeScore, 0, before, 1500);
    if (beforeCircle) {
        const offset = circumference - (before / 100) * circumference;
        beforeCircle.style.strokeDashoffset = offset;
        beforeCircle.classList.add(getScoreColorClass(before));
    }
    
    // Animate after score
    setTimeout(() => {
        animateValue(afterScore, 0, after, 1500);
        if (afterCircle) {
            const offset = circumference - (after / 100) * circumference;
            afterCircle.style.strokeDashoffset = offset;
            afterCircle.classList.add(getScoreColorClass(after));
        }
    }, 300);
}

// Animate number value
function animateValue(element, start, end, duration) {
    if (!element) return;
    
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.round(start + (end - start) * progress);
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Get score color class
function getScoreColorClass(score) {
    if (score >= 71) return 'text-emerald-500';
    if (score >= 41) return 'text-amber-500';
    return 'text-rose-500';
}

// Populate keywords
function populateKeywords(data) {
    const keywordsAdded = document.getElementById('keywords-added');
    const keywordsMissing = document.getElementById('keywords-missing');
    const skillsGap = document.getElementById('skills-gap');
    
    if (keywordsAdded && data.keywords_added) {
        keywordsAdded.innerHTML = data.keywords_added.map(kw => 
            `<span class="keyword-chip keyword-chip-added">${kw}</span>`
        ).join('') || '<span class="text-slate-400">None</span>';
    }
    
    if (keywordsMissing && data.keywords_missing) {
        keywordsMissing.innerHTML = data.keywords_missing.map(kw => 
            `<span class="keyword-chip keyword-chip-missing">${kw}</span>`
        ).join('') || '<span class="text-emerald-400">All matched!</span>';
    }
    
    if (skillsGap && data.skills_gap) {
        skillsGap.innerHTML = data.skills_gap.map(skill => 
            `<span class="keyword-chip keyword-chip-gap">${skill}</span>`
        ).join('') || '<span class="text-slate-400">No gaps found</span>';
    }
}

// Show flash message
function showFlashMessage(message, type) {
    const container = document.getElementById('flash-messages');
    if (!container) return;
    
    const div = document.createElement('div');
    div.className = `flash-message ${type}`;
    div.textContent = message;
    
    container.appendChild(div);
    
    // Auto dismiss
    setTimeout(() => {
        div.style.opacity = '0';
        setTimeout(() => div.remove(), 300);
    }, 4000);
}
