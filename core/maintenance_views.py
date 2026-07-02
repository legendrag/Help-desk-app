import os
import shutil
import tempfile
from io import StringIO
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponse
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from tickets.models import Ticket, TicketMessage
from accounts.models import User
from kb.models import Article, ArticleAttachment

class MaintenancePermissionMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_superuser or (user.role and user.role.can_manage_maintenance)

class MaintenanceView(MaintenancePermissionMixin, TemplateView):
    template_name = "core/management/maintenance.html"

class BackupDatabaseView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        out = StringIO()
        try:
            # We exclude contenttypes, auth.Permission, and sessions as these can cause issues on DB import
            call_command('dumpdata', exclude=['contenttypes', 'auth.Permission', 'sessions'], format='json', indent=2, stdout=out)
            response = HttpResponse(out.getvalue(), content_type='application/json')
            response['Content-Disposition'] = 'attachment; filename="helpdesk_backup.json"'
            return response
        except Exception as e:
            return HttpResponse(f"Error creating backup: {str(e)}", status=500)

class BackupMediaView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            return HttpResponse("Media directory does not exist.", status=404)
        
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'media_backup')
        
        try:
            shutil.make_archive(zip_path, 'zip', media_root)
            zip_file = f"{zip_path}.zip"
            
            with open(zip_file, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
                response['Content-Disposition'] = 'attachment; filename="media_backup.zip"'
                return response
        except Exception as e:
            return HttpResponse(f"Error creating media backup: {str(e)}", status=500)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class CleanupTicketsView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            days = int(request.POST.get('days', 30))
        except ValueError:
            days = 30
            
        cutoff_date = timezone.now() - timedelta(days=days)
        
        tickets_to_delete = Ticket.objects.filter(status='closed', updated_at__lt=cutoff_date)
        count = tickets_to_delete.count()
        
        tickets_to_delete.delete()
        
        return HttpResponse(f"""
            <div class="notice success" style="margin-top: 1rem;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <span>Successfully deleted {count} closed tickets older than {days} days.</span>
            </div>
        """)

class CleanupMediaView(MaintenancePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            return HttpResponse("No media directory found.", status=200)

        active_files = set()
        
        for user in User.objects.exclude(avatar='').exclude(avatar__isnull=True):
            active_files.add(user.avatar.name)
        for ticket in Ticket.objects.exclude(attachment='').exclude(attachment__isnull=True):
            active_files.add(ticket.attachment.name)
        for msg in TicketMessage.objects.exclude(attachment='').exclude(attachment__isnull=True):
            active_files.add(msg.attachment.name)
        for article_att in ArticleAttachment.objects.exclude(file='').exclude(file__isnull=True):
            active_files.add(article_att.file.name)


        deleted_count = 0
        freed_space = 0

        for root, dirs, files in os.walk(media_root):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, media_root).replace('\\', '/')
                
                if rel_path not in active_files:
                    try:
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        freed_space += size
                    except Exception:
                        pass
                        
        mb_freed = freed_space / (1024 * 1024)

        return HttpResponse(f"""
            <div class="notice success" style="margin-top: 1rem;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                <span>Successfully cleaned {deleted_count} orphaned files, freeing {mb_freed:.2f} MB of space.</span>
            </div>
        """)
