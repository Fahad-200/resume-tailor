// PDF Preview using PDF.js

/**
 * Render a PDF preview in a canvas element
 * @param {string} fileId - The file ID (UUID)
 * @param {string} canvasId - The canvas element ID
 * @param {boolean} isOutput - Whether this is an output file (true) or upload (false)
 */
function renderPDFPreview(fileId, canvasId, isOutput) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.error('Canvas not found:', canvasId);
        return;
    }
    
    const url = isOutput ? `/preview/${fileId}` : `/preview/${fileId}`;
    
    // Show loading state
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Loading text
    ctx.fillStyle = '#94a3b8';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Loading PDF...', canvas.width / 2, canvas.height / 2);
    
    // Load the PDF
    pdfjsLib.getDocument(url).promise.then(function(pdf) {
        // Get first page
        return pdf.getPage(1);
    }).then(function(page) {
        // Calculate scale to fit container
        const container = canvas.parentElement;
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight || 500;
        
        const viewport = page.getViewport({ scale: 1 });
        const scaleX = containerWidth / viewport.width;
        const scaleY = containerHeight / viewport.height;
        const scale = Math.min(scaleX, scaleY, 1.5); // Max scale of 1.5
        
        const scaledViewport = page.getViewport({ scale: scale });
        
        // Set canvas dimensions
        canvas.height = scaledViewport.height;
        canvas.width = scaledViewport.width;
        
        // Render the page
        const renderContext = {
            canvasContext: ctx,
            viewport: scaledViewport
        };
        
        return page.render(renderContext).promise;
    }).then(function() {
        console.log('PDF rendered successfully');
    }).catch(function(error) {
        console.error('Error rendering PDF:', error);
        
        // Show error state
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#f43f5e';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Preview unavailable', canvas.width / 2, canvas.height / 2 - 10);
        ctx.fillStyle = '#94a3b8';
        ctx.font = '12px sans-serif';
        ctx.fillText(error.message || 'Could not load PDF', canvas.width / 2, canvas.height / 2 + 15);
    });
}

/**
 * Render a specific page of a PDF
 * @param {string} fileId - The file ID
 * @param {string} canvasId - The canvas element ID
 * @param {number} pageNumber - Page number to render (1-indexed)
 */
function renderPDFPage(fileId, canvasId, pageNumber) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const url = `/preview/${fileId}`;
    const ctx = canvas.getContext('2d');
    
    pdfjsLib.getDocument(url).promise.then(function(pdf) {
        if (pageNumber > pdf.numPages) {
            pageNumber = pdf.numPages;
        }
        return pdf.getPage(pageNumber);
    }).then(function(page) {
        const container = canvas.parentElement;
        const containerWidth = container.clientWidth;
        
        const viewport = page.getViewport({ scale: 1 });
        const scale = (containerWidth / viewport.width) * 0.95;
        const scaledViewport = page.getViewport({ scale: scale });
        
        canvas.height = scaledViewport.height;
        canvas.width = scaledViewport.width;
        
        return page.render({
            canvasContext: ctx,
            viewport: scaledViewport
        }).promise;
    }).catch(function(error) {
        console.error('Error rendering page:', error);
    });
}

/**
 * Get the number of pages in a PDF
 * @param {string} fileId - The file ID
 * @returns {Promise<number>} Number of pages
 */
function getPDFPageCount(fileId) {
    const url = `/preview/${fileId}`;
    return pdfjsLib.getDocument(url).promise.then(function(pdf) {
        return pdf.numPages;
    });
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
    window.renderPDFPreview = renderPDFPreview;
    window.renderPDFPage = renderPDFPage;
    window.getPDFPageCount = getPDFPageCount;
}