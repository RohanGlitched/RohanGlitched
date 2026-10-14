"""Rebuilds the live parts of the profile README.

Draws the hero, the learning curve and the git-log graph, once per GitHub
theme, transparent, in GitHub's own fonts.

Runs daily from .github/workflows/refresh.yml, and locally with:
    python scripts/refresh.py            (set GITHUB_TOKEN to avoid rate limits)
"""
import hashlib
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape

USER = "RohanGlitched"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

CURVE_DAYS = 45
LOG_DAYS = 30

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "dark": dict(fg="#e6edf3", muted="#8b949e", faint="#30363d", accent="#e0805f", cyan="#56d4dd", hash="#d29922",
                 agents="#e0805f", quantum="#a594f9", onchain="#e3b341", main="#6e7681"),
    "light": dict(fg="#1f2328", muted="#59636e", faint="#d1d9e0", accent="#bc4c2a", cyan="#0969da", hash="#9a6700",
                  agents="#bc4c2a", quantum="#5a54c8", onchain="#9a6700", main="#818b98"),
}

# Repo topics that describe the product rather than a tool or technique.
NOT_TECH = set("""hackathon education payments freelance energy music live-music touring recalls disputes chargebacks
evidence alarm-clock smart-home demand-response electricity-prices cross-border-payments streaming-payments index-fund
etf defi rwa tokenized-stocks stablecoin privacy security testing open-source developer-tools smart-display voice
gauge-reading taste-graph config github-config monad-metropolis opencv-ai-competition decoder repetition-code
surface-code minimum-weight-perfect-matching quantum-computing quantum-error-correction""".split())
SAME_AS = {"model-context-protocol": "mcp", "mcp-server": "mcp", "mcp-client": "mcp", "mcp-host": "mcp",
           "nvidia-nemotron": "nemotron", "midnightntwrk": "midnight", "alexa-plus": "alexa",
           "monad-testnet": "monad", "ai-agent": "agents", "agent": "agents"}
# Stack for repos that have no topics yet.
EXTRA_TECH = {"no-signal": ["qiskit", "ionq"], "switched-off": ["arkiv", "vite", "react"],
              "kildespor": ["httpx", "selectolax", "dnspython"]}

TRACK_OF = {"switched-off": "onchain", "no-signal": "quantum", "kildespor": "agents"}
ONCHAIN = {"solana", "monad", "anchor", "solidity", "midnight", "zero-knowledge", "arkiv", "token-2022", "foundry"}
QUANTUM = {"qiskit", "ionq", "quantum-computing", "quantum-error-correction"}

# Commit messages for the git log; new repos fall back to their description.
COMMIT = {
    "kildespor": "tie every company fact to its org number",
    "tell": "measure zero-knowledge privacy leaks in bits",
    "switched-off": "keep india's shutdown orders on the record",
    "no-signal": "play nonlocal games on noisy qubits",
    "below-threshold": "reproduce willow's error-correction result",
    "sheaf": "back index shares with real stocks, in kind",
    "routed": "route tours to where fans already are",
    "dialed": "read analog gauges, escalate to a human",
    "tagout": "check everything you own for recalls",
    "exhibit": "pin every dispute sentence to its proof",
    "countertop": "test mcp servers the way a smart display would",
    "lowtide": "let alexa plan around tonight's power prices",
    "segundo": "stream pay for every second you work",
    "rise-clockin": "bet your friends you'll wake up on time",
}

