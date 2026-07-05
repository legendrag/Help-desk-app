import logging
import os
import shutil
import tempfile
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse, FileResponse
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from tickets.models import Ticket, TicketMessage
from notifications.models import InAppNotification

logger = logging.getLogger(__name__)

# Rate-limit: one backup download per user per 5 minutes
BACKUP_COOLDOWN_SECONDS = 300


class MaintenancePermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or (user.role and user.role.can_manage_maintenance)


class MaintenanceView(MaintenancePermissionMixin, TemplateView):
    template_name = "core/management/maintenance.html"


# ---------------------------------------------------------------------------
# Rate-limit helper
# ---------------------------------------------------------------------------

def _check_rate_limit(user, action_key):
    """Return (allowed: bool, wait_seconds: int)."""
    cache_key = f"maintenance_rate_{action_key}_{user.pk}"
    last_use = cache.get(cache_key)
    if last_use is not None:
        elapsed = (timezone.now() - last_use).total_seconds()
        remaining = int(BACKUP_COOLDOWN_SECONDS - elapsed)
        if remaining > 0:
            return False, remaining
    return True, 0


def _set_rate_limit(user, action_key):
    cache.set(
        f"maintenance_rate_{action_key}_{user.pk}",
        timezone.now(),
        BACKUP_COOLDOWN_SECONDS,
    )


# ---------------------------------------------------------------------------
# Backup views
# ---------------------------------------------------------------------------

