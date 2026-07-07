function getDeleteUrl(id) {
    if (window.chatUrlTemplates && window.chatUrlTemplates.deleteMessage) {
        return window.chatUrlTemplates.deleteMessage.replace('/0/', `/${id}/`);
    }
    return `/tickets/message/${id}/delete/`;
}

function getEditUrl(id) {
    if (window.chatUrlTemplates && window.chatUrlTemplates.editMessage) {
        return window.chatUrlTemplates.editMessage.replace('/0/', `/${id}/`);
    }
    return `/tickets/message/${id}/edit/`;
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function getCsrfToken() {
    const input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
}

// ── Optimistic UI: Pending Message Tracker ──
// Tracks messages that have been optimistically rendered but not yet confirmed by WebSocket.
// Key: pendingKey (timestamp-based), Value: { element, messageText, timeoutId }
const pendingMessages = {};
const PENDING_CONFIRM_TIMEOUT_MS = 8000; // Promote to "Sent" if WS doesn't confirm in 8s

function initChat(ticketId) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const socket = new WebSocket(`${protocol}//${host}/ws/tickets/${ticketId}/`);

    const chatBox = document.getElementById('chat-box');

    socket.onopen = function() {
        console.log(`[Chat WS] Connected to ticket ${ticketId}`);
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log("[Chat WS] message:", data);

        if (data.event === "message_created") {
            appendMessage(data.payload);
        } else if (data.event === "ticket_status_changed") {
            updateTicketStatus(data.payload);
        } else if (data.event === "ticket_picked") {
            updateTicketPicked(data.payload);
        } else if (data.event === "message_deleted") {
            removeMessage(data.payload);
        } else if (data.event === "message_edited") {
            updateMessage(data.payload);
        } else if (data.event === "typing") {
            showTypingIndicator(data.payload);
        } else if (data.event === "ticket_transfer_update") {
            window.location.reload();
        }
    };

    // --- Typing indicator logic ---
    let lastTypingSent = 0;
    const TYPING_THROTTLE_MS = 1500;
    const TYPING_EXPIRE_MS = 3000;
    const activeTypers = {};  // { sender_id: { username, timeout } }

    const chatTextarea = document.querySelector('.chat-form textarea[name="message"]');
    if (chatTextarea) {
        chatTextarea.addEventListener('input', function() {
            if (!this.value.trim()) return;  // Don't signal on empty/clearing
            const now = Date.now();
            if (now - lastTypingSent > TYPING_THROTTLE_MS && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: "typing" }));
                lastTypingSent = now;
            }
        });
    }

    function showTypingIndicator(payload) {
        if (String(payload.sender) === window.userId) return;

        const key = String(payload.sender);

        // Clear existing timeout for this user
        if (activeTypers[key]) clearTimeout(activeTypers[key].timeout);

        // Set auto-expire
        activeTypers[key] = {
            username: payload.sender_username,
            timeout: setTimeout(() => {
                delete activeTypers[key];
                renderTypingIndicator();
            }, TYPING_EXPIRE_MS),
        };

        renderTypingIndicator();
    }

    function hideTypingForUser(senderId) {
        const key = String(senderId);
        if (activeTypers[key]) {
            clearTimeout(activeTypers[key].timeout);
            delete activeTypers[key];
            renderTypingIndicator();
        }
    }

    function renderTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        const usernameEl = document.getElementById('typing-username');
        if (!indicator || !usernameEl) return;

        const names = Object.values(activeTypers).map(t => t.username);

        if (names.length === 0) {
            indicator.classList.remove('visible');
            return;
        }

        if (names.length === 1) {
            usernameEl.textContent = names[0];
        } else if (names.length === 2) {
            usernameEl.textContent = names.join(' and ');
        } else {
            usernameEl.textContent = names.slice(0, 2).join(', ') + ' and others';
        }

        indicator.style.display = 'flex';
        // Force reflow then add class for smooth transition
        void indicator.offsetWidth;
        indicator.classList.add('visible');

        // Auto-scroll chat to keep indicator visible
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < 80;
            if (isNearBottom) {
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
    }

    function removeMessage(payload) {
        const el = document.getElementById('message-' + payload.id) ||
                   document.querySelector('[data-message-id="' + payload.id + '"]');
        if (el) {
            el.style.transition = 'opacity 0.3s, transform 0.3s';
            el.style.opacity = '0';
            el.style.transform = 'scale(0.95)';
            setTimeout(() => el.remove(), 300);
        }
    }

    function updateMessage(payload) {
        const display = document.getElementById('msg-display-' + payload.id);
        if (display) {
            const p = display.querySelector('p');
            if (p) p.textContent = payload.message;
        }
        // Hide edit form if open
        const editForm = document.getElementById('msg-edit-' + payload.id);
        if (editForm) {
            editForm.style.display = 'none';
            const displayDiv = document.getElementById('msg-display-' + payload.id);
            if (displayDiv) displayDiv.style.display = 'block';
        }
    }

    function updateTicketStatus(payload) {
        const newStatus = payload.status || payload.new_status;
        const isCurrentlyClosed = document.querySelector('.action-bar-closed-badge') !== null;
        
        // If transitioning to or from a closed/merged state, reload to update the action bar UI
        if ((newStatus === 'closed' || newStatus === 'merged') !== isCurrentlyClosed) {
            window.location.reload();
            return;
        }

        // Update status badge
        const statusPill = document.querySelector('.ticket-status-pill');
        if (statusPill) {
            statusPill.className = `badge badge-${payload.status} ticket-status-pill`;
            statusPill.textContent = payload.status_display || payload.new_status_display;
        }

        // Update status select dropdown
        const statusSelect = document.querySelector('.status-update-form select[name="status"]');
        if (statusSelect) {
            statusSelect.value = payload.status;
        }

        // Show/hide closed/merged ticket UI
        if (payload.status === 'closed' || payload.status === 'merged') {
            // Hide chat form
            const chatForm = document.querySelector('.chat-form');
            if (chatForm) chatForm.style.display = 'none';
        } else {
            const chatForm = document.querySelector('.chat-form');
            if (chatForm) chatForm.style.display = '';
        }

        // Add timeline entry
        addTimelineEntry(payload.status, payload.status_display || payload.new_status_display, payload.changed_by);
    }

    function updateTicketPicked(payload) {
        // Update assigned to
        const assignedSpan = document.getElementById('ticket-assigned-to') || document.querySelector('.meta-grid .meta-item:nth-child(4) span:last-child');
        if (assignedSpan) {
            assignedSpan.textContent = payload.assigned_to || 'Pending Support Agent';
        }

        // Update status badge
        const statusPill = document.querySelector('.ticket-status-pill');
        if (statusPill) {
            statusPill.className = `badge badge-${payload.status} ticket-status-pill`;
            statusPill.textContent = payload.status_display;
        }

        // Hide pick button if exists
        const pickForm = document.querySelector('form[action*="pick_ticket"]');
        if (pickForm) {
            pickForm.style.display = 'none';
        }

        // Update status select dropdown
        const statusSelect = document.querySelector('.status-update-form select[name="status"]');
        if (statusSelect) {
            statusSelect.value = payload.status;
        }

        // Add timeline entry
        addTimelineEntry(payload.status, payload.status_display, payload.picked_by);

        // Reload the page if the current user's permissions need to change
        const newAssigneeId = String(payload.assigned_to_id || '');
        const currentAssigneeId = window.ticketAssigneeId || '';
        
        if (newAssigneeId !== currentAssigneeId) {
            if (newAssigneeId === window.userId || currentAssigneeId === window.userId) {
                window.location.reload();
                return;
            }
            window.ticketAssigneeId = newAssigneeId;
        }
    }

    function addTimelineEntry(status, statusDisplay, changedBy) {
        const timelineList = document.querySelector('.timeline-list');
        if (!timelineList) return;

        const now = new Date();
        const timeStr = now.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '');

        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `
            <span class="timeline-dot status-${status}"></span>
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="badge badge-${status}" style="font-size: 0.7rem;">${statusDisplay}</span>
                    <span class="timeline-time" style="font-size: 0.7rem;">${timeStr}</span>
                </div>
                <p style="font-size: 0.8rem; margin: 0.2rem 0;">By ${changedBy || 'Unknown'}</p>
            </div>
        `;
        
        // Remove "No updates" message if present
        const emptyMsg = timelineList.querySelector('.timeline-empty');
        if (emptyMsg) emptyMsg.remove();

        timelineList.appendChild(item);
    }

    function appendMessage(payload) {
        // Instantly clear typing indicator for this sender
        hideTypingForUser(payload.sender);

        let chatBox = document.getElementById('chat-box');
        
        // If chatBox doesn't exist (e.g., initial empty state), try to find/create container
        if (!chatBox) {
            const container = document.querySelector('.chat-panel');
            if (container) {
                // Remove the "No messages yet" placeholder if it exists
                const placeholder = container.querySelector('.no-messages-text');
                if (placeholder) placeholder.remove();

                chatBox = document.createElement('div');
                chatBox.id = 'chat-box';
                chatBox.className = 'chat-box';
                
                // Insert before the typing indicator, or chat-form as fallback
                const indicator = container.querySelector('#typing-indicator');
                const form = container.querySelector('.chat-form');
                if (indicator) {
                    container.insertBefore(chatBox, indicator);
                } else if (form) {
                    container.insertBefore(chatBox, form);
                } else {
                    container.appendChild(chatBox);
                }
            }
        }

        if (!chatBox) return;

        if (document.getElementById(`message-${payload.id}`)) return;

        // ── Optimistic UI: Replace pending message if this is a confirmation ──
        // Check if this incoming WS message matches any pending optimistic message.
        // Match by sender + similar text (the server message should match what we sent).
        const isMe = String(payload.sender) === window.userId;
        if (isMe) {
            const matchedKey = _findMatchingPendingMessage(payload.message);
            if (matchedKey) {
                const pending = pendingMessages[matchedKey];
                if (pending.timeoutId) clearTimeout(pending.timeoutId);
                if (pending.element) pending.element.remove();
                delete pendingMessages[matchedKey];
            }
        }

        if (payload.is_system_message) {
            const row = document.createElement('div');
            row.id = `message-${payload.id}`;
            row.className = 'chat-system-message-row';
            row.dataset.messageId = payload.id;
            row.innerHTML = `
                <div class="chat-system-message-content">
                    <span>${escapeHtml(payload.message)}</span>
                </div>
            `;
            chatBox.appendChild(row);
            chatBox.scrollTop = chatBox.scrollHeight;
            return;
        }

        const dateObj = new Date(payload.created_at);
        const timeStr = isNaN(dateObj) ? '' : dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        const fullDateStr = isNaN(dateObj) ? '' : dateObj.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '');

        const article = document.createElement('article');
        article.id = `message-${payload.id}`;
        article.className = `chat-item ${isMe ? 'me' : ''}`;
        article.dataset.messageId = payload.id;
        article.dataset.sender = payload.sender_username;

        const reply = payload.reply_to || null;

        const isSuper = window.userIsSuperuser || false;
        const canEdit = window.chatPermissions && window.chatPermissions.canEdit && (isMe || isSuper);
        const canDelete = window.chatPermissions && window.chatPermissions.canDelete && (isMe || isSuper);

        const menuItems = [
            canEdit ? `<button type="button" class="message-menu-item" onclick="toggleEdit(${payload.id}); closeMessageMenu(${payload.id});">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                Edit
            </button>` : '',
            canDelete ? `<form action="${getDeleteUrl(payload.id)}" method="post" onsubmit="return confirm('Are you sure you want to delete this message?');">
                <input type="hidden" name="csrfmiddlewaretoken" value="${getCsrfToken()}">
                <button type="submit" class="message-menu-item danger">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    Delete
                </button>
            </form>` : '',
            `<button type="button" class="message-menu-item" onclick="toggleMessageDetails(${payload.id}); closeMessageMenu(${payload.id});">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                Details
            </button>`
        ].filter(Boolean).join('');

        article.innerHTML = `
            <div class="chat-row">
                <div class="chat-bubble">
                    <header>
                        <strong>${payload.sender_username}</strong>
                        </header>
                    <div id="msg-display-${payload.id}">
                        ${reply ? `
                            <div class="message-reply-quote">
                                <div class="reply-quote-meta">
                                    <span class="reply-quote-sender">${escapeHtml(reply.sender_username || '')}</span>
                                </div>
                                <div class="reply-quote-text">${escapeHtml(reply.message || '')}</div>
                            </div>
                        ` : ''}
                        <div class="chat-bubble-text">${payload.message}</div>
                        ${payload.attachment_url ? (
                            payload.attachment_url.match(/\.(jpg|jpeg|png|gif|webp|bmp|svg)($|\?)/i) ? `
                            <div style="margin-top: 0.5rem;">
                                <img src="${payload.attachment_url}" alt="Attachment" class="chat-image-preview" onclick="openLightbox(this.src)">
                            </div>
                            ` : `
                            <div style="margin-top: 0.5rem;">
                                <a href="${payload.attachment_url}" target="_blank" download style="color: ${isMe ? '#fff' : 'var(--primary)'}; font-size: 0.8rem; text-decoration: underline;">
                                    📎 ${payload.attachment_name || 'View Attachment'}
                                </a>
                            </div>
                            `
                        ) : ''}
                    </div>
                </div>
                <div class="chat-actions-outside">
                    <div class="chat-time" title="${fullDateStr}">${timeStr}</div>
                    <button type="button" class="message-reply-btn" data-preview="${escapeHtml(payload.message)}" data-sender="${escapeHtml(payload.sender_username)}" onclick="replyToMessage(this)" aria-label="Reply">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"></polyline><path d="M4 12h11a4 4 0 0 1 0 8h-1"></path></svg>
                    </button>
                    <div class="message-menu-wrapper">
                        <button type="button" class="message-menu-btn" onclick="toggleMessageMenu(${payload.id})" aria-label="Message options">
                            <span></span><span></span><span></span>
                        </button>
                        <div class="message-menu" id="message-menu-${payload.id}">
                            ${menuItems}
                        </div>
                    </div>
                </div>
            </div>
            <div class="message-details" id="message-details-${payload.id}">
                <span>Sender: ${payload.sender_username}</span>
                <span>Time: ${fullDateStr}</span>
            </div>
            ${canEdit ? `
            <form id="msg-edit-${payload.id}" action="${getEditUrl(payload.id)}" method="post" class="msg-edit-form" style="display: none;">
                <input type="hidden" name="csrfmiddlewaretoken" value="${getCsrfToken()}">
                <textarea name="message" rows="2" class="chat-textarea-no-resize">${payload.message}</textarea>
                <div class="msg-edit-actions">
                    <button type="button" class="btn-edit-cancel" onclick="toggleEdit(${payload.id})">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        Cancel
                    </button>
                    <button type="submit" class="btn-edit-save">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        Save
                    </button>
                </div>
            </form>` : ''}
        `;

        chatBox.appendChild(article);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    socket.onclose = function(e) {
        console.log("[Chat WS] Closed. Reconnecting...");
        setTimeout(() => initChat(ticketId), 3000);
    };

    socket.onerror = function(err) {
        console.error("[Chat WS] Error:", err);
    };
}

