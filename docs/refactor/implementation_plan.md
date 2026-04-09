# Refactor to Django Monolithic (Templates)

This plan outlines the steps to convert the existing React + Django Rest Framework (DRF) setup into a single Django application using Server-Side Rendering (SSR) with Django Templates.

## Technical Summary
- **Backend**: Transition from DRF ViewSets to standard Django Class-Based Views (CBVs) or Function-Based Views (FBVs).
- **Authentication**: Switch from JWT (SimpleJWT) to Django's built-in session-based authentication.
- **Frontend**: Port React components and logic to Django Templates (`.html`) using Vanilla CSS and Vanilla JavaScript.
- **Real-time**: Keep Django Channels but rewrite the client-side WebSocket handling in Vanilla JS.

## User Review Required
> [!IMPORTANT]
> This refactor will result in page reloads during navigation unless we use a library like HTMX. I recommend using **HTMX** to keep the "Single Page App" feel without the complexity of React.

> [!WARNING]
> Switching from JWT to Session authentication will invalidate all current user sessions. Users will need to log in again after the update.

## Proposed Changes

### [Backend]
Summary: Update views to return templates and switch to session auth.

#### [MODIFY] [settings.py](file:///d:/Ayman/PY%20PROJECT/help%20disk/backend/config/settings.py)
- Update `TEMPLATES` to include a `templates` directory.
- Configure `STATICFILES_DIRS`.
- Add `LOGIN_URL` and `LOGIN_REDIRECT_URL`.

#### [MODIFY] [urls.py](file:///d:/Ayman/PY%20PROJECT/help%20disk/backend/config/urls.py)
- Add paths for the new HTML views.
- (Optional) Keep `/api/` temporarily during transition.

#### [NEW] [Templates Directory](file:///d:/Ayman/PY%20PROJECT/help%20disk/backend/templates/)
- `base.html`: Main layout (navigation, sidebar).
- `accounts/login.html`: Login page.
- `tickets/list.html`: Ticket listing.
- `tickets/detail.html`: Ticket details and chat.
- `dashboard.html`: Statistics dashboard.

### [Frontend]
Summary: Port React logic to Templates.

#### [DELETE] [frontend directory](file:///d:/Ayman/PY%20PROJECT/help%20disk/frontend/)
- To be removed once all pages are ported.

---

## Verification Plan

### Automated Tests
- No existing automated tests were found for the UI. I will create a simple suite of Django `TestCase` to verify view status codes.
- `python manage.py test`

### Manual Verification
1. **Authentication**: Verify login/logout flow works with sessions.
2. **Navigation**: Ensure the sidebar links work and load correct data.
3. **Ticket Workflow**: 
   - Create a ticket.
   - Pick/Assign a ticket.
   - Post a message/comment and see if it appears.
4. **Real-time**: Verify notifications still pop up using the WebSocket connection.
