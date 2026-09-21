from openpyxl import load_workbook
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from statistics import mean
import json
import math

path = r"c:\Users\Omar-Laptop\Downloads\ticket_export.xlsx"
wb = load_workbook(path, read_only=True, data_only=True)


def sheet_rows(name):
    ws = wb[name]
    rows = ws.iter_rows(values_only=True)
    header = [str(h) if h is not None else "" for h in next(rows)]
    out = []
    for row in rows:
        d = {}
        for i, h in enumerate(header):
            d[h] = row[i] if i < len(row) else None
        out.append(d)
    return out


def parse_dt(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def secs(v):
    if v is None or v == "":
        return None
    try:
        n = float(v)
        return n if n >= 0 else None
    except Exception:
        return None


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def hours(s):
    return None if s is None else round(s / 3600, 2)


def mins(s):
    return None if s is None else round(s / 60, 1)


users = {
    str(r["user_id"]): f"{(r.get('first_name') or '').strip()} {(r.get('last_name') or '').strip()}".strip()
    or str(r["user_id"])
    for r in sheet_rows("Users")
}
users["1544806"] = "Unknown (deleted user)"
users["None"] = "Unassigned"
cats = {str(r["ticket_category_id"]): r.get("name") for r in sheet_rows("Ticket Categories")}

tca = sheet_rows("Tickets to Custom Attributes")
ticket_branch = {}
for r in tca:
    tid = str(r["ticket_id"])
    aid = str(r["custom_attribute_id"])
    if aid == "769108":
        ticket_branch[tid] = (r.get("value") or "").strip() or "Unspecified"

tickets = sheet_rows("Tickets")
now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
egypt = timezone(timedelta(hours=3))

print("NON_CLOSED")
for t in tickets:
    if str(t.get("status")) != "Closed":
        tid = str(t["ticket_id"])
        print(
            json.dumps(
                {
                    "number": t.get("ticket_number"),
                    "status": t.get("status"),
                    "summary": t.get("summary"),
                    "assignee": users.get(str(t.get("assignee_id")), str(t.get("assignee_id"))),
                    "category": cats.get(str(t.get("ticket_category_id"))),
                    "branch": ticket_branch.get(tid),
                    "created": t.get("created_at"),
                    "updated": t.get("updated_at"),
                    "priority": t.get("priority"),
                },
                ensure_ascii=False,
            )
        )

frs = [x for x in (secs(t.get("first_response_secs")) for t in tickets) if x is not None]
cts = [x for x in (secs(t.get("close_time_secs")) for t in tickets) if x is not None]
print("FR_N", len(frs), "CT_N", len(cts))
print(
    "FR_MED_MIN",
    mins(pct(frs, 50)),
    "FR_P90_MIN",
    mins(pct(frs, 90)),
    "FR_MEAN_MIN",
    mins(mean(frs)),
    "FR_P95",
    mins(pct(frs, 95)),
)
print(
    "CT_MED_H",
    hours(pct(cts, 50)),
    "CT_P90_H",
    hours(pct(cts, 90)),
    "CT_MEAN_H",
    hours(mean(cts)),
    "CT_P95_H",
    hours(pct(cts, 95)),
)


def bucket_fr(s):
    m = s / 60
    if m <= 15:
        return "<=15m"
    if m <= 60:
        return "15-60m"
    if m <= 240:
        return "1-4h"
    if m <= 1440:
        return "4-24h"
    return ">24h"


print("FR_BUCKETS", Counter(bucket_fr(x) for x in frs))


def bucket_ct(s):
    h = s / 3600
    if h <= 1:
        return "<=1h"
    if h <= 4:
        return "1-4h"
    if h <= 24:
        return "4-24h"
    if h <= 72:
        return "1-3d"
    if h <= 168:
        return "3-7d"
    return ">7d"


print("CT_BUCKETS", Counter(bucket_ct(x) for x in cts))

created_m = Counter()
closed_m = Counter()
hour_of_day = Counter()
weekday_eg = Counter()
for t in tickets:
    c = parse_dt(t.get("created_at"))
    if c:
        created_m[c.strftime("%Y-%m")] += 1
        local = c.astimezone(egypt)
        hour_of_day[local.hour] += 1
        weekday_eg[local.strftime("%A")] += 1
    cl = parse_dt(t.get("last_closed_at"))
    if cl:
        closed_m[cl.strftime("%Y-%m")] += 1

print("CREATED_M", dict(sorted(created_m.items())))
print("CLOSED_M", dict(sorted(closed_m.items())))
print("WEEKDAY_EG", dict(weekday_eg))
print("HOUR_EG", dict(sorted(hour_of_day.items())))

branches = Counter(ticket_branch.get(str(t["ticket_id"]), "Unspecified") for t in tickets)
print("N_WITH_BRANCH", sum(1 for t in tickets if str(t["ticket_id"]) in ticket_branch))
print("BRANCHES", json.dumps(branches.most_common(), ensure_ascii=False))

labors = sheet_rows("Labors")
labor_by_user = defaultdict(lambda: {"min": 0, "n": 0})
for r in labors:
    uid = str(r.get("user_id"))
    name = users.get(uid, uid)
    dur = float(r.get("duration") or 0)
    labor_by_user[name]["min"] += dur
    labor_by_user[name]["n"] += 1
print("LABOR_BY_USER", json.dumps(labor_by_user, ensure_ascii=False))
print("TICKETS_WITH_LABOR", len(set(str(r["ticket_id"]) for r in labors)))

cutoff90 = now - timedelta(days=90)
cutoff30 = now - timedelta(days=30)
n90 = sum(1 for t in tickets if parse_dt(t.get("created_at")) and parse_dt(t.get("created_at")) >= cutoff90)
n30 = sum(1 for t in tickets if parse_dt(t.get("created_at")) and parse_dt(t.get("created_at")) >= cutoff30)
print("LAST30", n30, "LAST90", n90)

fr_assignee = defaultdict(list)
ct_assignee = defaultdict(list)
vol_assignee = Counter()
for t in tickets:
    name = users.get(str(t.get("assignee_id")), str(t.get("assignee_id")))
    vol_assignee[name] += 1
    fr = secs(t.get("first_response_secs"))
    if fr is not None:
        fr_assignee[name].append(fr)
    ct = secs(t.get("close_time_secs"))
    if ct is not None:
        ct_assignee[name].append(ct)
print("ASSIGNEE_SLA")
for name, n in vol_assignee.most_common():
    print(
        name,
        n,
        "fr_med_min",
        mins(pct(fr_assignee[name], 50)),
        "ct_med_h",
        hours(pct(ct_assignee[name], 50)),
        "fr_n",
        len(fr_assignee[name]),
    )

print("CAT_VOL_SLA")
cat_vol = Counter()
cat_fr = defaultdict(list)
cat_ct = defaultdict(list)
for t in tickets:
    cname = cats.get(str(t.get("ticket_category_id")), "Uncategorized") or "Uncategorized"
    cat_vol[cname] += 1
    fr = secs(t.get("first_response_secs"))
    if fr is not None:
        cat_fr[cname].append(fr)
    ct = secs(t.get("close_time_secs"))
    if ct is not None:
        ct_ct = ct
        cat_ct[cname].append(ct)
for name, n in cat_vol.most_common():
    print(name, n, "fr_med_min", mins(pct(cat_fr[name], 50)), "ct_med_h", hours(pct(cat_ct[name], 50)))

print("N_WITH_MASTER", sum(1 for t in tickets if t.get("master_ticket_number")))

print("PRI_SLA")
for pri in ["1", "2"]:
    subset = [t for t in tickets if str(t.get("priority")) == pri]
    fr = [x for x in (secs(t.get("first_response_secs")) for t in subset) if x is not None]
    ct = [x for x in (secs(t.get("close_time_secs")) for t in subset) if x is not None]
    print("pri", pri, "n", len(subset), "fr_med_min", mins(pct(fr, 50)), "ct_med_h", hours(pct(ct, 50)))

weeks = Counter()
for t in tickets:
    c = parse_dt(t.get("created_at"))
    if c:
        local = c.astimezone(egypt)
        iso = local.isocalendar()
        weeks[f"{iso.year}-W{iso.week:02d}"] += 1
print("WEEKS", dict(sorted(weeks.items())[-16:]))

print("NO_FR", sum(1 for t in tickets if secs(t.get("first_response_secs")) is None))
print("NO_CT", sum(1 for t in tickets if secs(t.get("close_time_secs")) is None))
print("NO_ASSIGNEE", sum(1 for t in tickets if not t.get("assignee_id")))
print(
    "NO_BRANCH",
    sum(1 for t in tickets if str(t["ticket_id"]) not in ticket_branch or not ticket_branch.get(str(t["ticket_id"]))),
)

same_day = 0
ncl = 0
for t in tickets:
    c = parse_dt(t.get("created_at"))
    cl = parse_dt(t.get("last_closed_at"))
    if c and cl:
        ncl += 1
        if c.astimezone(egypt).date() == cl.astimezone(egypt).date():
            same_day += 1
print("SAME_DAY_CLOSE", same_day, "of", ncl, round(100 * same_day / ncl, 1) if ncl else None)

cutoff7 = now - timedelta(days=7)
n7 = [t for t in tickets if parse_dt(t.get("created_at")) and parse_dt(t.get("created_at")) >= cutoff7]
print("LAST7", len(n7))
for t in n7:
    print(
        t.get("ticket_number"),
        t.get("created_at"),
        t.get("status"),
        cats.get(str(t.get("ticket_category_id"))),
        users.get(str(t.get("assignee_id"))),
    )

# last 90 days monthly vs prior
# assignee last 30
print("ASSIGNEE_30")
for t in tickets:
    pass
a30 = Counter()
c30 = Counter()
for t in tickets:
    c = parse_dt(t.get("created_at"))
    if c and c >= cutoff30:
        a30[users.get(str(t.get("assignee_id")), str(t.get("assignee_id")))] += 1
        c30[cats.get(str(t.get("ticket_category_id")), "Uncategorized")] += 1
print(dict(a30))
print("CAT_30", dict(c30.most_common()))

# top branches last 30
b30 = Counter()
for t in tickets:
    c = parse_dt(t.get("created_at"))
    if c and c >= cutoff30:
        b30[ticket_branch.get(str(t["ticket_id"]), "Unspecified")] += 1
print("BRANCH_30", json.dumps(b30.most_common(), ensure_ascii=False))

# category grouping: POS/retail vs hardware vs people
print("DONE")
