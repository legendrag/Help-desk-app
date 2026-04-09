# Task: Refactor React/DRF to Django Monolithic (Templates)

## Research & Analysis
- [x] Analyze current API endpoints and React components
- [x] Evaluate the role of Django Channels in the current architecture
- [x] Define the pros and cons for the specific project context

## Planning
- [x] Create `implementation_plan.md`
- [x] Get user approval on the plan

## Implementation (Phased)
- [x] **Phase 1: Foundation**
    - [x] Configure Django Templates and Static files
    - [x] Create `base.html` from React's main layout
- [x] **Phase 2: Authentication**
    - [x] Port Login, Logout, and Register pages
- [x] **Phase 3: Core Features (Tickets)**
    - [x] Port Ticket Detail view
    - [x] Port Create/Update Ticket views
- [x] **Phase 4: Notifications & Channels**
    - [x] Adapt Channels client-side logic to Templates
- [x] **Phase 6: Structure Optimization**
    - [x] Move backend files to project root
    - [x] Update paths in `settings.py` and `manage.py`
    - [x] Final verification
- [x] **Phase 5: Cleanup**
    - [x] Remove `frontend` directory
    - [x] Remove DRF dependencies and unused packages
    - [x] Permanently delete legacy DRF files (serializers, views, etc.)

## Verification
- [x] Verify Auth flow
- [x] Verify Ticket creation
- [x] Verify WebSocket Notifications
- [x] Verify WebSocket Chat
- [x] Verify Project Structure (Root-level)
- [x] Verify Documentation (README, Reference, Deployment Guide)
- [x] Verify Helper Scripts (test-local, run-helpdesk, installer)
- [x] Verify MySQL configuration (Settings)
