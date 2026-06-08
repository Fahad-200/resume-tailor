// Diff View - Handles rendering and display of diffs

/**
 * Render diff HTML into a container
 * @param {string} diffHtml - The diff HTML string
 * @param {string} containerId - The container element ID
 */
function renderDiff(diffHtml, containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error('Diff container not found:', containerId);
        return;
    }
    
    container.innerHTML = diffHtml;
    
    // Apply dark theme to diff2html if available
    applyDarkTheme(container);
    
    // Setup collapsible sections
    setupDiffCollapsibles(container);
}

/**
 * Apply dark theme styling to diff content
 * @param {HTMLElement} container - The diff container
 */
function applyDarkTheme(container) {
    // Find and style diff lines
    const preElements = container.querySelectorAll('pre');
    preElements.forEach(pre => {
        pre.style.background = '#0f172a';
        pre.style.color = '#e2e8f0';
        pre.style.padding = '1rem';
        pre.style.borderRadius = '0.375rem';
        pre.style.overflowX = 'auto';
        pre.style.whiteSpace = 'pre-wrap';
        pre.style.wordBreak = 'break-word';
    });
    
    // Style diff lines with + and -
    const lines = container.querySelectorAll('div');
    lines.forEach(div => {
        const text = div.textContent || '';
        if (text.startsWith('+') && !text.startsWith('+++')) {
            div.style.background = 'rgba(16, 185, 129, 0.15)';
            div.style.color = '#10b981';
        } else if (text.startsWith('-') && !text.startsWith('---')) {
            div.style.background = 'rgba(244, 63, 94, 0.15)';
            div.style.color = '#f43f5e';
        } else if (text.startsWith('@@')) {
            div.style.color = '#fbbf24';
            div.style.fontWeight = 'bold';
        }
    });
}

/**
 * Setup collapsible sections for diff
 * @param {HTMLElement} container - The diff container
 */
function setupDiffCollapsibles(container) {
    // Find section headers
    const sections = container.querySelectorAll('.diff-section, h3, h4');
    
    sections.forEach(section => {
        section.style.cursor = 'pointer';
        
        // Create toggle button if not present
        if (!section.querySelector('.toggle-icon')) {
            const toggle = document.createElement('span');
            toggle.className = 'toggle-icon mr-2';
            toggle.textContent = '▼';
            toggle.style.display = 'inline-block';
            toggle.style.transition = 'transform 0.2s';
            
            if (section.tagName === 'H3' || section.tagName === 'H4') {
                section.insertBefore(toggle, section.firstChild);
            }
        }
        
        section.addEventListener('click', function() {
            const content = this.nextElementSibling;
            const toggle = this.querySelector('.toggle-icon');
            
            if (content && content.tagName === 'PRE') {
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    if (toggle) toggle.style.transform = 'rotate(0deg)';
                } else {
                    content.style.display = 'none';
                    if (toggle) toggle.style.transform = 'rotate(-90deg)';
                }
            }
        });
    });
}

/**
 * Generate a simple unified diff from two strings
 * @param {string} oldText - Original text
 * @param {string} newText - New text
 * @param {string} context - Context lines
 * @returns {string} Unified diff format
 */
function generateSimpleDiff(oldText, newText, context = 3) {
    const oldLines = oldText.split('\n');
    const newLines = newText.split('\n');
    
    // Simple diff algorithm
    let diff = '';
    let i = 0, j = 0;
    
    while (i < oldLines.length || j < newLines.length) {
        if (i < oldLines.length && j < newLines.length && oldLines[i] === newLines[j]) {
            diff += '  ' + oldLines[i] + '\n';
            i++;
            j++;
        } else if (j < newLines.length && (!oldLines[i] || newLines[j] !== oldLines[i])) {
            diff += '+ ' + newLines[j] + '\n';
            j++;
        } else if (i < oldLines.length) {
            diff += '- ' + oldLines[i] + '\n';
            i++;
        }
    }
    
    return diff;
}

/**
 * Create diff from resume sections
 * @param {Object} original - Original resume data
 * @param {Object} tailored - Tailored resume data
 * @returns {string} HTML diff
 */
function createResumeDiff(original, tailored) {
    let html = '';
    
    // Summary diff
    if (original.summary !== tailored.summary) {
        html += createSectionDiff('Summary', original.summary, tailored.summary);
    }
    
    // Experience diffs
    if (original.experience && tailored.experience) {
        original.experience.forEach((exp, i) => {
            if (tailored.experience[i]) {
                const origBullets = exp.bullets.join('\n');
                const newBullets = tailored.experience[i].bullets.join('\n');
                
                if (origBullets !== newBullets) {
                    html += createSectionDiff(
                        `Experience at ${exp.company}`,
                        origBullets,
                        newBullets
                    );
                }
            }
        });
    }
    
    // Skills diff
    const origSkills = JSON.stringify(original.skills);
    const newSkills = JSON.stringify(tailored.skills);
    if (origSkills !== newSkills) {
        html += createSectionDiff('Skills', origSkills, newSkills);
    }
    
    return html;
}

/**
 * Create a diff section
 * @param {string} title - Section title
 * @param {string} oldText - Original text
 * @param {string} newText - New text
 * @returns {string} HTML
 */
function createSectionDiff(title, oldText, newText) {
    const diff = generateSimpleDiff(oldText || '', newText || '');
    
    return `
        <div class="diff-section">
            <h4 class="text-sm uppercase tracking-wide text-slate-400 mb-2">${title}</h4>
            <pre class="bg-slate-900 p-4 rounded overflow-x-auto text-sm">${escapeHtml(diff)}</pre>
        </div>
    `;
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.renderDiff = renderDiff;
    window.generateSimpleDiff = generateSimpleDiff;
    window.createResumeDiff = createResumeDiff;
    window.escapeHtml = escapeHtml;
}