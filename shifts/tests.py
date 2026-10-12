from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Department, Role
from shifts.models import ShiftAssignment, ShiftType

User = get_user_model()


@contextmanager
def _both_clocks(now, day):
    with patch("django.utils.timezone.now", return_value=now), \
         patch("django.utils.timezone.localdate", return_value=day):
        yield


def aware(y, m, d, hh, mm=0):
    return timezone.make_aware(datetime(y, m, d, hh, mm))


def make_department(name="Desk"):
    return Department.objects.create(name=name)


def make_role(name="Agent", **flags):
    return Role.objects.create(name=name, **flags)


def make_user(username, user_type, department=None, role=None, superuser=False, first_name="", last_name=""):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="test-pass-123",
        user_type=user_type,
        department=department,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    if superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save()
    return user


def make_shift_type(department, name="Night", start=time(22, 0), end=time(6, 0), archived=False):
    return ShiftType.objects.create(
        department=department,
        name=name,
        start_time=start,
        end_time=end,
        colour="#336699",
        archived=archived,
    )


def make_assignment(user, shift_type, on, start=None, end=None):
    return ShiftAssignment.objects.create(
        user=user,
        shift_type=shift_type,
        date=on,
        start_time_override=start,
        end_time_override=end,
        times_set_by=user if start and end else None,
        times_set_at=timezone.now() if start and end else None,
    )


class ShiftTypeNightFlagTests(TestCase):
    def test_end_before_start_is_night(self):
        department = make_department()
        row = make_shift_type(department, start=time(22, 0), end=time(6, 0))
        self.assertTrue(row.is_night)

    def test_colour_validator_rejects_a_non_hex_value(self):
        department = make_department("Colour")
        row = make_shift_type(department, name="Colour night")
        row.colour = "blue"
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_same_day_span_is_not_night(self):
        department = make_department()
        row = make_shift_type(department, name="Day", start=time(9, 0), end=time(17, 0))
        self.assertFalse(row.is_night)

    def test_names_are_unique_per_department(self):
        department = make_department()
        make_shift_type(department, name="Night")
        with self.assertRaises(Exception):
            ShiftType.objects.create(
                department=department,
                name="Night",
                start_time=time(1, 0),
                end_time=time(2, 0),
                colour="#112233",
            )


class WeekAndHoursTests(TestCase):
    def test_wednesday_snaps_to_previous_saturday(self):
        from shifts.services import normalize_start, saturday_of, week_dates

        wednesday = date(2026, 10, 7)  # Wednesday
        saturday = date(2026, 10, 3)
        self.assertEqual(saturday_of(wednesday), saturday)
        self.assertEqual(saturday_of(saturday), saturday)
        self.assertEqual(normalize_start(wednesday, "week"), saturday)
        self.assertEqual(normalize_start(date(2026, 10, 7), "month"), date(2026, 10, 1))
        self.assertEqual(week_dates(saturday)[0], saturday)
        self.assertEqual(week_dates(saturday)[-1], date(2026, 10, 9))  # Friday
        self.assertEqual(len(week_dates(saturday)), 7)

    def test_night_type_minutes_stay_night_when_clipped(self):
        from shifts.services import clipped_day_night_minutes, interval_for

        department = make_department("Hours")
        user = make_user("hana", "support", department)
        night = make_shift_type(department)
        friday = date(2026, 10, 9)
        row = make_assignment(user, night, friday)
        start, end = interval_for(friday, time(22, 0), time(6, 0))
        day, night_m = clipped_day_night_minutes(row, start, end)
        # Night runs 6 PM to 6 AM, so the whole 10 PM to 6 AM shift is night.
        self.assertEqual((day, night_m), (0, 480))
        week_end = timezone.make_aware(datetime(2026, 10, 10, 0, 0))
        week_start = timezone.make_aware(datetime(2026, 10, 3, 0, 0))
        day, night_m = clipped_day_night_minutes(row, week_start, week_end)
        self.assertEqual((day, night_m), (0, 120))
        next_week_end = timezone.make_aware(datetime(2026, 10, 17, 0, 0))
        day, night_m = clipped_day_night_minutes(row, week_end, next_week_end)
        self.assertEqual((day, night_m), (0, 360))

    def test_same_evening_on_a_night_type_is_all_night_hours(self):
        from shifts.services import clipped_day_night_minutes

        department = make_department("Evening")
        user = make_user("omar", "support", department)
        night = make_shift_type(department, name="Night desk")
        row = make_assignment(user, night, date(2026, 10, 6), time(18, 0), time(23, 0))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 7, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (0, 300))

    def test_clock_split_ignores_the_type_flag(self):
        from shifts.services import clipped_day_night_minutes, clock_length

        department = make_department("Day cross")
        user = make_user("lina", "support", department)
        day_type = make_shift_type(department, name="Days", start=time(9, 0), end=time(17, 0))
        row = make_assignment(user, day_type, date(2026, 10, 6), time(22, 0), time(6, 0))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 8, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (0, 480))
        self.assertEqual(clock_length(time(22, 0), time(6, 0)), (480, 360))
        self.assertEqual(clock_length(time(9, 0), time(12, 30)), (210, 0))

    def test_half_open_touch_is_not_overlap(self):
        from shifts.services import interval_for, overlaps

        monday = date(2026, 10, 5)
        left = interval_for(monday, time(22, 0), time(6, 0))
        right = interval_for(date(2026, 10, 6), time(6, 0), time(14, 0))
        early = interval_for(date(2026, 10, 6), time(1, 0), time(9, 0))
        self.assertFalse(overlaps(left, right))
        self.assertTrue(overlaps(left, early))


class LandingTests(TestCase):
    def test_each_role_lands_on_its_page(self):
        department = make_department("Land")
        manager_role = make_role(name="Shift lead", can_manage_shifts=True)
        manager = make_user("lead", "support", department, manager_role)
        support = make_user("agent", "support", department)
        branch = make_user("branch", "branch")
        self.client.force_login(manager)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_rota"))
        self.client.force_login(support)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_mine"))
        self.client.force_login(branch)
        self.assertRedirects(self.client.get(reverse("shifts_home")), reverse("shifts_available"))

    def test_sidebar_link_is_present_for_support(self):
        department = make_department("Nav")
        support = make_user("navagent", "support", department)
        self.client.force_login(support)
        response = self.client.get(reverse("shifts_mine"))
        self.assertContains(response, 'data-nav-key="shifts"')


class ShiftTypeCrudTests(TestCase):
    def test_types_page_opens_on_a_department_that_has_types(self):
        make_department("Aaa empty")
        filled = make_department("Zzz filled")
        make_shift_type(filled, name="Desk night")
        role = make_role("Types default", can_manage_shifts=True)
        manager = make_user("types-default", "support", filled, role)
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_types"))
        self.assertContains(response, "Desk night")
        self.assertContains(response, f'value="{filled.pk}" selected')

    def test_support_cannot_open_types(self):
        department = make_department("Types")
        support = make_user("types-agent", "support", department)
        self.client.force_login(support)
        self.assertEqual(self.client.get(reverse("shifts_types")).status_code, 403)

    def test_manager_creates_and_archives(self):
        department = make_department("Types2")
        role = make_role("Types lead", can_manage_shifts=True)
        manager = make_user("types-lead", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": "Night",
            "start_time": "22:00",
            "end_time": "06:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 302)
        row = ShiftType.objects.get(name="Night")
        self.assertTrue(row.is_night)
        archive = self.client.post(reverse("shifts_type_archive", args=[row.pk]))
        self.assertEqual(archive.status_code, 302)
        row.refresh_from_db()
        self.assertTrue(row.archived)

    def test_equal_times_rejected(self):
        department = make_department("Types3")
        role = make_role("Types lead 2", can_manage_shifts=True)
        manager = make_user("types-lead-2", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": "Bad",
            "start_time": "09:00",
            "end_time": "09:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShiftType.objects.filter(name="Bad").exists())
        self.assertContains(response, "Start and end must differ.")

    def test_short_name_rejected(self):
        department = make_department("Types4")
        role = make_role("Types lead 3", can_manage_shifts=True)
        manager = make_user("types-lead-3", "support", department, role)
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_type_add"), {
            "department": department.pk,
            "name": " N ",
            "start_time": "09:00",
            "end_time": "17:00",
            "colour": "#336699",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShiftType.objects.filter(department=department).exists())
        self.assertContains(response, "at least 2 characters")


class RotaGridTests(TestCase):
    def setUp(self):
        self.department = make_department("Rota")
        self.role = make_role("Rota lead", can_manage_shifts=True)
        self.manager = make_user("rota-lead", "support", self.department, self.role)
        self.agent = make_user("rota-agent", "support", self.department)
        self.night = make_shift_type(self.department)
        self.client.force_login(self.manager)

    def test_rota_opens_on_a_department_that_has_types(self):
        empty = make_department("Aaa empty rota")
        response = self.client.get(reverse("shifts_rota"))
        self.assertContains(response, f'value="{self.department.pk}" selected')
        self.assertNotContains(response, f'value="{empty.pk}" selected')
        self.assertNotIn(">Show<", response.content.decode())

    def test_week_query_normalizes_to_saturday(self):
        response = self.client.get(reverse("shifts_rota"), {"view": "week", "start": "2026-10-07", "department": self.department.pk})
        self.assertContains(response, "2026-10-03")
        self.assertContains(response, "2026-10-09")

    def test_cell_post_blocks_overlap(self):
        make_assignment(self.agent, self.night, date(2026, 10, 5))
        response = self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "shift_type": self.night.pk,
            "start_time_override": "01:00",
            "end_time_override": "09:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "overlaps")
        self.assertEqual(ShiftAssignment.objects.filter(user=self.agent).count(), 1)

    def test_support_gets_403(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("shifts_rota")).status_code, 403)

    def test_grid_query_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for index in range(6):
            person = make_user(f"budget-{index}", "support", self.department)
            make_assignment(person, self.night, date(2026, 10, 5))
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse("shifts_rota_grid"), {
                "view": "week",
                "start": "2026-10-03",
                "department": self.department.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured), 12)


