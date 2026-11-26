VENV ?= .venv
BIN  := $(VENV)/bin

.PHONY: venv up down deploy smoke test destroy lab9-up lab9-down lab9-load lab9-failover lab9-compare

venv:            ## dev-залежності (pytest, ruff, awslocal, reportlab)
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
