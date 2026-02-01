import asyncio
import itertools
import json
import os
import os.path as osp
import random
import re
import time
from typing import List, Optional, Set

import pdfplumber
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm_engine.exceptions import ToolError
from app.tool.base import BaseTool, ToolResult
from app.tool.utils import get_files, load_json, save_json, save_txt


class FilteringTool(BaseTool):

    name: str = "filtering"
    description: str = """
    The filtering tool used to filter high-performance papers from extracted information. It can filter based on different metrics and thresholds.
    """

    async def execute(
        self,
        src_extract_info_root: str,
        output_root: str,
        ratio: float = 0.4,
        primary_filtering_thres: int = 10,
    ):
        self.preprocess(
            overall_metrics_root=osp.join(src_extract_info_root, "overall_metrics"),
            individual_metrics_root=osp.join(
                src_extract_info_root, "individual_metrics"
            ),
            output_root=output_root,
        )

        metrics_info_root = osp.join(output_root, "overall_metrics")
        individual_metrics_root = osp.join(output_root, "individual_metrics")
        await self.primary_filtering(
            individual_metrics_root=individual_metrics_root,
            metrics_info_root=metrics_info_root,
            output_root=output_root,
            num_thres=primary_filtering_thres,
        )
        # Get high-performance papers based on metrics
        await self.get_high_performance_papers(
            metrics_info_root=metrics_info_root,
            to_process_content_file=osp.join(output_root, "to_process_content.json"),
            metric_type_list_file=osp.join(output_root, "metric_type_list.json"),
            output_root=output_root,
            ratio=ratio,
        )

    async def random_select(self, num: int, pdf_list: List[str]) -> List[str]:
        """
        Randomly select a subset of PDF files from a list.

        :param num: Number of files to select.
        :param pdf_list: List of PDF file paths.
        :return: List of selected PDF file paths.
        """
        if num > len(pdf_list):
            raise ToolError("Number of files to select exceeds available files.")
        return random.sample(pdf_list, num)

    async def get_high_performance_papers(
        self,
        metrics_info_root: str,
        to_process_content_file: str,
        metric_type_list_file: str,
        output_root: str,
        ratio: float,
    ):
        overall_metrics_files = get_files(metrics_info_root, extension=".json")
        overall_metrics = {}
        overall_metrics_value_preference = {}
        for file in overall_metrics_files:
            metric_type = os.path.basename(file).split(".")[0]
            categories = load_json(file)
            index_name_mapping = {}
            index_preference_mapping = {}
            for category_info in categories:
                index_name_mapping[category_info["index"]] = category_info["type"]
                index_preference_mapping[category_info["index"]] = category_info[
                    "better_direction"
                ]
            overall_metrics_value_preference[metric_type] = index_preference_mapping
            overall_metrics[metric_type] = index_name_mapping

        to_process_content = load_json(to_process_content_file)
        metric_type_list = load_json(metric_type_list_file)

        overall_high_performance_papers = {}

        for metric_combination_name, papers_info in to_process_content.items():
            metric_indices = metric_combination_name.split("_")

            comb_high_performance_papers = None

            for metric_type, metric_index in zip(metric_type_list, metric_indices):
                metric_index = int(metric_index)
                metric_category = overall_metrics[metric_type][metric_index]
                metric_value_array = []
                for paper, paper_metric_info in papers_info.items():
                    paper_metric_value = paper_metric_info[metric_category]
                    metric_value_array.append(paper_metric_value)
                if not metric_value_array:
                    continue
                if (
                    overall_metrics_value_preference[metric_type][metric_index]
                    == "higher"
                ):
                    metric_thres_value = sorted(metric_value_array)[
                        min(
                            int(len(metric_value_array) * ratio),
                            len(metric_value_array) - 1,
                        )
                    ]
                elif (
                    overall_metrics_value_preference[metric_type][metric_index]
                    == "lower"
                ):
                    metric_thres_value = sorted(metric_value_array)[
                        int(len(metric_value_array) * (1 - ratio))
                    ]
                else:
                    raise ToolError(
                        f"Invalid metric preference: {overall_metrics_value_preference[metric_type][metric_index]}"
                    )
                high_performance_papers = set()
                for paper, paper_metric_info in papers_info.items():
                    paper_metric_value = paper_metric_info[metric_category]
                    if (
                        overall_metrics_value_preference[metric_type][metric_index]
                        == "higher"
                    ):
                        if paper_metric_value >= metric_thres_value:
                            high_performance_papers.add(paper)
                    elif (
                        overall_metrics_value_preference[metric_type][metric_index]
                        == "lower"
                    ):
                        if paper_metric_value <= metric_thres_value:
                            high_performance_papers.add(paper)
                    else:
                        raise ToolError(
                            f"Invalid metric preference: {overall_metrics_value_preference[metric_type][metric_index]}"
                        )
                if comb_high_performance_papers is None:
                    comb_high_performance_papers = high_performance_papers
                else:
                    comb_high_performance_papers = (
                        comb_high_performance_papers.intersection(
                            high_performance_papers
                        )
                    )
            if comb_high_performance_papers is None:
                comb_high_performance_papers = set()
            overall_high_performance_papers[metric_combination_name] = list(
                comb_high_performance_papers
            )
        # save the high performance papers
        save_json(
            osp.join(output_root, "overall_high_performance_papers.json"),
            overall_high_performance_papers,
        )

    def preprocess(
        self,
        overall_metrics_root: str,
        individual_metrics_root: str,
        output_root: str,
    ):

        metric_files = get_files(overall_metrics_root, extension=".json")

        for metric_f in metric_files:
            metric_name = os.path.basename(metric_f).split(".")[0]

            metric_overall_info_save_path = osp.join(
                output_root, "overall_metrics", metric_name + ".json"
            )
            if not osp.exists(metric_overall_info_save_path):
                os.makedirs(osp.dirname(metric_overall_info_save_path), exist_ok=True)
                generated_metrics_info = load_json(metric_f)
                generated_metrics = generated_metrics_info["generated_metrics"]

                count = 0
                metric_reorg = []
                for metric_type, metric_info in generated_metrics.items():
                    count += 1
                    metric_reorg.append(
                        {
                            "index": count + 0,
                            "better_direction": metric_info["better_direction"],
                            "description": metric_info["description"],
                            "type": metric_type,
                            "abbreviation": metric_info["abbreviation"],
                            "unit": metric_info["unit"],
                        }
                    )
                save_json(metric_overall_info_save_path, metric_reorg)

            metric_reorg = load_json(metric_overall_info_save_path)
            index_name_mapping = {}
            for metric_info in metric_reorg:
                index_name_mapping[metric_info["type"]] = metric_info["index"]

            metric_individual_save_root = osp.join(
                output_root, "individual_metrics", metric_name
            )

            if not osp.exists(metric_individual_save_root):
                os.makedirs(metric_individual_save_root)

            for f in get_files(osp.join(individual_metrics_root, metric_name)):
                paper_name_ele = os.path.basename(f).split(".")[:-1]
                paper_name = ".".join(paper_name_ele)
                output_file = osp.join(
                    metric_individual_save_root, f"{paper_name}.json"
                )
                if osp.exists(output_file):
                    continue

                paper_info = load_json(f)

                # check analyze result
                paper_metric_reflect_result = paper_info[
                    "metric_analyze_reflect_result"
                ]

                if not (
                    paper_metric_reflect_result["valid_group"] == "A"
                    and paper_metric_reflect_result["metric_value"]
                ):
                    continue

                paper_metric_analyze_result = paper_info["metric_analyze_result"][
                    "positive"
                ]

                paper_metric_type = paper_metric_analyze_result["metric_type"]
                paper_metric_value = paper_metric_analyze_result["metric_value"]

                paper_metric_index = index_name_mapping.get(paper_metric_type)

                save_json(
                    output_file,
                    {
                        "type_index": paper_metric_index,
                        "metric_value": paper_metric_value,
                    },
                )

    async def primary_filtering(
        self,
        individual_metrics_root: str,
        metrics_info_root: str,
        output_root: str,
        num_thres: int = 50,
    ):
        overall_metrics_files = get_files(metrics_info_root, extension=".json")
        overall_metrics = {}
        for file in overall_metrics_files:
            metric_name = os.path.basename(file).split(".")[0]
            categories = load_json(file)
            index_name_mapping = {}
            for category_info in categories:
                index_name_mapping[category_info["index"]] = category_info["type"]
            overall_metrics[metric_name] = index_name_mapping

        # Count the number of papers in each metric, and filter based on the threshold

        filtered_metric_papers = {}

        print(overall_metrics)

        for metric_name in overall_metrics.keys():
            filtered_metric_papers[metric_name] = {}
            metric_root = osp.join(individual_metrics_root, metric_name)
            metric_count_dict = {}
            # metric_index_name_mapping = overall_metrics[metric_name]
            # error_list = []
            for file in get_files(metric_root):
                # paper_name = os.path.basename(file).split(".")[0]
                paper_name_ele = os.path.basename(file).split(".")[:-1]
                paper_name = ".".join(paper_name_ele)
                paper_info = load_json(file)
                if paper_info and paper_info.get("type_index") is not None:
                    paper_metric_index = paper_info["type_index"]

                    if paper_metric_index not in metric_count_dict:
                        metric_count_dict[paper_metric_index] = {}
                    if paper_info["metric_value"] is not None:
                        metric_count_dict[paper_metric_index][paper_name] = paper_info[
                            "metric_value"
                        ]

            for metric_index, papers in metric_count_dict.items():
                if len(papers) > num_thres:
                    filtered_metric_papers[metric_name][metric_index] = papers

                print(
                    f"Metric: {metric_name}, Index: {metric_index}, Number of papers: {len(papers)}"
                )

        # iterate all combinations of metrics

        metric_type_list = list(filtered_metric_papers.keys())
        metric_combination_list = {}

        metrics_list = []
        for metric_type in metric_type_list:
            metrics_list.append(map(str, filtered_metric_papers[metric_type].keys()))

        for metric_combination in itertools.product(*metrics_list):
            metric_combination_name = "_".join(metric_combination)
            metric_combination_list[metric_combination_name] = []

            metric_combination_papers = None
            for i, metric_index in enumerate(metric_combination):
                metric_type = metric_type_list[i]
                metric_papers = filtered_metric_papers[metric_type][
                    int(metric_index)
                ].keys()
                if metric_combination_papers is None:
                    metric_combination_papers = set(metric_papers)
                else:
                    metric_combination_papers = metric_combination_papers.intersection(
                        set(metric_papers)
                    )
            metric_combination_list[metric_combination_name] = list(
                metric_combination_papers
            )

        to_process_content = {}
        for metric_combination, papers in metric_combination_list.items():
            to_process_content[metric_combination] = {}

            metric_indices = metric_combination.split("_")
            for i, metric_index in enumerate(metric_indices):
                metric_type = metric_type_list[i]
                metric_category = overall_metrics[metric_type][int(metric_index)]
                if metric_combination not in to_process_content:
                    to_process_content[metric_combination] = {}

                for paper in papers:
                    paper_metric_value = filtered_metric_papers[metric_type][
                        int(metric_index)
                    ][paper]
                    if paper not in to_process_content[metric_combination]:
                        to_process_content[metric_combination][paper] = {}

                    to_process_content[metric_combination][paper][
                        metric_category
                    ] = paper_metric_value

        # save the metric combination list
        save_json(osp.join(output_root, "to_process_content.json"), to_process_content)
        save_json(osp.join(output_root, "metric_type_list.json"), metric_type_list)
