CLINICAL_EXTRACTION_PROMPT = """You are a clinical data extraction specialist. Extract the following variables from the provided study document/images. Return your answer as structured JSON.

Extraction Guidelines:
1. DICHOTOMOUS OUTCOMES: Extract Event and Total numbers only. Do NOT extract percentages.
2. CONTINUOUS OUTCOMES: Extract Mean and SD. Note whether data is reported as change-from-baseline or post-intervention.
3. BASELINE DATA: Extract baseline Mean and SD when available.
4. MEDIAN/IQR: If only Median and IQR are reported, extract those and note sample size.
5. NCT NUMBERS: Look for ClinicalTrials.gov identifiers (NCTxxxxxxxx).
6. ARM/POPULATION: Identify all intervention arms and note which population/subgroup they apply to.
7. CHUNKED DOCUMENT: The text below is ONE CHUNK of a longer document (all chunks are processed in order, so the full study is covered). The chunk may start or end mid-section. Extract ONLY values explicitly present in this chunk's text. Never invent or estimate values. If nothing matches in this chunk, return an empty arms list.

User-defined extraction variables:
{variables_json}

Document chunk {chunk_context}:
{document_text}

Respond with JSON only in this format:
{{
  "nct_number": "NCTxxxxxxx or null",
  "arms": [
    {{
      "label": "Arm name",
      "population": "Specific population if applicable",
      "continuous": [
        {{
          "variable": "variable name",
          "n": number,
          "mean": number or null,
          "sd": number or null,
          "median": number or null,
          "q1": number or null,
          "q3": number or null,
          "baseline_mean": number or null,
          "baseline_sd": number or null,
          "post_mean": number or null,
          "post_sd": number or null,
          "mean_change": number or null,
          "sd_change": number or null,
          "data_type": "post" or "change" or "median_iqr",
          "source_page": page number or null
        }}
      ],
      "dichotomous": [
        {{
          "variable": "variable name",
          "events": number,
          "total": number,
          "source_page": page number or null
        }}
      ]
    }}
  ]
}}
"""


GRAPH_EXTRACTION_PROMPT = """You are a clinical data extractor specializing in reading forest plots, bar charts, and line graphs. Analyze the provided figure image and extract numerical data values visible on the plot.

For forest plots:
- Extract each study row (author, year, effect size, CI lower, CI upper, weight/events/total if shown)
- Identify the pooled effect estimate diamond

For bar/line charts:
- Extract group labels and corresponding values
- Note error bars (SD, SE, or CI) if present

Extract all visible numerical values precisely as they appear on the figure.

Tesseract OCR was run on this figure and captured embedded text (axis labels, tick values, data labels, in-figure table cells). Use this OCR text to VERIFY your reading of exact digits and labels. When your visual reading conflicts with the OCR text, prefer the value supported by the OCR text unless it is clearly a segmentation artifact.

OCR text from this figure:
{ocr_text}

User-defined extraction variables:
{variables_json}

Respond with JSON containing the extracted data points.
"""


TEMPLATE_MAPPING_PROMPT = """You are a data mapping specialist for systematic review extraction. Given a list of extracted variable names and a list of template column headers, semantically map each variable to the most appropriate column.

Rules:
- Match by meaning, not exact string. "Age" may map to "Participant_Mean_Age_Years".
- A single variable may map to multiple columns if the template separates values (e.g. "SBP_Intervention_Mean", "SBP_Control_Mean").
- If no meaningful match exists for a variable, return an empty string.
- Return ONLY a JSON object with variable names as keys and matched column names (or empty string) as values.

Variable names: {variable_names}
Template headers: {template_headers}

Respond with JSON only:
{{
  "variable_name_1": "Matched Column Name or ''",
  "variable_name_2": "Matched Column Name or ''"
}}
"""