CSS = """
text{white-space:pre}
.in{animation:in .8s cubic-bezier(.2,.8,.2,1) backwards}
@keyframes in{from{opacity:0;transform:translateY(8px)}}
.draw{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 2.2s cubic-bezier(.6,0,.2,1) .3s backwards}
@keyframes draw{from{stroke-dashoffset:1}}
.ga,.gb{opacity:0;animation:ga 6s steps(1,end) -4.2s infinite}
.gb{animation-name:gb}
.gm{animation:gm 6s steps(1,end) -4.2s infinite}
@keyframes ga{0%,84%{opacity:0;transform:none}85%{opacity:1;transform:translate(-4px,1px)}87%{transform:translate(3px,-1px)}89%{transform:translate(-2px,0)}91%,100%{opacity:0;transform:none}}
@keyframes gb{0%,84%{opacity:0;transform:none}85%{opacity:1;transform:translate(4px,-1px)}87%{transform:translate(-3px,1px)}89%{transform:translate(2px,0)}91%,100%{opacity:0;transform:none}}
@keyframes gm{0%,84%{transform:none}85%{transform:translateX(2px)}87%{transform:translateX(-2px)}89%,100%{transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


# ---------------------------------------------------------------- data

def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def load_repos():
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    out = []
    for r in repos:
        if r["fork"] or r["private"] or r["name"] == USER:
            continue
        tech = {SAME_AS.get(t, t) for t in r["topics"] if t not in NOT_TECH}
        if r["language"]:
            tech.add(r["language"].lower())
        tech |= set(EXTRA_TECH.get(r["name"], []))
        topics = set(r["topics"]) | tech
        track = TRACK_OF.get(r["name"]) or ("onchain" if topics & ONCHAIN else "quantum" if topics & QUANTUM else "agents")
        out.append(dict(name=r["name"], created=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).date(),
                        desc=r["description"] or "", tech=tech, track=track))
    return sorted(out, key=lambda r: r["created"])


# ---------------------------------------------------------------- drawing

def t(x, y, s, size, fill, family=SANS, weight=400, anchor="start", ls=0, extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{escape(s)}</text>')


def svg(w, h, body, label, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}"><title>{escape(label)}</title>'
            f'<defs>{defs}</defs><style>{CSS}</style>{body}</svg>')


def hero(c):
    W, H = 900, 236
    big = f'font-family="{SANS}" font-size="52" font-weight="600" letter-spacing="-1.8"'
    line1 = "I break things."
    defs = ""
    b = [f'<g class="in">' + t(0, 28, "Rohan Borade", 17, c["fg"], weight=600)
         + t(128, 28, "·   AI engineer   ·   Mumbai", 17, c["muted"]) + '</g>',
         f'<g class="in" style="animation-delay:.1s">'
         f'<g class="ga"><text x="-3" y="104" {big} fill="{c["cyan"]}">{line1}</text></g>'
         f'<g class="gb"><text x="-3" y="104" {big} fill="{c["accent"]}">{line1}</text></g>'
         f'<g class="gm"><text x="-3" y="104" {big} fill="{c["fg"]}">{line1}</text></g></g>',
         f'<g class="in" style="animation-delay:.25s"><text x="-3" y="166" {big} fill="{c["fg"]}">'
         f'Then I build agents <tspan fill="{c["accent"]}">that don\'t.</tspan></text></g>']
    motto = [("BREAK IT", c["fg"]), ("  →  ", c["faint"]), ("BUILD IT", c["fg"]), ("  →  ", c["faint"]), ("PROVE IT", c["accent"])]
    spans = "".join(f'<tspan fill="{col}">{escape(s)}</tspan>' for s, col in motto)
    b.append(f'<g class="in" style="animation-delay:.4s"><text x="0" y="218" font-family="{MONO}" font-size="12" '
             f'font-weight="600" letter-spacing="2.5">{spans}</text></g>')
    return svg(W, H, "".join(b), "Rohan Borade, AI engineer, Mumbai. I break things. Then I build agents that don't. Break it, build it, prove it.", defs)


def curve(c, repos, today):
    W, H = 900, 330
    start = today - timedelta(days=CURVE_DAYS)
    known = set().union(*[r["tech"] for r in repos if r["created"] < start]) if repos else set()
    pts, seen = [], set(known)
    for r in repos:
        if r["created"] < start:
            continue
        new = r["tech"] - seen
        seen |= new
        pts.append((r["created"], len(seen) - len(known), len(new), r["name"]))
    total = pts[-1][1] if pts else 0
    first = pts[0][0] if pts else today
    span = max((today - first).days, 1)
    top, base = 118, 286
    ymax = max(10, -(-total // 20) * 20)

    def X(d):
        return 6 + (d - start).days / CURVE_DAYS * (W - 12)

    def Y(v):
        return base - v / ymax * (base - top)

    b = [f'<g class="in">' + t(-2, 58, f"+{total}", 58, c["fg"], weight=600, ls=-2) + '</g>',
         f'<g class="in" style="animation-delay:.1s">'
         + t(0, 88, f"tools and techniques used for the first time in a public repo, in the last {span} days", 15, c["muted"]) + '</g>']
    for v in range(0, ymax + 1, 20):
        b.append(f'<line x1="0" y1="{Y(v) + .5:.1f}" x2="{W}" y2="{Y(v) + .5:.1f}" stroke="{c["faint"]}" '
                 f'stroke-dasharray="{"none" if v == 0 else "2 4"}"/>')
        if v:
            b.append(t(W, Y(v) - 6, str(v), 10, c["muted"], family=MONO, anchor="end"))
    d, area, prev = f"M{X(start):.1f} {Y(0):.1f}", "", 0
    for day, cum, _, _ in pts:
        d += f" H{X(day):.1f} V{Y(cum):.1f}"
    d += f" H{X(today):.1f}"
    area = d + f" V{Y(0):.1f} Z"
    b.append(f'<path d="{area}" fill="{c["accent"]}" fill-opacity=".09" class="in" style="animation-delay:1.2s"/>')
    b.append(f'<path d="{d}" pathLength="1" fill="none" stroke="{c["accent"]}" stroke-width="2.2" stroke-linejoin="round" class="draw"/>')
    big = sorted(pts, key=lambda p: -p[2])[:5]
    for i, (day, cum, new, name) in enumerate(pts):
        delay = .3 + 2.2 * (X(day) / W) ** .8
        b.append(f'<circle cx="{X(day):.1f}" cy="{Y(cum):.1f}" r="3.2" fill="{c["accent"]}" class="in" style="animation-delay:{delay:.2f}s"/>')
        if (day, cum, new, name) in big and new:
            b.append(f'<g class="in" style="animation-delay:{delay + .1:.2f}s">'
                     + t(X(day) - 9, Y(cum) + 4, f"{name} +{new}", 10.5, c["fg"], family=MONO, anchor="end") + '</g>')
    for k in range(0, CURVE_DAYS + 1, 15):
        day = start + timedelta(days=k)
        if (today - day).days < 8:
            continue
        b.append(t(X(day), base + 24, day.strftime("%b %d").upper(), 10, c["muted"], family=MONO,
                   anchor="start" if k == 0 else "middle", ls=1.5))
    b.append(t(W, base + 24, "TODAY", 10, c["accent"], family=MONO, anchor="end", ls=1.5))
    return svg(W, H, "".join(b), f"Learning curve: {total} tools and techniques used for the first time in a public repo in the last {span} days")


def gitlog(c, repos, today):
    rows = [r for r in reversed(repos) if (today - r["created"]).days <= LOG_DAYS and (r["desc"] or r["name"] in COMMIT)]
    lanes = {"agents": 44, "quantum": 68, "onchain": 92}
    main_x, rh, top = 18, 30, 62
    W, H = 900, top + len(rows) * rh + 44
    b = [f'<text x="0" y="22" font-family="{MONO}" font-size="12"><tspan fill="{c["muted"]}">$ </tspan>'
         f'<tspan fill="{c["fg"]}">git log --graph --oneline --since="{LOG_DAYS} days ago"</tspan></text>']
    ys = lambda i: top + i * rh
    end_y = ys(len(rows) - 1) + 18 if rows else top
    b.append(f'<line x1="{main_x}" y1="{top - 22}" x2="{main_x}" y2="{end_y + 10}" stroke="{c["main"]}" stroke-width="2"/>')
    for track, lx in lanes.items():
        idx = [i for i, r in enumerate(rows) if r["track"] == track]
        if not idx:
            continue
        y0, y1 = ys(idx[0]) - 4, ys(idx[-1]) - 4
        col = c[track]
        b.append(f'<path d="M{main_x} {y0 - 22} C{main_x} {y0 - 8} {lx} {y0 - 16} {lx} {y0}" fill="none" stroke="{col}" stroke-width="2" stroke-opacity=".7"/>')
        b.append(f'<line x1="{lx}" y1="{y0}" x2="{lx}" y2="{y1}" stroke="{col}" stroke-width="2" stroke-opacity=".7"/>')
        b.append(f'<path d="M{lx} {y1} C{lx} {y1 + 16} {main_x} {y1 + 8} {main_x} {y1 + 22}" fill="none" stroke="{col}" stroke-width="2" stroke-opacity=".7"/>')
    for i, r in enumerate(rows):
        y = ys(i)
        lx, col = lanes[r["track"]], c[r["track"]]
        sha = hashlib.sha1(f"{USER}/{r['name']}".encode()).hexdigest()[:7]
        msg = COMMIT.get(r["name"]) or re.split(r"[.:;]", r["desc"])[0].strip().lower()
        g = [f'<circle cx="{lx}" cy="{y - 4}" r="5" fill="{col}"/>',
             f'<text x="124" y="{y}" font-family="{MONO}" font-size="12.5">'
             f'<tspan fill="{c["hash"]}">{sha}</tspan>  '
             + (f'<tspan fill="{c["cyan"]}" font-weight="700">(HEAD -&gt; main)</tspan> ' if i == 0 else "")
             + f'<tspan fill="{c["muted"]}">feat(</tspan><tspan fill="{col}" font-weight="700">{escape(r["name"])}</tspan>'
               f'<tspan fill="{c["muted"]}">): </tspan><tspan fill="{c["fg"]}">{escape(msg)}</tspan></text>',
             t(W, y, r["created"].strftime("%b %d"), 11, c["muted"], family=MONO, anchor="end")]
        b.append(f'<g class="in" style="animation-delay:{.15 + i * .07:.2f}s">{"".join(g)}</g>')
    ly = H - 12
    x = 0
    for name, col in (("main", c["main"]), ("agents", c["agents"]), ("quantum", c["quantum"]), ("onchain", c["onchain"])):
        b.append(f'<circle cx="{x + 5}" cy="{ly - 4}" r="4" fill="{col}"/>' + t(x + 15, ly, name, 11, c["muted"], family=MONO))
        x += 15 + len(name) * 7 + 24
    return svg(W, H, "".join(b), f"The last {LOG_DAYS} days as a git log: {len(rows)} projects shipped")


def main():
    today = datetime.now(timezone.utc).date()
    repos = load_repos()
    os.makedirs(ASSETS, exist_ok=True)
    for theme, c in THEMES.items():
        for name, body in (("hero", hero(c)), ("curve", curve(c, repos, today)), ("gitlog", gitlog(c, repos, today))):
            with open(os.path.join(ASSETS, f"{name}-{theme}.svg"), "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
    print(f"refreshed {len(repos)} repos as of {today}")


if __name__ == "__main__":
    main()
