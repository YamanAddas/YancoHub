/**
 * CatByte Overlay — Standalone in-game chat companion
 * Self-contained JS for the overlay pywebview window.
 * Talks to the same Flask backend on port 8745.
 */

'use strict';

const $ = (id) => document.getElementById(id);

async function fetchJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status} from ${url}`);
    return r.json();
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function escapeAttr(s) {
    return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── State ────────────────────────────────────────────────────────────────────

const state = {
    online: false,
    currentModel: '',
    models: [],
    sessionId: null,
    chatHistory: [],
    sessions: [],
    sidebarOpen: false,
};

// ── Status ───────────────────────────────────────────────────────────────────

async function checkStatus() {
    let d = null;
    try {
        d = await fetchJSON('/api/catbyte/status');
        state.online = d.status === 'online';
    } catch {
        state.online = false;
    }

    const statusEl = $('overlayStatus');
    statusEl.textContent = state.online ? 'Online' : 'Offline';
    statusEl.classList.toggle('online', state.online);

    if (state.online && d && d.model) {
        state.currentModel = d.model;
        updateModelPill();
    }
}

// ── Model Dropdown ───────────────────────────────────────────────────────────

async function loadModels() {
    try {
        const [models, config] = await Promise.all([
            fetchJSON('/api/catbyte/models'),
            fetchJSON('/api/catbyte/config'),
        ]);
        state.models = models;
        state.currentModel = config.model || (state.models[0] || '');
        updateModelPill();
    } catch {
        state.models = [];
    }
}

function updateModelPill() {
    const el = $('overlayModelName');
    if (!el) return;
    const display = state.currentModel || 'model';
    el.textContent = display.length > 14 ? display.slice(0, 12) + '\u2026' : display;
    el.title = state.currentModel;
}

async function toggleModelDropdown(e) {
    e.stopPropagation();
    const dd = $('overlayModelDropdown');
    const wasHidden = dd.classList.contains('hidden');
    dd.classList.toggle('hidden');
    if (wasHidden) {
        dd.innerHTML = '<div class="overlay-model-option" style="color:var(--text-dim);cursor:default">Loading...</div>';
        try {
            const [models] = await Promise.all([
                fetchJSON('/api/catbyte/models'),
                fetchJSON('/api/catbyte/config'),
            ]);
            state.models = models;
        } catch { state.models = []; }
        renderModelDropdown();
    }
}

function renderModelDropdown() {
    const dd = $('overlayModelDropdown');
    if (state.models.length === 0) {
        dd.innerHTML = '<div class="overlay-model-option" style="color:var(--text-dim);cursor:default">No models found</div>';
        return;
    }
    dd.innerHTML = state.models.slice(0, 20).map(m => {
        const active = m === state.currentModel ? ' active' : '';
        return `<div class="overlay-model-option${active}" data-model="${escapeAttr(m)}">${escapeHtml(m)}</div>`;
    }).join('');

    dd.querySelectorAll('.overlay-model-option[data-model]').forEach(opt => {
        opt.addEventListener('click', async (e) => {
            e.stopPropagation();
            const model = opt.dataset.model;
            if (!model) return;
            state.currentModel = model;
            updateModelPill();
            dd.classList.add('hidden');
            try {
                await fetch('/api/catbyte/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model }),
                });
            } catch {}
        });
    });
}

// ── Sessions ─────────────────────────────────────────────────────────────────

async function loadSessions() {
    try {
        const data = await fetchJSON('/api/catbyte/sessions');
        state.sessions = data.sessions || [];
    } catch { state.sessions = []; }
    renderSidebar();
}

function renderSidebar() {
    const list = $('overlaySessionList');
    if (!list) return;
    if (state.sessions.length === 0) {
        list.innerHTML = '<div style="padding:14px;text-align:center;font-size:11px;color:var(--text-dim)">No conversations yet</div>';
        return;
    }
    list.innerHTML = state.sessions.map(s => {
        const active = s.id === state.sessionId ? ' active' : '';
        const pinIcon = s.pinned ? '<i class="ph ph-push-pin session-pin"></i>' : '';
        const timeStr = formatTimeAgo(s.updated_at);
        const preview = escapeHtml((s.preview || 'New conversation').slice(0, 35));
        return `<div class="overlay-session-item${active}" data-session-id="${escapeAttr(s.id)}">
            ${pinIcon}
            <div class="session-info">
                <div class="session-title">${escapeHtml(s.title)}</div>
                <div class="session-meta">${preview} &middot; ${timeStr}</div>
            </div>
            <div class="session-actions">
                <button class="session-action-btn" data-action="pin" title="${s.pinned ? 'Unpin' : 'Pin'}"><i class="ph ph-push-pin"></i></button>
                <button class="session-action-btn" data-action="delete" title="Delete"><i class="ph ph-trash"></i></button>
            </div>
        </div>`;
    }).join('');

    list.querySelectorAll('.overlay-session-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.closest('.session-action-btn')) return;
            selectSession(el.dataset.sessionId);
            closeSidebar();
        });
    });
    list.querySelectorAll('.session-action-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const sid = btn.closest('.overlay-session-item').dataset.sessionId;
            if (btn.dataset.action === 'delete') {
                await deleteSession(sid);
            } else if (btn.dataset.action === 'pin') {
                try {
                    await fetch(`/api/catbyte/sessions/${sid}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ pinned: true }),
                    });
                } catch {}
                await loadSessions();
            }
        });
    });
}