class CopyWeekTests(TestCase):
    def test_worker_times_are_not_copied(self):
        from shifts.services import plan_copy

        department = make_department("Copy")
        agent = make_user("copy-agent", "support", department)
        manager = make_user("copy-lead", "support", department, make_role("Copy lead", can_manage_shifts=True))
        night = make_shift_type(department)
        source = make_assignment(agent, night, date(2026, 10, 3), time(18, 0), time(23, 0))
        planned = plan_copy([source], timedelta(days=7), manager)
        self.assertEqual(planned[0]["start"], None)
        self.assertEqual(planned[0]["end"], None)
        self.assertIsNone(planned[0]["times_set_by_id"])
        self.assertEqual(planned[0]["date"], date(2026, 10, 10))

    def test_repeat_rejects_13(self):
        department = make_department("Repeat")
        manager = make_user("repeat-lead", "support", department, make_role("Repeat lead", can_manage_shifts=True))
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_repeat_week"), {
            "department": department.pk,
            "start": "2026-10-03",
            "weeks": "13",
        })
        self.assertEqual(response.status_code, 302)
        followed = self.client.get(response["Location"])
        self.assertContains(followed, "1 to 12")
        self.assertEqual(ShiftAssignment.objects.count(), 0)

    def test_friday_tail_does_not_become_saturday(self):
        department = make_department("Tail")
        manager = make_user("tail-lead", "support", department, make_role("Tail lead", can_manage_shifts=True))
        agent = make_user("tail-agent", "support", department)
        night = make_shift_type(department, name="Tail night")
        make_assignment(agent, night, date(2026, 10, 9))  # Friday
        self.client.force_login(manager)
        self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        })
        self.assertFalse(ShiftAssignment.objects.filter(user=agent, date=date(2026, 10, 10)).exists())
        copied = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 16))
        self.assertIsNone(copied.checked_in_at)
        self.assertIsNone(copied.start_time_override)

    def test_manager_set_override_is_copied_and_repeated(self):
        department = make_department("Mgr copy")
        manager = make_user("mgr-copy-lead", "support", department, make_role("Mgr copy lead", can_manage_shifts=True))
        agent = make_user("mgr-copy-agent", "support", department)
        night = make_shift_type(department, name="Mgr night")
        source = make_assignment(agent, night, date(2026, 10, 3), time(18, 0), time(23, 0))
        source.times_set_by = manager
        source.save()
        self.client.force_login(manager)
        self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        })
        copied = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 10))
        self.assertEqual(copied.start_time_override, time(18, 0))
        self.assertEqual(copied.end_time_override, time(23, 0))
        self.assertEqual(copied.times_set_by_id, manager.pk)
        self.client.post(reverse("shifts_repeat_week"), {
            "department": department.pk,
            "start": "2026-10-10",
            "weeks": "1",
        })
        repeated = ShiftAssignment.objects.get(user=agent, date=date(2026, 10, 17))
        self.assertEqual(repeated.start_time_override, time(18, 0))
        self.assertEqual(repeated.end_time_override, time(23, 0))
        self.assertEqual(repeated.times_set_by_id, manager.pk)


class RotationTests(TestCase):
    def test_three_people_six_nights_are_even_and_not_consecutive(self):
        from shifts.services import suggest_nights

        department = make_department("Fair")
        people = [make_user(f"fair-{i}", "support", department) for i in range(3)]
        night = make_shift_type(department, name="Fair night")
        dates = [date(2026, 10, 5) + timedelta(days=i) for i in range(6)]
        result = suggest_nights(people, dates, night, {person.pk: [] for person in people})
        assigned = [row for row in result if not row.get("gap")]
        counts = {}
        for row in assigned:
            counts[row["user_id"]] = counts.get(row["user_id"], 0) + 1
        self.assertEqual(sorted(counts.values()), [2, 2, 2])
        by_date = {row["date"]: row["user_id"] for row in assigned}
        for idx in range(1, 6):
            self.assertNotEqual(by_date[dates[idx]], by_date[dates[idx - 1]])

    def test_apply_does_not_overwrite(self):
        department = make_department("Keep")
        role = make_role("Keep lead", can_manage_shifts=True)
        manager = make_user("keep-lead", "support", department, role)
        agent = make_user("keep-agent", "support", department)
        night = make_shift_type(department, name="Keep night")
        existing = make_assignment(agent, night, date(2026, 10, 5))
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "2026-10-05",
            "end": "2026-10-05",
            "shift_type": night.pk,
            "users": [agent.pk],
            "action": "apply",
        })
        self.assertContains(response, "already assigned")
        existing.refresh_from_db()
        self.assertEqual(existing.shift_type_id, night.pk)

    def test_day_or_archived_night_type_returns_404_and_writes_nothing(self):
        department = make_department("Gate")
        role = make_role("Gate lead", can_manage_shifts=True)
        manager = make_user("gate-lead", "support", department, role)
        agent = make_user("gate-agent", "support", department)
        day = make_shift_type(department, name="Gate day", start=time(9, 0), end=time(17, 0))
        archived = make_shift_type(department, name="Gate old night", archived=True)
        self.client.force_login(manager)
        payload = {
            "department": department.pk,
            "start": "2026-10-05",
            "end": "2026-10-05",
            "users": [agent.pk],
            "action": "apply",
        }
        for bad in (day, archived):
            response = self.client.post(
                reverse("shifts_calc_rotation"),
                {**payload, "shift_type": bad.pk},
            )
            self.assertEqual(response.status_code, 404)
        self.assertEqual(ShiftAssignment.objects.count(), 0)

    def test_two_people_two_dates_are_one_each(self):
        from shifts.services import suggest_nights

        department = make_department("Pair")
        people = [make_user(f"pair-{i}", "support", department) for i in range(2)]
        night = make_shift_type(department, name="Pair night")
        dates = [date(2026, 10, 5), date(2026, 10, 6)]
        result = suggest_nights(people, dates, night, {person.pk: [] for person in people})
        self.assertEqual([row["user_id"] for row in result], [people[0].pk, people[1].pk])
        self.assertFalse(any(row["back_to_back"] for row in result))

    def test_calculator_lists_night_types_and_preview_uses_names(self):
        department = make_department("Picker")
        manager = make_user("picker-lead", "support", department, make_role("Picker lead", can_manage_shifts=True))
        agent = make_user("picker-agent", "support", department, first_name="Nora", last_name="Saleh")
        make_user("picker-day-only", "branch")
        night = make_shift_type(department, name="Picker night")
        make_shift_type(department, name="Picker day", start=time(9, 0), end=time(17, 0))
        make_shift_type(department, name="Picker old", archived=True)
        self.client.force_login(manager)
        page = self.client.get(reverse("shifts_calculator"))
        self.assertContains(page, "Picker night")
        self.assertContains(page, "Nora Saleh")
        self.assertContains(page, 'name="users"')
        self.assertContains(page, "Select all")
        self.assertContains(page, "checked")
        self.assertNotContains(page, "multiple")
        self.assertNotContains(page, "Picker day")
        self.assertNotContains(page, "Picker old")
        preview = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "2026-10-05",
            "end": "2026-10-05",
            "shift_type": night.pk,
            "users": [agent.pk],
            "action": "preview",
        })
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Nora Saleh")
        hx = self.client.get(reverse("shifts_calculator"), HTTP_HX_REQUEST="true")
        self.assertEqual(hx.status_code, 200)
        self.assertNotContains(hx, "<main")
        empty = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "",
            "end": "",
            "shift_type": "",
            "action": "preview",
        })
        self.assertEqual(empty.status_code, 404)

    def test_plain_auto_fill_post_redirects_to_the_rota(self):
        department = make_department("Fill page")
        manager = make_user("fill-lead", "support", department, make_role("Fill lead", can_manage_shifts=True))
        make_user("fill-agent", "support", department, first_name="Hana", last_name="Nour")
        make_shift_type(department, name="Fill night")
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "preview",
            "start": "2026-10-03",
            "view": "week",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/shifts/rota/", response["Location"])
        followed = self.client.get(response["Location"])
        self.assertEqual(followed.status_code, 200)
        self.assertContains(followed, "Open the rota to review the night rotation.")
        self.assertNotIn(b"<table", response.content)

    def test_hx_auto_fill_without_a_night_type_is_only_a_message(self):
        department = make_department("No night")
        manager = make_user("none-lead", "support", department, make_role("None lead", can_manage_shifts=True))
        make_shift_type(department, name="Day only", start=time(9, 0), end=time(17, 0))
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "preview",
            "start": "2026-10-06",
            "view": "week",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="shifts-shell-pane"')
        self.assertContains(response, "This department has no night shift.")
        plain = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "preview",
            "start": "2026-10-06",
            "view": "week",
        })
        self.assertEqual(plain.status_code, 302)
        self.assertIn("/shifts/rota/", plain["Location"])

    def test_auto_fill_skips_past_dates_and_nights_already_assigned(self):
        department = make_department("Skip nights")
        manager = make_user("skip-lead", "support", department, make_role("Skip lead", can_manage_shifts=True))
        veteran = make_user("skip-vet", "support", department, first_name="Omar", last_name="Hassan")
        fresh = make_user("skip-fresh", "support", department, first_name="Sara", last_name="Nabil")
        night = make_shift_type(department, name="Skip night")
        today = timezone.localdate()
        make_assignment(veteran, night, today)
        make_assignment(fresh, night, today + timedelta(days=1))
        self.client.force_login(manager)
        past_week = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "preview",
            "start": (today - timedelta(days=7)).isoformat(),
            "view": "week",
        }, HTTP_HX_REQUEST="true")
        self.assertContains(past_week, "skipped (past)")
        self.assertNotContains(past_week, 'id="shifts-shell-pane"')
        preview = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "preview",
            "start": today.isoformat(),
            "view": "week",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(preview.status_code, 200)
        self.assertNotContains(preview, 'id="shifts-shell-pane"')
        self.assertContains(preview, "skipped (already assigned)")
        self.assertContains(preview, today.isoformat())
        applied = self.client.post(reverse("shifts_auto_fill"), {
            "department": department.pk,
            "action": "apply",
            "start": today.isoformat(),
            "view": "week",
            "shift_type": night.pk,
        }, HTTP_HX_REQUEST="true")
        self.assertNotContains(applied, 'id="shifts-shell-pane"')
        self.assertEqual(ShiftAssignment.objects.get(user=veteran, date=today).shift_type_id, night.pk)
        self.assertEqual(ShiftAssignment.objects.filter(date=today, shift_type__is_night=True).count(), 1)
        self.assertEqual(ShiftAssignment.objects.filter(user=fresh, date=today + timedelta(days=1)).count(), 1)

    def test_copy_conflict_names_the_person_and_redirects(self):
        department = make_department("Named copy")
        manager = make_user("name-lead", "support", department, make_role("Name lead", can_manage_shifts=True))
        agent = make_user("name-agent", "support", department, first_name="Mona", last_name="Saleh")
        night = make_shift_type(department, name="Named night")
        make_assignment(agent, night, date(2026, 10, 3))
        make_assignment(agent, night, date(2026, 10, 10))
        self.client.force_login(manager)
        page = self.client.get(reverse("shifts_rota"), {"department": department.pk, "start": "2026-10-10"})
        self.assertContains(page, "Copy last week into this week?")
        self.assertContains(page, "Repeat this week forward?")
        self.client.cookies["django_language"] = "ar"
        arabic = self.client.get(reverse("shifts_rota"), {"department": department.pk, "start": "2026-10-10"})
        body = arabic.content.decode()
        self.assertEqual(body.count('data-confirm-title="تأكيد الإجراء"'), 2)
        self.assertEqual(body.count('data-confirm-ok="نعم، متابعة"'), 2)
        self.assertEqual(body.count('data-confirm-cancel="إلغاء"'), 2)
        self.client.cookies["django_language"] = "en"
        response = self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/shifts/rota/", response["Location"])
        followed = self.client.get(response["Location"])
        self.assertContains(followed, "Mona Saleh")
        hx = self.client.post(reverse("shifts_copy_week"), {
            "department": department.pk,
            "start": "2026-10-10",
        }, HTTP_HX_REQUEST="true")
        self.assertEqual(hx.status_code, 200)
        self.assertNotContains(hx, 'id="shifts-shell-pane"')
        self.assertContains(hx, "Mona Saleh")
        self.assertNotContains(hx, f">{agent.pk}<")

    def test_one_person_second_night_is_back_to_back(self):
        from shifts.services import suggest_nights

        department = make_department("Solo")
        person = make_user("solo", "support", department)
        night = make_shift_type(department, name="Solo night")
        dates = [date(2026, 10, 5), date(2026, 10, 6)]
        result = suggest_nights([person], dates, night, {person.pk: []})
        self.assertEqual(result[1]["back_to_back"], True)

    def test_back_to_back_preview_names_the_reason(self):
        department = make_department("Reason")
        manager = make_user("reason-lead", "support", department, make_role("Reason lead", can_manage_shifts=True))
        agent = make_user("reason-agent", "support", department, first_name="Mona", last_name="Saleh")
        night = make_shift_type(department, name="Reason night")
        self.client.force_login(manager)
        preview = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "2026-10-05",
            "end": "2026-10-06",
            "shift_type": night.pk,
            "users": [agent.pk],
            "action": "preview",
        })
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Only one person available")
        self.assertNotContains(preview, "Others already assigned on this date")

    def test_back_to_back_reason_names_others_when_the_date_is_taken(self):
        from shifts.services import suggest_nights

        department = make_department("Taken")
        veteran = make_user("taken-vet", "support", department)
        other = make_user("taken-other", "support", department)
        night = make_shift_type(department, name="Taken night")
        day = make_shift_type(department, name="Taken day", start=time(9, 0), end=time(17, 0))
        existing_night = make_assignment(veteran, night, date(2026, 10, 5))
        existing_day = make_assignment(other, day, date(2026, 10, 6))
        result = suggest_nights(
            [veteran, other],
            [date(2026, 10, 6)],
            night,
            {veteran.pk: [existing_night], other.pk: [existing_day]},
        )
        self.assertEqual(result[0]["user_id"], other.pk)
        self.assertFalse(result[0]["back_to_back"])
        both_nights = suggest_nights(
            [veteran, other],
            [date(2026, 10, 6)],
            night,
            {
                veteran.pk: [existing_night],
                other.pk: [make_assignment(other, night, date(2026, 10, 5)), existing_day],
            },
        )
        self.assertEqual(both_nights[0]["user_id"], veteran.pk)
        self.assertTrue(both_nights[0]["back_to_back"])
        self.assertEqual(str(both_nights[0]["reason"]), "Others already assigned on this date")

    def test_missing_rotation_dates_ask_for_dates(self):
        department = make_department("Dates")
        manager = make_user("dates-lead", "support", department, make_role("Dates lead", can_manage_shifts=True))
        night = make_shift_type(department, name="Dates night")
        self.client.force_login(manager)
        response = self.client.post(reverse("shifts_calc_rotation"), {
            "department": department.pk,
            "start": "",
            "end": "",
            "shift_type": night.pk,
            "action": "preview",
        })
        self.assertContains(response, "Enter a start and an end date.")

    def test_proposed_night_counts_toward_the_earliest_last_night(self):
        from shifts.services import suggest_nights

        department = make_department("Tie break")
        veteran = make_user("tie-veteran", "support", department)
        fresh = make_user("tie-fresh", "support", department)
        night = make_shift_type(department, name="Tie night")
        older = make_assignment(veteran, night, date(2026, 9, 28))
        dates = [date(2026, 10, 5), date(2026, 10, 7)]
        result = suggest_nights(
            [veteran, fresh],
            dates,
            night,
            {veteran.pk: [older], fresh.pk: []},
        )
        self.assertEqual(result[0]["user_id"], fresh.pk)
        self.assertEqual(result[1]["user_id"], veteran.pk)


