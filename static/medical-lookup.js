/**
 * Medical Lookup Utility
 * Handles all API communication and response formatting
 * Compatible with the new hybrid search API (app.py v2.0)
 *
 * Response shapes handled:
 *  - local+llm  → codes[] + enrichment text
 *  - llm        → explanation text + optional codes[]
 *  - local      → codes[] only (LLM unavailable)
 *  - rejected   → non-medical query refusal
 *  - empty      → no results found
 *  - error      → server error
 */

class MedicalLookup {
    constructor() {
        this.apiEndpoint   = '/search';
        this.chatHistory   = document.getElementById('chatHistory');
        this.userInput     = document.getElementById('userInput');
        this.chatForm      = document.getElementById('chatForm');
        this.isLoading     = false;
    }

    // ─────────────────────────────────────────────────────────
    // RESPONSE FORMATTER  (handles every source type)
    // ─────────────────────────────────────────────────────────

    /**
     * Build a nicely formatted HTML string from the API response.
     * @param {Object} data  - parsed JSON from /search
     * @returns {string}     - HTML string ready for innerHTML
     */
    formatResponse(data) {

        // ── Rejected (non-medical query) ──────────────────────
        if (data.status === 'rejected') {
            return this._wrapAlert('info',
                '🚫 Not a Medical Query',
                data.message || "I can only answer medical questions about conditions, medications, symptoms, treatments, and medical codes."
            );
        }

        // ── Empty ─────────────────────────────────────────────
        if (data.status === 'empty') {
            return this._wrapAlert('info',
                '🔍 No Results Found',
                data.message || "No medical information found. Try different keywords."
            );
        }

        // ── Error ─────────────────────────────────────────────
        if (data.status === 'error') {
            return this._wrapAlert('error',
                '⚠️ Server Error',
                data.message || "Something went wrong. Please try again."
            );
        }

        // ── Success ───────────────────────────────────────────
        let html = '';

        const source      = data.source || '';
        const codes       = data.codes || [];
        const enrichment  = data.enrichment || '';
        const explanation = data.data || data.explanation || '';
        const disclaimer  = data.disclaimer || '';
        const warning     = data.warning || '';

        // 1. Warning (if any) - shown at the top as informational alert
        if (warning) {
            html += this._wrapAlert('warning',
                '⚠️ Medical Warning',
                warning
            );
        }

        // 2. Codes table (shown for local, local+llm)
        if (codes.length > 0) {
            html += this._renderCodesTable(codes);
        }

        // 3. LLM enrichment block (symptoms / conditions / clinical notes)
        if (enrichment) {
            html += this._renderRichText(enrichment, '🩺 Clinical Information');
        }

        // 4. Pure LLM explanation (when no codes found, or llm-only route)
        if (explanation && !enrichment) {
            html += this._renderRichText(explanation, '💬 Medical Answer');
        }

        // 5. Fallback if nothing rendered
        if (!html) {
            html = this._wrapAlert('info',
                '🔍 No Results',
                "No results found. Try rephrasing your medical question."
            );
        }

        // 6. Disclaimer footer
        if (disclaimer) {
            html += `<div class="disclaimer">${this._esc(disclaimer)}</div>`;
        }

        return html;
    }

    // ─────────────────────────────────────────────────────────
    // RENDER HELPERS
    // ─────────────────────────────────────────────────────────

