import json
import re
from pathlib import Path
from typing import Any, Optional

from config import settings
from extraction.biostatistics import (
    Arm,
    ContinuousData,
    DichotomousData,
    ExtractionResult,
    convert_median_iqr_to_mean_sd,
)
from extraction.chunker import DEFAULT_CHUNK_CHARS, DEFAULT_OVERLAP_CHARS, build_chunks
from extraction.prompts import CLINICAL_EXTRACTION_PROMPT, GRAPH_EXTRACTION_PROMPT
from models.exceptions import ModelQueryError
from models.router import query_vision_model
from utils.helpers import logger, save_json, load_json

CONTINUOUS_FIELDS = [
    "n",
    "mean",
    "sd",
    "median",
    "q1",
    "q3",
    "baseline_mean",
    "baseline_sd",
    "post_mean",
    "post_sd",
    "mean_change",
    "sd_change",
]

GRAPH_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


class ExtractionEngine:
    def __init__(
        self,
        markdown_path: str | Path,
        images_dir: str | Path,
        pagemap_path: Optional[str | Path] = None,
        figure_ocr_path: Optional[str | Path] = None,
    ):
        self.markdown_path = Path(markdown_path)
        self.images_dir = Path(images_dir)
        self.pagemap_path = Path(pagemap_path) if pagemap_path else None
        self.figure_ocr_path = Path(figure_ocr_path) if figure_ocr_path else None
        if not self.markdown_path.exists():
            raise FileNotFoundError(f"Markdown not found: {self.markdown_path}")
        self.doc_text = self.markdown_path.read_text(encoding="utf-8")

    def extract(
        self,
        variables: list[str],
        population_filter: Optional[str] = None,
        arm_filter: Optional[str] = None,
        process_graphs: bool = True,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        chunk_overlap: int = DEFAULT_OVERLAP_CHARS,
    ) -> ExtractionResult:
        result = ExtractionResult(
            study_id=self.markdown_path.stem,
            population_filter=population_filter,
        )
        nct = self._find_nct(self.doc_text)
        if nct:
            result.nct_number = nct
            logger.info(f"NCT found: {nct}")

        variables_str = json.dumps(variables, indent=2)
        chunks = build_chunks(
            self.doc_text,
            target_chars=chunk_chars,
            overlap_chars=chunk_overlap,
            pagemap_path=self.pagemap_path,
        )
        logger.info(
            f"Document ({len(self.doc_text)} chars) split into {len(chunks)} "
            f"chunks (target ~{chunk_chars} chars, overlap {chunk_overlap})"
        )

        parsed_chunks = []
        for chunk in chunks:
            logger.info(
                f"Processing chunk {chunk.context_label} "
                f"({len(chunk.text)} chars)..."
            )
            prompt = CLINICAL_EXTRACTION_PROMPT.format(
                variables_json=variables_str,
                chunk_context=chunk.context_label,
                document_text=chunk.text,
            )
            try:
                response = query_vision_model(prompt)
            except ModelQueryError as e:
                result.warnings.append(
                    f"Chunk {chunk.context_label} failed model query: {e}"
                )
                continue
            parsed = self._parse_json_response(response)
            if parsed is None:
                result.warnings.append(
                    f"Chunk {chunk.context_label} produced no valid JSON"
                )
                continue
            if parsed.get("arms"):
                parsed_chunks.append(parsed)

        if not parsed_chunks:
            result.warnings.append(
                "No extraction data returned from any chunk of the document."
            )

        merged = self._merge_arm_results(parsed_chunks)
        if merged.get("arms"):
            self._populate_arms(merged, result, population_filter, arm_filter)
            result.check_mixed_data_types()
            result.check_bias_unequal_baselines()
            result.warnings.extend(
                w for arm in result.arms for cd in arm.continuous for w in cd.warnings
            )

        if process_graphs:
            graph_data = self._process_graphs(variables_str)
            if graph_data:
                result.warnings.append(
                    "Graph/Figure data extracted separately - review for integration."
                )

        return result

    @staticmethod
    def _merge_arm_results(parsed_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        """Reduce step: merge per-chunk extractions, deduplicating repeated arms
        and variables while preferring the most complete entries."""
        arms_by_label: dict[str, dict[str, Any]] = {}
        for parsed in parsed_chunks:
            for arm_data in parsed.get("arms", []):
                label = arm_data.get("label") or "Unknown"
                if label not in arms_by_label:
                    arms_by_label[label] = {
                        "label": label,
                        "population": arm_data.get("population"),
                        "continuous": [],
                        "dichotomous": [],
                    }
                merged = arms_by_label[label]
                if arm_data.get("population") and not merged.get("population"):
                    merged["population"] = arm_data["population"]
                merged["continuous"].extend(arm_data.get("continuous", []))
                merged["dichotomous"].extend(arm_data.get("dichotomous", []))

        for arm in arms_by_label.values():
            arm["continuous"] = ExtractionEngine._dedupe_continuous(
                arm["continuous"]
            )
            arm["dichotomous"] = ExtractionEngine._dedupe_dichotomous(
                arm["dichotomous"]
            )
        return {"arms": [a for a in arms_by_label.values() if a["label"]]}

    @staticmethod
    def _completeness_score(cd: dict[str, Any]) -> int:
        return sum(1 for f in CONTINUOUS_FIELDS if cd.get(f) is not None)

    @staticmethod
    def _dedupe_continuous(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        for cd in entries:
            variable = (cd.get("variable") or "").strip().lower() or "unspecified"
            data_type = cd.get("data_type") or "post"
            key = (variable, data_type)
            if key not in best:
                best[key] = cd
                order.append(key)
            elif ExtractionEngine._completeness_score(cd) > ExtractionEngine._completeness_score(best[key]):
                best[key] = cd
        return [best[k] for k in order]

    @staticmethod
    def _dedupe_dichotomous(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for dd in entries:
            variable = (dd.get("variable") or "").strip().lower() or "unspecified"
            if variable not in best:
                best[variable] = dd
                order.append(variable)
            else:
                current = best[variable]
                if (dd.get("events", 0) + (dd.get("total") or 0)) > (
                    current.get("events", 0) + (current.get("total") or 0)
                ):
                    best[variable] = dd
        return [best[k] for k in order]

    def _populate_arms(
        self,
        parsed: dict,
        result: ExtractionResult,
        population_filter: Optional[str],
        arm_filter: Optional[str],
    ) -> None:
        for arm_data in parsed.get("arms", []):
            arm = Arm(
                label=arm_data.get("label", "Unknown"),
                population=arm_data.get("population"),
            )
            if population_filter and arm.population:
                if population_filter.lower() not in arm.population.lower():
                    logger.info(
                        f"Skipping arm '{arm.label}' - population filter mismatch"
                    )
                    continue
            if arm_filter and arm_filter.lower() not in arm.label.lower():
                logger.info(f"Skipping arm '{arm.label}' - arm filter mismatch")
                continue
            self._populate_continuous(arm, arm_data.get("continuous", []))
            self._populate_dichotomous(arm, arm_data.get("dichotomous", []))
            result.arms.append(arm)

    @staticmethod
    def _populate_continuous(arm: Arm, continuous_data: list[dict]) -> None:
        for cd in continuous_data:
            cont = ContinuousData(
                group_label=arm.label,
                n=cd.get("n", 0),
                variable=cd.get("variable"),
                mean=cd.get("mean"),
                sd=cd.get("sd"),
                median=cd.get("median"),
                q1=cd.get("q1"),
                q3=cd.get("q3"),
                baseline_mean=cd.get("baseline_mean"),
                baseline_sd=cd.get("baseline_sd"),
                post_mean=cd.get("post_mean"),
                post_sd=cd.get("post_sd"),
                mean_change=cd.get("mean_change"),
                sd_change=cd.get("sd_change"),
                data_type=cd.get("data_type", "post"),
                source_page=cd.get("source_page"),
            )
            if cont.data_type == "median_iqr" and cont.median is not None:
                cont.convert_median_iqr()
            cont.check_baseline_discrepancy()
            if cont.mean is None and cont.mean_change is None:
                cont.mean = cont.compute_mean_change()
            if cont.sd is None and cont.sd_change is None:
                cont.sd = cont.compute_sd_change()
            arm.continuous.append(cont)

    @staticmethod
    def _populate_dichotomous(arm: Arm, dichotomous_data: list[dict]) -> None:
        for dd in dichotomous_data:
            dich = DichotomousData(
                group_label=arm.label,
                events=dd.get("events", 0),
                total=dd.get("total", 0),
                variable=dd.get("variable"),
                source_page=dd.get("source_page"),
            )
            arm.dichotomous.append(dich)

    @staticmethod
    def _find_nct(text: str) -> Optional[str]:
        match = re.search(r"NCT\d{8}", text)
        return match.group(0) if match else None

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if not json_match:
            return None
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from model response: {e}")
            return None

    def _load_figure_ocr(self) -> dict[str, str]:
        if (
            self.figure_ocr_path is None
            or not self.figure_ocr_path.exists()
        ):
            return {}
        try:
            data = load_json(self.figure_ocr_path)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Could not read figure OCR data: {e}")
            return {}

    def _process_graphs(self, variables_str: str) -> Optional[dict]:
        graph_files = sorted(
            f
            for f in self.images_dir.glob("*")
            if f.is_file() and f.suffix.lower() in GRAPH_IMAGE_EXTENSIONS
        )
        if not graph_files:
            logger.info("No graph images found to process")
            return None

        figure_ocr = self._load_figure_ocr()
        ocr_count = sum(1 for f in graph_files if figure_ocr.get(f.name))
        logger.info(
            f"Processing {len(graph_files)} graph images "
            f"({ocr_count} with OCR grounding text)..."
        )

        figures: list[dict[str, Any]] = []
        for fig in graph_files:
            ocr_text = figure_ocr.get(fig.name) or "(no OCR text captured)"
            prompt = GRAPH_EXTRACTION_PROMPT.format(
                variables_str=variables_str,
                ocr_text=ocr_text,
            )
            try:
                response = query_vision_model(prompt, [fig])
            except ModelQueryError as e:
                logger.warning(f"Graph extraction failed for {fig.name}: {e}")
                figures.append({"figure": fig.name, "error": str(e)})
                continue
            parsed = self._parse_json_response(response)
            if parsed:
                if isinstance(parsed, dict):
                    parsed.setdefault("figure", fig.name)
                    figures.append(parsed)
            else:
                logger.warning(f"No valid JSON extracted from figure {fig.name}")
                figures.append({"figure": fig.name, "error": "no valid JSON in response"})

        if not figures:
            return None

        graph_path = settings.RESULTS_DIR / f"{self.markdown_path.stem}_graphs.json"
        save_json({"figures": figures}, graph_path)
        logger.info(f"Graph data saved to {graph_path}")
        return {"figures": figures}

    def export_results(self, result: ExtractionResult) -> Path:
        output = {
            "study_id": result.study_id,
            "nct_number": result.nct_number,
            "population_filter": result.population_filter,
            "sensitivity_analysis_needed": result.sensitivity_analysis_needed,
            "warnings": result.warnings,
            "arms": [
                {
                    "label": arm.label,
                    "population": arm.population,
                    "continuous": [
                        {
                            "variable": cd.variable or cd.group_label,
                            "n": cd.n,
                            "mean": cd.mean,
                            "sd": cd.sd,
                            "median": cd.median,
                            "q1": cd.q1,
                            "q3": cd.q3,
                            "baseline_mean": cd.baseline_mean,
                            "baseline_sd": cd.baseline_sd,
                            "post_mean": cd.post_mean,
                            "post_sd": cd.post_sd,
                            "mean_change": cd.mean_change,
                            "sd_change": cd.sd_change,
                            "data_type": cd.data_type,
                            "source_page": cd.source_page,
                            "warnings": cd.warnings,
                        }
                        for cd in arm.continuous
                    ],
                    "dichotomous": [
                        {
                            "variable": dd.variable or dd.group_label,
                            "events": dd.events,
                            "total": dd.total,
                            "risk": dd.risk,
                            "source_page": dd.source_page,
                        }
                        for dd in arm.dichotomous
                    ],
                }
                for arm in result.arms
            ],
        }
        out_path = settings.RESULTS_DIR / f"{result.study_id}_extraction.json"
        save_json(output, out_path)
        logger.info(f"Extraction results saved to {out_path}")
        return out_path
