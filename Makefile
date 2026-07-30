# Pipeline for the synthetic-data clustering study.
#
#   make all        run everything that is not already done
#   make help       list targets
#
# Stages are guarded by their outputs, so `make all` after an interrupted run
# continues rather than restarting. Every stage now resumes mid-stage: synthesis
# skips SD files that already exist, clustering checkpoints each of the 144 design
# scenarios, and metrics checkpoints each of the 720 (scenario, replicate) units --
# so a kill costs ~9 min of work there rather than the ~43 a whole scenario takes.
#
# ESTIMATED wall times at m = 1000, 18 workers, on a 24-core workstation.
# None of these has been validated by a completed m = 1000 run; each is a
# per-unit cost measured on this machine, multiplied out:
#   synthesis   ~1.1 h   from 37.7 files/s observed live during the m=1000 run
#   clustering  ~1.4 h   from 0.65 s/SD file, timed over p=2/5/10 on m=100 data
#   recompute   ~5.2 h   from 26.1 ms/pair, from the completed m=100 run (1880s)
# The earlier ~3.2 h clustering figure came from March file mtimes, which
# include idle time between stages; the per-file timing supersedes it.

SHELL      := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:

REPO       := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
DATA_ROOT  ?= $(REPO)
UV         ?= uv
RSCRIPT    ?= Rscript

# Uncompressed by default: ZSTD costs ~2-4% disk here and a minimal `arrow`
# build cannot read it. Override with `make all SYNTHCLUST_PARQUET_CODEC=zstd`.
SYNTHCLUST_PARQUET_CODEC ?= uncompressed
export SYNTHCLUST_PARQUET_CODEC

OD_DIR     := $(DATA_ROOT)/data/original
SD_DIR     := $(DATA_ROOT)/data/synthetic
RESULTS    := $(REPO)/results
MANUSCRIPT := $(REPO)/manuscript

CLUSTER_OUT  := $(RESULTS)/clustering_results.parquet
FIDELITY_OUT := $(RESULTS)/khat_fidelity_full.parquet
SUPP_TABLE   := $(MANUSCRIPT)/supp_table.tex
MAIN_PDF     := $(MANUSCRIPT)/main.pdf

# Expected file counts, read from config.json -- the single source of truth for m.
M      := $(shell python3 -c "import json;print(json.load(open('$(REPO)/config.json'))['simulation']['m'])")
N_OD   := 144
N_SD   := $(shell echo $$(( $(N_OD) * $(M) )) )

.PHONY: all help watch setup original synthetic cluster metrics figures manuscript \
        verify test status clean-results clean-data distclean

# scripts/pipeline.py owns the run: it declares "phase i/7", polls each stage's
# progress off disk to show an ETA, logs stage output under results/logs/, and
# resumes wherever a kill left off. The per-stage targets below still work on their
# own for running one stage by hand.
all:
	$(UV) run python $(REPO)/scripts/pipeline.py
	@$(MAKE) --no-print-directory status

# Read-only view of the same phase table, safe to attach mid-run from any terminal.
watch:
	@$(UV) run python $(REPO)/scripts/pipeline.py --watch

help:
	@echo "Targets:"
	@echo "  all          all 7 phases, with progress + ETA (scripts/pipeline.py)"
	@echo "  watch        read-only phase view; attach any time, any terminal"
	@echo "  setup        install R packages, check arrow has the needed codec"
	@echo "  original     generate the $(N_OD) original datasets"
	@echo "  synthetic    generate the $(N_SD) synthetic datasets (resumable)"
	@echo "  cluster      run clustering       (resumes per scenario)"
	@echo "  metrics      recompute fidelity   (resumes per scenario x replicate)"
	@echo "  figures      figures + supplementary table"
	@echo "  manuscript   build both PDFs"
	@echo "  verify       check every parquet is readable and complete"
	@echo "  test         run the resume/checkpoint regression tests"
	@echo "  status       what exists now"
	@echo "  clean-results  delete derived results, keep the datasets"
	@echo "  clean-data     delete the generated datasets"
	@echo
	@echo "Current: m = $(M), expecting $(N_OD) OD and $(N_SD) SD files"
	@echo "Codec:   $(SYNTHCLUST_PARQUET_CODEC)"

# ---- environment ------------------------------------------------------------
# Re-run every time: it is idempotent (installs only what is missing) and it is
# the step that catches an `arrow` without the codec the datasets need.
setup:
	@echo "==> R packages and arrow codec support"
	$(RSCRIPT) $(REPO)/R/setup.R
	@echo "==> python environment"
	$(UV) sync