class ExportTicketsView(MaintenancePermissionMixin, View):
    """Export all tickets and their chat messages as a readable .txt file."""

    def post(self, request, *args, **kwargs):
        allowed, wait = _check_rate_limit(request.user, "export_tickets")
        if not allowed:
            return HttpResponse(
                f"Rate limit: please wait {wait} seconds before downloading another export.",
                status=429,
            )

        try:
            lines = []
            lines.append("=" * 80)
            lines.append("HELP DESK — TICKETS & MESSAGES EXPORT")
            lines.append(f"Exported on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
            lines.append(f"Exported by: {request.user.username}")
            lines.append("=" * 80)

            tickets = (
                Ticket.objects
                .select_related(
                    "branch", "department", "category",
                    "created_by", "assigned_to",
                )
                .prefetch_related("messages__sender")
                .order_by("-created_at")
            )

            lines.append(f"\nTotal tickets: {tickets.count()}\n")

            for ticket in tickets.iterator(chunk_size=2000) if hasattr(tickets, 'iterator') else tickets:
                lines.append("\n" + "-" * 80)
                lines.append(f"Ticket:      {ticket.ticket_number}")
                lines.append(f"Title:       {ticket.title}")
                lines.append(f"Status:      {ticket.get_status_display()}")
                lines.append(f"Priority:    {ticket.get_priority_display()}")
                lines.append(f"Branch:      {ticket.branch}")
                lines.append(f"Department:  {ticket.department}")
                lines.append(f"Category:    {ticket.category}")
                lines.append(f"Client:      {ticket.client_name} ({ticket.client_phone})")
                lines.append(f"Created by:  {ticket.created_by.username}")
                lines.append(f"Assigned to: {ticket.assigned_to.username if ticket.assigned_to else 'Unassigned'}")
                lines.append(f"Created:     {ticket.created_at.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"Updated:     {ticket.updated_at.strftime('%Y-%m-%d %H:%M')}")
                if ticket.closed_at:
                    lines.append(f"Closed:      {ticket.closed_at.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"\nDescription:\n  {ticket.description}")

                ticket_msgs = ticket.messages.select_related("sender").order_by("created_at")
                if ticket_msgs.exists():
                    lines.append(f"\n  --- Messages ({ticket_msgs.count()}) ---")
                    for msg in ticket_msgs:
                        sender = msg.sender.username
                        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
                        tag = " [SYSTEM]" if msg.is_system_message else ""
                        attachment = f"  [Attachment: {os.path.basename(msg.attachment.name)}]" if msg.attachment else ""
                        lines.append(f"\n  [{time}] {sender}{tag}:")
                        if msg.message:
                            # Indent each line of the message body
                            for line in msg.message.splitlines():
                                lines.append(f"    {line}")
                        if attachment:
                            lines.append(f"    {attachment}")

            lines.append("\n" + "=" * 80)
            lines.append("END OF EXPORT")
            lines.append("=" * 80 + "\n")

            content = "\n".join(lines)
            timestamp = timezone.now().strftime("%Y%m%d_%H%M")
            response = HttpResponse(content, content_type="text/plain; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="tickets_export_{timestamp}.txt"'

            _set_rate_limit(request.user, "export_tickets")
            logger.warning(
                "Tickets export downloaded by user '%s' (id=%s) from %s",
                request.user.username, request.user.pk,
                request.META.get("REMOTE_ADDR", "unknown"),
            )

            response.set_cookie('fileDownload', 'true', path='/')
            return response
        except Exception as e:
            logger.error("Tickets export failed for user '%s': %s", request.user.username, e)
            return HttpResponse(f"Error creating export: {str(e)}", status=500)


class BackupMediaView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        allowed, wait = _check_rate_limit(request.user, "backup_media")
        if not allowed:
            return HttpResponse(
                f"Rate limit: please wait {wait} seconds before downloading another backup.",
                status=429,
            )

        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            return HttpResponse("Media directory does not exist.", status=404)

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'media_backup')

        try:
            shutil.make_archive(zip_path, 'zip', media_root)
            zip_file = f"{zip_path}.zip"

            # Stream the file instead of loading it all into memory
            response = FileResponse(
                open(zip_file, 'rb'),
                content_type='application/zip',
                as_attachment=True,
                filename='media_backup.zip',
            )
            # Store temp_dir path so we can clean up after streaming finishes.
            # FileResponse closes the file handle; we rely on the OS to allow
            # deletion after the response is fully sent.  For safety we also
            # register a cleanup callback.
            response._temp_dir_to_cleanup = temp_dir

            _set_rate_limit(request.user, "backup_media")
            logger.warning(
                "Media backup downloaded by user '%s' (id=%s) from %s",
                request.user.username, request.user.pk,
                request.META.get("REMOTE_ADDR", "unknown"),
            )

            response.set_cookie('fileDownload', 'true', path='/')
            return response
        except Exception as e:
            logger.error("Media backup failed for user '%s': %s", request.user.username, e)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return HttpResponse(f"Error creating backup: {str(e)}", status=500)


# ---------------------------------------------------------------------------
# Cleanup views
# ---------------------------------------------------------------------------

class CleanupTicketsPreviewView(MaintenancePermissionMixin, View):
    """Return a count of tickets that would be deleted (HTMX fragment)."""

    def post(self, request, *args, **kwargs):
        try:
            days = int(request.POST.get('days', 30))
        except ValueError:
            days = 30

        cutoff_date = timezone.now() - timedelta(days=days)
        count = Ticket.objects.filter(status='closed', updated_at__lt=cutoff_date).count()
        confirm_url = reverse('cleanup_tickets')

        if count == 0:
            return HttpResponse(f"""
                <div class="notice info" style="margin-top: 1rem;">
                    <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    <span>There is nothing to clear! No closed tickets older than {days} days were found. <em>(Checked at {timezone.now().strftime('%H:%M:%S')})</em></span>
                </div>
                <div style="margin-top: 0.75rem;">
                    <button type="button" class="btn secondary mgmt-btn-sm"
                            onclick="document.getElementById('cleanup-response').innerHTML=''">
                        Close
                    </button>
                </div>
            """)

        return HttpResponse(f"""
            <div class="notice info" style="margin-top: 1rem;">
                <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                <span><strong>{count}</strong> closed ticket(s) older than {days} days will be permanently deleted. <em>(Checked at {timezone.now().strftime('%H:%M:%S')})</em></span>
            </div>
            <form hx-post="{confirm_url}"
                  hx-target="#cleanup-response"
                  style="margin-top: 0.75rem;">
                <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get('CSRF_COOKIE', '')}">
                <input type="hidden" name="days" value="{days}">
                <input type="hidden" name="confirmed" value="1">
                <button type="submit" class="btn danger mgmt-btn-sm">
                    Confirm Delete {count} Ticket(s)
                </button>
                <button type="button" class="btn secondary mgmt-btn-sm"
                        onclick="document.getElementById('cleanup-response').innerHTML=''">
                    Cancel
                </button>
            </form>
        """)


class CleanupTicketsView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            days = int(request.POST.get('days', 30))
        except ValueError:
            days = 30

        # If not confirmed, redirect to preview
        if request.POST.get('confirmed') != '1':
            return CleanupTicketsPreviewView.as_view()(request, *args, **kwargs)

        cutoff_date = timezone.now() - timedelta(days=days)

        tickets_to_delete = Ticket.objects.filter(status='closed', updated_at__lt=cutoff_date)
        count = tickets_to_delete.count()

        # Delete attachment files from disk before deleting DB records
        messages_with_attachments = TicketMessage.objects.filter(
            ticket__in=tickets_to_delete,
            attachment__isnull=False,
        ).exclude(attachment='')

        orphan_files_deleted = 0
        for msg in messages_with_attachments.iterator():
            try:
                if msg.attachment and msg.attachment.storage.exists(msg.attachment.name):
                    msg.attachment.delete(save=False)
                    orphan_files_deleted += 1
            except Exception:
                # Log but don't block the cleanup
                logger.warning(
                    "Failed to delete attachment file for message %s", msg.pk
                )

        tickets_to_delete.delete()

        logger.warning(
            "Ticket cleanup by user '%s' (id=%s): deleted %d tickets older than %d days, "
            "removed %d attachment files from disk.",
            request.user.username, request.user.pk, count, days, orphan_files_deleted,
        )

        return HttpResponse(f"""
            <div class="notice success" style="margin-top: 1rem;">
                <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <span>Successfully deleted {count} closed tickets older than {days} days ({orphan_files_deleted} attachment files removed).</span>
            </div>
        """)


class CleanupNotificationsPreviewView(MaintenancePermissionMixin, View):
    """Return a count of notifications that would be deleted (HTMX fragment)."""

    def post(self, request, *args, **kwargs):
        try:
            read_days = int(request.POST.get('read_days', 30))
        except ValueError:
            read_days = 30
        try:
            all_days = int(request.POST.get('all_days', 90))
        except ValueError:
            all_days = 90

        now = timezone.now()

        all_cutoff = now - timedelta(days=all_days)
        all_count = InAppNotification.objects.filter(created_at__lt=all_cutoff).count()

        read_cutoff = now - timedelta(days=read_days)
        # Exclude the ones already counted above to avoid double-counting
        read_count = InAppNotification.objects.filter(
            is_read=True, created_at__lt=read_cutoff, created_at__gte=all_cutoff
        ).count()

        total = all_count + read_count
        remaining = InAppNotification.objects.count()
        confirm_url = reverse('cleanup_notifications')

        if total == 0:
            return HttpResponse(f"""
                <div class="notice info" style="margin-top: 1rem;">
                    <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    <span>There is nothing to clear! No notifications match your selected criteria. <em>(Checked at {timezone.now().strftime('%H:%M:%S')})</em></span>
                </div>
                <div style="margin-top: 0.75rem;">
                    <button type="button" class="btn secondary mgmt-btn-sm"
                            onclick="document.getElementById('cleanup-response').innerHTML=''">
                        Close
                    </button>
                </div>
            """)

        return HttpResponse(f"""
            <div class="notice info" style="margin-top: 1rem;">
                <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                <span><strong>{total}</strong> notification(s) will be deleted ({all_count} all older than {all_days} days + {read_count} read older than {read_days} days). Currently {remaining} total. <em>(Checked at {timezone.now().strftime('%H:%M:%S')})</em></span>
            </div>
            <form hx-post="{confirm_url}"
                  hx-target="#cleanup-response"
                  style="margin-top: 0.75rem;">
                <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get('CSRF_COOKIE', '')}">
                <input type="hidden" name="read_days" value="{read_days}">
                <input type="hidden" name="all_days" value="{all_days}">
                <input type="hidden" name="confirmed" value="1">
                <button type="submit" class="btn danger mgmt-btn-sm">
                    Confirm Delete {total} Notification(s)
                </button>
                <button type="button" class="btn secondary mgmt-btn-sm"
                        onclick="document.getElementById('cleanup-response').innerHTML=''">
                    Cancel
                </button>
            </form>
        """)


class CleanupNotificationsView(MaintenancePermissionMixin, View):
    """Actually delete notifications — requires confirmed=1."""

    def post(self, request, *args, **kwargs):
        # If not confirmed, redirect to preview
        if request.POST.get('confirmed') != '1':
            return CleanupNotificationsPreviewView.as_view()(request)

        try:
            read_days = int(request.POST.get('read_days', 30))
        except ValueError:
            read_days = 30
        try:
            all_days = int(request.POST.get('all_days', 90))
        except ValueError:
            all_days = 90

        now = timezone.now()

        # 1) Delete ALL notifications older than all_days first (to avoid double-counting)
        all_cutoff = now - timedelta(days=all_days)
        all_qs = InAppNotification.objects.filter(created_at__lt=all_cutoff)
        all_count = all_qs.count()
        if all_count:
            all_qs.delete()

        # 2) Delete read notifications older than read_days (remaining ones only)
        read_cutoff = now - timedelta(days=read_days)
        read_qs = InAppNotification.objects.filter(is_read=True, created_at__lt=read_cutoff)
        read_count = read_qs.count()
        if read_count:
            read_qs.delete()

        total = all_count + read_count
        remaining = InAppNotification.objects.count()

        logger.warning(
            "Notification cleanup by user '%s' (id=%s): deleted %d total "
            "(%d all older than %d days, %d read older than %d days). %d remaining.",
            request.user.username, request.user.pk,
            total, all_count, all_days, read_count, read_days, remaining,
        )

        return HttpResponse(f"""
            <div class="notice success" style="margin-top: 1rem;">
                <svg width="20" height="20" style="vertical-align: middle; margin-right: 0.5rem;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <span>Cleanup complete: deleted {total} notification(s) ({all_count} older than {all_days} days + {read_count} read older than {read_days} days). {remaining} remaining.</span>
            </div>
        """)
