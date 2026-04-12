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

        // Show/hide closed ticket UI
        if (payload.status === 'closed') {
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
                const placeholder = container.querySelector('p[style*="text-align: center"]');
                if (placeholder) placeholder.remove();

                chatBox = document.createElement('div');
                chatBox.id = 'chat-box';
                chatBox.className = 'chat-box';
                
                // Insert before the chat-form
                const form = container.querySelector('.chat-form');
                if (form) {
                    container.insertBefore(chatBox, form);
                } else {
                    container.appendChild(chatBox);
                }
            }
        }

        if (!chatBox) return;

        if (document.getElementById(`message-${payload.id}`)) return;

        const dateObj = new Date(payload.created_at);
        const timeStr = isNaN(dateObj) ? '' : dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        const fullDateStr = isNaN(dateObj) ? '' : dateObj.toLocaleString([], { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).replace(',', '');

        const isMe = String(payload.sender) === window.userId;
        const article = document.createElement('article');
        article.id = `message-${payload.id}`;
        article.className = `chat-item ${isMe ? 'me' : ''}`;
        article.dataset.messageId = payload.id;
        article.dataset.sender = payload.sender_username;

        const reply = payload.reply_to || null;

        const canEdit = window.chatPermissions && window.chatPermissions.canEdit;
        const canDelete = window.chatPermissions && window.chatPermissions.canDelete;

        const menuItems = [
            canEdit ? `<button type="button" class="message-menu-item" onclick="toggleEdit(${payload.id}); closeMessageMenu(${payload.id});">Edit</button>` : '',
            canDelete ? `<form action="${getDeleteUrl(payload.id)}" method="post" onsubmit="return confirm('Are you sure you want to delete this message?');">
                <input type="hidden" name="csrfmiddlewaretoken" value="${getCsrfToken()}">
                <button type="submit" class="message-menu-item danger">Delete</button>
            </form>` : '',
            `<button type="button" class="message-menu-item" onclick="toggleMessageDetails(${payload.id}); closeMessageMenu(${payload.id});">Details</button>`
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
                        <p style="margin: 0.5rem 0;">${payload.message}</p>
                        ${payload.attachment_url ? (
                            payload.attachment_url.match(/\.(jpg|jpeg|png|gif|webp|bmp|svg)($|\?)/i) ? `
                            <div style="margin-top: 0.5rem;">
                                <img src="${payload.attachment_url}" alt="Attachment" class="chat-image-preview" onclick="openLightbox(this.src)">
                            </div>
                            ` : `
                            <div style="margin-top: 0.5rem;">
                                <a href="${payload.attachment_url}" target="_blank" download style="color: ${isMe ? '#fff' : 'var(--primary)'}; font-size: 0.8rem; text-decoration: underline;">
                                    📎 View Attachment
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
            <form id="msg-edit-${payload.id}" action="${getEditUrl(payload.id)}" method="post" style="display: none; margin-top: 0.5rem; width: 100%;">
                <input type="hidden" name="csrfmiddlewaretoken" value="${getCsrfToken()}">
                <textarea name="message" rows="2" style="width: 100%; border-radius: 8px; padding: 0.6rem; border: 1px solid var(--border); resize: none; color: black;">${payload.message}</textarea>
                <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem;">
                    <button type="button" class="secondary" onclick="toggleEdit(${payload.id})" style="padding: 0.3rem 0.7rem; font-size: 0.8rem; height: auto; line-height: 1;">Cancel</button>
                    <button type="submit" style="padding: 0.3rem 0.7rem; font-size: 0.8rem; height: auto; line-height: 1;">Save</button>
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