# ---- data -------------------------------------------------------------------
# Guarded on the LAST expected file rather than the directory, so an interrupted
# synthesis is not mistaken for a finished one.
original: setup
	@n=$$(ls $(OD_DIR) 2>/dev/null | wc -l); \
	if [ "$$n" -eq "$(N_OD)" ]; then \
	  echo "==> original data present ($$n files), skipping"; \
	else \
	  echo "==> generating original data ($$n/$(N_OD) present)"; \
	  $(RSCRIPT) $(REPO)/R/generate_original.R; \
	fi

synthetic: original
	@n=$$(ls $(SD_DIR) 2>/dev/null | wc -l); \
	if [ "$$n" -eq "$(N_SD)" ]; then \
	  echo "==> synthetic data complete ($$n files), skipping"; \
	else \
	  echo "==> generating synthetic data ($$n/$(N_SD) present; existing files are kept)"; \
	  $(RSCRIPT) $(REPO)/R/generate_synthetic.R; \
	fi

# ---- analysis ---------------------------------------------------------------
# A stamp recording which m the datasets were built for. Without it, results
# from a previous m satisfy make's file guards and the analysis is silently
# skipped -- leaving a manuscript whose numbers come from the old design.
# Changing m in config.json invalidates the stamp and forces both stages to rerun.
STAMP := $(RESULTS)/.design-m$(M)

$(STAMP): | synthetic
	@n=$$(ls $(SD_DIR) 2>/dev/null | wc -l); \
	if [ "$$n" -ne "$(N_SD)" ]; then \
	  echo "synthetic data incomplete ($$n/$(N_SD)); not stamping" >&2; exit 1; \
	fi
	@mkdir -p $(RESULTS) && rm -f $(RESULTS)/.design-m* && touch $@
	@echo "==> datasets complete for m = $(M)"

$(CLUSTER_OUT): $(STAMP)
	@echo "==> clustering (checkpoints each scenario; a kill loses only those in flight)"
	$(UV) run run-clustering

cluster: $(CLUSTER_OUT)

$(FIDELITY_OUT): $(CLUSTER_OUT)
	@echo "==> recomputing fidelity metrics (checkpoints each scenario)"
	$(UV) run recompute-metrics

metrics: $(FIDELITY_OUT)

# ---- outputs ----------------------------------------------------------------
$(SUPP_TABLE): $(FIDELITY_OUT)
	$(UV) run make-supp-table

figures: $(FIDELITY_OUT) $(SUPP_TABLE)
	@echo "==> figures"
	$(UV) run make-figures

$(MAIN_PDF): figures
	@echo "==> manuscript"
	cd $(MANUSCRIPT) && ./build.sh main && ./build.sh supplementary

manuscript: $(MAIN_PDF)

# ---- checks -----------------------------------------------------------------
verify:
	$(UV) run verify-data

test:
	$(UV) run --extra dev python -m pytest tests/ -q

status:
	@printf "  %-26s %s\n" "config m"        "$(M)"
	@printf "  %-26s %s / %s\n" "original files" "$$(ls $(OD_DIR) 2>/dev/null | wc -l)" "$(N_OD)"
	@printf "  %-26s %s / %s\n" "synthetic files" "$$(ls $(SD_DIR) 2>/dev/null | wc -l)" "$(N_SD)"
	@for f in $(CLUSTER_OUT) $(FIDELITY_OUT) $(MAIN_PDF); do \
	  if [ -f "$$f" ]; then s=$$(date -r "$$f" '+%Y-%m-%d %H:%M'); else s="ABSENT"; fi; \
	  printf "  %-26s %s\n" "$$(basename $$f)" "$$s"; \
	done

# ---- cleaning ---------------------------------------------------------------
# Deliberately never deletes data/ or results/ as part of `all`; regenerating
# is hours of compute. Each clean target names exactly what it removes.
clean-results:
	rm -f $(CLUSTER_OUT) $(FIDELITY_OUT) $(RESULTS)/khat_agreement.csv
	rm -f $(MANUSCRIPT)/figures/*.pdf $(MANUSCRIPT)/figures/*.png $(SUPP_TABLE)
	@echo "Derived results removed. Datasets kept. *_m100.* backups kept."

clean-data:
	@echo "This deletes $(N_SD) synthetic and $(N_OD) original files (hours to regenerate)."
	@read -p "Type yes to continue: " a; [ "$$a" = yes ]
	rm -f $(SD_DIR)/*.parquet $(OD_DIR)/*.parquet

distclean: clean-results
	rm -rf $(REPO)/.venv $(MANUSCRIPT)/*.aux $(MANUSCRIPT)/*.log \
	       $(MANUSCRIPT)/*.bbl $(MANUSCRIPT)/*.blg $(MANUSCRIPT)/*.out
