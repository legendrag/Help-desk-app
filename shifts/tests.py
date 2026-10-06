from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
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

    def test_day_type_crossing_midnight_stays_day_hours(self):
        from shifts.services import clipped_day_night_minutes, clock_length

        department = make_department("Day cross")
        user = make_user("lina", "support", department)
        day_type = make_shift_type(department, name="Days", start=time(9, 0), end=time(17, 0))
        row = make_assignment(user, day_type, date(2026, 10, 6), time(22, 0), time(6, 0))
        start = timezone.make_aware(datetime(2026, 10, 6, 0, 0))
        end = timezone.make_aware(datetime(2026, 10, 8, 0, 0))
        self.assertEqual(clipped_day_night_minutes(row, start, end), (480, 0))
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
        self.assertEqual(response.status_code, 200)
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
        self.assertContains(response, "1 to 12")
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

    def test_one_person_second_night_is_back_to_back(self):
        from shifts.services import suggest_nights

        department = make_department("Solo")
        person = make_user("solo", "support", department)
        night = make_shift_type(department, name="Solo night")
        dates = [date(2026, 10, 5), date(2026, 10, 6)]
        result = suggest_nights([person], dates, night, {person.pk: []})
        self.assertEqual(result[1]["back_to_back"], True)


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
        self.agent = make_user("check-agent", "support", self.department)
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
        manager = make_user("check-panel-lead", "support", self.department, make_role("Panel lead", can_manage_shifts=True))
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
            "shift_type": self.night.pk,
        })
        self.row.refresh_from_db()
        self.assertEqual(self.row.shift_type_id, self.night.pk)
        self.assertIsNone(self.row.checked_in_at)


class TeamRotaTests(TestCase):
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