// ══════════════════════════════════════════════════════════════════
// Optimistic UI: Pending Message Functions
// ══════════════════════════════════════════════════════════════════

/**
 * Find a pending message whose text matches the incoming confirmed message.
 * Uses normalized comparison (trim + collapse whitespace).
 */
function _findMatchingPendingMessage(confirmedText) {
    const normalize = (s) => (s || '').trim().replace(/\s+/g, ' ');
    const target = normalize(confirmedText);
    for (const key of Object.keys(pendingMessages)) {
        if (normalize(pendingMessages[key].messageText) === target) {
            return key;
        }
    }
    return null;
}

/**
 * Render an optimistic (pending) message bubble in the chat.
 * Called immediately when the user clicks Send, before the HTTP request completes.
 * Returns the pendingKey for tracking.
 */
function appendOptimisticMessage(messageText, replyData) {
    let chatBox = document.getElementById('chat-box');

    // Create chat-box if it doesn't exist (empty chat state)
    if (!chatBox) {
        const container = document.querySelector('.chat-panel');
        if (container) {
            const placeholder = container.querySelector('.no-messages-text');
            if (placeholder) placeholder.remove();

            chatBox = document.createElement('div');
            chatBox.id = 'chat-box';
            chatBox.className = 'chat-box';

            const indicator = container.querySelector('#typing-indicator');
            const form = container.querySelector('.chat-form');
            if (indicator) {
                container.insertBefore(chatBox, indicator);
            } else if (form) {
                container.insertBefore(chatBox, form);
            } else {
                container.appendChild(chatBox);
            }
        }
    }

    if (!chatBox) return null;

    const pendingKey = 'pending-' + Date.now();
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    const username = window.currentUsername || 'You';

    const article = document.createElement('article');
    article.id = pendingKey;
    article.className = 'chat-item me pending';
    article.dataset.pendingKey = pendingKey;

    const replyHtml = replyData ? `
        <div class="message-reply-quote">
            <div class="reply-quote-meta">
                <span class="reply-quote-sender">${escapeHtml(replyData.sender)}</span>
            </div>
            <div class="reply-quote-text">${escapeHtml(replyData.text)}</div>
        </div>
    ` : '';

    article.innerHTML = `
        <div class="chat-row">
            <div class="chat-bubble">
                <header><strong>${escapeHtml(username)}</strong></header>
                <div>
                    ${replyHtml}
                    <div class="chat-bubble-text">${escapeHtml(messageText)}</div>
                </div>
            </div>
            <div class="chat-actions-outside">
                <div class="chat-time">${timeStr}</div>
            </div>
        </div>
        <div class="message-status-indicator" id="status-${pendingKey}">Sending...</div>
    `;

    chatBox.appendChild(article);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Set a timeout: if WS doesn't confirm in time, promote to "Sent"
    const timeoutId = setTimeout(() => {
        _promotePendingToSent(pendingKey);
    }, PENDING_CONFIRM_TIMEOUT_MS);

    pendingMessages[pendingKey] = {
        element: article,
        messageText: messageText,
        timeoutId: timeoutId,
    };

    return pendingKey;
}

