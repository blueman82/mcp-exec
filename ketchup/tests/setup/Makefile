# Ketchup Bot Makefile

.PHONY: setup test test-unit test-integration test-e2e test-jira-reporter test-jira-reporter-unit test-jira-reporter-integration test-jira-reporter-coverage test-mcp-jira-integration lint clean copy-packages sam-build sam-local ngrok local-dev lambda-burst-test lambda-burst-clean lambda-burst-logs lambda-burst-logs-follow lambda-burst-aggregate docker-build docker-rebuild setup-ipaas test-mcp-auth help
ARGS?=

PYTHON=python3
PIP=pip3
VENV?=.venv
SHELL := /bin/bash
export PYTHONDONTWRITEBYTECODE=1

# Setup virtual environment and install dependencies
setup:
	@if [ ! -d $(VENV) ]; then $(PYTHON) -m venv $(VENV); fi
	. $(VENV)/bin/activate && $(PIP) install --upgrade pip
	. $(VENV)/bin/activate && $(PIP) install -r requirements.txt

# Run all tests
test:
	. $(VENV)/bin/activate && cd ../../ && PYTHONPATH=. pytest tests

# Run only unit tests (by convention, not in integration/ or e2e/)
test-unit:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. pytest tests --ignore=tests/integration --ignore=tests/e2e $(ARGS)

# Run TypedDI validation tests (constructor signatures, dependency coverage, smoke checks)
test-typed-di:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. python -m unittest -v tests.unit.core.typed_di.test_constructor_signature_validation && \
	PYTHONPATH=. python -m unittest -v tests.unit.core.typed_di.test_service_batch_smoke_checks

# Run all TypedDI tests with full validation suite
test-typed-di-full:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. python -m unittest discover -s tests/unit/core/typed_di -p "test_*.py" -v

# Run pylint scoped to TypedDI paths only for CI compliance
pylint-typed-di:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. python -m pylint packages/core/typed_di/ tests/unit/core/typed_di/ --rcfile=tests/setup/.pylintrc-typed-di || true

# Run only JIRA reporter unit tests
test-jira-reporter-unit:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter $(ARGS)

# Test JIRA reporter feature flags
test-jira-reporter-feature-flag:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter/test_feature_flag.py -v $(ARGS)

# Run only integration tests
test-integration:
	. $(VENV)/bin/activate && cd ../../ && AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration $(ARGS)

# Run only JIRA reporter integration tests
test-jira-reporter-integration:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration/test_jira_reporter $(ARGS)

# Run MCP JIRA service integration tests
test-mcp-jira-integration:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_mcp_direct.py $(ARGS)

# Test JIRA reporter authentication
test-jira-reporter-auth:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_jira_reporter_auth.py::test_jira_service_with_ims_authentication $(ARGS)

# Run full JIRA reporter integration test (posts to real JIRA)
test-jira-reporter-full:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_jira_reporter_auth.py::test_jira_reporter_full_integration $(ARGS)

# Test JIRA comment posting (simple integration test)
test-jira-post:
	. $(VENV)/bin/activate && cd ../../ && \
	RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_jira_posting.py -v $(ARGS)

# Test JIRA posting with fresh IMS token
test-jira-fresh-token:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_jira_with_fresh_token.py::test_jira_posting_with_fresh_token -v -s $(ARGS)

# Test MCP auth with fresh token
test-mcp-fresh-token:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_jira_with_fresh_token.py::test_mcp_with_fresh_token -v -s $(ARGS)

# Test JIRA posting with direct token refresh (avoids DI issues)
test-jira-direct:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_direct_token_refresh.py::test_jira_with_direct_token_refresh -v -s $(ARGS)

# Test MCP health check
test-mcp-health:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_direct_token_refresh.py::test_mcp_health_with_fresh_token -v -s $(ARGS)

# Final JIRA posting test
test-jira-final:
	. $(VENV)/bin/activate && cd ../../ && \
	AWS_PROFILE=campaign_prod_v7 RUN_JIRA_INTEGRATION_TESTS=true PYTHONPATH=. pytest tests/integration/test_jira_reporter/test_final_jira_post.py -v -s $(ARGS)