async function selectSession(sessionId) {
    try {
        const session = await fetchJSON(`/api/catbyte/sessions/${sessionId}`);
        if (session.error) return;

        state.sessionId = sessionId;
        state.chatHistory = (session.messages || []).map(m => ({ role: m.role, content: m.content }));

        const titleEl = $('overlaySessionTitle');
        if (titleEl) titleEl.textContent = session.title || 'CatByte';

        const container = $('overlayMessages');
        container.innerHTML = '';

        if (session.messages && session.messages.length > 0) {
            renderMessagesWithGrouping(session.messages);
        } else {
            renderEmptyState();
        }

        fetch(`/api/catbyte/sessions/${sessionId}/active`, { method: 'POST' }).catch(() => {});
        renderSidebar();
    } catch (err) {
        console.error('Failed to load session:', err);
    }
}

async function createNewChat() {
    try {
        const session = await fetchJSON('/api/catbyte/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_context: '',
                model: state.currentModel,
            }),
        });
        state.sessionId = session.id;
        state.chatHistory = [];
        $('overlaySessionTitle').textContent = session.title || 'New conversation';
        renderEmptyState();
        await loadSessions();
        closeSidebar();
        $('overlayInput').focus();
    } catch (err) {
        console.error('Failed to create session:', err);
    }
}

async function deleteSession(sessionId) {
    try {
        await fetch(`/api/catbyte/sessions/${sessionId}`, { method: 'DELETE' });
        if (state.sessionId === sessionId) {
            state.sessionId = null;
            state.chatHistory = [];
            $('overlayMessages').innerHTML = '';
        }
        await loadSessions();
        if (!state.sessionId && state.sessions.length > 0) {
            await selectSession(state.sessions[0].id);
        } else if (!state.sessionId) {
            renderEmptyState();
        }
    } catch (err) {
        console.error('Failed to delete session:', err);
    }
}

// ── Sidebar Toggle ───────────────────────────────────────────────────────────

function toggleSidebar() {
    state.sidebarOpen = !state.sidebarOpen;
    $('overlaySidebar').classList.toggle('hidden', !state.sidebarOpen);
    $('overlaySidebarBackdrop').classList.toggle('hidden', !state.sidebarOpen);
}

function closeSidebar() {
    state.sidebarOpen = false;
    $('overlaySidebar').classList.add('hidden');
    $('overlaySidebarBackdrop').classList.add('hidden');
}