class CalculatorTests(TestCase):
    def test_length_reports_after_midnight_separately(self):
        department = make_department("Calc")
        manager = make_user("calc-lead", "support", department, make_role("Calc lead", can_manage_shifts=True))
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_calc_length"), {"start": "22:00", "end": "06:00"})
        self.assertContains(response, "8")
        self.assertContains(response, "6")
        self.assertContains(response, "after midnight")

    def test_support_forbidden(self):
        department = make_department("Calc2")
        agent = make_user("calc-agent", "support", department)
        self.client.force_login(agent)
        self.assertEqual(self.client.get(reverse("shifts_calculator")).status_code, 403)

    def test_quarter_hour_length(self):
        department = make_department("Calc3")
        manager = make_user("calc-lead-3", "support", department, make_role("Calc lead 3", can_manage_shifts=True))
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_calc_length"), {"start": "09:00", "end": "12:30"})
        self.assertContains(response, "3 hours 30 minutes")
        self.assertContains(response, "0 hours 0 minutes after midnight")

    def test_coverage_counts_overnight_until_but_not_including_06(self):
        department = make_department("Heat")
        manager = make_user("heat-lead", "support", department, make_role("Heat lead", can_manage_shifts=True))
        agent = make_user("heat-agent", "support", department)
        night = make_shift_type(department, name="Heat night")
        make_assignment(agent, night, date(2026, 10, 5))  # Monday 22:00–06:00
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_calc_coverage"), {
            "department": department.pk,
            "view": "week",
            "start": "2026-10-03",
        })
        self.assertContains(response, 'id="cov-2026-10-06-5">1')
        self.assertContains(response, 'id="cov-2026-10-06-6" class="shifts-gap">0')

    def test_same_evening_covers_18_through_22(self):
        department = make_department("Heat eve")
        manager = make_user("heat-lead-2", "support", department, make_role("Heat lead 2", can_manage_shifts=True))
        agent = make_user("heat-eve", "support", department)
        night = make_shift_type(department, name="Heat eve")
        make_assignment(agent, night, date(2026, 10, 6), time(18, 0), time(23, 0))
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_calc_coverage"), {
            "department": department.pk,
            "view": "week",
            "start": "2026-10-03",
        })
        self.assertContains(response, 'id="cov-2026-10-06-18">1')
        self.assertContains(response, 'id="cov-2026-10-06-22">1')
        self.assertContains(response, 'id="cov-2026-10-06-23" class="shifts-gap">0')

    def test_check_in_does_not_change_hours_or_coverage(self):
        department = make_department("Same hours")
        manager = make_user("same-lead", "support", department, make_role("Same lead", can_manage_shifts=True))
        agent = make_user("same-agent", "support", department)
        day = make_shift_type(department, name="Same day", start=time(9, 0), end=time(17, 0))
        row = make_assignment(agent, day, date(2026, 10, 5))
        self.client.force_login(manager)
        params = {"department": department.pk, "view": "week", "start": "2026-10-03"}
        before_hours = self.client.get(reverse("shifts_calc_hours"), params).content
        before_coverage = self.client.get(reverse("shifts_calc_coverage"), params).content
        row.checked_in_at = aware(2026, 10, 5, 9, 0)
        row.save()
        after_hours = self.client.get(reverse("shifts_calc_hours"), params).content
        after_coverage = self.client.get(reverse("shifts_calc_coverage"), params).content
        self.assertEqual(before_hours, after_hours)
        self.assertEqual(before_coverage, after_coverage)


class WorkerHoursTests(TestCase):
    def setUp(self):
        self.department = make_department("Mine")
        self.agent = make_user("mine-agent", "support", self.department)
        self.other = make_user("mine-other", "support", self.department)
        self.night = make_shift_type(self.department, name="Mine night")
        self.day = make_shift_type(self.department, name="Mine day", start=time(9, 0), end=time(17, 0))
        self.today = timezone.localdate()
        self.own = make_assignment(self.agent, self.night, self.today)
        self.client.force_login(self.agent)

    def test_mine_page_shows_a_colour_chip_not_the_hex(self):
        response = self.client.get(reverse("shifts_mine"))
        self.assertContains(response, 'class="shifts-chip')
        self.assertContains(response, "background-color: #336699")
        self.assertNotContains(response, ">#336699<")

    def test_time_ranges_keep_start_before_end_in_an_ltr_wrapper(self):
        response = self.client.get(reverse("shifts_mine"))
        self.assertContains(response, '<bdi class="shifts-ltr" dir="ltr">10:00 PM–6:00 AM</bdi>')
        self.assertNotContains(response, 'dir="auto"')
        self.assertNotContains(response, "13:00")

    def test_board_rota_and_mine_show_a_12_hour_clock(self):
        department = make_department("Clock")
        manager = make_user("clock-lead", "support", department, make_role("Clock lead", can_manage_shifts=True))
        agent = make_user("clock-agent", "support", department, first_name="Hana", last_name="Nabil")
        day = make_shift_type(department, name="Clock day", start=time(9, 0), end=time(13, 0))
        today = date(2026, 10, 6)
        row = make_assignment(agent, day, today)
        row.checked_in_at = aware(2026, 10, 6, 9, 30)
        row.save()
        during = aware(2026, 10, 6, 10, 0)
        self.client.force_login(manager)
        with _both_clocks(during, today):
            rota = self.client.get(reverse("shifts_rota"), {
                "department": department.pk,
                "view": "week",
                "start": "2026-10-06",
            })
        self.assertContains(rota, "1:00 PM")
        self.assertContains(rota, "9:00 AM")
        self.assertNotContains(rota, "13:00")
        self.client.force_login(agent)
        with _both_clocks(during, today):
            mine = self.client.get(reverse("shifts_mine"))
        self.assertContains(mine, "1:00 PM")
        self.assertNotContains(mine, "13:00")
        self.client.force_login(make_user("clock-branch", "branch"))
        with _both_clocks(during, today):
            board = self.client.get(reverse("shifts_available"))
        self.assertContains(board, "1:00 PM")
        self.assertNotContains(board, "13:00")

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_arabic_times_are_isolated_and_english_ranges_stay_left_to_right(self):
        department = make_department("Bidi")
        manager = make_user("bidi-lead", "support", department, make_role("Bidi lead", can_manage_shifts=True))
        agent = make_user("bidi-agent", "support", department, first_name="Sara", last_name="Nabil")
        day = make_shift_type(department, name="Bidi day", start=time(9, 0), end=time(17, 0))
        today = date(2026, 10, 6)
        row = make_assignment(agent, day, today)
        # 06:05 UTC is 9:05 AM in Africa/Cairo, independent of the server TIME_ZONE.
        row.checked_in_at = datetime(2026, 10, 6, 6, 5, tzinfo=dt_timezone.utc)
        row.save()
        params = {"department": department.pk, "view": "week", "start": "2026-10-06"}
        noon_utc = datetime(2026, 10, 6, 9, 0, tzinfo=dt_timezone.utc)
        self.client.force_login(manager)
        with _both_clocks(noon_utc, today):
            english = self.client.get(reverse("shifts_rota"), params)
        self.assertContains(english, '<bdi class="shifts-ltr" dir="ltr">9:00 AM–5:00 PM</bdi>')
        self.assertNotContains(english, 'dir="auto"')
        self.client.force_login(agent)
        with _both_clocks(noon_utc, today):
            mine_en = self.client.get(reverse("shifts_mine"))
        self.assertContains(mine_en, '<bdi class="shifts-ltr" dir="ltr">9:05 AM</bdi>')
        self.assertContains(mine_en, "Checked in at")
        self.client.cookies["django_language"] = "ar"
        self.client.force_login(manager)
        with _both_clocks(noon_utc, today):
            arabic = self.client.get(reverse("shifts_rota"), params)
        self.assertContains(arabic, '<bdi dir="auto">9:00 ص</bdi> – <bdi dir="auto">5:00 م</bdi>')
        self.assertNotContains(arabic, 'dir="ltr">9:00 ص')
        self.assertNotContains(arabic, 'class="shifts-ltr" dir="ltr">9:00 ص–5:00 م')
        self.client.force_login(agent)
        with _both_clocks(noon_utc, today):
            mine = self.client.get(reverse("shifts_mine"))
            board = self.client.get(reverse("shifts_available"))
        self.assertContains(mine, '<bdi dir="auto">9:00 ص</bdi> – <bdi dir="auto">5:00 م</bdi>')
        self.assertContains(mine, '<bdi dir="auto">9:05 ص</bdi>')
        self.assertContains(mine, "تم تسجيل الحضور في")
        self.assertNotContains(mine, 'dir="ltr">9:05')
        self.assertContains(board, '<bdi dir="auto">5:00 م</bdi>')
        self.assertContains(board, "حتى")
        self.assertNotContains(board, 'dir="ltr">5:00 م')

    def test_owner_can_set_same_evening_hours(self):
        response = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00",
            "end_time": "23:00",
            "action": "save",
        })
        self.assertEqual(response.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.start_time_override, time(18, 0))
        self.assertEqual(self.own.times_set_by_id, self.agent.pk)

    def test_other_user_and_day_shift_are_403(self):
        foreign = make_assignment(self.other, self.night, self.today)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[foreign.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        }).status_code, 403)
        foreign.refresh_from_db()
        self.assertIsNone(foreign.start_time_override)
        day_row = make_assignment(self.agent, self.day, self.today + timedelta(days=1))
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[day_row.pk]), {
            "start_time": "10:00", "end_time": "15:00", "action": "save",
        }).status_code, 403)

    def test_eight_days_ago_rejected_and_seven_accepted(self):
        old = make_assignment(self.agent, self.night, self.today - timedelta(days=8))
        response = self.client.post(reverse("shifts_mine_hours", args=[old.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        self.assertContains(response, "last 7 days")
        old.refresh_from_db()
        self.assertIsNone(old.start_time_override)
        recent = make_assignment(self.agent, self.night, self.today - timedelta(days=7))
        ok = self.client.post(reverse("shifts_mine_hours", args=[recent.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        self.assertEqual(ok.status_code, 200)
        recent.refresh_from_db()
        self.assertEqual(recent.start_time_override, time(18, 0))

    def test_branch_post_forbidden(self):
        branch = make_user("mine-branch", "branch")
        self.client.force_login(branch)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        }).status_code, 403)

    def test_length_cap_equal_times_overlap_and_reset(self):
        too_long = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "00:00", "end_time": "16:30", "action": "save",
        })
        self.assertContains(too_long, "16 hours")
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        equal = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "18:00", "action": "save",
        })
        self.assertContains(equal, "16 hours")
        crossing = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "02:00", "action": "save",
        })
        self.assertEqual(crossing.status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.end_time_override, time(2, 0))
        self.own.start_time_override = None
        self.own.end_time_override = None
        self.own.times_set_by = None
        self.own.times_set_at = None
        self.own.save()
        neighbor = make_assignment(self.agent, self.night, self.today + timedelta(days=1), time(1, 0), time(9, 0))
        blocked = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "02:00", "action": "save",
        })
        self.assertContains(blocked, "overlaps")
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        neighbor.delete()
        self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {
            "start_time": "18:00", "end_time": "23:00", "action": "save",
        })
        reset = self.client.post(reverse("shifts_mine_hours", args=[self.own.pk]), {"action": "reset"})
        self.assertEqual(reset.status_code, 200)
        self.own.refresh_from_db()
        self.assertIsNone(self.own.start_time_override)
        self.assertIsNone(self.own.times_set_by_id)
        self.assertIsNone(self.own.times_set_at)