# Run only end-to-end tests
test-e2e:
	. $(VENV)/bin/activate && cd ../../ && PYTHONPATH=. pytest tests/e2e

# Run all JIRA reporter tests (unit + integration)
test-jira-reporter:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter tests/integration/test_jira_reporter $(ARGS)

# Run JIRA reporter tests with coverage
test-jira-reporter-coverage:
	. $(VENV)/bin/activate && cd ../../ && \
	PYTHONPATH=. pytest tests/unit/test_jira_reporter tests/integration/test_jira_reporter \
	--cov=jira_reporter --cov-report=html --cov-report=term-missing $(ARGS)

# Lint code (ruff, black, isort)
pylint:
	. $(VENV)/bin/activate && ruff check ../../packages ../../tests
	. $(VENV)/bin/activate && black --check ../../packages ../../tests
	. $(VENV)/bin/activate && isort --check ../../packages ../../tests
	. $(VENV)/bin/activate && pylint ../../packages ../../tests

# Lint only TypedDI codepaths (faster, focused)
pylint-typed-di:
	. $(VENV)/bin/activate && ruff check ../../packages/core/typed_di ../../tests/unit/core/typed_di
	. $(VENV)/bin/activate && black --check ../../packages/core/typed_di ../../tests/unit/core/typed_di
	. $(VENV)/bin/activate && isort --check ../../packages/core/typed_di ../../tests/unit/core/typed_di
	. $(VENV)/bin/activate && pylint ../../packages/core/typed_di ../../tests/unit/core/typed_di

# Clean test artifacts and caches
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	find ../.. -type d -name '__pycache__' -exec rm -rf {} +
	find ../.. -type f -name '*.pyc' -delete

# Copy packages/ into the SAM hello_world directory
copy-packages:
	cp -r ../../packages ../../ketchup-sam-app/hello_world/

# Build the SAM application (after copying packages)
sam-build: copy-packages
	@echo "\033[1;36m[sam-build]\033[0m Build the SAM application."
	@echo "\033[1;33mPurpose:\033[0m Prepare AWS SAM for local or cloud deployment."
	@echo "\033[1;32mExpected:\033[0m SAM build artifacts created."
	cd ketchup-sam-app && sam build --template-file template.yaml

# Start the SAM local API (after build)
sam-local: sam-build
	@echo "\033[1;36m[sam-local]\033[0m Start the SAM local API."
	@echo "\033[1;33mPurpose:\033[0m Run the Lambda locally for testing."
	@echo "\033[1;32mExpected:\033[0m Local API running on http://localhost:3000."
	cd ketchup-sam-app && sam local start-api --template .aws-sam/build/template.yaml --env-vars ../env.json

# Start ngrok on port 3000 and print the public URL
ngrok:
	@echo "\033[1;36m[ngrok]\033[0m Start ngrok on port 3000 and print the public URL."
	@echo "\033[1;33mPurpose:\033[0m Expose local API to the internet."
	@echo "\033[1;32mExpected:\033[0m Public ngrok URL for local API."
	ngrok http 3000 > /dev/null &
	sleep 2
	curl --silent http://localhost:4040/api/tunnels | \
		python3 -c "import sys, json; print([t['public_url'] for t in json.load(sys.stdin)['tunnels'] if t['proto'] == 'https'][0])"

# Start SAM local and ngrok in parallel, then print the ngrok URL
local-dev:
	@echo "\033[1;36m[local-dev]\033[0m Start SAM local and ngrok in parallel, then print the ngrok URL."
	@echo "\033[1;33mPurpose:\033[0m Run local Lambda and expose it for integration."
	@echo "\033[1;32mExpected:\033[0m Both local API and ngrok tunnel running."
	( \
		$(MAKE) sam-local & \
		ngrok http 3000 > /dev/null & \
		while ! curl --silent http://localhost:4040/api/tunnels | grep -q 'public_url'; do sleep 1; done; \
		curl --silent http://localhost:4040/api/tunnels | \
			python3 -c "import sys, json; print([t['public_url'] for t in json.load(sys.stdin)['tunnels'] if t['proto'] == 'https'][0])"; \
		wait \
	)

