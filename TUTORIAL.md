# DataExtractor_Noora — Beginner's Tutorial

A complete walkthrough for clinical researchers, systematic review teams, and meta-analysts on how to use this tool — with or without an AI agent — to accelerate data extraction from scientific PDFs.

---

## Table of Contents

1. [What This Tool Does](#1-what-this-tool-does)
2. [Installation Walkthrough (15 minutes)](#2-installation-walkthrough-15-minutes)
3. [Basic Usage: One PDF](#3-basic-usage-one-pdf)
4. [Understanding the Output](#4-understanding-the-output)
5. [Using Your Own Extraction Template](#5-using-your-own-extraction-template)
6. [Working with AI Agent Desktops](#6-working-with-ai-agent-desktops)
   - [Claude Code](#claude-code)
   - [GitHub Copilot / Codex](#github-copilot--codex)
   - [Cursor](#cursor)
   - [OpenCode](#opencode)
7. [Standard Operating Procedure (SOP)](#7-standard-operating-procedure-sop)
8. [Best Practices for Accuracy](#8-best-practices-for-accuracy)
9. [Troubleshooting](#9-troubleshooting)
10. [Prompt Templates for AI Agents](#10-prompt-templates-for-ai-agents)

---

## 1. What This Tool Does

DataExtractor_Noora converts a **PDF of a clinical study** into **structured, machine-readable data** suitable for systematic reviews and meta-analyses.

**The pipeline:**

```
PDF  ──►  Markdown + Images  ──►  AI Vision Model  ──►  JSON + Excel
  (Docling OCR)          (qwen/Claude/Gemini)     (biostatistics applied)
```

**What it extracts:**
- Continuous outcomes (mean, SD, N) — with change scores calculated automatically
- Dichotomous outcomes (events, total) — no percentages
- NCT trial numbers from ClinicalTrials.gov
- Graph/figure data from forest plots, bar charts, line graphs
- Population subgroup data and intervention arm details

**What it does NOT do (by design):**
- It does not perform the meta-analysis — it prepares the data for tools like RevMan, R (meta/metafor), or Python (pymeta)
- It does not make clinical judgements — it flags discrepancies and biases for you to review

---

## 2. Installation Walkthrough (15 minutes)

### Step 1: Install Python

Download Python 3.11 or later from [python.org](https://python.org). During installation on Windows, check **"Add Python to PATH"**.

Verify:
```bash
python --version
```

### Step 2: Install Tesseract OCR

Tesseract extracts text from scanned PDFs (images of text).

**Windows:** Download from [GitHub UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). Run installer. Default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`

**macOS:** `brew install tesseract`

**Linux:** `sudo apt install tesseract-ocr`

Verify:
```bash
tesseract --version
```

### Step 3: Install Ollama (for local mode — free, no API key needed)

Download from [ollama.ai](https://ollama.ai) and install.

Pull the vision model (3.8B parameters, ~3.2 GB):
```bash
ollama pull qwen2.5vl:3b
```

Verify:
```bash
ollama list
```

> **No GPU? No problem.** qwen2.5vl:3b runs reasonably on CPU (8-16 GB RAM). For faster extraction, use cloud mode instead.

### Step 4: Clone and configure DataExtractor_Noora

```bash
git clone https://github.com/yourusername/DataExtractor_Noora.git
cd DataExtractor_Noora
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` — for local mode, the defaults are fine. For cloud mode, add your API key:

```ini
VISION_MODE=cloud
CLOUD_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 5: Verify installation

```bash
python main.py --help
```

You should see the CLI help output with all available options.

---

## 3. Basic Usage: One PDF

### 3.1 Minimal command

```bash
python main.py my_study.pdf -v "age" "blood_pressure" "heart_rate"
```

This does the full pipeline: converts the PDF, sends it to the AI model with extraction instructions, and saves results to `./output/results/`.

### 3.2 Common extraction scenarios

**Extract specific outcomes for meta-analysis:**
```bash
python main.py trial.pdf -v "HbA1c_change" "fasting_glucose" "NCT"
```

**Filter to adults in the treatment arm:**
```bash
python main.py trial.pdf -v "BMI" "waist_circumference" --population "adults" --arm "treatment"
```

**Skip re-conversion (use existing markdown from a previous run):**
```bash
python main.py trial.pdf -v "SBP" --skip-ingestion
```

**Use cloud model for better accuracy (requires API keys):**
```bash
python main.py trial.pdf -v "QoL_score" "adverse_events" --mode cloud
```

**Skip graph processing (faster, if you don't need figure data):**
```bash
python main.py trial.pdf -v "mortality" --no-graphs
```

### 3.3 Real example

```bash
# Extract diabetes trial data
python main.py "NEJM_Diabetes_Trial_2024.pdf" \
  -v "HbA1c" "fasting_glucose" "BMI" "systolic_BP" "adverse_events" "NCT" \
  --population "adults" \
  --arm "intervention"
```

---

## 4. Understanding the Output

### Directory structure after a run

```
output/
├── markdown/StudyName/
│   └── StudyName.md          # Full text converted to Markdown
├── extracted_images/StudyName/
│   ├── fig_0001.png          # Figures from the PDF
│   ├── fig_0002.png
│   └── ...
└── results/
    ├── StudyName_extraction.json   # Main extraction result
    ├── StudyName_graphs.json       # Graph data (if graphs were found)
    └── StudyName_template_output.xlsx  # Template output (if --template used)
```

### JSON output structure

```json
{
  "study_id": "NEJM_Diabetes_Trial_2024",
  "nct_number": "NCT01234567",
  "sensitivity_analysis_needed": true,
  "warnings": [
    "MIXED: Both 'Change' and 'Post-intervention' data detected..."
  ],
  "arms": [
    {
      "label": "Metformin",
      "population": "adults",
      "continuous": [
        {
          "variable": "HbA1c",
          "n": 150,
          "mean": 7.2,
          "sd": 0.8,
          "data_type": "post",
          "mean_change": null,
          "sd_change": null
        }
      ],
      "dichotomous": [
        {
          "variable": "adverse_events",
          "events": 23,
          "total": 150,
          "risk": 0.153
        }
      ]
    }
  ]
}
```

### Key fields explained

| Field | Meaning |
|-------|---------|
| `n` | Sample size in this arm |
| `mean` | Mean value (post-intervention OR change, depending on `data_type`) |
| `sd` | Standard deviation |
| `data_type` | `"post"` = post-intervention, `"change"` = change-from-baseline, `"median_iqr"` = converted from median/IQR |
| `mean_change` | Explicitly reported change score (if available) |
| `sd_change` | Explicitly reported SD of change (if available) |
| `baseline_mean` | Baseline value (helps the engine calculate change) |
| `risk` | Events / Total for dichotomous outcomes |

---

## 5. Using Your Own Extraction Template

If your systematic review team uses a standardized extraction sheet (e.g., a Cochrane data collection form), you can populate it automatically.

### Step 1: Prepare your template

Create an Excel file with headers in row 1:

| Study_ID | SBP_Mean | SBP_SD | SBP_N | Mortality_Events | Mortality_Total |
|----------|----------|--------|-------|------------------|-----------------|

Leave the second row empty — it will be populated by the tool.

### Step 2: Run with template

```bash
python main.py trial.pdf -v "SBP" "death" -t template.xlsx --template-output populated.xlsx
```

### Step 3: What happens

1. The tool extracts "SBP" and "death" values from the PDF
2. It maps "SBP" → "SBP_Mean" (semantically, via the AI or heuristic fallback)
3. It creates `SBP_SD`, `SBP_N` columns automatically
4. It maps "death" → "Mortality" → populates `Mortality_Events` and `Mortality_Total`
5. If a column can't be matched, it writes **"Not Found"** with an Excel comment

### Template best practices

- Use **clear, consistent column names** that relate to common clinical terms
- Prefix columns that belong together: `HbA1c_Mean`, `HbA1c_SD`, `HbA1c_N`
- For dichotomous: `Outcome_Events`, `Outcome_Total`
- The `Study_ID` column is populated automatically
- Columns not in your template are ignored (no data loss)

---

## 6. Working with AI Agent Desktops

AI agent desktops (Claude Code, Codex CLI, Cursor, OpenCode) can run this tool on your behalf. Below are the prompts to give each agent.

### Claude Code

Claude Code (Anthropic's terminal agent) runs in your terminal. Use it to iterate on extractions without typing commands manually.

```
/init
```

Then:

```
Extract clinical data from all PDFs in ./papers/ using DataExtractor_Noora. 
For each PDF, extract: "SBP" "DBP" "heart_rate" "BMI" "HbA1c" "NCT". 
Use the template at ./template.xlsx and save results to ./results/.
Run in local mode. Show me a summary table of all extracted values.
```

**Power use — batch processing:**

```
Run DataExtractor_Noora on every PDF in ./papers/ in sequence. 
Skip any PDF that already has results in ./output/results/. 
Use --skip-ingestion if markdown already exists. 
After all extractions, merge the JSON results into a single CSV using Python pandas.
List any studies with warnings or sensitivity_analysis_needed=true.
```

**Power use — accuracy audit:**

```
For each PDF in ./papers/, run DataExtractor_Noora extraction, 
then verify the extracted HbA1c values against the original text 
by reading the markdown file. Report any discrepancies.
```

### GitHub Copilot / Codex

GitHub Copilot (in VS Code) or Codex CLI can run the tool via terminal commands:

```
@terminal Run DataExtractor_Noora on the latest RCT PDF.
Use variables: "age" "BMI" "SBP" "DBP" "total_cholesterol" "HDL" "LDL" "triglycerides" "NCT".
Use cloud mode with Claude. Save template output to screening_results.xlsx.
```

### Cursor

In Cursor's Composer (Ctrl/Cmd+I):

```
Run in terminal: python main.py "paper.pdf" -v "primary_outcome" "adverse_events" "NCT" -p "adults"
Then read the output JSON and give me a human-readable summary.
```

### OpenCode

OpenCode supports skills and can be prompted to use DataExtractor_Noora as part of a systematic review workflow:

```
Use DataExtractor_Noora to extract variables from all PDFs in the 
./data/pdfs directory. Apply the extraction template at ./templates/cohort_extraction.xlsx.
Output results to ./data/extracted/. After extraction, merge all results and 
flag any studies where sensitivity_analysis_needed is true.
```

---

## 7. Standard Operating Procedure (SOP)

Use this SOP for consistent, auditable data extraction across your systematic review.

### Phase 1: Preparation (30 min)

1. **Organize your PDFs** — Place all study PDFs in a single folder, named consistently: `Author_Year_Title.pdf`
2. **Prepare your extraction template** — Create an `.xlsx` with your review's column headers (see Section 5)
3. **Set mode** — Decide: local (free, slower) or cloud ($, faster, better accuracy)
4. **Configure `.env`** — Set mode, model, and API keys

### Phase 2: First-pass extraction (automated)

```bash
# Batch script example (save as batch_extract.py)
import subprocess, glob
pdfs = glob.glob("papers/*.pdf")
for pdf in pdfs:
    subprocess.run([
        "python", "main.py", pdf,
        "-v", "SBP", "DBP", "HbA1c", "LDL", "NCT",
        "-t", "template.xlsx",
        "--template-output", f"results/{Path(pdf).stem}_output.xlsx"
    ])
```

### Phase 3: Quality check (15 min per study)

1. **Check warnings** — Open the JSON output. Does `sensitivity_analysis_needed` = true? Are there bias warnings?
2. **Spot-check numbers** — Open the study PDF and verify 2-3 extracted values manually
3. **Review "Not Found" cells** — In the template output, columns marked "Not Found" may need manual extraction
4. **Check NCT numbers** — Verify against ClinicalTrials.gov if applicable

### Phase 4: Reconciliation

- **If sensitivity analysis is flagged:** Note this in your review protocol. Run the meta-analysis with and without the post-intervention studies.
- **If baselines are unequal:** Document the discrepancy. Consider adjusting or using change-from-baseline data only.
- **If values are missing:** Re-run with `--mode cloud` for better accuracy, or extract manually.

### Phase 5: Export for meta-analysis

The template output (`.xlsx`) can be loaded directly into:
- **RevMan** → Save as CSV, import
- **R (meta package)** → `read.csv("output.csv")`
- **Python (pymeta)** → `pandas.read_excel("output.xlsx")`

---

## 8. Best Practices for Accuracy

### Choosing your model

| Scenario | Recommended Model | Why |
|----------|-------------------|-----|
| No budget, strong hardware | Local (qwen2.5vl:3b) | Free, private, reasonable accuracy |
| Highest accuracy needed | Cloud (Claude 3.5 Sonnet) | Best at parsing complex tables |
| Budget-conscious cloud | Cloud (Gemini 2.5 Pro) | Good accuracy, competitive pricing |
| Sensitive data (local) | Local only | Data never leaves your machine |

### Maximizing extraction quality

1. **Be specific in your variables** — Not `"outcome"` but `"HbA1c_change_from_baseline"`. The AI understands context.
2. **Use population and arm filters** — Reduces noise from irrelevant study groups.
3. **Always include "NCT"** — It's a reliable anchor that helps the model locate the study metadata section.
4. **Prefer PDFs with selectable text** — Scanned PDFs still work (OCR handles them), but accuracy is higher with born-digital PDFs.
5. **Split large multi-arm studies** — If a study has 5+ arms, consider extracting in two passes with different `--arm` filters.
6. **Review the markdown output** — If the Docling conversion looks garbled, the extraction will be too. Check `./output/markdown/`.

### What to do when values are missing

| Issue | Likely cause | Fix |
|-------|-------------|-----|
| Values are null | AI model missed them in the text | Re-run with `--mode cloud` |
| Wrong values extracted | Table structure confused the model | Check markdown for table fidelity |
| Graph data missing | No graph images found | Check `./output/extracted_images/` |
| Population filter skipped everything | Filter string didn't match | Run without `--population` to see all arms |
| Template has "Not Found" everywhere | Variable names don't match column headers | Rename variables to be closer to column names |

---

## 9. Troubleshooting

### "model requires more system memory"

The qwen2.5vl:3b model needs ~8.4 GB RAM. Solutions:
- Close other applications
- Use a smaller model: change `.env` to `OLLAMA_MODEL=llama3.2-vision:11b` (if available) or `moondream:latest`
- Switch to cloud mode (`VISION_MODE=cloud`)
- Ensure Ollama is running: `ollama serve`

### "Tesseract not found"

- Windows: Add `Tesseract-OCR` to PATH or set `TESSERACT_CMD` in `.env` to the full path
- Verify: `tesseract --version`

### "No module named 'docling'"

Run: `pip install -r requirements.txt`

If issues persist, create a fresh virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### "API connection failed"

- For Claude: Verify `ANTHROPIC_API_KEY` is set correctly in `.env`
- For Gemini: Verify `GOOGLE_API_KEY` is set correctly
- Check internet connection
- Check API usage quotas/limits

### "No NCT number found"

Some studies don't register on ClinicalTrials.gov. The tool returns `null` for `nct_number`. This is normal.

### Output JSON is empty or minimal

- The document text might exceed the 80,000 character limit. Check `./output/markdown/` for completeness.
- Try `--mode cloud` which handles longer documents better.

---

## 10. Prompt Templates for AI Agents

Copy-paste these prompts into your AI agent desktop to automate specific tasks.

### Batch extraction with progress tracking

```
Run DataExtractor_Noora on every PDF in the folder ./papers/.
For each PDF, extract: "age" "sex" "BMI" "SBP" "DBP" "heart_rate" 
"total_cholesterol" "LDL" "HDL" "triglycerides" "fasting_glucose" 
"HbA1c" "eGFR" "creatinine" "NCT".

Use template at ./extraction_template.xlsx and save each output to 
./results/{filename}_extracted.xlsx.

After each PDF, print a one-line status: 
  "✓ filename — NCT: value — Arms: N — Warnings: N"
After all are done, print a summary table of all studies and their NCT numbers.
If any study has sensitivity_analysis_needed=true, flag it in red text.
```

### Quality audit pass

```
Read the extraction JSON files in ./output/results/ for every study.
For each study:
1. Read the corresponding markdown file in ./output/markdown/  
2. Check if the extracted HbA1c and SBP values match what's in the text
3. If the extraction says "data_type=change", verify the baseline and post values exist
4. If warnings include "unequal baselines", note the baseline values

Produce a single report table: Study | Variable | Extracted | In-text | Match?
```

### Template creation helper

```
I need to create an extraction template for a meta-analysis of 
blood pressure trials. My outcome variables are:
- Systolic BP (mean, SD, N) for intervention and control groups  
- Diastolic BP (mean, SD, N)
- Heart rate (mean, SD, N)
- Adverse events (events, total)
- Study ID and NCT number

Create an Excel file called bp_template.xlsx with appropriate 
column headers organized for easy mapping by DataExtractor_Noora.
Use the format Study_ID, then outcome columns with _Mean, _SD, _N, 
_Events, _Total suffixes.
```

### Post-extraction data merge (for multi-study meta-analysis)

```
All extraction results are in ./output/results/ as JSON files.
Merge them into a single CSV for meta-analysis.
Each row = one arm of one study.
Columns: study_id, nct, arm_label, population, 
         variable, n, mean, sd, data_type, 
         events, total, risk, warnings.

Save as merged_extraction.csv in the project root.
Print the number of studies and arms in the merged file.
```

### Forest plot digitization

```
For each image in ./output/extracted_images/StudyName/:
1. Identify if it's a forest plot
2. If yes, extract: author, year, effect_size, lower_CI, upper_CI, weight_pct
3. Note the pooled effect (diamond) values
4. Save as structured JSON

Use the graph extraction capability of DataExtractor_Noora 
(graph prompts already route images to the vision model).
```

---

## Quick Reference Card

```bash
# Basic
python main.py study.pdf -v "var1" "var2"

# All options
python main.py study.pdf \
  -v "var1" "var2" \            # Variables to extract
  -p "adults" \                  # Population filter
  -a "intervention" \            # Arm filter
  -t template.xlsx \             # Template export
  --template-output out.xlsx \   # Output path for template
  --mode cloud \                 # Model backend override
  --no-graphs \                  # Skip figure processing
  --skip-ingestion               # Reuse existing markdown

# Output locations
./output/markdown/{study}/{study}.md
./output/extracted_images/{study}/fig_*.png
./output/results/{study}_extraction.json
./output/results/{study}_template_output.xlsx
```
