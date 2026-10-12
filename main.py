import argparse
import sys
from pathlib import Path
from typing import Optional

from config import settings
from ingestion.converter import DoclingConverter
from extraction.engine import ExtractionEngine
from models.router import get_available_backends
from export.template_exporter import export_to_template
from utils.helpers import logger, timestamp


def main():
    parser = argparse.ArgumentParser(
        description="DataExtractor_Noora - Clinical Data Extraction from Scientific PDFs"
    )
    parser.add_argument("pdf", type=str, help="Path to the input PDF file")
    parser.add_argument(
        "--variables", "-v", nargs="+", required=True,
        help="Variables to extract (e.g., 'age' 'blood_pressure' 'NCT number')",
    )
    parser.add_argument(
        "--population", "-p", type=str, default=None,
        help="Filter by specific population/subgroup (e.g., 'adults')",
    )
    parser.add_argument(
        "--arm", "-a", type=str, default=None,
        help="Filter by specific intervention arm",
    )
    parser.add_argument(
        "--no-graphs", action="store_true",
        help="Skip graph/figure image processing",
    )
    parser.add_argument(
        "--mode", type=str, choices=["local", "cloud"], default=None,
        help="Override vision model backend (local or cloud)",
    )
    parser.add_argument(
        "--skip-ingestion", action="store_true",
        help="Skip PDF ingestion and use existing markdown",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=35000,
        help="Max characters per document chunk for thorough end-to-end extraction (default: 35000)",
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=2000,
        help="Character overlap between consecutive chunks (default: 2000)",
    )
    parser.add_argument(
        "--template", "-t", type=str, default=None,
        help="Path to extraction template (.xlsx or .csv) for structured export",
    )
    parser.add_argument(
        "--template-output", type=str, default=None,
        help="Output path for template-populated file (default: ./output/results/{study}_template.xlsx)",
    )

    args = parser.parse_args()

    backends = get_available_backends()
    logger.info(f"Available backends: {[b.value for b in backends]}")

    if args.mode:
        settings.VISION_MODE = args.mode

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # Step 1: Ingest PDF to Markdown
    if args.skip_ingestion:
        md_path = settings.MARKDOWN_DIR / pdf_path.stem / f"{pdf_path.stem}.md"
        images_dir = settings.IMAGES_DIR / pdf_path.stem
        if not md_path.exists():
            logger.error(f"Skipped ingestion but no existing markdown at {md_path}")
            sys.exit(1)
        logger.info(f"Using existing markdown: {md_path}")
        pagemap_path = md_path.parent / f"{pdf_path.stem}_pagemap.json"
        pagemap_path = pagemap_path if pagemap_path.exists() else None
        figure_ocr_path = images_dir / f"{pdf_path.stem}_figure_ocr.json"
        figure_ocr_path = figure_ocr_path if figure_ocr_path.exists() else None
    else:
        logger.info("Step 1: Ingesting PDF to Markdown...")
        converter = DoclingConverter(pdf_path)
        md_path = Path(converter.convert())
        images_dir = converter.images_dir
        pagemap_path = converter.pagemap_path
        figure_ocr_path = converter.figure_ocr_path

    # Step 2: Extract clinical variables
    logger.info("Step 2: Extracting clinical variables...")
    engine = ExtractionEngine(
        md_path,
        images_dir,
        pagemap_path=pagemap_path,
        figure_ocr_path=figure_ocr_path,
    )
    result = engine.extract(
        variables=args.variables,
        population_filter=args.population,
        arm_filter=args.arm,
        process_graphs=not args.no_graphs,
        chunk_chars=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    # Step 3: Export results as JSON
    out_path = engine.export_results(result)

    # Step 4: Populate template if provided
    if args.template:
        template_path = Path(args.template)
        if not template_path.exists():
            logger.error(f"Template not found: {template_path}")
            sys.exit(1)
        template_out = (
            Path(args.template_output)
            if args.template_output
            else settings.RESULTS_DIR / f"{result.study_id}_template_output.xlsx"
        )
        logger.info("Step 4: Populating template with extracted data...")
        export_to_template(out_path, template_path, template_out)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Extraction Complete: {result.study_id}")
    print(f"{'='*60}")
    if result.nct_number:
        print(f"NCT Number: {result.nct_number}")
    print(f"Arms found: {len(result.arms)}")
    for arm in result.arms:
        print(f"  - {arm.label} (pop: {arm.population or 'all'})")
        for cd in arm.continuous:
            print(f"      Continuous: n={cd.n}, mean={cd.mean}, sd={cd.sd} [{cd.data_type}]")
        for dd in arm.dichotomous:
            print(f"      Dichotomous: events={dd.events}, total={dd.total}")
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  ! {w}")
    if result.sensitivity_analysis_needed:
        print(f"\n  *** SENSITIVITY ANALYSIS RECOMMENDED ***")
    print(f"\nResults saved to: {out_path}")
    if args.template:
        print(f"Template output: {template_out}")


if __name__ == "__main__":
    main()
