from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Department, Role
from shifts.models import ShiftAssignment, ShiftType

User = get_user_model()


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
