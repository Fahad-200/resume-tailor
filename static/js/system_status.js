document.addEventListener('DOMContentLoaded', function () {
    const openButton = document.getElementById('open-system-status');
    const modal = document.getElementById('system-status-modal');
    const closeButton = document.getElementById('close-system-status');
    const runButton = document.getElementById('run-system-status');
    const passwordInput = document.getElementById('system-status-password');
    const loadingText = document.getElementById('system-status-loading');
    const errorText = document.getElementById('system-status-error');
    const summary = document.getElementById('system-status-summary');
    const grid = document.getElementById('system-status-grid');

    if (!openButton || !modal || !closeButton || !runButton || !passwordInput || !loadingText || !errorText || !summary || !grid) {
        return;
    }

    function openModal() {
        modal.classList.remove('hidden');
        passwordInput.focus();
    }

    function closeModal() {
        modal.classList.add('hidden');
        errorText.classList.add('hidden');
    }

    function setLoading(isLoading) {
        loadingText.classList.toggle('hidden', !isLoading);
        runButton.disabled = isLoading;
    }

    function statusLabel(status) {
        const labels = {
            ok: 'Operational',
            idle: 'Ready',
            warning: 'Warning',
            degraded: 'Degraded',
            outage: 'Outage'
        };
        return labels[status] || 'Unknown';
    }

    function renderStatusPayload(data) {
        summary.classList.remove('hidden');
        grid.classList.remove('hidden');

        summary.innerHTML = `
            <div class="flex flex-wrap items-center gap-3 mb-3">
                <span class="system-status-pill ${data.overall_status}">${statusLabel(data.overall_status)}</span>
                <span class="text-sm text-slate-400">${new Date(data.checked_at).toLocaleString()}</span>
            </div>
            <p class="text-white font-medium">${data.overall_message}</p>
            <p class="text-sm text-slate-400 mt-2">Last generation status: ${data.recent_runtime.last_generate_status}.</p>
        `;

        grid.innerHTML = data.systems.map(system => `
            <div class="system-status-card">
                <div class="flex items-center justify-between gap-3 mb-3">
                    <h4 class="text-white font-semibold">${system.name}</h4>
                    <span class="system-status-pill ${system.status}">${statusLabel(system.status)}</span>
                </div>
                <p class="text-sm text-slate-300">${system.details}</p>
            </div>
        `).join('');
    }

    async function runSystemCheck() {
        errorText.classList.add('hidden');
        setLoading(true);

        try {
            const response = await fetch('/api/system-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    password: passwordInput.value
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'System check failed');
            }

            renderStatusPayload(data);
        } catch (error) {
            errorText.textContent = error.message;
            errorText.classList.remove('hidden');
        } finally {
            setLoading(false);
        }
    }

    openButton.addEventListener('click', openModal);
    closeButton.addEventListener('click', closeModal);
    runButton.addEventListener('click', runSystemCheck);
    passwordInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
            runSystemCheck();
        }
    });

    modal.addEventListener('click', function (event) {
        const target = event.target;
        if (target instanceof HTMLElement && target.dataset.closeSystemStatus === 'true') {
            closeModal();
        }
    });
});