// ── Send Message ─────────────────────────────────────────────────────────────

async function sendMessage() {
    const input = $('overlayInput');
    const msg = input.value.trim();
    if (!msg) return;

    if (!state.sessionId) {
        await createNewChat();
        const empty = $('overlayMessages').querySelector('.overlay-empty');
        if (empty) empty.remove();
    }

    appendChat('user', msg, Date.now() / 1000);
    input.value = '';
    input.style.height = 'auto';
    state.chatHistory.push({ role: 'user', content: msg });

    showTypingIndicator();

    try {
        const d = await fetchJSON('/api/catbyte/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                session_id: state.sessionId,
                game_context: '',
            }),
        });
        hideTypingIndicator();
        appendChat('bot', d.response, Date.now() / 1000);
        state.chatHistory.push({ role: 'assistant', content: d.response });
        loadSessions();
    } catch {
        hideTypingIndicator();
        appendChat('bot', '\uD83D\uDE3F Connection error \u2014 check your AI backend in Settings.', Date.now() / 1000);
    }
}

// ── Chat Rendering ───────────────────────────────────────────────────────────

function appendChat(role, text, ts) {
    const container = $('overlayMessages');
    const empty = container.querySelector('.overlay-empty');
    if (empty) empty.remove();

    const lastMsg = container.querySelector('.chat-msg:last-of-type');
    const lastRole = lastMsg?.classList.contains('bot') ? 'bot' : (lastMsg?.classList.contains('user') ? 'user' : null);
    const currentRole = role === 'assistant' ? 'bot' : role;
    const isGroupCont = lastRole === currentRole;

    const div = document.createElement('div');
    div.className = `chat-msg ${currentRole}${isGroupCont ? ' group-cont' : ''} animate`;

    const bubbleContent = currentRole === 'bot' ? renderMarkdown(text) : escapeHtml(text);
    const timeStr = ts ? formatMessageTime(ts) : '';
    div.innerHTML = `<div class="chat-bubble">${bubbleContent}</div>
        <div class="chat-bubble-time">${timeStr}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function renderMessagesWithGrouping(messages) {
    const container = $('overlayMessages');
    container.innerHTML = '';
    let lastRole = null;
    let lastDate = null;

    messages.forEach((m, i) => {
        const msgDate = formatDateLabel(m.ts);
        if (msgDate !== lastDate) {
            const sep = document.createElement('div');
            sep.className = 'chat-date-sep';
            sep.textContent = msgDate;
            container.appendChild(sep);
            lastDate = msgDate;
            lastRole = null;
        }

        const isGroupCont = m.role === lastRole;
        const role = m.role === 'assistant' ? 'bot' : 'user';
        const div = document.createElement('div');
        div.className = `chat-msg ${role}${isGroupCont ? ' group-cont' : ''}`;
        div.style.animationDelay = `${Math.min(i * 40, 400)}ms`;
        div.classList.add('animate');

        const bubbleContent = role === 'bot' ? renderMarkdown(m.content) : escapeHtml(m.content);
        const timeStr = formatMessageTime(m.ts);
        div.innerHTML = `<div class="chat-bubble">${bubbleContent}</div>
            <div class="chat-bubble-time">${timeStr}</div>`;
        container.appendChild(div);
        lastRole = m.role;
    });

    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

function renderEmptyState() {
    const container = $('overlayMessages');
    container.innerHTML = `<div class="overlay-empty">
        <div class="overlay-empty-avatar">😺</div>
        <h3>CatByte Overlay</h3>
        <p>Your in-game AI companion.<br>Press F10 to show/hide.</p>
        <div class="overlay-quick-actions">
            <button class="overlay-quick-btn" data-prompt="Give me tips for the game I'm playing">Game tips</button>
            <button class="overlay-quick-btn" data-prompt="Help me optimize my PC for better gaming performance">Performance help</button>
        </div>
    </div>`;
    container.querySelectorAll('.overlay-quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $('overlayInput').value = btn.dataset.prompt;
            sendMessage();
        });
    });
}

// ── Typing Indicator ─────────────────────────────────────────────────────────

function showTypingIndicator() {
    const container = $('overlayMessages');
    if (container.querySelector('.typing-wrapper')) return;
    const div = document.createElement('div');
    div.className = 'chat-msg bot animate typing-wrapper';
    div.innerHTML = '<div class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const el = $('overlayMessages').querySelector('.typing-wrapper');
    if (el) el.remove();
}

// ── Markdown Renderer ────────────────────────────────────────────────────────

function renderMarkdown(text) {
    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g,
        '<pre class="chat-codeblock"><code class="lang-$1">$2</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code class="chat-code">$1</code>');
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/^### (.+)$/gm, '<h4 class="chat-heading">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="chat-heading">$1</h3>');
    html = html.replace(/^[*\-] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
        if (/^https?:|^mailto:/i.test(url)) {
            return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`;
        }
        return text;
    });
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

