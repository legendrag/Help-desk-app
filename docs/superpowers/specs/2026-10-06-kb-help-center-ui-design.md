# Knowledge Base Help-Center UI Redesign

**Date:** 2026-10-06  
**Status:** Design approved by owner; spec awaiting owner review  
**Owner:** Omar (GitHub: legendrag)  
**Target:** Single implementation PR

## Goal and Context

Redesign the internal Knowledge Base UI to feel like a Zendesk/Intercom-style help center. The current KB (PR #13 merged at 881d830) works but doesn't feel like a modern help center. The new design should be search-led, category-first, and serve both support agents (reading while handling tickets) and managers (writing and organizing content) equally well.

**Current state:** The KB at 881d830 has:
- Three-column filter/results layout (`templates/kb/list_shell_partial.html`, `list_content.html`)
- Basic search with typeahead suggestions (`kb/views.py::kb_search_suggest`, `static/js/kb-search.js`)
- Article detail with sidebar metadata (`templates/kb/detail.html`)
- TinyMCE editor with autosave, drag-and-drop attachments, and visibility controls (`templates/kb/form.html`)
- Permission-scoped visibility (only_me, department, all_support) enforced in `kb/access.py::published_visibility_q` and `articles_for_user`
- Sanitized HTML output (`kb/sanitize.py::sanitize_article_html`)
- Permissioned attachment serving (`kb/views.py::kb_attachment`)
- In-shell HTMX navigation (partials swap into `#shell-content` in `templates/base.html`)

**Target audience:** Support agents and KB managers (users with `can_access_kb` and `can_manage_kb` role flags).

**Approved approach:** Help-center hub with search-led discovery, clean layouts, and UX polish. Bigger changes are allowed if they make it feel like a real help center.

## Locked Decisions

These decisions are final and non-negotiable:

1. **Layouts:**
   - **Home:** Option B "Compact hub + drafts rail" (search bar, category list with counts, right rail with recent articles and manager drafts)
   - **Article detail:** Option A "Wide article + sticky TOC" (wide reading column, sticky table of contents, quiet right rail)
   - **Editor:** Option A "Sticky publish bar + side panel" (top bar with Save/Publish, TinyMCE left, settings right)
   
2. **Mockup references:** See `docs/superpowers/specs/assets/` for HTML mockups chosen by the owner.

3. **Security invariants from PR #13:** Every view keeps server-side permission checks:
   - Support-only access (`kb/access.py::user_can_read_kb`, `user_can_manage_kb`)
   - Publish-time visibility scoping (`published_visibility_q`, `articles_for_user`)
   - Sanitized HTML (`sanitize_article_html` on save)
   - Permissioned attachments (`kb_attachment` view checks article visibility before serving)
   - `/media/kb/` blocked in production (middleware blocks direct access when DEBUG=0)
   - Branch users blocked from KB entirely
   - Manage flag required for writes (create, edit, delete, drafts)

4. **No new search engine:** Use the existing search backend in `ArticleListView.get_queryset()` (case-insensitive `title__icontains` and `content__icontains`). The typeahead and empty-state must use the same permission scoping via `articles_for_user`.

5. **Keep in-shell navigation:** Preserve HTMX partial swaps and `pushState` navigation where already used (global nav, back/forward). No changes to Dashboard, Tickets, or global chrome.

6. **Keep TinyMCE:** Continue using the local TinyMCE from PR #13 with the `base_url` fix for manifest static storage.

7. **Keep existing features:** Autosave, drag-and-drop attachments, related ticket search, visibility controls, article deletion.

## Per-Screen Layouts

### 1. Home / Browse (`templates/kb/list_shell_partial.html`, `list_content.html`)

**Chosen layout:** Compact hub + drafts rail

**Description:**
- Top: "Knowledge Base" heading with "New article" button (managers only) aligned right
- Search bar directly below the heading, full width
- Main content area split into two columns:
  - **Left column (60%):** Category list
    - Each category: name, article count, icon (from `Category.icon`)
    - Click navigates to category page (filtered list)
    - Vertical list, not a grid
  - **Right rail (40%):** Recent articles + drafts
    - "Recent articles" section (all users): last 6 published articles visible to user
    - "My drafts" section (managers only): their unpublished articles
    - Each item: title, updated date, quick link

**Empty state (no search query, browse home):**
- Show category list + right rail (recent + drafts) as described above
- If no articles exist: "No articles yet. [Managers: Create your first article]"

**Search results (query present):**
- Hide category list and right rail
- Show full-width results list below search bar
- Each result: title, snippet (first 150 chars of content), category, updated date, visibility chip
- Pagination: load-more button (existing `append=true` pattern in `ArticleListView`)
- Empty search: "No articles match your search. Try different keywords."

**Category page (category filter, no search query):**
- Hide right rail
- Show breadcrumb: "KB › [Category name]"
- Full-width article list: title, snippet, updated date, visibility chip
- Remove the current three-column filter layout (`kb-filters-panel` aside in `list_shell_partial.html`)

**Visibility chips:**
- Displayed on article list items (not on home category cards or right rail)
- Labels: "Only me" (gray), "Department" (blue), "All support" (green)
- All three scopes are shown; the chip communicates the article's scope to the reader
- Implementation: new template partial `templates/kb/partials/visibility_chip.html`

**URL patterns:**
- Home: `/kb/` (`kb_list`, no query params)
- Search: `/kb/?q=password`
- Category: `/kb/?category=3`
- Drafts: `/kb/?status=draft` (managers only)

**Files affected:**
- `templates/kb/list_shell_partial.html` (replace three-column layout with hub + rail)
- `templates/kb/list_content.html` (update header, add right rail)
- `templates/kb/partials/result_item.html` (add visibility chip)
- `templates/kb/partials/visibility_chip.html` (new)
- `kb/views.py::ArticleListView.get_context_data()` (populate right rail data)
- `static/css/modern.css` (add new KB hub styles to existing KB section)

### 2. Article Detail (`templates/kb/detail.html`)

**Chosen layout:** Wide article + sticky TOC

**Description:**
- Breadcrumb: "KB › [Category] › [Article title]"
- Article header: title, author, created date, updated date (if different)
- Two-column layout:
  - **Main column (70%):** Article content (sanitized HTML from `article.content`)
  - **Right sidebar (30%):** Sticky, starts below header
    - **"On this page"** section: auto-generated table of contents from article headings
      - Links to stable anchor IDs on each heading
      - Highlights current section on scroll (optional polish)
    - **Meta section:** category, visibility chip, updated date, author
    - **Related ticket** (if present and user can view it): link to ticket
    - **Attachments** (if present): list with preview buttons
    - **Edit button** (managers only): navigates to editor

**Table of contents (TOC):**
- **Decision: Client-side generation** (recommended)
  - **Rationale:** The sanitized HTML is already rendered; parsing it server-side (with lxml/BeautifulSoup) adds dependency weight. Client-side JS can extract headings from the DOM after render, add stable IDs if missing, and build the TOC without a server round-trip. This keeps the implementation lightweight and avoids double-parsing the HTML.
  - **Implementation:** 
    - On page load, HTMX swap (`htmx:afterSwap`), and history restore (`htmx:historyRestore`), run JS to find all `h2`, `h3`, `h4` in `.kb-content`
    - Generate stable anchor IDs (slug of heading text, deduplicated if needed)
      - Slugification must handle non-Latin (e.g., Arabic, Chinese) text: use a Unicode-aware slug function or fallback to `kb-h-<n>` (where `n` is the heading index) when the slug is empty after normalization
      - Do not overwrite an existing `id` attribute (sanitizer may preserve heading IDs from the editor)
    - Inject `id` attributes into headings that lack them
    - Build TOC list with links to those IDs
    - Insert TOC into `#kb-toc-container` in the sidebar
    - Optional: add scroll-spy to highlight active section
    - **Critical for in-shell navigation:** KB pages are reached via HTMX swaps into `#shell-content`, so `kb-toc.js` must initialize on HTMX swaps and back/forward restores as well as on full page load. The script must not double-bind scroll listeners or leak event handlers across swaps. Use a cleanup pattern (e.g., remove old listeners before re-initializing, or guard against duplicate initialization).
  - **Fallback:** If JS is disabled, TOC is hidden (progressive enhancement)

**Visibility chip:**
- Shown in the meta section for all visibility scopes (Only me / Department / All support)
- Same styling as list view

**Files affected:**
- `templates/kb/detail.html` (rework layout: wide main + sticky sidebar with TOC placeholder)
- `static/js/kb-toc.js` (new: TOC generation with HTMX swap support and scroll-spy)
- `static/css/modern.css` (sticky sidebar, TOC styles in existing KB section)

### 3. Editor (`templates/kb/form.html`)

**Chosen layout:** Sticky publish bar + side panel

**Description:**
- Sticky top bar (always visible on scroll):
  - Left: "← Back" link, autosave status ("Draft autosaved")
  - Right: "Save draft" button (secondary), "Publish" buttons (primary: Only me / My department / All support)
- Two-column layout below top bar:
  - **Main column (70%):** Title field, TinyMCE editor
  - **Right sidebar (30%):** 
    - Visibility (display-only field showing current visibility when editing a published article; cannot be changed directly in the sidebar)
    - Category dropdown
    - Related ticket search (existing HTMX `kb_ticket_search`)
    - Attachments (drag-and-drop zone, existing file list)

**Publish buttons:**
- Three separate publish buttons in the sticky top bar: "Only me", "My department" (if user has department), "All support"
- These are the same three publish actions from PR #13 (`ArticleWriteMixin.publish_actions`: `Article.Visibility.ONLY_ME`, `DEPARTMENT`, `ALL_SUPPORT`) moved from the sidebar into the top bar
- Each sets `action=<visibility>` and submits the form
- When editing a published article, clicking a publish button changes the article's visibility to the new scope and saves it (same behavior as PR #13: `_apply_action` sets `form.instance.is_published = True` and `form.instance.visibility = action`)
- If the user has no department, "My department" is not shown
- **Department snapshot behavior (preserved from PR #13):** When publishing to "My department", `visibility_department_id` is set to the author's current `department_id` at publish time (see `ArticleWriteMixin._apply_action` lines 414-416 in `views.py`). When publishing to "Only me" or "All support", `visibility_department` is cleared. This behavior is unchanged.

**No changes to:**
- TinyMCE initialization (keep `base_url` fix from PR #13)
- Autosave logic (keep existing `X-KB-Autosave` header, 2.5s debounce, JSON response)
- Drag-and-drop attachments (keep existing `kb-dropzone`, `DataTransfer` logic)
- Related ticket search (keep HTMX endpoint `kb_ticket_search`)

**Files affected:**
- `templates/kb/form.html` (move publish buttons to sticky top bar, adjust layout, show visibility as display-only)
- `kb/views.py::ArticleWriteMixin` (no changes; publish button behavior is identical to PR #13)
- `static/css/modern.css` (sticky top bar styles in existing KB section)

### 4. Empty, Loading, and Error States

**Empty states:**
- **No articles at all:** "No articles yet. [Managers: Create the first article.]"
- **No search results:** "No articles match your search. Try different keywords."
- **No drafts:** "No drafts yet. Articles you save as draft will appear here."
- **No category articles:** "No articles in this category yet."

**Loading states:**
- **Typeahead:** Show "Searching..." in suggestion dropdown while fetching
- **Load-more:** Disable button and show "Loading..." while fetching next page

**Error states:**
- **Typeahead fetch fails:** Hide suggestions, allow user to submit full search
- **Attachment upload fails:** Show "Upload failed: [file name]" (no retry UI; user can re-upload manually via the same dropzone or file input)
- **Autosave fails:** Update status to "Draft not saved yet"

**Files affected:**
- `templates/kb/partials/search_suggestions.html` (loading/empty states)
- `templates/kb/partials/load_more.html` (loading state)
- `templates/kb/form.html` (error messages)

## Data Flow and Endpoints

### Typeahead Endpoint

**Endpoint:** `kb/views.py::kb_search_suggest` (`/kb/search-suggest/`)

**Current behavior:** Returns top 5 articles matching `title__icontains` query, rendered as HTML links in `templates/kb/partials/search_suggestions.html`.

**New behavior (enhanced):**
- **Input:** `?q=<query>` (min 2 chars)
- **Permission scoping:** Use `articles_for_user(request.user, include_drafts=False)` (same as full search, no drafts in suggestions)
- **Query:** Filter by `title__icontains` only (same as current). Note that full search (`ArticleListView`) matches both `title__icontains` and `content__icontains`, but typeahead intentionally matches only titles for faster, more relevant suggestions.
- **Response:** HTML with up to 5 suggestions, each:
  - Article title
  - Category name (if present)
  - Visibility chip (all three scopes: Only me / Department / All support)
  - Direct link to article detail
- **Behavior:** Clicking a suggestion navigates directly to the article (skips search results page)
- **Empty state (no matches):** Render empty `<div>` (JS will hide dropdown)

**Files affected:**
- `kb/views.py::kb_search_suggest` (add category, visibility to context)
- `templates/kb/partials/search_suggestions.html` (add category, visibility chip)
- `static/js/kb-search.js` (no changes, already handles empty state)

### Empty-State Results (No Query)

**Endpoint:** `kb/views.py::ArticleListView` (`/kb/`)

**Current behavior:** When no query and no filters (`_is_browse_home()`), view skips pagination and loads only metadata (categories, recent articles).

**New behavior:**
- Keep `_is_browse_home()` logic (no query, no category filter, status=published)
- **Recent articles:** Load 6 most recent published articles visible to user
  - Query: `articles_for_user(request.user, include_drafts=False).order_by('-updated_at')[:6]`
  - Already implemented in `get_context_data()` as `recent_articles` (currently loads 6)
- **Manager drafts:** If `user_can_manage_kb(request.user)`, load their unpublished articles
  - Query: `articles_for_user(request.user, include_drafts=True).filter(is_published=False, created_by=request.user).order_by('-updated_at')[:6]`
  - Add to context as `my_drafts`
  - **Rationale:** All article queries go through `articles_for_user` (the spec's own security rule). Even though managers can see all drafts via `include_drafts=True`, we filter to `created_by=request.user` to show only the current user's drafts in the rail. Field names verified from `kb/models.py`: `is_published` (BooleanField), `created_by` (ForeignKey to User).
- **Permission scoping:** Recent articles already use `articles_for_user` (correct). Drafts use `articles_for_user(..., include_drafts=True).filter(...)` (correct).

**Files affected:**
- `kb/views.py::ArticleListView.get_context_data()` (add `my_drafts` to context)
- `templates/kb/list_content.html` (render drafts rail for managers)

### Category Page

**Endpoint:** `kb/views.py::ArticleListView` (`/kb/?category=3`)

**Current behavior:** Filters articles by `category_id`, shows three-column layout with filters.

**New behavior:**
- Filter by category (same query as current)
- Remove left sidebar filters
- Show full-width article list (title, snippet, updated date, visibility chip)
- Breadcrumb: "KB › [Category name]"

**Files affected:**
- `templates/kb/list_shell_partial.html` (conditionally hide filters when category is active, or remove filters entirely)
- `templates/kb/list_content.html` (full-width results when category filter)

## Permissions and Security Invariants

All security checks from PR #13 are preserved:

1. **Access control:**
   - `KBPermissionMixin` (read views): requires `user_can_read_kb(request.user)`
   - `KBManageMixin` (write views): requires `user_can_manage_kb(request.user)`
   - Branch users (`user_type="branch"`) are blocked from KB entirely

2. **Visibility scoping:**
   - All list/search/recent/typeahead queries use `articles_for_user(request.user, include_drafts=False)`
   - `articles_for_user` enforces:
     - `only_me`: article.created_by == user
     - `department`: article.visibility_department_id == user.department_id
     - `all_support`: all support users
   - Managers can see drafts in detail and edit views via `include_drafts=True` in `ArticleDetailView.get_queryset()` and `ArticleUpdateView.get_queryset()`

3. **HTML sanitization:**
   - `Article.save()` runs `sanitize_article_html(self.content)` on every save (including autosave)
   - Allowlist-based (see `kb/sanitize.py::ALLOWED_TAGS`, `ALLOWED_ATTRS`)
   - Strips scripts, event handlers, `javascript:` URLs, `data:` URLs

4. **Attachment serving:**
   - `kb_attachment` view checks `articles_for_user(request.user, include_drafts=_user_can_manage_kb(user)).filter(pk=attachment.article_id).exists()` before serving file
   - `/media/kb/` is blocked by middleware when DEBUG=0 (direct access returns 403)

5. **No cross-department ticket unlock:**
   - `kb_ticket_search` view filters tickets by user's department (`user.department_id`) for support users, or branch for branch users
   - Related ticket is only linked if `user_can_view_ticket(user, ticket)` in `ArticleDetailView`

**New views must:**
- Inherit from `KBPermissionMixin` (read) or `KBManageMixin` (write)
- Use `articles_for_user` for any article query
- Never expose drafts to non-managers
- Never expose `only_me` or `department` articles to out-of-audience users

## Responsive Behavior

**Target breakpoints:**
- Desktop: ≥1024px (two-column layouts)
- Tablet: 640px–1023px (sidebar below main content)
- Mobile: <640px (single column, compact spacing)

**Responsive rules:**
1. **Home:**
   - Desktop: category list (60%) + right rail (40%) side by side
   - Tablet/Mobile: right rail below category list, both full width

2. **Article detail:**
   - Desktop: main content (70%) + sticky sidebar (30%)
   - Tablet/Mobile: sidebar below main content, TOC becomes a collapsible accordion at top of article

3. **Editor:**
   - Desktop: TinyMCE (70%) + settings sidebar (30%), sticky top bar
   - Tablet/Mobile: settings sidebar below editor, top bar remains sticky

4. **Search bar:**
   - Always full width on all breakpoints

**Files affected:**
- `static/css/modern.css` (media queries for responsive layouts in existing KB section)

## Accessibility

**Keyboard navigation:**
- **Typeahead:** Arrow keys to navigate suggestions, Enter to select, Escape to close (already implemented in `kb-search.js`)
- **TOC links:** Tab-accessible, Enter to jump to section
- **Sticky top bar:** buttons are tab-accessible, focus order: back link → save draft → publish options

**Screen readers:**
- Breadcrumbs: `aria-label="Breadcrumb"` on `<nav>`
- TOC: `aria-label="On this page"` on `<nav>` or `<aside>`
- Visibility chips: `aria-label="Visible to: [scope]"` on chip element
- Empty states: Use `<p>` with clear text, not just placeholders
- Loading states: `aria-live="polite"` on status messages (e.g., "Searching...", autosave status)

**Focus management:**
- After autosave, keep focus on editor (do not steal focus)
- After selecting typeahead suggestion, navigate to article (no focus trap)

**Files affected:**
- All templates: add ARIA labels to new `<nav>`, `<aside>`, interactive elements
- `static/js/kb-toc.js`: ensure TOC links are keyboard-accessible

## Testing Plan

### Unit and View Tests

**New tests in `kb/tests.py`:**

1. **Typeahead scoping:**
   - Test that `kb_search_suggest` returns only articles visible to the current user (all_support, department, only_me)
   - Test that drafts are excluded from typeahead
   - Test that branch users receive a 403 response (`UserPassesTestMixin` raises `PermissionDenied`, Django converts to 403)

2. **Empty-state scoping:**
   - Test that `recent_articles` in `ArticleListView` are permission-scoped
   - Test that `my_drafts` shows only user's own drafts, not other managers' drafts
   - Test that non-managers do not see drafts rail

3. **Visibility chip rendering:**
   - Test that visibility chip is rendered for all three scopes: `only_me`, `department`, `all_support`
   - Test that visibility chip text matches article.visibility for each of the three choices
   - Test that "Only me" articles show "Only me" chip, "Department" articles show "Department" chip, "All support" articles show "All support" chip

4. **TOC generation (JS):**
   - Manual browser check only (JS unit tests are out of scope for this project)

5. **Responsive behavior:**
   - Manual browser checks at 1280px, 768px, 375px widths

### Manual Browser Checks

**Test scenarios:**
1. **Home page:**
   - Load `/kb/` as manager: verify category list, recent articles, drafts rail, "New article" button
   - Load `/kb/` as non-manager agent: verify no drafts rail, no "New article" button
   - Click category: verify full-width article list with visibility chips

2. **Search:**
   - Type 2+ chars: verify typeahead appears with category and visibility chip
   - Click suggestion: verify direct navigation to article
   - Submit search: verify full results list, no category list or right rail
   - Empty search: verify "No articles match..." message

3. **Article detail:**
   - Load article: verify TOC is generated and sticky
   - Click TOC link: verify scroll to section
   - Verify visibility chip in meta section
   - Verify related ticket link (if user can view ticket)
   - Verify attachments preview works

4. **Editor:**
   - Create article: verify sticky top bar, TinyMCE, sidebar fields
   - Autosave: verify status updates every 2.5s
   - Publish: verify "Only me", "My department" (if user has department), "All support" buttons work
   - Upload attachment: verify drag-and-drop works

5. **Permissions:**
   - Log in as agent without `can_access_kb`: verify KB nav link is hidden, direct `/kb/` access returns 403 (`UserPassesTestMixin` raises `PermissionDenied`)
   - Log in as branch user: verify 403 on `/kb/` (same mechanism)
   - Log in as support user with department A: verify cannot see department B articles

6. **Responsive:**
   - Test all pages at 1280px, 768px, 375px widths
   - Verify sidebars collapse below main content on narrow widths
   - Verify sticky top bar works on mobile

### MySQL and DEBUG=0 Checks

**MySQL compatibility:**
- Run `python manage.py test kb` on MySQL/MariaDB (the app's primary DB)
- Verify no `icontains` or ORM issues (current code already uses `icontains`, should work)

**Static files (DEBUG=0):**
- Run `python manage.py collectstatic` with `ManifestStaticFilesStorage`
- Verify `kb-toc.js`, `kb-search.js`, `modern.css` are collected and hashed
- Verify TinyMCE `base_url` fix from PR #13 still works (local vendor files load correctly)

## Out of Scope

**Explicitly not included in this redesign:**

1. **New search engine:** No Elasticsearch, PostgreSQL full-text search, or external search service. Use existing `title__icontains` and `content__icontains` queries.

2. **Article versions/history:** No revision tracking, no "view history" or "restore previous version".

3. **Pinning or featured articles:** No "pin to top" or "featured" flag.

4. **Replacing TinyMCE:** Keep the current editor. No switch to ProseMirror, Quill, or other editors.

5. **Changes to PR #13 security/visibility rules:** No new visibility scopes, no changes to permission checks, no changes to sanitization rules.

6. **Letting branch users into KB:** Branch users remain blocked. Only support users with `can_access_kb` role flag.

7. **DB connection pool, auth stress, or perf fixes:** No changes to database configuration, no caching layer, no D2/Phase E performance work.

8. **Public-facing KB:** This is an internal KB for support staff only. No public portal, no unauthenticated access.

9. **Bulk operations:** No bulk publish, bulk delete, bulk category reassignment.

10. **Analytics or usage tracking:** No "views count", "most helpful", or read-time analytics.

## Open Questions

None. All design decisions have been made explicitly:

- **TOC generation:** Client-side JS with HTMX swap support (rationale: lightweight, avoids server-side HTML parsing dependencies)
- **Typeahead endpoint:** Enhance current `kb_search_suggest` with category and visibility chip; matches title only (no new endpoint)
- **Empty state:** Use existing `_is_browse_home()` logic, add `my_drafts` to context via `articles_for_user(..., include_drafts=True).filter(...)`
- **Category page:** Full-width list, remove three-column filter layout (simplify to browsing UX)
- **Visibility chips:** Show all three scopes (Only me / Department / All support) on list and detail
- **Editor visibility on published articles:** Same behavior as PR #13 (publish buttons change visibility and save)
- **Responsive rails:** Collapse below main content on narrow widths (<1024px)
- **Sticky top bar in editor:** Always visible, no collapse (critical publish controls)

## Implementation Checklist

**Phase 1: Home and List Views**
- [ ] Update `templates/kb/list_shell_partial.html`: replace three-column with hub + rail
- [ ] Update `templates/kb/list_content.html`: add category list, right rail (recent + drafts)
- [ ] Create `templates/kb/partials/visibility_chip.html` (all three scopes)
- [ ] Update `templates/kb/partials/result_item.html`: add visibility chip
- [ ] Update `kb/views.py::ArticleListView.get_context_data()`: add `my_drafts` via `articles_for_user`
- [ ] Update `static/css/modern.css`: home layout styles in existing KB section
- [ ] Test: home page, category page, permissions

**Phase 2: Article Detail and TOC**
- [ ] Update `templates/kb/detail.html`: wide main + sticky sidebar with TOC placeholder
- [ ] Create `static/js/kb-toc.js`: client-side TOC generation with HTMX swap support, non-Latin slug handling, scroll-spy
- [ ] Update `static/css/modern.css`: sticky sidebar, TOC styles in existing KB section
- [ ] Test: article detail, TOC generation on swaps, visibility chip

**Phase 3: Editor**
- [ ] Update `templates/kb/form.html`: sticky top bar with publish buttons, visibility display-only
- [ ] Update `static/css/modern.css`: sticky top bar styles in existing KB section
- [ ] Test: editor layout, autosave, publish (verify visibility changes work), attachments

**Phase 4: Typeahead and Search**
- [ ] Update `kb/views.py::kb_search_suggest`: add category, visibility to context
- [ ] Update `templates/kb/partials/search_suggestions.html`: add category, visibility chip (all three scopes)
- [ ] Test: typeahead (title-only match), permission scoping, empty state

**Phase 5: Responsive and Accessibility**
- [ ] Add responsive media queries to `static/css/modern.css` (existing KB section)
- [ ] Add ARIA labels to all new templates
- [ ] Test: responsive layouts, keyboard navigation, screen reader compatibility

**Phase 6: Testing and Polish**
- [ ] Write unit tests in `kb/tests.py` (typeahead scoping, empty-state scoping, visibility chips for all three scopes)
- [ ] Run tests on MySQL/MariaDB
- [ ] Run `collectstatic` with DEBUG=0, verify TinyMCE loads
- [ ] Manual browser checks (all scenarios above)
- [ ] Fix any regressions in Dashboard, Tickets, or other non-KB views

**Phase 7: Review and Merge**
- [ ] Greg (planner/reviewer) reviews implementation PR for design fidelity, code quality
- [ ] Test agent runs regression + perf + KB permission tests on MySQL/MariaDB
- [ ] No new N+1 queries, typeahead remains fast
- [ ] Omar (owner) explicitly approves and merges

## Ship Path

1. **Single implementation PR:** All changes in one PR (title: "redesign: KB help-center UI"), implemented by our dev agent, based on this spec
2. **Code review:** Greg (planner/reviewer) reviews for design fidelity, code quality, UX, and security
3. **Regression and perf tests:** Test agent runs regression + perf + KB permission tests on MySQL/MariaDB, verifies no feature regressions elsewhere, checks typeahead performance
4. **Merged only when Omar says yes:** No auto-merge, explicit owner (Omar) approval required

## References

- **PR #13 (merged at 881d830):** Restrict KB to support staff, per-article visibility, HTML sanitization, permissioned attachments
- **Current KB code:**
  - Models: `kb/models.py` (Article, Category, ArticleAttachment)
  - Views: `kb/views.py` (ArticleListView, ArticleDetailView, ArticleCreateView, ArticleUpdateView, kb_search_suggest, kb_attachment)
  - URLs: `kb/urls.py`
  - Templates: `templates/kb/` (list.html, detail.html, form.html, partials/)
  - Static: `static/js/kb-search.js`
  - Access: `kb/access.py` (user_can_read_kb, user_can_manage_kb, articles_for_user, published_visibility_q)
  - Sanitization: `kb/sanitize.py` (sanitize_article_html)
- **Mockups:** `docs/superpowers/specs/assets/` (home-layout.html, article-layout.html, editor-layout.html)