class CheckInTests(TestCase):
    def setUp(self):
        self.department = make_department("Check")
        self.agent = make_user(
            "check-agent",
            "support",
            self.department,
            make_role("Check agent", can_check_in=True),
        )
        self.other = make_user("check-other", "support", self.department)
        self.day = make_shift_type(self.department, name="Check day", start=time(9, 0), end=time(17, 0))
        self.night = make_shift_type(self.department, name="Check night")
        self.today = date(2026, 6, 2)
        self.row = make_assignment(self.agent, self.day, self.today)
        self.client.force_login(self.agent)

    def _at(self, hh, mm=0):
        return _both_clocks(aware(2026, 6, 2, hh, mm), date(2026, 6, 2))

    def test_window_and_idempotent_press(self):
        with self._at(8, 0):
            too_soon = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.assertContains(too_soon, "30 minutes")
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        with self._at(8, 40):
            first = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        stamped = self.row.checked_in_at
        self.assertIsNotNone(stamped)
        with self._at(9, 0):
            second = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        self.assertEqual(self.row.checked_in_at, stamped)
        self.assertContains(second, "Checked in at")

    def test_hidden_for_night_other_and_branch(self):
        night = make_assignment(self.agent, self.night, self.today + timedelta(days=1))
        with self._at(8, 40):
            self.assertEqual(self.client.post(reverse("shifts_check_in", args=[night.pk])).status_code, 403)
        # Freezing timezone.now rewrites the session expiry into the past
        # because SESSION_SAVE_EVERY_REQUEST is on. Sign in again before the
        # unpatched request.
        self.client.force_login(self.agent)
        foreign = make_assignment(self.other, self.day, self.today + timedelta(days=2))
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[foreign.pk])).status_code, 403)
        self.client.force_login(make_user("check-branch", "branch"))
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.row.pk])).status_code, 403)

    def test_manager_clear_worker_cannot(self):
        self.row.checked_in_at = aware(2026, 6, 2, 8, 40)
        self.row.save()
        self.assertEqual(self.client.post(reverse("shifts_cell"), {
            "clear_check_in": "1",
            "user": self.agent.pk,
            "date": "2026-06-02",
            "department": self.department.pk,
            "shift_type": self.day.pk,
        }).status_code, 403)
        manager = make_user("check-lead", "support", self.department, make_role("Check lead", can_manage_shifts=True))
        self.client.force_login(manager)
        self.client.post(reverse("shifts_cell"), {
            "clear_check_in": "1",
            "user": self.agent.pk,
            "date": "2026-06-02",
            "department": self.department.pk,
            "shift_type": self.day.pk,
        })
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)

    def test_panel_only_for_the_owning_support_user(self):
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            mine = self.client.get(reverse("shifts_mine"))
        self.assertContains(mine, 'id="shifts-check-in"')
        self.client.force_login(self.other)
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            other = self.client.get(reverse("shifts_mine"))
        self.assertNotContains(other, 'id="shifts-check-in"')
        manager = make_user(
            "check-panel-lead",
            "support",
            self.department,
            make_role("Panel lead", can_manage_shifts=True, can_check_in=True),
        )
        make_assignment(manager, self.day, self.today)
        self.client.force_login(manager)
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 8, 40)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            rota = self.client.get(reverse("shifts_rota"))
        self.assertContains(rota, 'id="shifts-check-in"')

    def test_day_to_night_clears_check_in(self):
        self.row.checked_in_at = aware(2026, 6, 2, 9, 0)
        self.row.save()
        manager = make_user("type-lead", "support", self.department, make_role("Type lead", can_manage_shifts=True))
        self.client.force_login(manager)
        self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-06-02",
            "department": self.department.pk,
            "assignment": self.row.pk,
            "shift_type": self.night.pk,
        })
        self.row.refresh_from_db()
        self.assertEqual(self.row.shift_type_id, self.night.pk)
        self.assertIsNone(self.row.checked_in_at)

    def test_day_shift_check_in_window_30_minutes(self):
        # 08:29 is 31 minutes before 09:00 - check-in panel should NOT be visible
        with self._at(8, 29):
            res_early = self.client.get(reverse("shifts_mine"))
            self.assertNotContains(res_early, f'id="shifts-check-in-{self.row.pk}"')
            post_early = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
            self.assertContains(post_early, "30 minutes")
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)

        # 08:30 is exactly 30 minutes before 09:00 - check-in panel appears and POST succeeds
        with self._at(8, 30):
            res_open = self.client.get(reverse("shifts_mine"))
            self.assertContains(res_open, f'id="shifts-check-in-{self.row.pk}"')
            post_open = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
            self.assertContains(post_open, "Checked in at")
        self.row.refresh_from_db()
        self.assertIsNotNone(self.row.checked_in_at)

    def test_night_shift_cross_midnight_check_in_window(self):
        night_row = make_assignment(self.agent, self.night, self.today)
        # 21:29 is 31 minutes before 22:00 - check-in is early/hidden
        with self._at(21, 29):
            res_early = self.client.get(reverse("shifts_mine"))
            self.assertNotContains(res_early, f'id="shifts-check-in-{night_row.pk}"')
            post_early = self.client.post(reverse("shifts_check_in", args=[night_row.pk]))
            self.assertContains(post_early, "30 minutes")
        night_row.refresh_from_db()
        self.assertIsNone(night_row.checked_in_at)

        # 21:30 is 30 minutes before 22:00 - check-in opens
        with self._at(21, 30):
            res_open = self.client.get(reverse("shifts_mine"))
            self.assertContains(res_open, f'id="shifts-check-in-{night_row.pk}"')

        # Next day at 00:30 (cross-midnight, during the 22:00-06:00 shift)
        next_day = date(2026, 6, 3)
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 3, 0, 30)), \
             patch("django.utils.timezone.localdate", return_value=next_day):
            res_cross = self.client.get(reverse("shifts_mine"))
            self.assertContains(res_cross, f'id="shifts-check-in-{night_row.pk}"')
            post_cross = self.client.post(reverse("shifts_check_in", args=[night_row.pk]))
            self.assertContains(post_cross, "Checked in at")
        night_row.refresh_from_db()
        self.assertIsNotNone(night_row.checked_in_at)

    def test_check_in_panels_htmx_partial_endpoint(self):
        with self._at(8, 20):
            res = self.client.get(reverse("shifts_check_in_panels"))
            self.assertEqual(res.status_code, 200)
            self.assertNotContains(res, f'id="shifts-check-in-{self.row.pk}"')

        with self._at(8, 35):
            res = self.client.get(reverse("shifts_check_in_panels"))
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, f'id="shifts-check-in-{self.row.pk}"')