nimbus-dry-run:
	@echo "\033[1;36m[nimbus-dry-run]\033[0m Preview nimbus → ketchup replacements (dry run)."
	@echo "\033[1;33mPurpose:\033[0m Show what would change without modifying files."
	@echo "\033[1;32mExpected:\033[0m List of files that would be updated."
	cd ../../ && python3 replace_nimbus_with_ketchup.py --dry-run --nimbus

ketchup-dry-run:
	@echo "\033[1;36m[ketchup-dry-run]\033[0m Preview ketchup → nimbus replacements (dry run)."
	@echo "\033[1;33mPurpose:\033[0m Show what would change without modifying files."
	@echo "\033[1;32mExpected:\033[0m List of files that would be updated."
	cd ../../ && python3 replace_nimbus_with_ketchup.py --dry-run --ketchup

nimbus-replace:
	@echo "\033[1;36m[nimbus-replace]\033[0m Replace nimbus → ketchup in codebase."
	@echo "\033[1;33mPurpose:\033[0m Update all code and docs to use ketchup."
	@echo "\033[1;32mExpected:\033[0m All nimbus references replaced with ketchup."
	cd ../../ && python3 replace_nimbus_with_ketchup.py --nimbus

ketchup-replace:
	@echo "\033[1;36m[ketchup-replace]\033[0m Replace ketchup → nimbus in codebase."
	@echo "\033[1;33mPurpose:\033[0m Update all code and docs to use nimbus."
	@echo "\033[1;32mExpected:\033[0m All ketchup references replaced with nimbus."
	cd ../../ && python3 replace_nimbus_with_ketchup.py --ketchup

