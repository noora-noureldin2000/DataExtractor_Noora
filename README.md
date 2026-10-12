# DataExtractor_Noora

**Automated clinical data extraction from scientific PDFs for systematic reviews and meta-analyses.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

DataExtractor_Noora converts unstructured scientific PDFs into structured extraction data using AI vision models. It ingests study PDFs, performs OCR, parses complex tables, reads figures and graphs via vision-capable LLMs, and applies strict biostatistical rules for clinical variable extraction.

---

## Features

- **PDF Ingestion** — High-fidelity Markdown conversion via Docling with OCR, table structure extraction, and embedded figure/image export
- **Thorough End-to-End Extraction** — Documents are chunked (heading-aware, with overlap) and every chunk is processed to the end; per-chunk results are merged and deduplicated — no more silent truncation of long PDFs
- **Page Map & Scanned-Page OCR** — Fast pdf-inspector pre-flight (PyMuPDF fallback) classifies every page; scanned pages are rendered at 300 DPI and OCRed with Tesseract so text embedded in scanned sections is captured
- **Dedicated Figure OCR** — Tesseract runs directly on exported figures (multi-config, preprocessed) to catch axis labels, tick values, and in-figure table cells; OCR text grounds the vision model for digit-level precision
- **Multi-Model Vision Router** — Swap between local (Ollama/qwen2.5-vl) or cloud (Claude, Gemini, Muse Spark via OpenAI-compatible endpoint) VLMs without code changes
- **Biostatistical Calculation Engine** — Automates Cochrane-style extraction rules (change scores, SD imputation, median/IQR conversion, baseline discrepancies)
- **Graph & Figure Extraction** — Each figure is processed individually with its OCR text for verification
- **Template Export** — Maps extracted variables to your existing `.xlsx` or `.csv` extraction sheets via LLM or heuristic matching, with "Not Found" flags
- **Audit Trail** — Every imputation and calculation is logged with warnings; mixed data types trigger sensitivity analysis flags
- **NCT Detection** — Automatic ClinicalTrials.gov identifier extraction from document text

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and configure environment
cp .env.example .env
# Edit .env: set VISION_MODE=local (default) or cloud and add API keys if needed

# 3. Run extraction on a PDF
python main.py study.pdf -v "age" "blood_pressure" "NCT number"

# 4. Run with template export
python main.py study.pdf -v "SBP" "Death" -t template.xlsx --template-output results.xlsx
```

---

## Installation

### Prerequisites

| Component | Required | Notes |
|-----------|----------|-------|
| Python 3.11+ | Yes | Tested on 3.14 |
| Tesseract OCR 5.x | Yes | Local binary shared by **all** OCR paths (see OCR wiring below). [Install guide](https://github.com/tesseract-ocr/tesseract) |
| Ollama | Local mode only | For `qwen2.5-vl:3b`. [Install guide](https://ollama.ai) |
| API keys | Cloud mode only | Anthropic, Google AI, and/or OpenCode Go (for Muse Spark) |

### OCR Wiring

Docling ships its own default OCR engine, but this repo explicitly wires `TesseractOcrOptions` (`ingestion/converter.py`) so every OCR path uses your local Tesseract install through the single `TESSERACT_CMD` setting:

- **Docling PDF conversion** — `TesseractOcrOptions(tesseract_cmd=...)` for scanned pages and table structure
- **Figure OCR** — `pytesseract` on exported figures (`ingestion/figure_ocr.py`)
- **Scanned-page OCR** — `pytesseract` on 300 DPI page renders (`ingestion/page_mapper.py`)

Ingestion verifies the whole stack at startup (`ingestion/ocr_setup.py`) and logs the Tesseract version it finds.

### Setup

```bash
git clone https://github.com/yourusername/DataExtractor_Noora.git
cd DataExtractor_Noora
pip install -r requirements.txt

# Pull the local vision model (if using local mode)
ollama pull qwen2.5vl:3b

# Configure
cp .env.example .env

# Verify OCR prerequisites (Tesseract binary + Python bindings)
tesseract --version
python -c "import pytesseract; print('pytesseract ok')"
```

---

## Usage

### Basic Extraction

```bash
python main.py clinical_trial.pdf -v "systolic_blood_pressure" "heart_rate" "NCT"
```

### Population & Arm Filtering

```bash
# Extract only adult patients from the intervention arm
python main.py study.pdf -v "BMI" "glucose" --population "adults" --arm "intervention"
```

### Template-Based Export

Prepare an extraction template (`.xlsx`) with your column headers, then:

```bash
python main.py study.pdf -v "SBP" "DBP" -t extraction_template.xlsx
```

The tool will semantically map extracted variables to your columns and populate a new row.

### Cloud Models (better accuracy, requires API keys)

```bash
# Edit .env:
# VISION_MODE=cloud
# CLOUD_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-...