// ── Time Formatting ──────────────────────────────────────────────────────────

function formatMessageTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (d.toDateString() === now.toDateString()) return time;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ', ' + time;
}

function formatDateLabel(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) return 'Today';
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function formatTimeAgo(ts) {
    if (!ts) return '';
    const now = Date.now() / 1000;
    const diff = now - ts;
    if (diff < 60) return 'now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 172800) return 'yesterday';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return new Date(ts * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// ── Textarea Auto-expand ─────────────────────────────────────────────────────

function setupInput() {
    const textarea = $('overlayInput');
    if (!textarea) return;
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    });
}

// ── Called by overlay.py when window is shown ────────────────────────────────

function onOverlayShow() {
    checkStatus();
    $('overlayInput').focus();
}

// ── Drag support ─────────────────────────────────────────────────────────────

function setupDrag() {
    const handle = $('overlayDrag');
    if (!handle) return;

    // pywebview supports drag via special attribute
    handle.style.webkitAppRegion = 'drag';
    handle.style.appRegion = 'drag';
}

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
    setupDrag();
    setupInput();

    // Check status
    await checkStatus();
    await loadModels();

    if (!state.online) {
        // Show offline state
        $('overlayMessages').innerHTML = `<div class="overlay-offline">
            <div class="overlay-offline-icon">🐱</div>
            <h3>CatByte is offline</h3>
            <p>Connect an AI backend in<br>YancoHub Settings to chat.</p>
        </div>`;
    } else {
        // Load sessions and restore or create
        await loadSessions();
        if (state.sessions.length > 0) {
            const data = await fetchJSON('/api/catbyte/sessions');
            const activeId = data.active_session_id;
            if (activeId && state.sessions.find(s => s.id === activeId)) {
                await selectSession(activeId);
            } else {
                await selectSession(state.sessions[0].id);
            }
        } else {
            renderEmptyState();
        }
    }

    // Periodic status check
    setInterval(checkStatus, 60000);

    // Event listeners
    $('overlayBtnSend').addEventListener('click', sendMessage);
    $('overlayInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    $('overlayInput').addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (state.sidebarOpen) closeSidebar();
        }
    });

    $('btnOverlayNewChat').addEventListener('click', createNewChat);
    $('btnOverlaySessions').addEventListener('click', toggleSidebar);
    $('btnCloseSidebar').addEventListener('click', closeSidebar);
    $('overlaySidebarBackdrop').addEventListener('click', closeSidebar);
    $('btnOverlayClose').addEventListener('click', () => {
        // Hide overlay via pywebview API bridge
        if (window.pywebview && window.pywebview.api && window.pywebview.api.hide_overlay) {
            window.pywebview.api.hide_overlay();
        }
    });

    $('overlayModelPill').addEventListener('click', toggleModelDropdown);
    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.overlay-model-pill')) {
            $('overlayModelDropdown').classList.add('hidden');
        }
    });
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