class AutoCheckOutTests(TestCase):
    def setUp(self):
        self.department = make_department("Auto out")
        self.agent = make_user(
            "auto-agent",
            "support",
            self.department,
            make_role("Auto agent", can_check_in=True),
            first_name="Nada",
            last_name="Farid",
        )
        self.day = make_shift_type(self.department, name="Auto day", start=time(9, 0), end=time(17, 0))
        self.night = make_shift_type(self.department, name="Auto night")
        self.today = date(2026, 6, 2)
        self.row = make_assignment(self.agent, self.day, self.today)
        self.client.force_login(self.agent)

    def _stamp_checked_in(self, at):
        self.row.checked_in_at = at
        self.row.checked_out_at = None
        self.row.save(update_fields=["checked_in_at", "checked_out_at"])

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_lazy_clear_after_effective_end_in_cairo(self):
        checked_in = timezone.make_aware(datetime(2026, 6, 2, 9, 5))
        end = timezone.make_aware(datetime(2026, 6, 2, 17, 0))
        self._stamp_checked_in(checked_in)
        manager = make_user(
            "auto-lead",
            "support",
            self.department,
            make_role("Auto lead", can_manage_shifts=True),
        )
        self.client.force_login(manager)
        with _both_clocks(end, self.today):
            rota = self.client.get(reverse("shifts_rota"), {
                "department": self.department.pk,
                "view": "week",
                "start": "2026-05-30",
            })
        self.assertNotContains(rota, "Checked in at")
        self.client.force_login(self.agent)
        with _both_clocks(end, self.today):
            mine = self.client.get(reverse("shifts_mine"))
            board = self.client.get(reverse("shifts_available"))
        self.assertNotContains(mine, "Checked in at")
        self.assertNotContains(board, "Nada Farid")
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        self.assertEqual(self.row.checked_out_at, end)

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_override_end_is_the_auto_check_out_time(self):
        self.row.start_time_override = time(9, 0)
        self.row.end_time_override = time(15, 0)
        self.row.times_set_by = self.agent
        self.row.times_set_at = timezone.now()
        self.row.checked_in_at = timezone.make_aware(datetime(2026, 6, 2, 9, 5))
        self.row.save()
        still_open = timezone.make_aware(datetime(2026, 6, 2, 14, 59))
        with _both_clocks(still_open, self.today):
            self.client.get(reverse("shifts_mine"))
        self.row.refresh_from_db()
        self.assertIsNotNone(self.row.checked_in_at)
        ended = timezone.make_aware(datetime(2026, 6, 2, 15, 0))
        with _both_clocks(ended, self.today):
            mine = self.client.get(reverse("shifts_mine"))
        self.assertNotContains(mine, "Checked in at")
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        self.assertEqual(self.row.checked_out_at, ended)

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_agent_cannot_check_in_again_after_auto_or_manager_clear(self):
        self._stamp_checked_in(timezone.make_aware(datetime(2026, 6, 2, 9, 5)))
        end = timezone.make_aware(datetime(2026, 6, 2, 17, 0))
        with _both_clocks(end, self.today):
            self.client.get(reverse("shifts_mine"))
            blocked = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        self.assertIsNotNone(self.row.checked_out_at)
        self.assertNotContains(blocked, "Checked in at")
        self.row.start_time_override = time(9, 0)
        self.row.end_time_override = time(21, 0)
        self.row.times_set_by = self.agent
        self.row.times_set_at = timezone.now()
        self.row.save()
        later = timezone.make_aware(datetime(2026, 6, 2, 18, 0))
        with _both_clocks(later, self.today):
            self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        self.assertIsNotNone(self.row.checked_out_at)

        fresh = make_assignment(self.agent, self.day, self.today + timedelta(days=1))
        # Manager clear is on today's row; use a new open day shift that is today.
        fresh.delete()
        self.row.end_time_override = None
        self.row.start_time_override = None
        self.row.times_set_by = None
        self.row.times_set_at = None
        self.row.checked_out_at = None
        self.row.checked_in_at = timezone.make_aware(datetime(2026, 6, 2, 9, 5))
        self.row.save()
        manager = make_user(
            "auto-clear-lead",
            "support",
            self.department,
            make_role("Auto clear lead", can_manage_shifts=True),
        )
        during = timezone.make_aware(datetime(2026, 6, 2, 10, 0))
        self.client.force_login(manager)
        with _both_clocks(during, self.today):
            self.client.post(reverse("shifts_cell"), {
                "clear_check_in": "1",
                "user": self.agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "shift_type": self.day.pk,
            })
        self.client.force_login(self.agent)
        with _both_clocks(during, self.today):
            again = self.client.post(reverse("shifts_check_in", args=[self.row.pk]))
        self.row.refresh_from_db()
        self.assertIsNone(self.row.checked_in_at)
        self.assertIsNotNone(self.row.checked_out_at)
        self.assertNotContains(again, "Checked in at")
        self.assertNotContains(again, "Check out")

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_manager_can_restore_check_in_without_the_agent_flag(self):
        self._stamp_checked_in(timezone.make_aware(datetime(2026, 6, 2, 9, 5)))
        manager = make_user(
            "auto-restore-lead",
            "support",
            self.department,
            make_role("Auto restore lead", can_manage_shifts=True),
        )
        during = timezone.make_aware(datetime(2026, 6, 2, 10, 0))
        self.client.force_login(manager)
        with _both_clocks(during, self.today):
            self.client.post(reverse("shifts_cell"), {
                "clear_check_in": "1",
                "user": self.agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "shift_type": self.day.pk,
            })
            form = self.client.get(reverse("shifts_cell"), {
                "user": self.agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "assignment": self.row.pk,
            })
        self.assertContains(form, 'name="restore_check_in"')
        self.assertNotContains(form, "Clear check-in")
        with _both_clocks(during, self.today):
            self.client.post(reverse("shifts_cell"), {
                "restore_check_in": "1",
                "user": self.agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "shift_type": self.day.pk,
            })
        self.row.refresh_from_db()
        self.assertIsNotNone(self.row.checked_in_at)
        self.assertIsNone(self.row.checked_out_at)
        self.client.force_login(self.agent)
        with _both_clocks(during, self.today):
            mine = self.client.get(reverse("shifts_mine"))
            board = self.client.get(reverse("shifts_available"))
        self.assertContains(mine, "Checked in at")
        self.assertContains(board, "Nada Farid")

    @override_settings(TIME_ZONE="Africa/Cairo")
    def test_night_shift_checks_out_when_it_ends(self):
        night = make_assignment(self.agent, self.night, date(2026, 6, 1))
        night.checked_in_at = timezone.make_aware(datetime(2026, 6, 1, 22, 5))
        night.save(update_fields=["checked_in_at"])
        later = timezone.make_aware(datetime(2026, 6, 2, 8, 0))
        with _both_clocks(later, self.today):
            self.client.get(reverse("shifts_available"))
            posted = self.client.post(reverse("shifts_check_in", args=[night.pk]))
        self.assertEqual(posted.status_code, 403)
        night.refresh_from_db()
        self.assertIsNone(night.checked_in_at)
        self.assertEqual(night.checked_out_at, timezone.make_aware(datetime(2026, 6, 2, 6, 0)))


class CheckInPermissionTests(TestCase):
    def setUp(self):
        self.department = make_department("Check flag")
        self.day = make_shift_type(self.department, name="Flag day", start=time(9, 0), end=time(17, 0))
        self.today = date(2026, 6, 2)
        self.during = aware(2026, 6, 2, 10, 0)

    def test_flag_allows_check_in_and_hides_it_when_missing(self):
        allowed_user = make_user(
            "flag-yes",
            "support",
            self.department,
            make_role("Flag yes", can_check_in=True),
        )
        denied_user = make_user("flag-no", "support", self.department)
        allowed = make_assignment(allowed_user, self.day, self.today)
        denied = make_assignment(denied_user, self.day, self.today)
        self.client.force_login(denied_user)
        with _both_clocks(self.during, self.today):
            hidden = self.client.get(reverse("shifts_mine"))
            blocked = self.client.post(reverse("shifts_check_in", args=[denied.pk]))
        self.assertNotContains(hidden, 'id="shifts-check-in"')
        self.assertEqual(blocked.status_code, 403)
        denied.refresh_from_db()
        self.assertIsNone(denied.checked_in_at)
        self.client.force_login(allowed_user)
        with _both_clocks(self.during, self.today):
            shown = self.client.get(reverse("shifts_mine"))
            opened = self.client.post(reverse("shifts_check_in", args=[allowed.pk]))
        self.assertContains(shown, 'id="shifts-check-in"')
        self.assertContains(opened, "Checked in at")
        allowed.refresh_from_db()
        self.assertIsNotNone(allowed.checked_in_at)

    def test_manager_without_check_in_flag_can_still_clear_and_restore(self):
        agent = make_user(
            "flag-agent",
            "support",
            self.department,
            make_role("Flag agent", can_check_in=True),
        )
        row = make_assignment(agent, self.day, self.today)
        row.checked_in_at = self.during
        row.save(update_fields=["checked_in_at"])
        manager = make_user(
            "flag-lead",
            "support",
            self.department,
            make_role("Flag lead", can_manage_shifts=True),
        )
        make_assignment(manager, self.day, self.today)
        self.client.force_login(manager)
        with _both_clocks(self.during, self.today):
            own = self.client.get(reverse("shifts_mine"))
        self.assertNotContains(own, 'id="shifts-check-in"')
        with _both_clocks(self.during, self.today):
            self.client.post(reverse("shifts_cell"), {
                "clear_check_in": "1",
                "user": agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "shift_type": self.day.pk,
            })
            restored = self.client.post(reverse("shifts_cell"), {
                "restore_check_in": "1",
                "user": agent.pk,
                "date": "2026-06-02",
                "department": self.department.pk,
                "shift_type": self.day.pk,
            })
        self.assertEqual(restored.status_code, 200)
        row.refresh_from_db()
        self.assertIsNotNone(row.checked_in_at)
        self.assertIsNone(row.checked_out_at)


class TeamRotaTests(TestCase):
    def test_manager_opens_on_a_department_that_has_types(self):
        make_department("Aaa empty team")
        filled = make_department("Zzz filled team")
        make_shift_type(filled, name="Team night")
        role = make_role("Team default", can_manage_shifts=True)
        manager = make_user("team-default", "support", filled, role)
        self.client.force_login(manager)
        response = self.client.get(reverse("shifts_team"))
        self.assertContains(response, f'value="{filled.pk}" selected')
        self.assertNotIn(">Show<", response.content.decode())

    def test_support_cannot_switch_department(self):
        home = make_department("Home team")
        other = make_department("Other team")
        agent = make_user("team-agent", "support", home)
        self.client.force_login(agent)
        response = self.client.get(reverse("shifts_team"), {"department": other.pk, "start": "2026-10-03"})
        self.assertEqual(response.status_code, 403)

    def test_branch_forbidden(self):
        self.client.force_login(make_user("team-branch", "branch"))
        self.assertEqual(self.client.get(reverse("shifts_team")).status_code, 403)


