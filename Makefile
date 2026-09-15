# Kairo Phantom — Command Surface (SPEC §S9)
# A stage isn't done until its command prints a real green result.
# The kernel imports nothing from /domains or /legacy.

.PHONY: build test demo bench gauntlet safety acceptance domains-check license-check run samples help lint pre-push

PYTHON ?= python
FIXTURES_DIR ?= fixtures/invoice
DEMO_FILE ?= $(FIXTURES_DIR)/sample_invoice_01.txt

help: ## Show this help
	@echo "Kairo Phantom — Command Surface (SPEC S9)"
	@echo ""
	@echo "  make build          Build kernel + wedge Pack (NOT /domains)"
	@echo "  make test           Real unit/integration suites"
	@echo "  make demo FILE=...  Full on-device pipeline -> overlay"
	@echo "  make run DOC=... Q=...  Grounded Q&A on a document (refuses if ungrounded)"
	@echo "  make samples        Run Q&A on all bundled samples (grounded + refusal)"
	@echo "  make bench          Run labeled fixtures -> REPORT.json/md"
	@echo "  make gauntlet       Verification gauntlet, full denominator"
	@echo "  make safety         Air-gap + injection + fuzz + gate-bypass"
	@echo "  make acceptance     Full acceptance -> ACCEPTANCE.md"
	@echo "  make domains-check  CI guard: /domains byte-for-byte unchanged"
	@echo ""

build: ## Build kernel + wedge Pack (NOT /domains)
	$(PYTHON) -c "import kernel; import packs; import bench; print('kernel + packs + bench import OK')"
	$(PYTHON) scripts/ci/kernel_purity_guard.py
	$(PYTHON) scripts/ci/license_check.py
	@echo "BUILD: GREEN"

license-check:
	$(PYTHON) scripts/ci/license_check.py

test: ## Real unit/integration suites (no mocks on production path)
	$(PYTHON) -m pytest kernel/tests/ packs/tests/ -v --tb=short
	$(PYTHON) scripts/ci/kernel_purity_guard.py
	@echo "TEST: GREEN"

demo: ## Full on-device pipeline -> overlay
	$(PYTHON) -m kernel.sidecar.demo --file $(or $(FILE),$(DEMO_FILE))

bench: ## Run labeled fixtures -> REPORT.json/md
	$(PYTHON) -m bench.harness --fixtures-dir $(FIXTURES_DIR) --output bench/REPORT.json
	@echo "BENCH: see bench/REPORT.json and bench/REPORT.md"

gauntlet: ## Verification gauntlet, full denominator (PENDING-REAL-APP counted, not passed)
	$(PYTHON) scripts/ci/kernel_purity_guard.py
	$(PYTHON) scripts/ci/domains_unchanged_guard.py
	$(PYTHON) -m pytest kernel/tests/ packs/tests/ -v --tb=short
	$(PYTHON) -m bench.safety --fixtures-dir $(FIXTURES_DIR)
	$(PYTHON) -m bench.harness --fixtures-dir $(FIXTURES_DIR) --output bench/REPORT.json
	@echo "GAUNTLET: GREEN"

safety: ## Air-gap egress + injection corpus + ingestor fuzz + gate-bypass
	$(PYTHON) -m bench.safety --fixtures-dir $(FIXTURES_DIR)
	@echo "SAFETY: GREEN"

acceptance: ## Full acceptance on a real wedge doc -> ACCEPTANCE.md
	$(PYTHON) -m bench.acceptance --file $(or $(FILE),$(DEMO_FILE)) --output ACCEPTANCE.md
	@echo "ACCEPTANCE: see ACCEPTANCE.md"

ablation: ## Run verifier ablation study (ON vs OFF vs confidence-threshold)
	$(PYTHON) scripts/run_ablation.py --output bench/ablation_report.json
	@echo "ABLATION: see bench/ablation_report.json"

domains-check: ## CI guard: /domains byte-for-byte unchanged
	$(PYTHON) scripts/ci/domains_unchanged_guard.py
	@echo "DOMAINS-CHECK: GREEN"

## P0.1 — Runnable artifact targets
run: ## Grounded Q&A on a document: make run DOC=path Q="question"
	@if [ -z "$(DOC)" ]; then echo "ERROR: DOC is required. Usage: make run DOC=samples/invoice/sample_invoice_01.txt Q=\"What is the invoice number?\""; exit 1; fi
	@if [ -z "$(Q)" ]; then echo "ERROR: Q is required. Usage: make run DOC=samples/invoice/sample_invoice_01.txt Q=\"What is the invoice number?\""; exit 1; fi
	@if [ ! -f "$(DOC)" ]; then echo "ERROR: Document not found: $(DOC)"; exit 1; fi
	$(PYTHON) scripts/qa_pipeline.py --doc "$(DOC)" --question "$(Q)"

samples: ## Run Q&A on all bundled samples (grounded + refusal demo)
	@echo "=== Kairo Phantom — Bundled Samples Demo ==="
	@echo ""
	@echo "--- Invoice (grounded) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/invoice/sample_invoice_01.txt --question "What is the invoice number?"
	@echo ""
	@echo "--- Invoice (refusal) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/invoice/sample_invoice_01.txt --question "What is the CEO's salary?"
	@echo ""
	@echo "--- Contract (grounded) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/contract/sample_contract_01.txt --question "What is the termination date?"
	@echo ""
	@echo "--- Contract (refusal) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/contract/sample_contract_01.txt --question "What is the annual revenue of the Licensor?"
	@echo ""
	@echo "--- Paper (grounded) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/paper/sample_paper_01.txt --question "What architecture does the paper propose?"
	@echo ""
	@echo "--- Paper (refusal) ---"
	@-$(PYTHON) scripts/qa_pipeline.py --doc samples/paper/sample_paper_01.txt --question "What is the author's home address?"
	@echo ""
	@echo "=== Samples demo complete ==="

release-check: ## Release gate automation — asserts all 4 gates + air-gap + verifier on held-out corpus
	$(PYTHON) scripts/release_check.py
	@echo "RELEASE-CHECK: see RELEASE_REPORT.md"

lint: ## Ruff gates exactly as CI focused-runtime runs them (repo root)
	python3 -m ruff check --select E9,F overlay kernel kairo/context/compressor.py scripts/stress_sec006_gauntlet.py stress_test.py
	python3 -m ruff check overlay/server.py kernel/sidecar/melious_router.py overlay/tests/test_server_wave11.py kernel/tests/test_melious_router_wave11.py scripts/stress_wave11.py

pre-push: ## Full local release gate: lint + focused suites + runner syntax
	./ci/pre-push.sh

.PHONY: serve
serve: ## Start the local overlay API (not the grounded-Q&A CLI)
	$(PYTHON) -m uvicorn overlay.server:app --host 127.0.0.1 --port 8765
