# DataExtractor_Noora

**Automated clinical data extraction from scientific PDFs for systematic reviews and meta-analyses.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

DataExtractor_Noora converts unstructured scientific PDFs into structured extraction data using AI vision models. It ingests study PDFs, performs OCR, parses complex tables, reads figures and graphs via vision-capable LLMs, and applies strict biostatistical rules for clinical variable extraction.

---

## Features

- **PDF Ingestion** — High-fidelity Markdown conversion via Docling with OCR, table structure extraction, and embedded figure/image export
- **Multi-Model Vision Router** — Swap between local (Ollama/qwen2.5-vl) or cloud (Claude, Gemini) VLMs without code changes
- **Biostatistical Calculation Engine** — Automates Cochrane-style extraction rules (change scores, SD imputation, median/IQR conversion, baseline discrepancies)
- **Graph & Figure Extraction** — Routes extracted images alongside precision prompts to the vision model
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
| Tesseract OCR | Yes | For scanned PDF text. [Install guide](https://github.com/tesseract-ocr/tesseract) |
| Ollama | Local mode only | For `qwen2.5-vl:3b`. [Install guide](https://ollama.ai) |
| API keys | Cloud mode only | Anthropic and/or Google AI |

### Setup

```bash
git clone https://github.com/yourusername/DataExtractor_Noora.git
cd DataExtractor_Noora
pip install -r requirements.txt

# Pull the local vision model (if using local mode)
ollama pull qwen2.5vl:3b

# Configure
cp .env.example .env
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
│   └── converter.py             # Docling PDF to Markdown + images
├── models/
│   ├── router.py                # Vision model routing (local/cloud)
│   ├── local.py                 # Ollama VLM connector
│   ├── cloud.py                 # Claude & Gemini connectors
│   └── exceptions.py            # Custom error types
├── extraction/
│   ├── engine.py                # Extraction orchestration
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
| `CLOUD_PROVIDER` | `anthropic` | `anthropic` or `gemini` |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Claude model ID |
| `GEMINI_MODEL` | `gemini-2.5-pro-exp-03-25` | Gemini model ID |
| `DEFAULT_CORR` | `0.5` | Default correlation coefficient for SD imputation |
| `TESSERACT_CMD` | `tesseract` | Tesseract OCR executable path |

---

## Output

After running, results are written to `./output/`:

```
output/
├── markdown/{study_name}/       # High-fidelity Markdown conversion
├── extracted_images/{study_name}/  # Figures and graphs from PDF
└── results/
    ├── {study_name}_extraction.json   # Structured extraction data
    ├── {study_name}_graphs.json       # Graph-specific data (if present)
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
