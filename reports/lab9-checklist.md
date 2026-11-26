# Лаба 9 — чекліст кадрів

Усі кадри `reports/screens/9-*.png` — реальні знімки екрана (`screencapture`), зроблені під
час живого виконання команд: термінал — 9-01…9-12; браузер (лише вміст сторінки) — 9-13.
PDF-звіт: `.venv/bin/python reports/build_report.py 9` → `reports/lab9-loadbalancing.pdf`.

Вимоги методички:
1 — контейнеризована версія застосунку з лаби 8;
2 — щонайменше 3 екземпляри, кожен повертає власний ідентифікатор;
3 — балансувальник для маршрутизації запитів;
4 — endpoint `/health`;
5 — серія HTTP-запитів і розподіл між екземплярами;
6 — вивести один екземпляр з роботи і перевірити поведінку балансувальника;
7 — відновити екземпляр і перевірити, що він знову обробляє запити;
8 — порівняти систему з балансуванням і без.

| Кадр | Що видно | Вимоги |
|---|---|---|
| `9-01` | `tree`: нові `app/`, `nginx/`, `scripts/lab9/`, `docker-compose.lab9.yml`; `app/Dockerfile`: `python:3.12-slim`, `COPY lambda/handler.py`, користувач `app` (uid 10001), `HEALTHCHECK` на `/health` | 1, 4 |
| `9-02` | `config --services`: localstack, init-table, app1–3, nginx; `nginx.conf`: upstream з 3 серверів `max_fails=2 fail_timeout=5s`, `/nginx-health`, `proxy_connect_timeout 1s`, `proxy_next_upstream` | 3 |
| `9-03` | `up -d --wait` і `ps`: app1–3 (один образ `bookings-app:lab9`), nginx, localstack — healthy; init-table — `Exited (0)` | 1, 2 |
| `9-04` | 6 × `GET /health` через `:8080`: 200, `X-Instance-Id` і `instance` у тілі чергуються 1→2→3→1→2→3 | 2, 3, 4 |
| `9-05` | `load.sh 30`: розподіл 10/10/10, 30/30 = 100%; 3 POST обробили instance-1/2/3, `GET /bookings` → `count=3` | 5 |
| `9-06` | POST обробив instance-2 (201), той самий id прочитали instance-3 і instance-1 (200) — спільна БД | 5 |
| `9-07` | `stop app2` і `ps`: app2 — `Exited (0)`, решта healthy | 6 |
| `9-08` | `load.sh 30` при зупиненому app2: 30/30 = 100%, лише instance-1 (14) і instance-3 (16), макс. 1,025 с | 6 |
| `9-09` | `start app2`, через 7 с `ps`: app2 healthy | 7 |
| `9-10` | `load.sh 30` після відновлення: знову 10/10/10, 30/30 = 100% | 7 |
| `9-11` | `compare.sh`: з LB 3/3 і 2/3 — 100%; без LB 1/1 — 100%, 0/1 — 0% (30/30 помилок) | 8 |
| `9-12` | `make test`: 21 passed (16 лаби 8 + 5 адаптера), ruff — All checks passed | 1 |
| `9-13` | GitHub: коміти лаби 9 (адаптер, балансувальник, скрипти, документація) поверх лаби 8 | — |

Документація: `LAB9.md` (архітектура, nginx.conf по директивах, запуск, failover, таблиця
порівняння, обмеження), `DEFENSE-LAB9.md`, PDF-звіт.
