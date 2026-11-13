"""Render minimal profile stats SVGs from the GitHub GraphQL API."""
import json, os, sys, urllib.request
from collections import Counter
from datetime import date

USER = os.environ.get("GH_USER", "Ahsan221B")
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
ACCENT, MUTED, TEXT = "#FF6A1A", "#8b949e", "#8b949e"
FONT = "font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif"

Q = """query($u:String!){ user(login:$u){
  createdAt followers{totalCount}
  repositories(first:100, ownerAffiliations:OWNER, isFork:false){ totalCount nodes{
    stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{size node{name color}} } } }
  contributionsCollection{ totalCommitContributions restrictedContributionsCount
    totalPullRequestContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date } } } } } }"""

def fetch():
    if os.environ.get("FAKE"):
        return json.load(open(os.environ["FAKE"]))
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": Q, "variables": {"u": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"})
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data: sys.exit(data["errors"])
    return data["data"]["user"]

def streaks(days):
    cur = best = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        best = max(best, run)
    for d in reversed(days):
        if d["contributionCount"]: cur += 1
        elif d["date"] != date.today().isoformat(): break
    return cur, best

def stats_svg(u):
    c = u["contributionsCollection"]
    days = [d for w in c["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days)
    items = [
        (f'{c["contributionCalendar"]["totalContributions"]:,}', "contributions"),
        (f'{c["totalCommitContributions"] + c["restrictedContributionsCount"]:,}', "commits"),
        (f"{cur}", "current streak"), (f"{best}", "best streak"),
    ]
    w, cell = 480, 120
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="80" viewBox="0 0 {w} 80" style="{FONT}">']
    for i, (n, label) in enumerate(items):
        x = i * cell + cell / 2
        parts.append(f'<text x="{x}" y="36" text-anchor="middle" font-size="24" font-weight="600" fill="{ACCENT}">{n}</text>')
        parts.append(f'<text x="{x}" y="60" text-anchor="middle" font-size="11" fill="{MUTED}">{label}</text>')
    parts.append("</svg>")
    return "".join(parts)

def langs_svg(u):
    size, color = Counter(), {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            size[e["node"]["name"]] += e["size"]; color[e["node"]["name"]] = e["node"]["color"] or MUTED
    top = size.most_common(6); total = sum(s for _, s in top) or 1
    w = 480; x = 0
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="80" viewBox="0 0 {w} 80" style="{FONT}">',
             f'<clipPath id="r"><rect width="{w}" height="8" rx="4"/></clipPath><g clip-path="url(#r)">']
    for name, s in top:
        bw = w * s / total
        parts.append(f'<rect x="{x:.1f}" width="{bw:.1f}" height="8" fill="{color[name]}"/>'); x += bw
    parts.append("</g>")
    for i, (name, s) in enumerate(top):
        cx, cy = (i % 3) * 160, 36 + (i // 3) * 24
        parts.append(f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{color[name]}"/>')
        parts.append(f'<text x="{cx+16}" y="{cy}" font-size="12" fill="{TEXT}">{name} <tspan fill="{MUTED}" opacity=".7">{100*s/total:.0f}%</tspan></text>')
    parts.append("</svg>")
    return "".join(parts)

def heatmap_svg(u):
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    mx = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1) or 1
    s, g = 11, 3; W = len(weeks) * (s + g); H = 7 * (s + g)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    for i, wk in enumerate(weeks):
        for d in wk["contributionDays"]:
            j = date.fromisoformat(d["date"]).isoweekday() % 7; n = d["contributionCount"]
            op = 0.12 if n == 0 else 0.3 + 0.7 * min(1, n / mx) ** 0.6
            fill = MUTED if n == 0 else ACCENT
            parts.append(f'<rect x="{i*(s+g)}" y="{j*(s+g)}" width="{s}" height="{s}" rx="2" fill="{fill}" fill-opacity="{op:.2f}"><title>{d["date"]}: {n}</title></rect>')
    parts.append("</svg>")
    return "".join(parts)

u = fetch(); os.makedirs(OUT, exist_ok=True)
for name, fn in [("stats", stats_svg), ("languages", langs_svg), ("contributions", heatmap_svg)]:
    open(f"{OUT}/{name}.svg", "w").write(fn(u))
