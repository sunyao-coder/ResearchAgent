import asyncio
import os.path as osp

from app.config import PROJECT_ROOT, WORKSPACE_ROOT, get_config, init_config
from app.tool.extract_info_from_structured_paper import ExtractInfoTool
from app.tool.filtering_from_structured_paper import FilteringTool
from app.tool.generate_guidance_from_structured_paper import GenerateGuidanceTool

# from app.tool.get_structured_text import (
#     extract_texts_from_pdfs,
#     split_and_label_sentences,
# )


# def run_get_structured_text():
#     pdf_root = osp.join(WORKSPACE_ROOT, "raw_pdf")
#     mineru_output_root = osp.join(WORKSPACE_ROOT, "mineru_output")
#     structured_root = osp.join(WORKSPACE_ROOT, "structured_text_test")
#     structured_text_root = osp.join(structured_root, "text")
#     labeled_sentences_root = osp.join(structured_root, "labeled_sentences")

#     # Step 1: Extract texts from PDFs
#     extract_texts_from_pdfs(pdf_root, mineru_output_root)

#     # Step 2: Split and label sentences
#     split_and_label_sentences(
#         mineru_output_root, structured_text_root, labeled_sentences_root
#     )


def run_extract_info_tool():
    tool = ExtractInfoTool()
    topic = "Fe single-atom catalysts"
    metrics = {
        "activity": "The indicator that reflects the catalytic potential activity of a catalyst, like half-wave potential.",
        "stability": "An indicator that can describe the duration stability of a catalyst, such as cycles or hours.",
    }
    structured_root = osp.join(WORKSPACE_ROOT, "structured_text")
    structured_text_root = osp.join(structured_root, "text")
    labeled_sentences_root = osp.join(structured_root, "labeled_sentences")
    output_root = osp.join(WORKSPACE_ROOT, "extract_info")

    asyncio.run(
        tool.execute(
            topic=topic,
            metrics=metrics,
            structured_text_root=structured_text_root,
            labeled_sentences_root=labeled_sentences_root,
            output_root=output_root,
        )
    )


def run_filtering_tool():
    tool = FilteringTool()

    extract_info_root = osp.join(WORKSPACE_ROOT, "extract_info")
    output_root = osp.join(WORKSPACE_ROOT, "filtering")
    ratio = 1.0
    primary_filtering_thres = 0

    asyncio.run(
        tool.execute(
            src_extract_info_root=extract_info_root,
            output_root=output_root,
            ratio=ratio,
            primary_filtering_thres=primary_filtering_thres,
        )
    )


def run_generate_guidance_tool():
    tool = GenerateGuidanceTool()
    topic = "Key factors in designing efficient Fe single-atom catalysts"
    structured_text_root = osp.join(WORKSPACE_ROOT, "structured_text", "text")
    labeled_sentences_root = osp.join(
        WORKSPACE_ROOT, "structured_text", "labeled_sentences"
    )
    output_root = osp.join(WORKSPACE_ROOT, "guidance")
    selected_file_info_path = osp.join(
        WORKSPACE_ROOT, "filtering", "overall_high_performance_papers.json"
    )

    asyncio.run(
        tool.execute(
            topic=topic,
            structured_text_root=structured_text_root,
            labeled_sentences_root=labeled_sentences_root,
            selected_file_info_path=selected_file_info_path,
            output_root=output_root,
        )
    )


if __name__ == "__main__":
    init_config("config.yaml")

    # Step 1. extract text from pdfs
    # run_get_structured_text()

    # Step 2. extract info from structured papers
    run_extract_info_tool()

    # Step 3. filtering from structured papers
    run_filtering_tool()

    # Step 4. generate guidance from structured papers
    run_generate_guidance_tool()