/**
 * Promote a pending message to "Sent" state.
 * Called when the timeout expires (WS didn't confirm) but the HTTP POST succeeded.
 */
function _promotePendingToSent(pendingKey) {
    const pending = pendingMessages[pendingKey];
    if (!pending || !pending.element) return;

    pending.element.classList.remove('pending');
    const statusEl = pending.element.querySelector('.message-status-indicator');
    if (statusEl) {
        statusEl.textContent = '';
        // Briefly flash "Sent" then fade out
        statusEl.textContent = 'Sent';
        setTimeout(() => {
            statusEl.style.transition = 'opacity 0.5s';
            statusEl.style.opacity = '0';
            setTimeout(() => statusEl.remove(), 500);
        }, 2000);
    }

    // Show the actions (time, reply, menu)
    const actions = pending.element.querySelector('.chat-actions-outside');
    if (actions) actions.style.visibility = '';

    // Clean up tracker but keep element in DOM
    if (pending.timeoutId) clearTimeout(pending.timeoutId);
    delete pendingMessages[pendingKey];
}

/**
 * Mark a pending message as failed with a retry button.
 * Called when the HTMX POST returns an error.
 */
function markPendingAsFailed(pendingKey, retryFn) {
    const pending = pendingMessages[pendingKey];
    if (!pending || !pending.element) return;

    if (pending.timeoutId) clearTimeout(pending.timeoutId);

    pending.element.classList.remove('pending');
    pending.element.classList.add('send-failed');

    const statusEl = pending.element.querySelector('.message-status-indicator');
    if (statusEl) {
        statusEl.className = 'message-status-indicator status-failed';
        statusEl.innerHTML = `
            <span>Failed to send</span>
            <button type="button" class="retry-btn" aria-label="Retry sending">Retry</button>
        `;
        const retryBtn = statusEl.querySelector('.retry-btn');
        if (retryBtn && retryFn) {
            retryBtn.addEventListener('click', function() {
                // Remove the failed message and re-send
                pending.element.remove();
                delete pendingMessages[pendingKey];
                retryFn();
            });
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// Chat Form: HTMX Interception for Optimistic UI
// ══════════════════════════════════════════════════════════════════

/**
 * Intercept the chat form submission to:
 * 1. Render an optimistic message immediately
 * 2. Show a loading spinner on the send button
 * 3. Handle success/failure states
 */
function initChatFormInterception() {
    const chatForm = document.querySelector('.chat-form');
    if (!chatForm) return;

    // Before the HTMX request fires, render the optimistic message
    chatForm.addEventListener('htmx:beforeRequest', function(evt) {
        const textarea = chatForm.querySelector('textarea[name="message"]');
        const messageText = textarea ? textarea.value.trim() : '';
        if (!messageText) return; // Don't optimistically render empty messages

        // Capture reply data if present
        const replyIdInput = document.getElementById('reply-to-id');
        const replySenderEl = document.getElementById('reply-to-sender');
        const replyTextEl = document.getElementById('reply-to-text');
        const replyId = replyIdInput ? replyIdInput.value : '';
        const replyData = replyId ? {
            sender: replySenderEl ? replySenderEl.textContent : '',
            text: replyTextEl ? replyTextEl.textContent : '',
        } : null;

        const pendingKey = appendOptimisticMessage(messageText, replyData);

        // Map this request to its specific optimistic message
        evt.detail.requestConfig.chatCtx = {
            pendingKey: pendingKey,
            failedText: messageText,
            failedReply: replyData
        };

        // Clear the form immediately so they can type the next message
        chatForm.reset();
        if (typeof window.clearReply === 'function') window.clearReply();
        if (typeof window.clearFilePreview === 'function') window.clearFilePreview();

        // Show loading state on send button
        const sendBtn = chatForm.querySelector('.chat-send-btn');
        if (sendBtn) sendBtn.classList.add('sending');
    });

    // After the HTMX request completes
    chatForm.addEventListener('htmx:afterRequest', function(evt) {
        const sendBtn = chatForm.querySelector('.chat-send-btn');
        if (sendBtn) sendBtn.classList.remove('sending');

        const ctx = evt.detail.requestConfig ? evt.detail.requestConfig.chatCtx : null;
        if (!ctx) return;

        if (!evt.detail.successful) {
            // POST failed — mark this specific optimistic message as failed
            if (ctx.pendingKey) {
                markPendingAsFailed(ctx.pendingKey, function retryFn() {
                    // Re-populate the form and re-submit
                    const textarea = chatForm.querySelector('textarea[name="message"]');
                    if (textarea) textarea.value = ctx.failedText;

                    // Restore reply context if it existed
                    if (ctx.failedReply) {
                        const replyIdInput = document.getElementById('reply-to-id');
                        const preview = document.getElementById('reply-preview');
                        const senderEl = document.getElementById('reply-to-sender');
                        const textEl = document.getElementById('reply-to-text');
                        
                        // Fake a reply structure if needed, or rely on existing global functions
                        if (preview) preview.style.display = 'flex';
                        if (senderEl) senderEl.textContent = ctx.failedReply.sender;
                        if (textEl) textEl.textContent = ctx.failedReply.text;
                    }

                    // Re-submit the form
                    if (typeof chatForm.requestSubmit === 'function') {
                        chatForm.requestSubmit();
                    } else {
                        chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                    }
                });
            }
        }
    });
}

function openLightbox(src) {
    const modal = document.getElementById('lightbox-modal');
    const img = document.getElementById('lightbox-image');
    if (!modal || !img) return;
    img.src = src;
    modal.classList.add('open');
}

function closeLightbox() {
    const modal = document.getElementById('lightbox-modal');
    if (modal) modal.classList.remove('open');
}

if (window.currentTicketId) {
    initChat(window.currentTicketId);
}

// Initialize optimistic UI form interception
document.addEventListener('DOMContentLoaded', initChatFormInterception);

// --- Drag-and-drop, paste, and file preview ---
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function showFilePreview(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];

    const bar = document.getElementById('file-preview-bar');
    const nameEl = document.getElementById('file-preview-name');
    const sizeEl = document.getElementById('file-preview-size');
    if (!bar || !nameEl || !sizeEl) return;

    nameEl.textContent = file.name;
    sizeEl.textContent = '(' + formatFileSize(file.size) + ')';
    bar.style.display = 'flex';
}

function clearFilePreview() {
    const bar = document.getElementById('file-preview-bar');
    const input = document.getElementById('file-upload');
    if (bar) bar.style.display = 'none';
    if (input) input.value = '';
}

function setFileOnInput(file) {
    const input = document.getElementById('file-upload');
    if (!input) return;

    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    showFilePreview(input);
}

// Drag-and-drop on the chat form
// Mobile Chat Actions Toggle (Event Delegation)
document.addEventListener('click', function(e) {
    const bubble = e.target.closest('.chat-bubble');
    if (bubble) {
        const chatItem = bubble.closest('.chat-item');
        if (chatItem) {
            chatItem.classList.toggle('active-mobile-actions');
        }
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.querySelector('.chat-form');
    const overlay = document.getElementById('drop-zone-overlay');
    if (!chatForm || !overlay) return;

    let dragCounter = 0;

    chatForm.addEventListener('dragenter', function(e) {
        e.preventDefault();
        dragCounter++;
        overlay.classList.add('active');
    });

    chatForm.addEventListener('dragleave', function(e) {
        e.preventDefault();
        dragCounter--;
        if (dragCounter === 0) overlay.classList.remove('active');
    });

    chatForm.addEventListener('dragover', function(e) {
        e.preventDefault();
    });

    chatForm.addEventListener('drop', function(e) {
        e.preventDefault();
        dragCounter = 0;
        overlay.classList.remove('active');

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setFileOnInput(e.dataTransfer.files[0]);
        }
    });

    // Clipboard paste (Ctrl+V) on textarea
    const textarea = chatForm.querySelector('textarea[name="message"]');
    if (textarea) {
        textarea.addEventListener('paste', function(e) {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (const item of items) {
                if (item.kind === 'file') {
                    e.preventDefault();
                    const file = item.getAsFile();
                    if (file) setFileOnInput(file);
                    return;
                }
            }
        });
    }
});
