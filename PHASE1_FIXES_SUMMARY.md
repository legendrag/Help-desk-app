# Phase 1 Performance Optimizations - Fixes Applied

## Branch & PR

- **Branch:** `cursor/phase1-perf-opts-38a6`
- **PR:** https://github.com/legendrag/Help-desk-app/pull/4 (draft, updated)
- **Base:** `main`
- **Status:** Tests passing (7/7), fixes applied, ready for review

## Commits

1. **`6a6ce15`** - Initial Phase 1 implementation (3 tasks)
2. **`9794658`** - Fix 1 (cheaper 304 path) + Fix 2 (restore polling after load-more)

## Changes Summary

### Original Implementation (commit 6a6ce15)

**Task 1:** Slim context on HTMX live refresh ✅  
**Task 2:** Cheaper ETag (attempted with queryset reuse) ⚠️  
**Task 3:** Cap loaded_pages on poll ⚠️  

Issues found:
- Task 2: Idle 304 still had ~6 queries (needed deeper optimization)
- Task 3: Pre-existing bug - polling stopped after load-more

### Fixes Applied (commit 9794658)

**Fix 1: Cheaper 304 path**

**Problem:** Even with queryset reuse, idle 304 still ran ~6 queries:
- Session read/write
- User query
- ETag calculation loaded all page rows (10-50 rows)

**Solution:** Lightweight aggregate-based ETag
- Replaced row-loading with `COUNT(*)` + `MAX(updated_at)`
- Check ETag match **before** calling `get_queryset()`
- Build filtered queryset without loading rows
- Run aggregate query only (~1 query on 304 path)

**Files changed:**
- `tickets/template_views.py`:
  - Renamed `_list_etag()` → `_list_etag_lightweight()`
  - Takes base_queryset, uses aggregates instead of loading rows
  - In `get()`: build filtered queryset, calculate ETag, check match early
  - Return 304 before calling super().get() which loads rows
- `tickets/tests.py`:
  - Updated `test_etag_lightweight_calculation` to validate aggregate approach
  - Added `test_etag_busts_on_filter_change` to verify filter signature

**Impact:**
- Idle poll (304): **~1-2 queries** (session + aggregate)
- Idle poll (200): ~3-5 queries (unchanged - rows must be loaded)
- **Correctness preserved:** Any data change busts ETag correctly

**Fix 2: Restore live poll after load-more**

**Problem:** Pre-existing bug in `htmx:afterSwap` handler
- Button click pauses polling: `onclick="document.body.classList.add('pause-polling')"`
- afterSwap handler checked if swapped element has `load-more-btn` class
- But swapped element is `#tickets-tbody` (target), not the button
- Result: `pause-polling` never removed, polling stopped forever

**Solution:** Check request path instead of element class
- afterSwap now checks `evt.detail.pathInfo.requestPath` for `append=true`
- If append request, remove `pause-polling` and update depth
- Works regardless of HTMX swap target vs trigger element

**Files changed:**
- `static/js/app-shell.js`:
  - Modified afterSwap handler to check `pathInfo.requestPath`
  - Added comment explaining the fix

**Impact:**
- Polling resumes after load-more (as intended)
- No UX regression - users still get live updates

## Expected Query Counts (Honest Assessment)

### Idle HTMX poll (304 hit) - MOST COMMON CASE
**After all fixes:** ~1-2 queries
- 1 session read
- 1 aggregate query (COUNT + MAX)
- (session write may be deferred/batched)

**Before fixes:** ~6 queries
- Session read/write
- User query
- Ticket list query (loaded 10 rows for ETag)
- Plus context queries if not skipped

**Improvement:** 3-6x reduction for the most common case

### HTMX poll with data change (200 response)
**After fixes:** ~3-5 queries
- Session queries
- Aggregate query for ETag
- Ticket list query
- No context queries (Task 1 optimization)

### Full page load
**After fixes:** ~6-10 queries
- Session queries
- Aggregate query for ETag
- Ticket list query
- Branches, assignees, announcements (when needed)

### After 5× load-more, automatic poll
**After fixes:**
- Fetches ~10 rows (first page only, Task 3)
- Polling continues (Fix 2)

**Before fixes:**
- Would fetch ~50 rows (all loaded pages)
- Polling would stop (bug)

## Testing Commands

```bash
# Run all performance tests
export PATH="/home/ubuntu/.local/bin:$PATH"
python3 manage.py test tickets.tests.TicketListPerformanceTests -v 2

# Expected: All 7 tests pass
# - test_htmx_live_poll_skips_branches_context
# - test_htmx_live_poll_skips_announcements_context  
# - test_htmx_append_includes_context
# - test_etag_lightweight_calculation (updated for Fix 1)
# - test_etag_not_calculated_for_append
# - test_etag_busts_on_filter_change (new)
# - test_poll_depth_reset_on_loaded_pages_param
```

## Verification on MySQL

### Setup

```bash
# Configure .env for MySQL
DB_ENGINE=mysql
DB_NAME=mlamehticket
DB_USER=mlamehticket_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306

# Migrate and seed
python manage.py migrate
python manage.py seed_demo_data --clear --ticket-count 500
```

### Verify Fix 1: Cheaper 304 path

```bash
# Install Django Debug Toolbar for query counting
pip install django-debug-toolbar

# Add to INSTALLED_APPS and MIDDLEWARE in settings.py (dev only)

# Run server
python manage.py runserver

# Test:
# 1. Visit http://localhost:8000/tickets/ in browser
# 2. Wait 20 seconds (do not interact)
# 3. Check Network tab for 304 response
# 4. Check Debug Toolbar for query count

# Expected: ~1-2 queries (session + aggregate)
# Before Fix 1: ~6 queries
```

### Verify Fix 2: Restore polling after load-more

```bash
# Run server
python manage.py runserver

# Test:
# 1. Visit http://localhost:8000/tickets/
# 2. Click "Load More" button several times
# 3. Wait 20 seconds after last load-more
# 4. Check browser console and Network tab

# Expected: Poll request appears every ~20 seconds
# Before Fix 2: Polling would stop permanently

# Also check that pause-polling class is removed:
# document.body.classList.contains('pause-polling') // should be false
```

## Code Changes Detail

### Fix 1: tickets/template_views.py

**Key changes:**
1. New `_list_etag_lightweight()` method using aggregates
2. Moved filter building from `get_queryset()` into `get()` method
3. Calculate ETag before calling super().get()
4. Return 304 early if ETag matches
5. Removed queryset caching (not needed with early 304)

### Fix 2: static/js/app-shell.js

**Key changes:**
1. In afterSwap handler, check `evt.detail.pathInfo.requestPath`
2. Look for 'append=true' in URL instead of element class
3. Resume polling if append request succeeded

## Safety Checklist

✅ `rollback/pre-perf-2026-09-28` @ `e431e23` preserved  
✅ No force-push  
✅ Feature branch + PR against main  
✅ No core feature changes  
✅ No user-visible behavior changes (except fixes)  
✅ Dashboard untouched  
✅ Tests passing (7/7)  
✅ Draft PR updated, not merged  
✅ Correctness verified (ETag busts on data changes)  
✅ Filter changes bust ETag correctly  
✅ Polling restored after load-more  

Ready for Greg's review!
