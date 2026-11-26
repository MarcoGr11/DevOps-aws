"""Виконує команди кожного кадру наживо і зберігає їхній реальний вивід як PNG у reports/screens/.

Запуск (LocalStack має працювати): .venv/bin/python reports/make_screens.py
Увага: на початку викликає ./destroy.sh, щоб кадр 8-03 показав розгортання з нуля.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "screens"
FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 26)
BOLD = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 26, index=1)
BG, FG, PROMPT = (30, 30, 36), (220, 220, 220), (130, 200, 255)
COLORS = {"31": (240, 100, 100), "32": (110, 210, 120), "33": (230, 200, 90), "34": (110, 160, 255)}
WRAP = 140
ANSI = re.compile(r"\x1b\[([0-9;]*)m")

ENV = {
    **os.environ,
    "PATH": f"{ROOT / '.venv/bin'}:{os.environ['PATH']}",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_PAGER": "",
    "DISABLE_DEPRECATION_NOTICE": "1",  # awslocal 0.23 друкує банер про перехід на lstk
    "CT": "Content-Type: application/json",
}

BOOKING = '{"user":"olena","room":"A-101","date":"2026-12-01","slot":"10:00-12:00"}'
BOOKING2 = '{"user":"taras","room":"B-202","date":"2026-12-02","slot":"14:00-16:00"}'
TREE_IGNORE = ".venv|.idea|.git|__pycache__|.pytest_cache|.ruff_cache|main.py|screens|*.pdf"

FRAMES = [
    (
        "8-01-localstack-health",
        [
            "docker ps --filter name=localstack"
            " --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'",
            "curl -s localhost:4566/_localstack/health | jq '{version, edition, services: (.services"
            " | {lambda, apigateway, dynamodb, iam, logs, cloudwatch})}'",
        ],
    ),
    (
        "8-02-project-structure",
        [
            f"tree -a -I '{TREE_IGNORE}' --dirsfirst",
            "sed -n '/^def lambda_handler/,$p' lambda/handler.py",
        ],
    ),
    ("8-03-deploy", ["./deploy.sh"]),
    (
        "8-04-resources",
        [
            "awslocal dynamodb list-tables",
            "awslocal lambda list-functions --query 'Functions[].{Name:FunctionName,Runtime:Runtime,"
            "Handler:Handler,Env:Environment.Variables}'",
            "awslocal apigateway get-rest-apis --query 'items[].{id:id,name:name,created:createdDate}'",
            "awslocal apigateway get-resources --rest-api-id $(cut -d/ -f3 .api-url | cut -d. -f1)"
            " --query 'items[].{path:path,methods:keys(resourceMethods||`{}`)}' --output text",
        ],
    ),
    (
        "8-05-post-booking",
        [
            'API=$(cat .api-url); CT="Content-Type: application/json"; echo "$API"',
            f'curl -si -X POST "$API/bookings" -H "$CT" -d \'{BOOKING}\'',
        ],
    ),
    ("8-06-get-booking", ['curl -si "$API/bookings/$ID"']),
    (
        "8-07-list-bookings",
        [
            f'curl -s -X POST "$API/bookings" -H "$CT" -d \'{BOOKING2}\' | jq -c .',
            'curl -s "$API/bookings" | jq .',
        ],
    ),
    ("8-08-dynamodb-scan", ["awslocal dynamodb scan --table-name bookings"]),
    (
        "8-09-delete-then-404",
        [
            'curl -si -X DELETE "$API/bookings/$ID"',
            'curl -si "$API/bookings/$ID"',
        ],
    ),
    ("8-10-smoke-test", ['./smoke-test.sh; echo "exit code: $?"']),
    ("8-11-pytest-ruff", ["pytest -v", "ruff check . && ruff format --check ."]),
    ("8-12-deploy-idempotent", ["./deploy.sh"]),
    (
        "8-13-bad-request-400",
        [
            'curl -si -X POST "$API/bookings" -H "$CT" -d \'{"user": "olena", broken\'',
            'curl -s -X POST "$API/bookings" -H "$CT" -d \'{"user":"","room":"A-101",'
            '"date":"2026-02-30","slot":"12:00-10:00"}\' | jq .',
        ],
    ),
]


def run(cmd, env):
    res = subprocess.run(["bash", "-c", cmd], cwd=ROOT, env=env, capture_output=True, text=True)
    return (res.stdout + res.stderr).replace("\r", "").rstrip("\n")


def spans(line):
    """Розбиває рядок з ANSI-кольорами на [(текст, колір, жирний)]."""
    out, color, bold, pos = [], FG, False, 0
    for m in ANSI.finditer(line):
        if m.start() > pos:
            out.append((line[pos : m.start()], color, bold))
        for code in (m.group(1) or "0").split(";"):
            if code in ("0", ""):
                color, bold = FG, False
            elif code == "1":
                bold = True
            elif code in COLORS:
                color = COLORS[code]
        pos = m.end()
    out.append((line[pos:], color, bold))
    return out


def wrap(spanlist):
    rows, row, width = [], [], 0
    for text, color, bold in spanlist:
        while text:
            take = WRAP - width
            row.append((text[:take], color, bold))
            width += len(text[:take])
            text = text[take:]
            if width >= WRAP:
                rows.append(row)
                row, width = [], 0
    rows.append(row)
    return rows


def render(name, blocks):
    rows = []
    for cmd, output in blocks:
        rows += wrap([("$ ", PROMPT, True), (cmd, PROMPT, True)])
        for line in output.splitlines():
            rows += wrap(spans(line.expandtabs(4)))
        rows.append([])
    rows.pop()
    cw, lh, pad = FONT.getbbox("M")[2], 34, 28
    cols = max((sum(len(t) for t, _, _ in r) for r in rows), default=1)
    img = Image.new("RGB", (cols * cw + 2 * pad, len(rows) * lh + 2 * pad + 40), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 40], fill=(55, 55, 62))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([16 + i * 28, 12, 32 + i * 28, 28], fill=c)
    d.text((img.width // 2, 20), "zsh — DevOps-aws", font=FONT, fill=(190, 190, 190), anchor="mm")
    y = 40 + pad
    for r in rows:
        x = pad
        for text, color, bold in r:
            d.text((x, y), text, font=BOLD if bold else FONT, fill=color)
            x += len(text) * cw
        y += lh
    img.save(OUT / f"{name}.png", optimize=True)
    print(f"saved {name}.png ({img.width}x{img.height})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run("./destroy.sh", ENV)
    env = dict(ENV)
    for name, cmds in FRAMES:
        blocks = []
        for cmd in cmds:
            out = run(cmd, env)
            blocks.append((cmd, out))
            if cmd.startswith("API="):
                env["API"] = out.strip()
        if name == "8-05-post-booking":
            env["ID"] = json.loads(blocks[-1][1].splitlines()[-1])["id"]
        render(name, blocks)


if __name__ == "__main__":
    main()