    /** Render codes as a clean structured table — show top 3 only to avoid clutter */
    _renderCodesTable(codes) {
        const systemEmoji = {
            'ICD-10':    '🏥',
            'LOINC':     '🧪',
            'RxNorm':    '💊',
            'SNOMED CT': '🔬',
        };
        const systemColor = {
            'ICD-10':    '#e3f2fd',
            'LOINC':     '#e8f5e9',
            'RxNorm':    '#fff3e0',
            'SNOMED CT': '#f3e5f5',
        };

        // Show top 3 only — prevents overwhelming output
        const topCodes = codes.slice(0, 3);

        let rows = topCodes.map((r, i) => {
            const emoji   = systemEmoji[r.system] || '📋';
            const bgColor = systemColor[r.system] || '#f5f5f5';
            const code    = this._esc(r.code   || '—');
            const term    = this._esc(r.term   || '—');
            const system  = this._esc(r.system || '—');
            return `
                <tr>
                    <td class="col-num" style="color:#888;font-size:12px;">${i + 1}</td>
                    <td class="col-system">
                        <span class="badge" style="background:${bgColor};padding:3px 8px;border-radius:12px;font-size:12px;">
                            ${emoji} ${system}
                        </span>
                    </td>
                    <td class="col-code"><code style="background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:13px;">${code}</code></td>
                    <td class="col-term"><strong>${term}</strong></td>
                </tr>`;
        }).join('');

        const moreNote = codes.length > 3
            ? `<p style="color:#888;font-size:12px;margin-top:6px;">Showing top 3 of ${codes.length} results. Refine your query for more specific results.</p>`
            : '';

        return `
            <div class="result-section codes-section">
                <h3 style="margin-bottom:10px;">📂 Code Lookup Results</h3>
                <div class="table-wrapper" style="overflow-x:auto;">
                    <table class="codes-table" style="width:100%;border-collapse:collapse;">
                        <thead>
                            <tr style="border-bottom:2px solid #e0e0e0;font-size:12px;color:#666;text-align:left;">
                                <th style="padding:6px 8px;">#</th>
                                <th style="padding:6px 8px;">System</th>
                                <th style="padding:6px 8px;">Code</th>
                                <th style="padding:6px 8px;">Term</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
                ${moreNote}
            </div>`;
    }