# Simulate Lambda-style concurrency burst with Docker
lambda-burst-test: lambda-burst-clean
	@echo "Cleaning up previous test run results"
	rm -rf results/*.json
	@echo "\033[1;36m[lambda-burst-test]\033[0m Launches 90 Docker containers to simulate Lambda concurrency burst."
	@echo "\033[1;33mPurpose:\033[0m Stress-test concurrency, rate-limiting, and AWS credential handling."
	@echo "\033[1;32mExpected:\033[0m 90 containers started, each running the test script and writing results."
	mkdir -p results
	for i in $$(seq 1 90); do \
		docker run -d \
		  --name token-test-$$i \
		  --memory=2g --cpus=1 \
		  -e NUM_CONNECTIONS=1 \
		  -e AWS_ACCESS_KEY_ID="$(aws configure get aws_access_key_id --profile campaign_prod_v7)" \
		  -e AWS_SECRET_ACCESS_KEY="$(aws configure get aws_secret_access_key --profile campaign_prod_v7)" \
		  -e AWS_SESSION_TOKEN="$(aws configure get aws_session_token --profile campaign_prod_v7)" \
		  -e AWS_DEFAULT_REGION=eu-west-1 \
		  -v ~/.aws:/root/.aws \
		  -v $(CURDIR)/results:/app/results \
		  token-test; \
	done

lambda-burst-clean:
	@echo "\033[1;36m[lambda-burst-clean]\033[0m Stops and removes all token-test-* containers."
	@echo "\033[1;33mPurpose:\033[0m Ensure a clean environment before running new burst tests."
	@echo "\033[1;32mExpected:\033[0m No token-test-* containers remain."
	docker ps -a -q --filter "name=token-test-" | xargs -r docker rm -f

lambda-burst-logs:
	@echo "\033[1;36m[lambda-burst-logs]\033[0m Shows the last 90 lines of logs for each token-test-* container."
	@echo "\033[1;33mPurpose:\033[0m Quickly review recent output/errors from all test containers."
	@echo "\033[1;32mExpected:\033[0m Last 90 log lines per container, in order."
	for i in $$(seq 1 90); do \
		echo "--- Logs for token-test-$$i ---"; \
		docker logs token-test-$$i 2>&1 | tail -n 90; \
	done

lambda-burst-logs-follow:
	@echo "\033[1;36m[lambda-burst-logs-follow]\033[0m Follows logs in real time for all token-test-* containers."
	@echo "\033[1;33mPurpose:\033[0m Live monitoring of all test containers as they run."
	@echo "\033[1;32mExpected:\033[0m Real-time log output for each container (Ctrl+C to stop)."
	for i in $$(seq 1 90); do \
		echo "--- Following logs for token-test-$$i ---"; \
		docker logs -f token-test-$$i & \
	done; \
	wait

lambda-burst-aggregate:
	@echo "\033[1;36m[lambda-burst-aggregate]\033[0m Aggregates all container result files and prints a summary of concurrency test outcomes."
	@echo "\033[1;33mPurpose:\033[0m Summarize success/failure, timing, and token usage across all containers."
	@echo "\033[1;32mExpected:\033[0m A summary table and success metrics for all requests."
	@printf '%s\n' "import json, glob" \
	"from tabulate import tabulate" \
	"from colorama import Fore, Style, init" \
	"init()" \
	"files = glob.glob('results/result-*.json')" \
	"results = [json.load(open(f)) for f in files]" \
	"all_connections = []" \
	"for r in results:" \
	"    for row in r['results']:" \
	"        all_connections.append(row)" \
	"total = len(all_connections)" \
	"total_successes = sum(1 for _, s, *_ in all_connections if s == 'Success (Handler)')" \
	"failures = sum(1 for _, s, *_ in all_connections if isinstance(s, str) and s.startswith('Failed (Handler'))" \
	"total_input_tokens = sum(inp for *_, inp, _ in all_connections if inp is not None)" \
	"total_output_tokens = sum(out for *_, _, out in all_connections if out is not None)" \
	"avg_time = sum(r[2] for r in all_connections) / total if total > 0 else 0" \
	"max_time = max(r[2] for r in all_connections) if total > 0 else 0" \
	"min_time = min(r[2] for r in all_connections) if total > 0 else 0" \
	"avg_retry_sleep = sum(r[3] for r in all_connections) / total if total > 0 else 0" \
	"def color(val, color): return f'{color}{val}{Style.RESET_ALL}'" \
	"header = [color('Metric', Fore.CYAN + Style.BRIGHT), color('Value', Fore.CYAN + Style.BRIGHT)]" \
	"summary_table = [" \
	"    [color('Total Successful', Fore.CYAN), color(total_successes, Fore.GREEN)]," \
	"    [color('Total Failed', Fore.CYAN), color(failures, Fore.RED if failures else Fore.GREEN)]," \
	"    [color('Total execution time', Fore.CYAN), f'{sum(r[2] for r in all_connections):.2f}s']," \
	"    [color('Average request time', Fore.CYAN), f'{avg_time:.2f}s']," \
	"    [color('Fastest request', Fore.CYAN), f'{min_time:.2f}s']," \
	"    [color('Slowest request', Fore.CYAN), f'{max_time:.2f}s']," \
	"    [color('Average retry sleep time', Fore.CYAN), f'{avg_retry_sleep:.2f}s']," \
	"    [color('Total input tokens', Fore.CYAN), f'{total_input_tokens:,}']," \
	"    [color('Total output tokens', Fore.CYAN), f'{total_output_tokens:,}']," \
	"    [color('Total tokens used', Fore.CYAN), f'{total_input_tokens + total_output_tokens:,}']," \
	"    [color('Average total tokens per request', Fore.CYAN), f'{(total_input_tokens + total_output_tokens) / total:,.2f}' if total else '0.00']," \
	"    [color('Average input tokens per request', Fore.CYAN), f'{total_input_tokens / total:,.2f}' if total else '0.00']," \
	"    [color('Average output tokens per request', Fore.CYAN), f'{total_output_tokens / total:,.2f}' if total else '0.00']," \
	"]" \
	"print('Summary Table:')" \
	"print(tabulate(summary_table, headers=header, tablefmt='fancy_grid'))" \
	"metrics_header = [color('Metric', Fore.CYAN + Style.BRIGHT), color('Value', Fore.CYAN + Style.BRIGHT)]" \
	"metrics_table = [" \
	"    [color('Total Requests', Fore.CYAN), color(total, Fore.GREEN)]," \
	"    [color('Success Rate', Fore.CYAN), color(f'{(total_successes / total) * 100:.2f}%' if total else '0.00%', Fore.GREEN)]," \
	"    [color('Failure Rate', Fore.CYAN), color(f'{(failures / total) * 100:.2f}%' if total else '0.00%', Fore.RED if failures else Fore.GREEN)]," \
	"]" \
	"print('\nSuccess Metrics Summary:')" \
	"print(tabulate(metrics_table, headers=metrics_header, tablefmt='fancy_grid'))" > results/aggregate_results.py
	@python3 results/aggregate_results.py

# Build the Docker image for burst tests
docker-build:
	@echo "\033[1;36m[docker-build]\033[0m Build the Docker image for burst tests."
	@echo "\033[1;33mPurpose:\033[0m Create or update the 'token-test' image with the latest code."
	@echo "\033[1;32mExpected:\033[0m Docker image 'token-test' is ready to use."
	docker build -f tests/setup/Dockerfile -t token-test .

docker-rebuild:
	@echo "\033[1;36m[docker-rebuild]\033[0m Remove old Docker image and build a fresh one."
	@echo "\033[1;33mPurpose:\033[0m Ensure no stale layers or cache are used."
	@echo "\033[1;32mExpected:\033[0m Clean, up-to-date 'token-test' image."
	docker rmi -f token-test || true
	$(MAKE) docker-build

# Setup iPaaS environment variables from AWS Secrets Manager
setup-ipaas:
	@echo "\033[1;36m[setup-ipaas]\033[0m Setup iPaaS environment variables from AWS Secrets Manager."
	@echo "\033[1;33mPurpose:\033[0m Fetch and export JIRA credentials for docker-compose and testing."
	@echo "\033[1;32mExpected:\033[0m Environment variables set for JIRA_API_KEY, JIRA_USERNAME, JIRA_PASSWORD, JIRA_IMS_TOKEN."
	@echo "Note: Run 'source <(make setup-ipaas)' to export variables to your shell"
	@bash setup-ipaas-env.sh

# Integration test examples (use make test-integration ARGS="-k test_name")
# Examples:
#   make test-integration ARGS="-k test_mcp_auth"
#   make test-integration ARGS="-k test_real_jira_auth"
#   make test-integration ARGS="-k test_ims_token_update"
#   make test-jira-reporter ARGS="-k test_archive_monitor"
#   make test-jira-reporter-unit ARGS="-v"
#   make test-jira-reporter-coverage

help:
	@echo "Available Makefile targets:"
	@awk -F: '/^[a-zA-Z0-9][^$#\t=]*:/ {print "  -", $$1}' $(MAKEFILE_LIST) | grep -v 'phony' | sort
	@echo "Key targets:"
	@echo "  setup                Set up the Python virtual environment and install dependencies."
	@echo "  test                 Run all tests."
	@echo "  test-unit            Run only unit tests (supports ARGS for specific tests)."
	@echo "  test-integration     Run only integration tests (supports ARGS for specific tests)."
	@echo "  test-e2e             Run only end-to-end tests."
	@echo "  test-jira-reporter   Run all JIRA reporter tests (unit + integration)."
	@echo "  test-jira-reporter-unit       Run only JIRA reporter unit tests."
	@echo "  test-jira-reporter-integration Run only JIRA reporter integration tests."
	@echo "  test-jira-reporter-coverage   Run JIRA reporter tests with coverage report."
	@echo "  setup-ipaas          Setup iPaaS environment variables from AWS Secrets Manager."
	@echo "  docker-build         Build the Docker image for burst tests."
	@echo "  docker-rebuild       Remove old Docker image and build a fresh one."
	@echo "  lambda-burst-test    Launch 90 Docker containers to simulate Lambda concurrency burst."
	@echo "  lambda-burst-clean   Stop and remove all burst test containers."
	@echo "  lambda-burst-logs    Show logs for all burst test containers."
	@echo "  lambda-burst-logs-follow  Follow logs in real time for all burst test containers."
	@echo "  lambda-burst-aggregate    Aggregate results from all burst test containers."
	@echo "Run 'make <target>' or 'make -C tests/setup <target>' from the project root."
