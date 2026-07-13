import json
import re
from pathlib import Path
from typing import Optional

from config import settings
from extraction.biostatistics import (
    Arm,
    ContinuousData,
    DichotomousData,
    ExtractionResult,
    convert_median_iqr_to_mean_sd,
)
from extraction.prompts import CLINICAL_EXTRACTION_PROMPT, GRAPH_EXTRACTION_PROMPT
from models.router import query_vision_model
from utils.helpers import logger, save_json


class ExtractionEngine:
    def __init__(self, markdown_path: str | Path, images_dir: str | Path):
        self.markdown_path = Path(markdown_path)
        self.images_dir = Path(images_dir)
        if not self.markdown_path.exists():
            raise FileNotFoundError(f"Markdown not found: {self.markdown_path}")
        self.doc_text = self.markdown_path.read_text(encoding="utf-8")

    def extract(
        self,
        variables: list[str],
        population_filter: Optional[str] = None,
        arm_filter: Optional[str] = None,
        process_graphs: bool = True,
    ) -> ExtractionResult:
        result = ExtractionResult(
            study_id=self.markdown_path.stem,
            population_filter=population_filter,
        )
        nct = self._find_nct(self.doc_text)
        if nct:
            result.nct_number = nct
            logger.info(f"NCT found: {nct}")

        logger.info("Sending document to extraction model...")
        variables_str = json.dumps(variables, indent=2)
        prompt = CLINICAL_EXTRACTION_PROMPT.format(
            variables_json=variables_str,
            document_text=self.doc_text[:80000],
        )
        response = query_vision_model(prompt)
        parsed = self._parse_json_response(response)
        if parsed and "arms" in parsed:
            self._populate_arms(parsed, result, population_filter, arm_filter)
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

    def _process_graphs(self, variables_str: str) -> Optional[dict]:
        graph_files = list(self.images_dir.glob("*"))
        if not graph_files:
            logger.info("No graph images found to process")
            return None

        logger.info(f"Processing {len(graph_files)} graph images...")
        prompt = GRAPH_EXTRACTION_PROMPT.format(variables_json=variables_str)
        response = query_vision_model(prompt, graph_files)
        parsed = self._parse_json_response(response)
        if parsed:
            graph_path = settings.RESULTS_DIR / f"{self.markdown_path.stem}_graphs.json"
            save_json(parsed, graph_path)
            logger.info(f"Graph data saved to {graph_path}")
        return parsed

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
                            "variable": cd.group_label,
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
                            "variable": dd.group_label,
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