class AvailableNowTests(TestCase):
    def test_night_shift_needs_check_in_until_end(self):
        department = make_department("Now")
        agent = make_user("now-agent", "support", department)
        night = make_shift_type(department, name="Now night")
        row = make_assignment(agent, night, date(2026, 6, 1))
        self.client.force_login(make_user("now-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            hidden = self.client.get(reverse("shifts_available_board"))
        self.assertNotContains(hidden, "now-agent")
        row.checked_in_at = aware(2026, 6, 1, 22, 10)
        row.save(update_fields=["checked_in_at"])
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            shown = self.client.get(reverse("shifts_available_board"))
        self.assertContains(shown, "now-agent")
        self.assertNotContains(shown, "Now night")
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 6, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            ended = self.client.get(reverse("shifts_available_board"))
        self.assertNotContains(ended, "now-agent")

    def test_day_shift_needs_check_in_and_etag_changes(self):
        department = make_department("Now day")
        agent = make_user("day-agent", "support", department)
        day = make_shift_type(department, name="Now day", start=time(9, 0), end=time(17, 0))
        row = make_assignment(agent, day, date(2026, 6, 2))
        self.client.force_login(agent)
        noon = aware(2026, 6, 2, 12, 0)
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            before = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        self.assertNotContains(before, "day-agent")
        etag_before = before["ETag"]
        row.checked_in_at = noon
        row.save()
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            after = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        self.assertContains(after, "day-agent")
        self.assertNotEqual(after["ETag"], etag_before)
        with patch("django.utils.timezone.now", return_value=noon), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            cached = self.client.get(
                reverse("shifts_available_board"),
                HTTP_HX_REQUEST="true",
                HTTP_IF_NONE_MATCH=after["ETag"],
            )
        self.assertEqual(cached.status_code, 304)

    def test_early_check_in_stays_hidden_until_start_and_changes_etag(self):
        department = make_department("Early")
        agent = make_user("early-agent", "support", department)
        day = make_shift_type(department, name="Early day", start=time(9, 0), end=time(17, 0))
        row = make_assignment(agent, day, date(2026, 6, 2))
        self.client.force_login(agent)
        early = aware(2026, 6, 2, 8, 40)
        with patch("django.utils.timezone.now", return_value=early), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            before = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        row.checked_in_at = early
        row.save()
        with patch("django.utils.timezone.now", return_value=early), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            during = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
        self.assertNotContains(during, "early-agent")
        self.assertNotEqual(during["ETag"], before["ETag"])
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 9, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            started = self.client.get(reverse("shifts_available_board"))
        self.assertContains(started, "early-agent")
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 17, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            ended = self.client.get(reverse("shifts_available_board"))
        self.assertNotContains(ended, "early-agent")

    def test_empty_department_and_no_type_name_for_branch(self):
        empty = make_department("Empty desk")
        staffed = make_department("Staffed")
        agent = make_user("staffed-agent", "support", staffed, first_name="", last_name="")
        night = make_shift_type(staffed, name="Secret type")
        row = make_assignment(agent, night, date(2026, 6, 1))
        row.checked_in_at = aware(2026, 6, 1, 22, 10)
        row.save(update_fields=["checked_in_at"])
        self.client.force_login(make_user("board-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            response = self.client.get(reverse("shifts_available_board"))
        self.assertContains(response, "Nobody on shift now")
        self.assertContains(response, "staffed-agent")
        self.assertNotContains(response, "Secret type")
        self.assertContains(response, "6:00 AM")

    def test_history_restore_is_not_304(self):
        department = make_department("Hist")
        self.client.force_login(make_user("hist-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            first = self.client.get(reverse("shifts_available_board"), HTTP_HX_REQUEST="true")
            restored = self.client.get(
                reverse("shifts_available_board"),
                HTTP_HX_REQUEST="true",
                HTTP_IF_NONE_MATCH=first["ETag"],
                HTTP_HX_HISTORY_RESTORE_REQUEST="true",
            )
        self.assertEqual(restored.status_code, 200)

    def test_board_query_budget(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        department = make_department("Budget board")
        night = make_shift_type(department, name="Budget night")
        for index in range(6):
            person = make_user(f"board-{index}", "support", department)
            make_assignment(person, night, date(2026, 6, 1))
        self.client.force_login(make_user("budget-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)), \
             CaptureQueriesContext(connection) as captured:
            self.client.get(reverse("shifts_available_board"))
        self.assertLessEqual(len(captured), 8)

    def test_first_page_lists_worker_without_waiting_for_poll(self):
        department = make_department("First paint")
        agent = make_user("paint-agent", "support", department, first_name="Paint", last_name="Agent")
        night = make_shift_type(department, name="Paint night")
        row = make_assignment(agent, night, date(2026, 6, 1))
        row.checked_in_at = aware(2026, 6, 1, 22, 10)
        row.save(update_fields=["checked_in_at"])
        self.client.force_login(make_user("paint-branch", "branch"))
        with patch("django.utils.timezone.now", return_value=aware(2026, 6, 2, 5, 0)), \
             patch("django.utils.timezone.localdate", return_value=date(2026, 6, 2)):
            response = self.client.get(reverse("shifts_available"))
        self.assertContains(response, "Paint Agent")
        self.assertContains(response, 'hx-trigger="every 20s [!document.hidden], refresh"')
        self.assertContains(response, "data-no-progress")


class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.department = make_department("Perm")
        self.other = make_department("Perm other")
        self.support = make_user(
            "perm-agent",
            "support",
            self.department,
            make_role("Perm agent", can_check_in=True),
        )
        self.outsider = make_user("perm-out", "support", self.other)
        self.branch = make_user("perm-branch", "branch")
        self.manager = make_user("perm-lead", "support", self.department, make_role("Perm lead", can_manage_shifts=True))
        self.superuser = make_user("perm-root", "support", self.department, superuser=True)
        self.night = make_shift_type(self.department, name="Perm night")
        self.day = make_shift_type(self.department, name="Perm day", start=time(0, 0), end=time(23, 59))
        self.row = make_assignment(self.support, self.night, date(2026, 1, 10))
        self.today_row = make_assignment(self.support, self.day, timezone.localdate())

    def _assert_login(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_anonymous_redirects_every_named_url(self):
        gets = [
            reverse("shifts_home"),
            reverse("shifts_rota"),
            reverse("shifts_rota_grid"),
            reverse("shifts_cell"),
            reverse("shifts_types"),
            reverse("shifts_type_add"),
            reverse("shifts_type_edit", args=[self.night.pk]),
            reverse("shifts_calculator"),
            reverse("shifts_calc_hours"),
            reverse("shifts_calc_length"),
            reverse("shifts_calc_coverage"),
            reverse("shifts_available"),
            reverse("shifts_available_board"),
            reverse("shifts_mine"),
            reverse("shifts_team"),
        ]
        for url in gets:
            self._assert_login(self.client.get(url))
        posts = [
            reverse("shifts_cell"),
            reverse("shifts_copy_week"),
            reverse("shifts_repeat_week"),
            reverse("shifts_auto_fill"),
            reverse("shifts_type_archive", args=[self.night.pk]),
            reverse("shifts_night_starts"),
            reverse("shifts_calc_rotation"),
            reverse("shifts_mine_hours", args=[self.row.pk]),
            reverse("shifts_check_in", args=[self.today_row.pk]),
        ]
        for url in posts:
            self._assert_login(self.client.post(url, {}))

    def test_branch_support_and_manager_statuses(self):
        manager_gets = [
            "shifts_rota", "shifts_rota_grid", "shifts_types", "shifts_type_add",
            "shifts_calculator", "shifts_calc_hours", "shifts_calc_length", "shifts_calc_coverage",
        ]
        shared_gets = ["shifts_available", "shifts_available_board"]
        support_gets = ["shifts_mine", "shifts_team"]
        for user, forbidden in (
            (self.branch, manager_gets + support_gets),
            (self.support, manager_gets),
        ):
            self.client.force_login(user)
            home = self.client.get(reverse("shifts_home"))
            self.assertEqual(home.status_code, 302, user.username)
            for name in shared_gets:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
            for name in forbidden:
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403, f"{user.username} {name}")
                self.assertNotContains(response, "2099-01-01", status_code=403)
        self.client.force_login(self.support)
        self.assertEqual(self.client.get(reverse("shifts_mine")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shifts_team")).status_code, 200)
        self.assertEqual(self.client.get(reverse("shifts_team"), {"department": self.other.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse("shifts_type_edit", args=[self.night.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[make_assignment(self.outsider, self.night, date(2026, 10, 6)).pk]), {"action": "reset"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 200)
        for name, payload in (
            ("shifts_cell", {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}),
            ("shifts_copy_week", {"department": self.department.pk, "start": "2026-10-03"}),
            ("shifts_repeat_week", {"department": self.department.pk, "start": "2026-10-03", "weeks": "1"}),
            ("shifts_auto_fill", {"department": self.department.pk, "action": "apply", "start": "2026-10-03", "view": "week"}),
            ("shifts_calc_rotation", {"action": "apply", "department": self.department.pk, "shift_type": self.night.pk, "start": "2026-10-05", "end": "2026-10-05"}),
            ("shifts_night_starts", {"department": self.department.pk, "night_starts_at": "18:00"}),
        ):
            self.assertEqual(self.client.post(reverse(name), payload).status_code, 403, name)
        self.assertEqual(self.client.post(reverse("shifts_type_archive", args=[self.night.pk])).status_code, 403)
        self.client.force_login(self.branch)
        self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 403)
        for user in (self.manager, self.superuser):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("shifts_home")).status_code, 302)
            for name in manager_gets + shared_gets + support_gets:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, f"{user.username} {name}")
            self.assertEqual(self.client.get(reverse("shifts_type_edit", args=[self.night.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-06", "department": self.department.pk}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_cell"), {"user": self.support.pk, "date": "2026-10-07", "department": self.department.pk, "shift_type": self.night.pk}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_copy_week"), {"department": self.department.pk, "start": "2026-10-03"}).status_code, 302)
            self.assertEqual(self.client.post(reverse("shifts_repeat_week"), {"department": self.department.pk, "start": "2026-10-03", "weeks": "13"}).status_code, 302)
            self.assertEqual(self.client.post(reverse("shifts_auto_fill"), {"department": self.department.pk, "action": "preview", "start": "2026-10-03", "view": "week"}).status_code, 302)
            self.assertEqual(self.client.post(reverse("shifts_calc_rotation"), {"action": "preview", "department": self.department.pk, "shift_type": self.night.pk, "start": "2026-10-05", "end": "2026-10-05", "users": [self.support.pk]}).status_code, 200)
            self.assertEqual(self.client.post(reverse("shifts_night_starts"), {"department": self.department.pk, "night_starts_at": "19:00"}).status_code, 302)
            self.assertEqual(self.client.post(reverse("shifts_mine_hours", args=[self.row.pk]), {"action": "reset"}).status_code, 403)
            self.assertEqual(self.client.post(reverse("shifts_check_in", args=[self.today_row.pk])).status_code, 403)


class NightCutoffTests(TestCase):
    def test_cutoff_splits_evening_and_morning_hours(self):
        from shifts.services import clipped_day_night_minutes

        department = make_department("Split")
        user = make_user("split-agent", "support", department)
        evening = make_shift_type(department, name="Evening", start=time(16, 0), end=time(0, 0))
        overnight = make_shift_type(department, name="Overnight", start=time(22, 0), end=time(6, 0))
        self.assertTrue(evening.is_night)
        self.assertTrue(overnight.is_night)
        day_only = make_shift_type(department, name="Morning", start=time(8, 0), end=time(16, 0))
        self.assertFalse(day_only.is_night)
        evening_row = make_assignment(user, evening, date(2026, 10, 6))
        window_start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        window_end = timezone.make_aware(datetime(2026, 10, 7, 0, 0))
        self.assertEqual(clipped_day_night_minutes(evening_row, window_start, window_end), (120, 360))
        overnight_row = make_assignment(user, overnight, date(2026, 10, 7))
        full_start = timezone.make_aware(datetime(2026, 10, 7, 22, 0))
        full_end = timezone.make_aware(datetime(2026, 10, 8, 6, 0))
        self.assertEqual(clipped_day_night_minutes(overnight_row, full_start, full_end), (0, 480))

    def test_changing_the_cutoff_recomputes_types(self):
        from shifts.models import DepartmentShiftSettings

        department = make_department("Cutoff page")
        manager = make_user(
            "cutoff-lead",
            "support",
            department,
            make_role("Cutoff lead", can_manage_shifts=True),
        )
        afternoon = make_shift_type(department, name="Afternoon", start=time(15, 0), end=time(17, 0))
        self.assertFalse(afternoon.is_night)
        self.client.force_login(manager)
        page = self.client.get(reverse("shifts_types"), {"department": department.pk})
        self.assertContains(page, 'id="night-starts"')
        self.assertContains(page, 'value="18:00"')
        saved = self.client.post(reverse("shifts_night_starts"), {
            "department": department.pk,
            "night_starts_at": "15:00",
        })
        self.assertEqual(saved.status_code, 302)
        afternoon.refresh_from_db()
        self.assertTrue(afternoon.is_night)
        self.assertEqual(
            DepartmentShiftSettings.objects.get(department=department).night_starts_at,
            time(15, 0),
        )


class SameDayShiftTests(TestCase):
    def setUp(self):
        self.department = make_department("Double")
        self.manager = make_user(
            "double-lead",
            "support",
            self.department,
            make_role("Double lead", can_manage_shifts=True),
        )
        self.agent = make_user(
            "double-agent",
            "support",
            self.department,
            make_role("Double agent", can_check_in=True),
        )
        self.day = make_shift_type(self.department, name="Day desk", start=time(8, 0), end=time(16, 0))
        self.night = make_shift_type(self.department, name="Night desk", start=time(22, 0), end=time(6, 0))
        self.client.force_login(self.manager)

    def test_two_shifts_stack_and_overlap_is_rejected(self):
        on = date(2026, 10, 6)
        self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "shift_type": self.day.pk,
        })
        added = self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "shift_type": self.night.pk,
        })
        self.assertEqual(added.status_code, 200)
        self.assertEqual(ShiftAssignment.objects.filter(user=self.agent, date=on).count(), 2)
        grid = self.client.get(reverse("shifts_rota_grid"), {
            "department": self.department.pk,
            "view": "week",
            "start": "2026-10-03",
        })
        self.assertContains(grid, "Day desk")
        self.assertContains(grid, "Night desk")
        self.assertContains(grid, 'data-count="2"')
        self.assertContains(grid, "shifts-cell--filled", count=2)
        clash = self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "shift_type": make_shift_type(self.department, name="Late morning", start=time(9, 0), end=time(12, 0)).pk,
        })
        self.assertContains(clash, "overlaps")
        self.assertEqual(ShiftAssignment.objects.filter(user=self.agent, date=on).count(), 2)
        day_row = ShiftAssignment.objects.get(user=self.agent, date=on, shift_type=self.day)
        removed = self.client.post(reverse("shifts_cell"), {
            "user": self.agent.pk,
            "date": "2026-10-06",
            "department": self.department.pk,
            "assignment": day_row.pk,
            "shift_type": "",
        })
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(ShiftAssignment.objects.filter(pk=day_row.pk).exists())
        self.assertTrue(ShiftAssignment.objects.filter(user=self.agent, date=on, shift_type=self.night).exists())

    def test_copy_keeps_both_shifts(self):
        on = date(2026, 10, 3)
        make_assignment(self.agent, self.day, on)
        make_assignment(self.agent, self.night, on)
        self.client.post(reverse("shifts_copy_week"), {
            "department": self.department.pk,
            "start": "2026-10-10",
        })
        copied = ShiftAssignment.objects.filter(user=self.agent, date=date(2026, 10, 10))
        self.assertEqual(set(copied.values_list("shift_type_id", flat=True)), {self.day.pk, self.night.pk})

    def test_each_shift_checks_in_on_its_own(self):
        on = date(2026, 6, 2)
        day_row = make_assignment(self.agent, self.day, on)
        night_row = make_assignment(self.agent, self.night, on)
        self.client.force_login(self.agent)
        with _both_clocks(aware(2026, 6, 2, 9, 0), on):
            mine = self.client.get(reverse("shifts_mine"))
            day_in = self.client.post(reverse("shifts_check_in", args=[day_row.pk]))
        self.assertContains(mine, f'id="shifts-check-in-{day_row.pk}"')
        self.assertNotContains(mine, f'id="shifts-check-in-{night_row.pk}"')
        self.assertContains(day_in, "Checked in at")
        day_row.refresh_from_db()
        night_row.refresh_from_db()
        self.assertIsNotNone(day_row.checked_in_at)
        self.assertIsNone(night_row.checked_in_at)
        with _both_clocks(aware(2026, 6, 2, 22, 5), on):
            night_page = self.client.get(reverse("shifts_mine"))
            night_in = self.client.post(reverse("shifts_check_in", args=[night_row.pk]))
        self.assertContains(night_page, f'id="shifts-check-in-{night_row.pk}"')
        self.assertNotContains(night_page, f'id="shifts-check-in-{day_row.pk}"')
        self.assertContains(night_in, "Checked in at")
        day_row.refresh_from_db()
        night_row.refresh_from_db()
        self.assertIsNone(day_row.checked_in_at)
        self.assertIsNotNone(day_row.checked_out_at)
        self.assertIsNotNone(night_row.checked_in_at)
        self.assertIsNone(night_row.checked_out_at)


class ReviewFixTests(TestCase):
    """Regressions from the shifts review: bad input, tooltips, sticky forms, tabs."""

    def setUp(self):
        self.department = make_department("Review")
        self.manager = make_user(
            "review-lead",
            "support",
            self.department,
            make_role("Review lead", can_manage_shifts=True),
        )
        self.agent = make_user(
            "review-agent",
            "support",
            self.department,
            make_role("Review agent", can_check_in=True),
        )
        self.day = make_shift_type(self.department, name="Review day", start=time(8, 0), end=time(16, 0))
        self.night = make_shift_type(self.department, name="Review night", start=time(22, 0), end=time(6, 0))
        self.on = date(2026, 6, 2)
        self.client.force_login(self.manager)

    def test_bad_input_never_500s(self):
        cell = reverse("shifts_cell")
        base = {"department": self.department.pk, "user": self.agent.pk}
        for url, params in [
            (reverse("shifts_rota"), {"start": "2026-02-30"}),
            (reverse("shifts_rota"), {"department": "abc"}),
            (reverse("shifts_team"), {"start": "bad"}),
            (reverse("shifts_rota_grid"), {"start": "nope"}),
            (reverse("shifts_calc_hours"), {"start": "x"}),
            (reverse("shifts_calc_coverage"), {"start": "x"}),
            (cell, {**base}),
            (cell, {**base, "date": "garbage"}),
            (cell, {**base, "date": "2026-06-02", "assignment": "zz"}),
            (cell, {"department": self.department.pk, "user": "zz", "date": "2026-06-02"}),
        ]:
            response = self.client.get(url, params)
            self.assertIn(response.status_code, (200, 404), f"{url} {params}")
        posted = self.client.post(cell, {
            **base, "date": "2026-06-02", "shift_type": self.day.pk,
            "start_time_override": "99:00", "end_time_override": "10:00",
        })
        self.assertEqual(posted.status_code, 200)
        self.assertContains(posted, "Enter a valid time.")
        self.assertFalse(ShiftAssignment.objects.filter(user=self.agent).exists())
        copied = self.client.post(reverse("shifts_copy_week"), {"department": self.department.pk, "start": "bad"})
        self.assertIn(copied.status_code, (200, 302))

    def test_bad_hours_shows_error_and_keeps_typed_values(self):
        row = make_assignment(self.agent, self.night, self.on)
        self.client.force_login(self.agent)
        with _both_clocks(aware(2026, 6, 2, 12, 0), self.on):
            bad = self.client.post(
                reverse("shifts_mine_hours", args=[row.pk]),
                {"action": "save", "start_time": "25:99", "end_time": "05:00"},
                HTTP_HX_REQUEST="true",
            )
            long = self.client.post(
                reverse("shifts_mine_hours", args=[row.pk]),
                {"action": "save", "start_time": "06:00", "end_time": "23:30"},
                HTTP_HX_REQUEST="true",
            )
            saved = self.client.post(
                reverse("shifts_mine_hours", args=[row.pk]),
                {"action": "save", "start_time": "21:00", "end_time": "05:00"},
                HTTP_HX_REQUEST="true",
            )
        self.assertContains(bad, "Enter a valid time.")
        self.assertContains(bad, 'value="25:99"')
        self.assertContains(long, 'value="06:00"')
        self.assertContains(long, 'value="23:30"')
        self.assertTemplateUsed(long, "shifts/mine_hours_form.html")
        self.assertNotIn("HX-Trigger", long)
        self.assertEqual(saved["HX-Trigger"], "closeModal, shiftsChanged")
        self.assertEqual(saved["HX-Retarget"], f"#shift-mine-{row.pk}")
        self.assertTemplateUsed(saved, "shifts/mine_row.html")
        row.refresh_from_db()
        self.assertEqual(row.start_time_override, time(21, 0))

    def test_overlap_error_keeps_chosen_type_and_times(self):
        make_assignment(self.agent, self.day, self.on)
        clash = make_shift_type(self.department, name="Review clash", start=time(9, 0), end=time(12, 0))
        response = self.client.post(reverse("shifts_cell"), {
            "department": self.department.pk,
            "user": self.agent.pk,
            "date": "2026-06-02",
            "shift_type": clash.pk,
            "start_time_override": "09:30",
            "end_time_override": "11:00",
        })
        self.assertContains(response, "overlaps")
        self.assertContains(response, f'<option value="{clash.pk}" selected>')
        self.assertContains(response, 'value="09:30"')
        self.assertContains(response, 'value="11:00"')

    def test_checked_in_tooltip_is_plain_text(self):
        row = make_assignment(self.agent, self.day, self.on)
        row.checked_in_at = aware(2026, 6, 2, 8, 5)
        row.save()
        with _both_clocks(aware(2026, 6, 2, 9, 0), self.on):
            grid = self.client.get(reverse("shifts_rota"), {
                "department": self.department.pk, "start": "2026-06-02",
            })
        html = grid.content.decode()
        self.assertIn('title="Checked in at 8:05 AM"', html)
        self.assertNotIn('title="Checked in at <bdi', html)

    def test_check_in_swaps_whole_list_for_htmx(self):
        row = make_assignment(self.agent, self.day, self.on)
        self.client.force_login(self.agent)
        with _both_clocks(aware(2026, 6, 2, 8, 40), self.on):
            response = self.client.post(reverse("shifts_check_in", args=[row.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(response["HX-Retarget"], "#shifts-check-in")
        self.assertContains(response, 'id="shifts-check-in"')
        self.assertContains(response, "Checked in at")
        self.assertContains(response, "You are on shift until")
        self.assertEqual(response.content.decode().count('type="submit"'), 0)

    def test_check_in_list_hidden_when_nothing_to_show(self):
        make_assignment(self.agent, self.day, self.on)
        self.client.force_login(self.agent)
        with _both_clocks(aware(2026, 6, 2, 6, 0), self.on):
            mine = self.client.get(reverse("shifts_mine"))
        self.assertContains(mine, 'class="shifts-checkin-list" data-sig="" hidden')

    def test_types_tab_stays_active_after_saving_night_start(self):
        response = self.client.post(
            reverse("shifts_night_starts"),
            {"department": self.department.pk, "night_starts_at": "19:00"},
            HTTP_HX_REQUEST="true",
        )
        self.assertRegex(
            response.content.decode(),
            r'class="settings-tab active"[^>]*\n\s*aria-current="page"[^>]*\n[^\n]*\n\s*href="/shifts/types/"',
        )

    def test_coverage_rows_use_12_hour_labels(self):
        response = self.client.get(reverse("shifts_calc_coverage"), {
            "department": self.department.pk, "start": "2026-06-06",
        })
        self.assertContains(response, "1:00 PM")
        self.assertNotContains(response, ">13<")


class MyShiftsLayoutTests(TestCase):
    def setUp(self):
        self.department = make_department("Layout")
        self.agent = make_user(
            "layout-agent",
            "support",
            self.department,
            make_role("Layout agent", can_check_in=True),
        )
        self.day = make_shift_type(self.department, name="Layout day", start=time(9, 0), end=time(17, 0))
        self.night = make_shift_type(self.department, name="Layout night", start=time(22, 0), end=time(6, 0))
        # Tuesday; the rota week runs Saturday 2026-05-30 to Friday 2026-06-05.
        self.today = date(2026, 6, 2)
        self.client.force_login(self.agent)

    def _get(self, hh, mm=0):
        with _both_clocks(aware(2026, 6, 2, hh, mm), self.today):
            return self.client.get(reverse("shifts_mine"))

    def test_groups_this_week_later_and_recent(self):
        make_assignment(self.agent, self.day, self.today)
        make_assignment(self.agent, self.day, date(2026, 6, 10))
        make_assignment(self.agent, self.night, date(2026, 5, 29))
        response = self._get(7)
        self.assertEqual([row.date for row in response.context["this_week"]], [self.today])
        self.assertEqual([row.date for row in response.context["later"]], [date(2026, 6, 10)])
        self.assertEqual([row.date for row in response.context["recent"]], [date(2026, 5, 29)])
        self.assertContains(response, "This week")
        self.assertContains(response, "Later")
        self.assertContains(response, '<details class="panel shifts-mine-section shifts-recent">')

    def test_running_night_from_yesterday_stays_in_this_week(self):
        make_assignment(self.agent, self.night, date(2026, 6, 1))
        response = self._get(2)
        self.assertEqual([row.date for row in response.context["this_week"]], [date(2026, 6, 1)])
        self.assertEqual(response.context["recent"], [])
        self.assertContains(response, "Yesterday")
        self.assertContains(response, "Next day")

    def test_status_badges(self):
        row = make_assignment(self.agent, self.day, self.today)
        self.assertContains(self._get(7), "Upcoming")
        self.assertContains(self._get(8, 40), "badge-waiting_for_branch")
        row.checked_in_at = aware(2026, 6, 2, 8, 45)
        row.save()
        on_shift = self._get(10)
        self.assertContains(on_shift, '<span class="badge badge-open">On shift</span>')
        row.checked_in_at = None
        row.save()
        self.assertContains(self._get(18), '<span class="badge badge-expired">Missed</span>')

    def test_today_row_is_marked_and_labelled(self):
        make_assignment(self.agent, self.day, self.today)
        response = self._get(7)
        self.assertContains(response, "shifts-day-pill--today")
        self.assertContains(response, "shifts-day--today")
        self.assertContains(response, "8 hours")

    def test_edit_hours_opens_a_dialog_for_night_rows_only(self):
        day_row = make_assignment(self.agent, self.day, self.today)
        night_row = make_assignment(self.agent, self.night, self.today)
        response = self._get(7)
        self.assertContains(response, reverse("shifts_mine_hours", args=[night_row.pk]))
        self.assertNotContains(response, reverse("shifts_mine_hours", args=[day_row.pk]))
        self.assertNotContains(response, 'name="start_time"')
        with _both_clocks(aware(2026, 6, 2, 7, 0), self.today):
            dialog = self.client.get(reverse("shifts_mine_hours", args=[night_row.pk]))
        self.assertContains(dialog, 'class="modal-header"')
        self.assertContains(dialog, 'value="22:00"')
        self.assertContains(dialog, "Save hours")
        self.assertNotContains(dialog, "Reset to shift default")

    def test_check_in_panel_has_one_check_in_control(self):
        make_assignment(self.agent, self.day, self.today)
        html = self._get(8, 40).content.decode()
        panel = html[html.index('id="shifts-check-in"'):html.index("shifts-mine-section")]
        self.assertEqual(panel.count(">Check in<"), 1)
        self.assertIn("Check-in open", panel)

    def test_empty_state(self):
        response = self._get(7)
        self.assertContains(response, 'class="empty-state"')
        self.assertContains(response, "You have no upcoming shifts.")


class RowRefreshAndDateTests(TestCase):
    def setUp(self):
        self.department = make_department("Refresh")
        self.agent = make_user(
            "refresh-agent",
            "support",
            self.department,
            make_role("Refresh agent", can_check_in=True),
        )
        self.day = make_shift_type(self.department, name="Refresh day", start=time(9, 0), end=time(17, 0))
        self.night = make_shift_type(self.department, name="Refresh night", start=time(22, 0), end=time(6, 0))
        self.today = date(2026, 10, 12)  # a Monday
        self.client.force_login(self.agent)

    def test_nearby_rows_reload_after_check_in(self):
        row = make_assignment(self.agent, self.day, self.today)
        later = make_assignment(self.agent, self.day, date(2026, 10, 20))
        with _both_clocks(aware(2026, 10, 12, 8, 40), self.today):
            page = self.client.get(reverse("shifts_mine"))
            self.client.post(reverse("shifts_check_in", args=[row.pk]), HTTP_HX_REQUEST="true")
            refreshed = self.client.get(reverse("shifts_mine_row", args=[row.pk]))
        self.assertContains(page, f'data-sig="{row.pk}:open"')
        self.assertContains(page, f'hx-get="{reverse("shifts_mine_row", args=[row.pk])}"')
        self.assertNotContains(page, reverse("shifts_mine_row", args=[later.pk]))
        self.assertContains(refreshed, '<span class="badge badge-open">On shift</span>')
        self.assertNotContains(refreshed, "Check-in open")

    def test_row_endpoint_is_owner_only(self):
        other = make_user("refresh-other", "support", self.department)
        row = make_assignment(other, self.day, self.today)
        self.assertEqual(self.client.get(reverse("shifts_mine_row", args=[row.pk])).status_code, 403)

    def test_arabic_dates_use_full_weekday_and_arabic_comma(self):
        make_assignment(self.agent, self.day, self.today)
        self.client.cookies["django_language"] = "ar"
        with _both_clocks(aware(2026, 10, 12, 7, 0), self.today):
            html = self.client.get(reverse("shifts_mine")).content.decode()
        self.assertIn("الاثنين، 12 أكتوبر 2026", html)
        self.assertIn("الاثنين 12 أكتوبر", html)
        self.assertNotIn("إثنين", html)
        self.assertNotIn("الاثنين, ", html)

    def test_english_dates(self):
        make_assignment(self.agent, self.day, self.today)
        with _both_clocks(aware(2026, 10, 12, 7, 0), self.today):
            html = self.client.get(reverse("shifts_mine")).content.decode()
        self.assertIn("Monday, 12 October 2026", html)
        self.assertIn("Mon 12 Oct", html)

    def test_two_shifts_are_two_entries(self):
        manager = make_user(
            "refresh-lead", "support", self.department, make_role("Refresh lead", can_manage_shifts=True),
        )
        make_assignment(self.agent, self.day, self.today)
        make_assignment(self.agent, self.night, self.today)
        self.client.force_login(manager)
        grid = self.client.get(reverse("shifts_rota_grid"), {
            "department": self.department.pk, "view": "week", "start": "2026-10-12",
        })
        self.assertContains(grid, 'data-count="2"', count=1)
        self.assertContains(grid, "shifts-cell--filled", count=2)
        self.assertContains(grid, '<span class="shifts-moon" aria-hidden="true"></span>', count=1)
        self.assertNotContains(grid, "shifts-split")


class NightWindowRuleTests(TestCase):
    """Night hours run night start to night end; a night shift is more than half night."""

    def setUp(self):
        self.department = make_department("Window")

    def _type(self, name, start, end, mode="auto"):
        row = ShiftType(
            department=self.department, name=name, start_time=start, end_time=end,
            colour="#336699", night_mode=mode,
        )
        row.save()
        return row

    def test_majority_rule(self):
        self.assertFalse(self._type("Late", time(14, 0), time(22, 0)).is_night)  # 4 of 8
        self.assertFalse(self._type("Noon to midnight", time(12, 0), time(0, 0)).is_night)  # 6 of 12
        self.assertFalse(self._type("Midnight to noon", time(0, 0), time(12, 0)).is_night)  # 6 of 12
        self.assertTrue(self._type("Evening", time(18, 0), time(23, 0)).is_night)  # 5 of 5
        self.assertTrue(self._type("Overnight", time(22, 0), time(6, 0)).is_night)  # 8 of 8
        self.assertTrue(self._type("Long night", time(20, 0), time(8, 0)).is_night)  # 10 of 12

    def test_early_morning_counts_as_night(self):
        from shifts.services import interval_for, split_day_night_minutes

        start, end = interval_for(date(2026, 10, 16), time(0, 0), time(12, 0))
        self.assertEqual(split_day_night_minutes(start, end, time(18, 0), time(6, 0)), (360, 360))
        start, end = interval_for(date(2026, 10, 16), time(12, 0), time(0, 0))
        self.assertEqual(split_day_night_minutes(start, end, time(18, 0), time(6, 0)), (360, 360))

    def test_manual_override_changes_the_label_only(self):
        from shifts.services import clipped_day_night_minutes

        always = self._type("Late always", time(14, 0), time(22, 0), mode="always")
        never = self._type("Overnight never", time(22, 0), time(6, 0), mode="never")
        self.assertTrue(always.is_night)
        self.assertFalse(never.is_night)
        user = make_user("window-agent", "support", self.department)
        row = make_assignment(user, never, date(2026, 10, 6))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 8, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (0, 480))

    def test_saving_the_night_window_recomputes_types(self):
        from shifts.models import DepartmentShiftSettings

        manager = make_user(
            "window-lead", "support", self.department, make_role("Window lead", can_manage_shifts=True),
        )
        early = self._type("Early", time(4, 0), time(10, 0))  # 2 of 6 night with a 6 AM end
        self.assertFalse(early.is_night)
        self.client.force_login(manager)
        page = self.client.get(reverse("shifts_types"), {"department": self.department.pk})
        self.assertContains(page, 'id="night-ends"')
        self.assertContains(page, 'value="06:00"')
        self.client.post(reverse("shifts_night_starts"), {
            "department": self.department.pk, "night_starts_at": "18:00", "night_ends_at": "08:00",
        })
        early.refresh_from_db()
        self.assertTrue(early.is_night)  # 4 of 6 night with an 8 AM end
        settings = DepartmentShiftSettings.objects.get(department=self.department)
        self.assertEqual((settings.night_starts_at, settings.night_ends_at), (time(18, 0), time(8, 0)))
        same = self.client.post(reverse("shifts_night_starts"), {
            "department": self.department.pk, "night_starts_at": "18:00", "night_ends_at": "18:00",
        }, HTTP_HX_REQUEST="true")
        self.assertContains(same, "Enter a night start and a night end that differ.")

    def test_type_form_saves_night_mode(self):
        manager = make_user(
            "window-lead2", "support", self.department, make_role("Window lead2", can_manage_shifts=True),
        )
        self.client.force_login(manager)
        self.client.post(reverse("shifts_type_add"), {
            "department": self.department.pk, "name": "Late", "start_time": "14:00",
            "end_time": "22:00", "colour": "#112233", "night_mode": "always",
        })
        row = ShiftType.objects.get(department=self.department, name="Late")
        self.assertEqual(row.night_mode, "always")
        self.assertTrue(row.is_night)
        page = self.client.get(reverse("shifts_types"), {"department": self.department.pk})
        self.assertContains(page, "Set manually")

    def test_no_next_day_badge_when_ending_at_midnight(self):
        # Dates stay before today: a clock ahead of real time trips session expiry.
        agent = make_user("window-agent2", "support", self.department)
        noon = self._type("Noon to midnight", time(12, 0), time(0, 0))
        overnight = self._type("Overnight", time(22, 0), time(6, 0))
        make_assignment(agent, noon, date(2026, 10, 9))
        self.client.force_login(agent)
        with _both_clocks(aware(2026, 10, 9, 9, 0), date(2026, 10, 9)):
            page = self.client.get(reverse("shifts_mine"))
        self.assertNotContains(page, "Next day")
        make_assignment(agent, overnight, date(2026, 10, 10))
        with _both_clocks(aware(2026, 10, 9, 9, 0), date(2026, 10, 9)):
            page = self.client.get(reverse("shifts_mine"))
        self.assertContains(page, "Next day", count=1)
