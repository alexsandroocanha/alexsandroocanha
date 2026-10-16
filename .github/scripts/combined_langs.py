import os
from collections import Counter
from xml.sax.saxutils import escape

import requests

TOP = 6
OUT = "profile/top-langs-combined.svg"

COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Python": "#3572A5",
    "Java": "#b07219", "HTML": "#e34c26", "CSS": "#563d7c", "SCSS": "#c6538c",
    "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "PHP": "#4F5D95",
    "Go": "#00ADD8", "Rust": "#dea584", "Kotlin": "#A97BFF", "Shell": "#89e051",
    "Dockerfile": "#384d54", "Vue": "#41b883", "Ruby": "#701516",
}
DEFAULT_COLOR = "#8b949e"


def get_all(url, headers, params=None):
    """Percorre todas as páginas de uma listagem paginada."""
    out, page = [], 1
    while True:
        r = requests.get(
            url,
            headers=headers,
            timeout=30,
            params={**(params or {}), "per_page": 100, "page": page},
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        out += data
        if len(data) < 100:
            break
        page += 1
    return out


langs = Counter()
github_names = set()

# --- GitHub (bytes por linguagem) ---
gh = {"Authorization": f"Bearer {os.environ['STATS_TOKEN']}"}
for repo in get_all("https://api.github.com/user/repos", gh, {"affiliation": "owner"}):
    if repo["fork"]:
        continue
    github_names.add(repo["name"].lower())
    r = requests.get(repo["languages_url"], headers=gh, timeout=30)
    r.raise_for_status()
    langs.update(r.json())

# --- GitLab (% por linguagem, convertido em bytes pelo tamanho do repo) ---
gl = {"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]}
projects = get_all(
    "https://gitlab.com/api/v4/projects",
    gl,
    {"owned": "true", "statistics": "true"},
)
for p in projects:
    if p.get("forked_from_project"):
        continue
    # evita contar duas vezes projetos espelhados nas duas contas
    if p["path"].lower() in github_names:
        continue
    size = (p.get("statistics") or {}).get("repository_size", 0)
    r = requests.get(
        f"https://gitlab.com/api/v4/projects/{p['id']}/languages",
        headers=gl,
        timeout=30,
    )
    r.raise_for_status()
    for name, pct in r.json().items():
        langs[name] += size * pct / 100

# --- Gera o SVG ---
top = langs.most_common(TOP)
total = sum(v for _, v in top) or 1
W, PAD, BAR_W = 400, 20, 360
rows = (len(top) + 1) // 2
H = 90 + rows * 24

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="4.5" fill="#0d1117" stroke="#30363d"/>',
    f'<text x="{PAD}" y="30" font-family="Segoe UI, Ubuntu, sans-serif" font-size="18" '
    f'font-weight="600" fill="#79c0ff">Top Languages (GitHub + GitLab)</text>',
    f'<clipPath id="bar"><rect x="{PAD}" y="48" width="{BAR_W}" height="8" rx="4"/></clipPath>',
    '<g clip-path="url(#bar)">',
]

x = PAD
for name, v in top:
    w = BAR_W * v / total
    parts.append(
        f'<rect x="{x:.2f}" y="48" width="{w:.2f}" height="8" '
        f'fill="{COLORS.get(name, DEFAULT_COLOR)}"/>'
    )
    x += w
parts.append("</g>")

for i, (name, v) in enumerate(top):
    col, row = i % 2, i // 2
    cx = PAD + col * 180
    cy = 82 + row * 24
    color = COLORS.get(name, DEFAULT_COLOR)
    parts.append(f'<circle cx="{cx+5}" cy="{cy-4}" r="5" fill="{color}"/>')
    parts.append(
        f'<text x="{cx+16}" y="{cy}" font-family="Segoe UI, Ubuntu, sans-serif" '
        f'font-size="12" fill="#c9d1d9">{escape(name)} '
        f'<tspan fill="#8b949e">{v/total*100:.1f}%</tspan></text>'
    )

parts.append("</svg>")

os.makedirs("profile", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(parts))

print(f"Gerado {OUT} com {len(top)} linguagens.")
