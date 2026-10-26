"""Write assets/streak.svg from the GitHub contribution calendar.

Runs in GitHub Actions (see .github/workflows/profile-assets.yml).
Needs GITHUB_TOKEN and GH_USER in the environment. No third-party packages.
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG_START = date(2026, 10, 26)  # day 1 of the 365 Build Log
OUT = Path(__file__).resolve().parent.parent / "assets" / "streak.svg"

SANS = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "'Cascadia Code', Consolas, 'DejaVu Sans Mono', monospace"
BG, PANEL, LINE = "#0b1411", "#101c18", "#1f2e29"
INK, MUTED, DIM = "#eef3f1", "#a3b5ad", "#6e857b"
ORANGE, GREEN = "#f97316", "#3fb950"

QUERY = """query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){ createdAt
    contributionsCollection(from:$from,to:$to){
      contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }"""


def gql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]


def fetch_days(login, today):
    """{date: count} for every day since the account was created."""
    first = gql({"login": login, "from": f"{today.year}-01-01T00:00:00Z", "to": f"{today}T23:59:59Z"})
    start_year = int(first["createdAt"][:4])
    days = {}
    for year in range(start_year, today.year + 1):
        to = f"{today}T23:59:59Z" if year == today.year else f"{year}-12-31T23:59:59Z"
        user = first if year == today.year else gql({"login": login, "from": f"{year}-01-01T00:00:00Z", "to": to})
        for w in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[date.fromisoformat(d["date"])] = d["contributionCount"]
    return days


def stats(days, today):
    total = sum(days.values())
    # current streak: today may still be open, so start from yesterday if today is 0
    d = today if days.get(today, 0) else today - timedelta(days=1)
    cur, cur_end = 0, d
    while days.get(d, 0):
        cur += 1
        d -= timedelta(days=1)
    cur_start = d + timedelta(days=1)
    best = run = 0
    best_range = None
    for day in sorted(days):
        run = run + 1 if days[day] else 0
        if run > best:
            best, best_range = run, (day - timedelta(days=run - 1), day)
    log_day = max(1, min(365, (today - LOG_START).days + 1))
    log_active = sum(1 for k, v in days.items() if v and LOG_START <= k <= today)
    return dict(total=total, cur=cur, cur_range=(cur_start, cur_end) if cur else None,
                best=best, best_range=best_range, log_day=log_day, log_active=log_active)


def fmt(d):
    return f"{d:%b} {d.day}, {d.year}"


def render(s):
    W, H = 1200, 250
    rng = lambda r: f"{fmt(r[0])} – {fmt(r[1])}" if r else "Start today"
    pct = s["log_day"] / 365
    bar_w = W - 96
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Current streak {s['cur']} days, longest {s['best']} days, {s['total']} total contributions">
<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" fill="{PANEL}" stroke="{LINE}"/>
<g font-family="{SANS}" text-anchor="middle">
  <text x="200" y="92" font-size="44" font-weight="700" fill="{INK}">{s['total']:,}</text>
  <text x="200" y="122" font-size="15" fill="{MUTED}">Total contributions</text>
  <text x="200" y="144" font-family="{MONO}" font-size="12" fill="{DIM}">all time</text>

  <circle cx="600" cy="80" r="56" fill="none" stroke="{LINE}" stroke-width="8"/>
  <circle cx="600" cy="80" r="56" fill="none" stroke="{ORANGE}" stroke-width="8" stroke-linecap="round"
          stroke-dasharray="{min(s['cur'], 365) / 365 * 351.9:.1f} 351.9" transform="rotate(-90 600 80)"/>
  <text x="600" y="96" font-size="46" font-weight="700" fill="{ORANGE}">{s['cur']}</text>
  <text x="600" y="164" font-size="15" font-weight="600" fill="{INK}">Current streak</text>
  <text x="600" y="184" font-family="{MONO}" font-size="12" fill="{DIM}">{rng(s['cur_range'])}</text>

  <text x="1000" y="92" font-size="44" font-weight="700" fill="{INK}">{s['best']}</text>
  <text x="1000" y="122" font-size="15" fill="{MUTED}">Longest streak</text>
  <text x="1000" y="144" font-family="{MONO}" font-size="12" fill="{DIM}">{rng(s['best_range'])}</text>
</g>
<line x1="400" y1="40" x2="400" y2="150" stroke="{LINE}"/><line x1="800" y1="40" x2="800" y2="150" stroke="{LINE}"/>
<text x="48" y="214" font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{ORANGE}">365 BUILD LOG</text>
<text x="{W-48}" y="214" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">day {s['log_day']} / 365 · {s['log_active']} active day{'' if s['log_active'] == 1 else 's'}</text>
<rect x="48" y="224" width="{bar_w}" height="6" rx="3" fill="{LINE}"/>
<rect x="48" y="224" width="{max(6, bar_w * pct):.0f}" height="6" rx="3" fill="{GREEN}"/>
</svg>'''


if __name__ == "__main__":
    today = datetime.now(timezone.utc).date()
    s = stats(fetch_days(os.environ["GH_USER"], today), today)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(s), encoding="utf-8")
    print(s)
