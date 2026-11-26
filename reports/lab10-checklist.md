# Лаба 10 — чекліст кадрів і вимог

Усі кадри `reports/screens/10-*.png` — реальні знімки екрана (`screencapture`) панелі
терміналу під час живого виконання команд; 10-13 — сторінка GitHub у браузері (лише вміст
сторінки). Кадри 10-01…10-11 і графіки `reports/graphs/*.png` — з одного прогону
`scripts/lab10/experiment.sh full` 26.11.2026 07:49–08:06 (журнал `reports/lab10-run.log`).
Кадри 10-05…10-09 обрізано лише по висоті (прибрано рядки зверху: розігрів у 10-05, однакові рядки стану в 10-06…10-09), вміст не змінено.
PDF: `.venv/bin/python reports/build_report.py 10` → `reports/lab10-cloudwatch.pdf`.

Вимоги методички:
1 — доступ до CloudWatch API;
2 — збір кількості запитів, помилок і тривалості;
3 — публікація метрик (PutMetricData);
4 — отримання метрик (GetMetricStatistics / GetMetricData);
5 — запити за інтервал, частка помилок, середній час відповіді;
6 — alarm на перевищення порогу;
7 — керована генерація навантаження;
8 — штучні помилки/затримка і перехід alarm у ALARM;
9 — графіки;
10 — висновки.

| Кадр / файл | Що видно | Вимоги |
|---|---|---|
| `10-01` | `compose ps`: app1–3, nginx, localstack — healthy; `cw-check.sh`: 12 метрик namespace Bookings (3 метрики × агрегат + 3 InstanceId) | 1, 2 |
| `10-02` | `app/server.py`: `metric_data()` (RequestCount/ErrorCount/Latency, Count/Milliseconds, два набори вимірів), `MetricsPublisher` (черга, пакети по 20, `put_metric_data`, помилки в журнал) | 2, 3 |
| `10-03` | `aws cloudwatch list-metrics --namespace Bookings`: 12 рядів | 1, 3 |
| `10-04` | підсумок loadgen фази 1 (240 запитів, 80/80/80, 0 помилок) і `stats.py`: 120 + 120 запитів, сер. 8,5 мс; GetMetricData за InstanceId | 4, 5, 7 |
| `10-05` | фаза 0: `alarms.sh` (SNS → SQS, 2 alarm), `describe-alarms`: обидва OK | 6 |
| `10-06` | фаза 3: `curl POST localhost:8102/admin/chaos {"fail_rate": 0.5}` і loadgen — 22 помилки 5xx за 60 с | 7, 8 |
| `10-07` | `alarm-watch.sh --watch 5`: bookings-high-errors OK → ALARM о 07:56:15, StateReason і точки 0, 5, 22 | 6, 8 |
| `10-08` | bookings-high-latency OK → ALARM о 07:59:15, точки 7,1 / 104,8 / 413,5 мс | 6, 8 |
| `10-09` | відновлення: high-errors уже OK (перехід о 08:01:15 — на кадрі 10-10), high-latency ALARM → OK о 08:04:15, далі обидва OK | 6, 8 |
| `10-10` | сирий `describe-alarm-history` (видно неточний Timestamp LocalStack), розібрана історія 6 переходів з `queryDate`, ті самі 6 сповіщень у черзі SQS | 6 |
| `10-11` | `stats.py --phases --instances`: 15 хвилин, по фазах (240/720/360/359/601 запитів, 65 помилок = 18,1% у фазі 3, 413,9 мс у фазі 4), реакція alarm +75 с / +195 с, 760/760/760 за InstanceId | 4, 5 |
| `10-12` | `make test`: 35 passed (16 лаби 8, 5 адаптера, 9 метрик і chaos, 5 формул stats.py), ruff — All checks passed | 2, 3, 5 |
| `10-13` | GitHub: коміти лаби 10 | — |
| `graphs/lab10-requests.png` | запити за хвилину, смуги фаз | 9 |
| `graphs/lab10-errors.png` | помилки за хвилину з порогом 10 і смугою ALARM; частка помилок, % | 9 |
| `graphs/lab10-latency.png` | Average і Maximum Latency з порогом 200 мс і смугою ALARM | 9 |
| `graphs/lab10-instances.png` | запити й помилки за InstanceId: помилки лише в instance-2 | 9 |
| PDF, розділ «Висновки» | продуктивність, стабільність, час реакції alarm, обмеження LocalStack | 10 |

Документація: `LAB10.md` (архітектура, метрики, формули, alarms, фази, результати,
обмеження LocalStack), `DEFENSE-LAB10.md`, PDF-звіт.
