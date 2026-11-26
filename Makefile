VENV ?= .venv
BIN  := $(VENV)/bin

.PHONY: venv up down deploy smoke test destroy lab9-up lab9-down lab9-load lab9-failover lab9-compare \
        lab10-up lab10-down lab10-alarms lab10-quick lab10-experiment lab10-stats

venv:            ## dev-залежності (pytest, ruff, awslocal, reportlab, matplotlib)
	python3 -m venv $(VENV) && $(BIN)/pip install -q -r requirements-dev.txt

up:              ## запустити LocalStack і дочекатися healthcheck
	docker compose up -d --wait

down:            ## зупинити LocalStack
	docker compose down

deploy:          ## розгорнути/оновити DynamoDB + Lambda + API Gateway
	./deploy.sh

smoke:           ## перевірити живий API через curl
	./smoke-test.sh

test:            ## юніт-тести і лінтер
	$(BIN)/pytest -q
	$(BIN)/ruff check .

destroy:         ## видалити ресурси з LocalStack
	./destroy.sh

# --- лаба 9: nginx + 3 екземпляри (окремий compose-проєкт devops-lab9) ---
LAB9 := docker compose -f docker-compose.lab9.yml

lab9-up:         ## зібрати образ і підняти localstack, init, app1..3, nginx (:8080)
	$(LAB9) up -d --build --wait

lab9-down:       ## зупинити і видалити контейнери лаби 9 (разом з app-single)
	$(LAB9) --profile nolb down

lab9-load:       ## 30 запитів через балансувальник + 3 POST
	scripts/lab9/load.sh 30

lab9-failover:   ## stop app2 -> запити -> start app2 -> запити
	scripts/lab9/failover-demo.sh

lab9-compare:    ## з балансуванням і без (app-single на :8081)
	scripts/lab9/compare.sh

# --- лаба 10: CloudWatch поверх стека лаби 9 (той самий проєкт devops-lab9) ---
LAB10 := docker compose -f docker-compose.lab9.yml -f docker-compose.lab10.yml

lab10-up:        ## стек лаби 9 + CloudWatch/SNS/SQS у LocalStack (:4567), chaos, порти 8101-8103
	$(LAB10) up -d --build --wait

lab10-down:      ## зупинити стек лаби 10
	$(LAB10) --profile nolb down

lab10-alarms:    ## SNS/SQS + alarms bookings-high-errors і bookings-high-latency
	scripts/lab10/alarms.sh

lab10-quick:     ## швидкий прогін експерименту (~7 хв, для налагодження)
	scripts/lab10/experiment.sh quick

lab10-experiment: ## повний прогін експерименту (~17 хв): журнал, фази, статистика, графіки
	scripts/lab10/experiment.sh full

lab10-stats:     ## статистика за останні 10 хв з CloudWatch
	$(BIN)/python scripts/lab10/stats.py --minutes 10 --instances
