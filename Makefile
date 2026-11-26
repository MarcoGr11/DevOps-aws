VENV ?= .venv
BIN  := $(VENV)/bin

.PHONY: venv up down deploy smoke test destroy

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