python main.py study.pdf -v "age" "outcome" --mode cloud
```

### Muse Spark via OpenCode Go (recommended for figure reading)

Muse Spark 1.3 (the model integrated in the official opencode agent) is accessed through your OpenCode Go subscription — no separate Muse key needed:

```bash
# 1. Sign in to OpenCode Zen, subscribe to Go, copy your API key
#    (same key you paste into the opencode agent via /connect -> OpenCode Go)
# 2. Edit .env:
# VISION_MODE=cloud
# CLOUD_PROVIDER=muse
# OPENCODE_API_KEY=sk-...

python main.py study.pdf -v "age" "outcome" --mode cloud
```

### Skip Ingestion (re-use previous conversion)

```bash
python main.py study.pdf -v "HbA1c" --skip-ingestion
```

---

## Biostatistical Rules

The extraction engine enforces the following rules defined in `extraction/biostatistics.py`:

| Rule | Behavior |
|------|----------|
| **Dichotomous data** | Extracts Event/Total only. Percentages are rejected by the prompt. |
| **Mean change** | Calculated as Post - Baseline if not explicitly reported. |
| **SD change imputation** | `sqrt(SD_baseline + SD_final - 2 * Corr * SD_baseline * SD_final)` with Corr defaulting to 0.5 |
| **Baseline = 0** | Uses post-intervention mean when baseline is effectively zero. |
| **Mixed data types** | Flags when "Change" and "Post" data are mixed; recommends sensitivity analysis. |
| **Unequal baselines** | Warns if arm baselines differ by >50%, as post-intervention data may be misleading. |
| **Median/IQR** | n > 25: Mean ≈ Median. n ≤ 25: Mean ≈ (Q1+Med+Q3)/3. SD ≈ IQR/1.35. |

---

## Project Structure

```
DataExtractor_Noora/
├── config.py                    # Environment-based configuration
├── main.py                      # CLI entry point
├── ingestion/
│   ├── converter.py             # Docling PDF to Markdown + images
│   ├── page_mapper.py           # Per-page text map (pdf-inspector/PyMuPDF) + scanned-page OCR
│   └── figure_ocr.py            # Dedicated Tesseract OCR on exported figures
├── models/
│   ├── router.py                # Vision model routing (local/cloud)
│   ├── local.py                 # Ollama VLM connector
│   ├── cloud.py                 # Claude, Gemini & Muse connectors
│   └── exceptions.py            # Custom error types
├── extraction/
│   ├── engine.py                # Chunked map-reduce extraction orchestration
│   ├── chunker.py               # Heading-aware overlapping chunking
│   ├── biostatistics.py         # Clinical calculation logic
│   └── prompts.py               # LLM prompt templates
├── export/
│   └── template_exporter.py     # Template mapping and Excel/CSV export
└── utils/
    └── helpers.py               # JSON I/O, logging
```

---

## Configuration

All configuration is via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_MODE` | `local` | `local` or `cloud` |
| `OLLAMA_MODEL` | `qwen2.5vl:3b` | Local vision model name |
| `CLOUD_PROVIDER` | `anthropic` | `anthropic`, `gemini`, or `muse` |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Claude model ID |
| `GEMINI_MODEL` | `gemini-2.5-pro-exp-03-25` | Gemini model ID |
| `OPENCODE_API_KEY` | (empty) | OpenCode Go subscription key from the Zen console (same key used in the opencode agent) |
| `OPENCODE_API_BASE` | `https://opencode.ai/zen/go/v1` | OpenCode Go API base URL (Muse uses its `/responses` endpoint) |
| `OPENCODE_MODEL` | `muse-spark-1.3-contributor` | Muse Spark model ID (verify IDs at `https://opencode.ai/zen/go/v1/models`) |
| `DEFAULT_CORR` | `0.5` | Default correlation coefficient for SD imputation |
| `TESSERACT_CMD` | `tesseract` | Tesseract OCR executable path |

---

## Output

After running, results are written to `./output/`:

```
output/
├── markdown/{study_name}/       # High-fidelity Markdown conversion
│   └── {study_name}_pagemap.json    # Per-page text map + OCR-needs diagnostics
├── extracted_images/{study_name}/  # Figures and graphs from PDF
│   ├── fig_0001.ocr.txt            # Per-figure OCR text (audit trail)
│   └── {study_name}_figure_ocr.json  # Figure OCR text map
└── results/
    ├── {study_name}_extraction.json   # Structured extraction data
    ├── {study_name}_graphs.json       # Per-figure graph data (with OCR grounding)
    └── {study_name}_template_output.xlsx  # Template-populated export (if requested)
```

---

## License

MIT

---

## Acknowledgments

This project draws inspiration from:
- [google/langextract](https://github.com/google/langextract) — Grounded extraction traceability
- [opendatalab/mineru](https://github.com/opendatalab/mineru) — Document parsing
- [JackKuo666/sci-data-extractor](https://github.com/JackKuo666/sci-data-extractor) — Scientific extraction prompt design
- [docling-project/docling](https://github.com/docling-project/docling) — PDF document conversion
- [amElnagdy/guard-skills](https://github.com/amElnagdy/guard-skills) — Code quality gate patterns