    /**
     * Core renderer — parses the structured plain text from the engine
     * and converts it into rich, readable HTML cards.
     *
     * Handles:
     *   "Condition  : X"           → bold header card
     *   "Medications:"             → section header
     *   "  • Drug — RXCUI: X — Y"  → styled drug row
     *   "Symptoms  :\n  • ..."      → bullet list
     *   "Guideline : name — URL"   → clickable link pill
     *   "🔗 Source: URL"           → source link
     *   "🔗 RxNorm lookup: URL"    → source link
     *   "Answer    : ..."          → answer paragraph
     *   "Key fact  : ..."          → highlighted callout
     *   "---\n🔬 Powered by Arcee" → footer (styled separately)
     */
    _renderRichText(raw, sectionTitle) {
        if (!raw) return '';

        // ── Split off Arcee footer ────────────────────────────
        const footerSep = '\n\n---\n';
        let mainText = raw;
        let footerText = '';
        const footerIdx = raw.indexOf(footerSep);
        if (footerIdx !== -1) {
            mainText   = raw.slice(0, footerIdx).trim();
            footerText = raw.slice(footerIdx + footerSep.length).trim();
        }

        // ── Parse lines into structured blocks ────────────────
        const lines  = mainText.split('\n');
        let bodyHtml = '';

        // Accumulate bullet lists
        let inBulletList = false;
        let bulletBuffer = [];

        const flushBullets = () => {
            if (bulletBuffer.length > 0) {
                bodyHtml += `<ul class="med-bullets">` +
                    bulletBuffer.map(b => `<li>${b}</li>`).join('') +
                    `</ul>`;
                bulletBuffer = [];
                inBulletList = false;
            }
        };

        for (const rawLine of lines) {
            const line = rawLine.trimEnd();

            // ── Bullet point (  • ...) ────────────────────────
            if (/^\s+[•\-]\s+/.test(line)) {
                inBulletList = true;
                const content = line.replace(/^\s+[•\-]\s+/, '').trim();
                bulletBuffer.push(this._formatInline(content));
                continue;
            }

            // ── Flush pending bullets before next label ───────
            if (inBulletList) flushBullets();

            // ── Empty line ────────────────────────────────────
            if (!line.trim()) {
                bodyHtml += '<div style="height:6px;"></div>';
                continue;
            }

            // ── Key : Value lines ─────────────────────────────
            const kvMatch = line.match(/^([A-Za-z][A-Za-zé '\/]+?)\s*:\s*(.+)$/);
            if (kvMatch) {
                const key = kvMatch[1].trim();
                const val = kvMatch[2].trim();
                bodyHtml += this._renderKV(key, val);
                continue;
            }

            // ── Section headers ending with ":" (e.g. "Medications:") ──
            if (/^[A-Za-z][A-Za-z\s\/]+:\s*$/.test(line.trim())) {
                const label = line.trim().replace(/:$/, '');
                bodyHtml += `<div class="section-label" style="font-weight:600;color:#1565c0;margin:10px 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">${this._esc(label)}</div>`;
                continue;
            }

            // ── Source / link lines ───────────────────────────
            if (/🔗/.test(line)) {
                bodyHtml += this._renderSourceLine(line.trim());
                continue;
            }

            // ── ✅ or ⚠️ verification lines ───────────────────
            if (/^[✅⚠️]/.test(line.trim())) {
                const color = line.includes('✅') ? '#2e7d32' : '#e65100';
                bodyHtml += `<div style="color:${color};font-weight:600;margin:6px 0;font-size:13px;">${this._formatInline(line.trim())}</div>`;
                continue;
            }

            // ── ⚠️ warning line ────────────────────────────────
            if (/^⚠️/.test(line.trim())) {
                bodyHtml += `<div style="color:#e65100;font-size:12px;margin:4px 0;">${this._esc(line.trim())}</div>`;
                continue;
            }

            // ── Default: plain paragraph ──────────────────────
            bodyHtml += `<p style="margin:4px 0;line-height:1.5;">${this._formatInline(line.trim())}</p>`;
        }

        // Flush any remaining bullets
        flushBullets();

        // ── Footer (Arcee credit) ─────────────────────────────
        let footerHtml = '';
        if (footerText) {
            // Extract URL from footer
            const urlMatch = footerText.match(/(https?:\/\/[^\s—]+)/);
            const url = urlMatch ? urlMatch[1] : 'https://openrouter.ai';
            footerHtml = `
                <div class="arcee-footer" style="margin-top:12px;padding:6px 10px;background:#f8f9fa;border-left:3px solid #90a4ae;border-radius:0 4px 4px 0;font-size:11px;color:#78909c;">
                    🔬 Powered by Arcee AI (trinity-mini) via OpenRouter —
                    <a href="${this._esc(url)}" target="_blank" rel="noopener" style="color:#1565c0;">deeper research</a>
                </div>`;
        }

        return `
            <div class="result-section rich-section">
                <h3 style="margin-bottom:10px;">${sectionTitle}</h3>
                <div class="rich-body" style="font-size:14px;line-height:1.6;">
                    ${bodyHtml}
                </div>
                ${footerHtml}
            </div>`;
    }

    /** Render a key:value pair with special handling by key type */
    _renderKV(key, val) {
        const keyLower = key.toLowerCase().trim();

        // Condition header → big bold title
        if (keyLower === 'condition') {
            return `<div class="condition-header" style="background:linear-gradient(135deg,#1565c0,#1976d2);color:white;padding:8px 14px;border-radius:8px;font-weight:700;font-size:15px;margin-bottom:10px;">🏥 ${this._esc(val)}</div>`;
        }

        // Answer block → styled paragraph
        if (keyLower === 'answer') {
            return `<div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:10px 14px;border-radius:0 6px 6px 0;margin:8px 0;"><strong>📋 Answer</strong><br><span style="color:#212121;">${this._esc(val)}</span></div>`;
        }

        // Key fact → callout box
        if (keyLower === 'key fact') {
            return `<div style="background:#fff8e1;border-left:4px solid #ffa000;padding:10px 14px;border-radius:0 6px 6px 0;margin:8px 0;"><strong>💡 Key Fact</strong><br><span style="color:#333;">${this._esc(val)}</span></div>`;
        }

        // Treatment → highlighted block
        if (keyLower === 'treatment') {
            return `<div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:10px 14px;border-radius:0 6px 6px 0;margin:8px 0;"><strong>💉 Treatment</strong><br><span style="color:#212121;">${this._esc(val)}</span></div>`;
        }

        // Guideline → link pill
        if (keyLower === 'guideline' || keyLower === 'guidelines') {
            return this._renderSourceLine(`Guideline: ${val}`);
        }

        // Summary → paragraph
        if (keyLower === 'summary') {
            return `<p style="margin:6px 0;color:#333;line-height:1.6;">${this._esc(val)}</p>`;
        }

        // Code / System / Term / Details → clean metadata row
        if (['code','system','term','details'].includes(keyLower)) {
            return `<div class="meta-row" style="display:flex;gap:8px;margin:3px 0;font-size:13px;">
                <span style="min-width:80px;color:#666;font-weight:500;">${this._esc(key)}</span>
                <span style="color:#212121;font-family:monospace;">${this._esc(val)}</span>
            </div>`;
        }

        // Default key:value → label + text
        return `<div style="display:flex;gap:8px;margin:4px 0;font-size:13px;">
            <span style="min-width:90px;color:#666;font-weight:500;">${this._esc(key)}</span>
            <span style="color:#212121;">${this._esc(val)}</span>
        </div>`;
    }

    /** Render source / link lines like "🔗 Source: https://..." */
    _renderSourceLine(line) {
        // Try to extract label + URL from line like "Guideline : WHO Guidelines — https://..."
        const urlMatch = line.match(/(https?:\/\/[^\s"'<>]+)/);
        if (!urlMatch) {
            return `<div style="color:#888;font-size:12px;margin-top:6px;">${this._esc(line)}</div>`;
        }

        const url = urlMatch[1];
        // Get label — everything before the URL
        let label = line.replace(url, '').replace(/[—\-:🔗\s]+$/, '').trim();
        // Clean up common prefixes
        label = label.replace(/^(guideline\s*:|source\s*:|🔗\s*|verify\s*:)/i, '').trim();
        if (!label) label = new URL(url).hostname.replace('www.', '');

        return `<a href="${this._esc(url)}" target="_blank" rel="noopener"
            style="display:inline-flex;align-items:center;gap:6px;background:#e3f2fd;color:#1565c0;
                   padding:5px 12px;border-radius:20px;font-size:12px;font-weight:500;
                   text-decoration:none;margin:4px 4px 4px 0;border:1px solid #bbdefb;"
            onmouseover="this.style.background='#1565c0';this.style.color='white'"
            onmouseout="this.style.background='#e3f2fd';this.style.color='#1565c0'">
            🔗 ${this._esc(label)}
        </a>`;
    }

    /** Format inline text — bold **x**, italic *x*, code `x` */
    _formatInline(text) {
        return this._esc(text)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:1px 4px;border-radius:3px;">$1</code>');
    }

    /** Wrap an alert/info message */
    _wrapAlert(type, title, message) {
        const colors = {
            info:      { bg: '#e3f2fd', border: '#1565c0', icon: 'ℹ️', className: '' },
            warning:   { bg: '#fff3e0', border: '#f57c00', icon: '⚠️', className: '' },
            error:     { bg: '#ffebee', border: '#c62828', icon: '⚠️', className: '' },
        };
        const c = colors[type] || colors.info;
        
        // For emergency, preserve HTML formatting; for others, escape it
        const escapedMessage = type === 'emergency' ? message : this._esc(message);
        
        return `
            <div class="result-alert ${c.className}" style="background:${c.bg};border-left:4px solid ${c.border};padding:12px 16px;border-radius:0 8px 8px 0;margin:4px 0;">
                <strong style="color:${c.border};">${title}</strong>
                <p style="margin:4px 0 0;color:#333;font-size:13px;">${escapedMessage}</p>
            </div>`;
    }

    /** Escape HTML special characters */
    _esc(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Keep old names as aliases for backward compat
    _escapeHtml(s) { return this._esc(s); }
    _renderEnrichment(t) { return this._renderRichText(t, '🩺 Clinical Information'); }
    _renderExplanation(t) { return this._renderRichText(t, '💬 Medical Answer'); }
    _formatText(t) { return this._renderRichText(t, ''); }

    // ─────────────────────────────────────────────────────────
    // API CALL
    // ─────────────────────────────────────────────────────────

    /**
     * Send query to /search and return formatted HTML response.
     */
    async lookupMedicalInfo(query) {
        if (!query || !query.trim()) {
            return this._wrapAlert('⚠️ Empty Query', 'Please enter a valid medical question.');
        }

        try {
            const response = await fetch(this.apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query.trim() }),
            });

            // Try to parse JSON regardless of HTTP status
            let data;
            try {
                data = await response.json();
            } catch {
                throw new Error(`Server returned non-JSON response (HTTP ${response.status})`);
            }

            if (!response.ok) {
                // Still try to render if server gave us a structured error
                return this.formatResponse(data);
            }

            return this.formatResponse(data);

        } catch (error) {
            console.error('[MedicalLookup] Fetch error:', error);

            // Show specific message for network failures
            if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                return this._wrapAlert(
                    '🔌 Connection Error',
                    'Cannot reach the server. Make sure Flask is running on port 5000.'
                );
            }

            return this._wrapAlert(
                '⚠️ Unexpected Error',
                `${error.message}. Please try again or check the console for details.`
            );
        }
    }

    // ─────────────────────────────────────────────────────────
    // CHAT UI HELPERS
    // ─────────────────────────────────────────────────────────

    /** Add a message bubble to chat history */
    addMessage(htmlContent, isUser = false) {
        const article = document.createElement('article');
        article.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (isUser) {
            // User messages are plain text
            const p = document.createElement('p');
            p.textContent = htmlContent;
            contentDiv.appendChild(p);
        } else {
            // Bot messages are pre-formatted HTML
            contentDiv.innerHTML = htmlContent;
        }

        article.appendChild(contentDiv);
        this.chatHistory.appendChild(article);
        this.scrollToBottom();
    }

    /** Show animated loading bubble */
    showLoading() {
        this.isLoading = true;
        const loader = document.createElement('article');
        loader.className = 'message bot-message';
        loader.id = 'loading-message';
        loader.innerHTML = `
            <div class="message-content">
                <p class="loading-dots">
                    <span></span><span></span><span></span>
                    &nbsp;Searching medical database...
                </p>
            </div>`;
        this.chatHistory.appendChild(loader);
        this.scrollToBottom();
    }

    /** Remove loading bubble */
    hideLoading() {
        this.isLoading = false;
        const loader = document.getElementById('loading-message');
        if (loader) loader.remove();
    }

    scrollToBottom() {
        this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
    }

    // ─────────────────────────────────────────────────────────
    // FORM HANDLER
    // ─────────────────────────────────────────────────────────

    async handleSubmit(event) {
        event.preventDefault();
        if (this.isLoading) return;

        const query = this.userInput.value.trim();
        if (!query) return;

        this.addMessage(query, true);   // user bubble (plain text)
        this.userInput.value = '';
        this.showLoading();

        const htmlResponse = await this.lookupMedicalInfo(query);

        this.hideLoading();
        this.addMessage(htmlResponse, false);  // bot bubble (HTML)
    }

    // ─────────────────────────────────────────────────────────
    // INIT
    // ─────────────────────────────────────────────────────────

    init() {
        if (this.chatForm) {
            this.chatForm.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        if (this.userInput) {
            this.userInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.chatForm?.dispatchEvent(new Event('submit'));
                }
            });
        }

        console.log('[MedicalLookup] Initialized — API endpoint:', this.apiEndpoint);
    }
}

// Make available globally
window.MedicalLookup = MedicalLookup;