import asyncio
import json
import os
import os.path as osp
import re
import time
from functools import partial
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm_engine.llm import LLM
from app.logger import logger
from app.prompts.extract_info_from_structured_paper import (
    INDIVIDUAL_METRIC_ANALYSIS_PROMPT,
    INDIVIDUAL_METRIC_ANALYSIS_REFLECT_PROMPT,
    METRIC_INFO_EXTRACT_PROMPT,
    METRIC_INFO_EXTRACT_REFLECT_PROMPT,
    METRIC_TYPE_GENERATION_PROMPT,
    METRIC_TYPE_GENERATION_REFLECT_PROMPT,
    TOPIC_RELEVANCE_PROMPT,
)
from app.llm_engine.schema import Message, ToolChoice
from app.tool.base import BaseTool, ToolResult
from app.tool.extract_info_utils import (
    check_individual_metric_analysis_reflect_result,
    check_individual_metric_analysis_result,
    check_metric_sample_reflect_result,
    check_sample_reflect_result,
    extract_brace_content,
    format_extracted_info,
    format_genereted_metrics,
    generate_extracted_info_sample_pair,
    generate_individual_metric_analysis_sample_pair,
    generate_metric_sample_pair,
    get_metric_overall_text,
    get_valid_metric_info,
)
from app.tool.utils import (
    convert_str_to_dict,
    get_files,
    load_json,
    save_json,
)

semaphore = asyncio.Semaphore(125)


class ExtractInfoTool(BaseTool):
    """"""

    name: str = "extract_info"
    description: str = """
    Extract information from research papers based on given metrics.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Topic to check relevance against.",
            },
            "metrics": {
                "type": "array",
                "description": "List of metrics to extract from research papers.",
            },
            "structured_text_root": {
                "type": "string",
                "description": "Root directory containing structured text files.",
            },
            "labeled_sentences_root": {
                "type": "string",
                "description": "Root directory containing labeled sentences.",
            },
            "output_root": {
                "type": "string",
                "description": "Number of search results to analyze per search (1-20). Default is 5.",
            },
        },
        "required": [
            "topic",
            "metrics",
            "structured_text_root",
            "labeled_sentences_root",
            "output_root",
        ],
    }

    # Dependency injection for easier testing
    retrieval_llm: LLM = Field(default_factory=partial(LLM, usage="retrieval"))
    reasoning_llm: LLM = Field(default_factory=partial(LLM, usage="reasoning"))

    async def execute(
        self,
        topic: str,
        metrics: Dict[str, str],
        structured_text_root: str,
        labeled_sentences_root: str,
        output_root: str,
    ):

        # Step 1. get metric info from structured papers
        papers = get_files(structured_text_root)
        metrics_info_root = osp.join(output_root, "metrics_info")
        os.makedirs(metrics_info_root, exist_ok=True)

        tasks = []
        batch_size = 50
        batch_count = 0

        for i, paper_path in enumerate(papers):
            paper_file = paper_path.split("/")[-1]
            file_name_ele = paper_file.split(".")[:-1]
            file_name = ".".join(file_name_ele)

            labeled_sentences = load_json(
                osp.join(labeled_sentences_root, f"{file_name}.json")
            )
            structured_paper = load_json(osp.join(structured_text_root, paper_file))
            output_path = osp.join(metrics_info_root, f"{file_name}.json")

            if not osp.exists(output_path):
                task = self._extract_metric_info_from_structured_paper(
                    topic=topic,
                    metrics=metrics,
                    structured_paper=structured_paper,
                    labeled_sentences=labeled_sentences,
                    output_path=output_path,
                )
                tasks.append(task)
                batch_count += 1
                if batch_count >= batch_size:
                    await asyncio.gather(*tasks)
                    tasks = []
                    batch_count = 0

        if tasks:
            await asyncio.gather(*tasks)

        for metric, metrics_description in metrics.items():
            # Step 2. generate overall metrics
            overall_metrics_root = osp.join(output_root, "overall_metrics")
            os.makedirs(overall_metrics_root, exist_ok=True)
            await self._generate_metrics(
                metric_name=metric,
                metric_description=metrics_description,
                extract_info_root=metrics_info_root,
                labeled_sentences_root=labeled_sentences_root,
                output_root=overall_metrics_root,
            )

            # Step 3. process individual metrics
            individual_metrics_root = osp.join(
                output_root, "individual_metrics", metric
            )
            os.makedirs(individual_metrics_root, exist_ok=True)
            await self._process_metrics(
                metric_name=metric,
                metric_description=metrics_description,
                extract_info_root=metrics_info_root,
                labeled_sentences_root=labeled_sentences_root,
                metric_info_file=osp.join(overall_metrics_root, f"{metric}.json"),
                output_root=individual_metrics_root,
            )

    async def _check_topic_relevance(
        self, topic: str, structured_paper: List, output_path: str
    ):
        if not osp.exists(output_path):
            """Check if the structured paper is relevant to the topic."""
            content = TOPIC_RELEVANCE_PROMPT.format(
                topic=topic, paper_content=json.dumps(structured_paper[:10])
            )
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "check_topic_relevance",
                        "description": "Check if the structured paper is relevant to the topic.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "is_relevant": {
                                    "type": "boolean",
                                    "description": "Whether the structured paper is relevant to the topic.",
                                }
                            },
                            "required": ["is_relevant"],
                        },
                    },
                }
            ]

            for i in range(10):
                try:

                    response = await self.retrieval_llm.ask_tool(
                        [{"role": "user", "content": content}],
                        tools=tools,
                        tool_choice=ToolChoice.REQUIRED,
                        stream=True,
                    )

                    if (
                        response
                        and response.tool_calls
                        and len(response.tool_calls) > 0
                    ):
                        tool_call = response.tool_calls[0]
                        arguments = json.loads(tool_call.function.arguments)
                        is_relevant = arguments.get("is_relevant", False)
                        save_json(output_path, {"is_relevant": is_relevant})
                        break
                except Exception as e:
                    logger.error(f"Error during LLM call: {e}")
                    asyncio.sleep(1)
                    continue

    async def _generate_metric_calling(
        self,
        metric_name: str,
        metric_description: str,
        overall_metric_info: list,
        overall_metric_dict: dict,
        doi_mapping: dict,
        retry: int = 10,
    ):
        metric_info = {metric_name: metric_description}
        generate_prompt = METRIC_TYPE_GENERATION_PROMPT.format(
            metric=json.dumps(metric_info)
        )

        system_message = Message.system_message(generate_prompt)
        user_message = Message.user_message(
            "Extracted metric information: {overall_metric_info}".format(
                overall_metric_info=json.dumps(overall_metric_info)
            )
        )
        sample_pair = {}
        for i in range(retry):
            try:
                response = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if response:
                    response = extract_brace_content(response)
                    response = convert_str_to_dict(response)
                    if response:
                        response, sample_pair = format_genereted_metrics(
                            response, doi_mapping, overall_metric_dict
                        )
                        if response:
                            break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue
        return response, sample_pair

    async def _generate_metric_reflect(
        self,
        metric_name: str,
        generated_metrics: dict,
        sample_pair: dict,
        retry: int = 10,
    ):
        reflect_prompt = METRIC_TYPE_GENERATION_REFLECT_PROMPT.format(
            metric_type_content=json.dumps(generated_metrics),
        )

        system_message = Message.system_message(reflect_prompt)

        user_message = Message.user_message(
            "Sample pair: {sample_pair}".format(
                sample_pair=json.dumps(sample_pair),
            )
        )

        for i in range(retry):
            try:
                reflection = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if reflection:
                    reflection = extract_brace_content(reflection)
                    reflection = convert_str_to_dict(reflection)
                    if reflection and check_metric_sample_reflect_result(reflection):
                        break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue
        return reflection

    async def _generate_metrics(
        self,
        metric_name: str,
        metric_description: str,
        extract_info_root: str,
        labeled_sentences_root: str,
        output_root: str,
        retry: int = 10,
    ):
        save_path = osp.join(output_root, f"{metric_name}.json")
        if not osp.exists(save_path):

            # get extract_info from local path

            overall_metric_info, overall_metric_dict, doi_mapping = (
                get_metric_overall_text(
                    metric_name=metric_name,
                    extract_info_root=extract_info_root,
                    labeled_sentences_root=labeled_sentences_root,
                    num_thres=300,
                )
            )
            result = {}
            # if not osp.exists(save_path):
            finish_flag = False
            while not finish_flag:
                generated_metrics, sample_pair = await self._generate_metric_calling(
                    metric_name=metric_name,
                    metric_description=metric_description,
                    overall_metric_info=overall_metric_info,
                    overall_metric_dict=overall_metric_dict,
                    doi_mapping=doi_mapping,
                )
                # Save the generated metric description
                overall_reflect_result = {}
                finish_flag = True
                for metric_type, metric_type_info in generated_metrics.items():

                    reflect_result = await self._generate_metric_reflect(
                        metric_name=metric_type,
                        generated_metrics=metric_type_info,
                        sample_pair=sample_pair[metric_type],
                    )

                    if reflect_result:
                        if (
                            reflect_result["valid_group"] in ["None", "B"]
                            or not reflect_result["clarity_assessment"]
                            or not reflect_result["effectiveness_assessment"]
                        ):
                            finish_flag = False
                            break
                    overall_reflect_result[metric_type] = reflect_result

                if finish_flag:
                    result["overall_reflect_result"] = overall_reflect_result
                    result["generated_metrics"] = generated_metrics

                    # Save the generated metrics to a file
                    save_json(save_path, result)

    async def _process_metrics(
        self,
        metric_name: str,
        metric_description: str,
        extract_info_root: str,
        labeled_sentences_root: str,
        metric_info_file: str,
        output_root: str,
    ):
        """Process individual metrics for each paper."""

        # get extract_info from local path
        extract_info_files = get_files(extract_info_root)

        overall_metrics = load_json(metric_info_file)

        tasks = []
        batch_size = 50
        batch_count = 0
        for f in extract_info_files:
            file_name_ele = f.split("/")[-1].split(".")[:-1]
            file_name = ".".join(file_name_ele)
            task = self._process_individual_metrics(
                metric_name=metric_name,
                metric_description=metric_description,
                overall_metrics=overall_metrics,
                file_name=file_name,
                extract_info_root=extract_info_root,
                labeled_sentences_root=labeled_sentences_root,
                output_root=output_root,
            )
            tasks.append(task)

            batch_count += 1
            if batch_count >= batch_size:
                await asyncio.gather(*tasks)
                tasks = []
                batch_count = 0

        # Run all the created tasks concurrently
        if tasks:
            await asyncio.gather(*tasks)

    async def _generate_individual_metrics(
        self,
        metric_name: str,
        metric_description: str,
        metric_statement: str,
        overall_metrics: dict,
        retry: int = 10,
    ):
        """Generate individual metrics for each paper."""
        generate_prompt = INDIVIDUAL_METRIC_ANALYSIS_PROMPT.format(
            metric=json.dumps({metric_name: metric_description}),
            overall_metrics=json.dumps(overall_metrics),
        )

        system_message = Message.system_message(generate_prompt)
        user_message = Message.user_message(
            "Extracted metric information: {metric_statement}".format(
                metric_statement=metric_statement
            )
        )
        for i in range(retry):
            try:
                response = await self.reasoning_llm.ask(
                    messages=[user_message], system_msgs=[system_message], stream=True
                )
                if response:
                    response = extract_brace_content(response)
                    response = convert_str_to_dict(response)
                    if response and check_individual_metric_analysis_result(response):
                        break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue
        return response

    async def _reflect_generated_individual_metrics(
        self,
        metric_name: str,
        generated_metrics: dict,
        overall_metrics: dict,
        sample_pair: dict,
        retry: int = 10,
    ):
        reflect_prompt = INDIVIDUAL_METRIC_ANALYSIS_REFLECT_PROMPT.format(
            overall_metrics=json.dumps(overall_metrics)
        )

        system_message = Message.system_message(reflect_prompt)

        user_message = Message.user_message(
            "Generated metric information: {generated_metrics}, sample pair: {sample_pair}".format(
                generated_metrics=json.dumps(generated_metrics),
                sample_pair=json.dumps(sample_pair),
            )
        )
        for i in range(retry):
            try:
                reflection = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if reflection:
                    reflection = extract_brace_content(reflection)
                    reflection = convert_str_to_dict(reflection)
                    if reflection and check_individual_metric_analysis_reflect_result(
                        reflection
                    ):
                        break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue

        return reflection

    async def _process_individual_metrics(
        self,
        metric_name: str,
        metric_description: str,
        overall_metrics: dict,
        file_name: str,
        extract_info_root: str,
        labeled_sentences_root: str,
        output_root: str,
        retry: int = 10,
    ):
        save_path = osp.join(output_root, f"{file_name}.json")
        if osp.exists(save_path):
            return

        extract_info_file = osp.join(extract_info_root, f"{file_name}.json")
        extracted_info = load_json(extract_info_file)
        labeled_sentences_file = osp.join(labeled_sentences_root, f"{file_name}.json")
        labeled_sentences = load_json(labeled_sentences_file)
        labeled_sentences_dict = {}
        for sentence in labeled_sentences:
            for key, value in sentence.items():
                labeled_sentences_dict[key] = value
        valid_metric_info = get_valid_metric_info(
            metric_name=metric_name,
            extracted_info=extracted_info,
            labeled_sentences=labeled_sentences_dict,
        )
        if not valid_metric_info:
            return

        finish_flag = False
        count = 0
        while not finish_flag:
            generated_individual_metrics = await self._generate_individual_metrics(
                metric_name=metric_name,
                metric_description=metric_description,
                metric_statement=valid_metric_info["statement"],
                overall_metrics=overall_metrics,
            )

            if generated_individual_metrics:
                if (
                    generated_individual_metrics["positive"]["metric_type"]
                    != "not_available"
                ):
                    sample_pair = generate_individual_metric_analysis_sample_pair(
                        generated_individual_metrics, valid_metric_info
                    )
                    reflect_result = await self._reflect_generated_individual_metrics(
                        metric_name=metric_name,
                        generated_metrics=generated_individual_metrics,
                        overall_metrics=overall_metrics,
                        sample_pair=sample_pair,
                    )

                    if reflect_result["valid_group"] in ["None", "B"]:
                        finish_flag = False
                        count += 1
                        if count >= 3:
                            finish_flag = True
                    else:
                        finish_flag = True

                        save_content = {
                            "metric_analyze_result": generated_individual_metrics,
                            "metric_analyze_reflect_result": reflect_result,
                        }
                        save_json(save_path, save_content)
                else:
                    count += 1
                    if count >= 3:
                        finish_flag = True

    async def _extract_metric_info_calling(
        self,
        topic: str,
        metrics: Dict[str, str],
        structured_paper: List,
        labeled_sentences: Dict,
        retry: int = 10,
    ):
        extract_info_content = METRIC_INFO_EXTRACT_PROMPT.format(
            metrics=json.dumps(metrics),
        )

        system_message = Message.system_message(extract_info_content)
        user_message = Message.user_message(
            "Paper content: {paper_content}".format(
                paper_content=json.dumps(structured_paper)
            )[:60000]
        )

        formatted_extracted_info = {}
        sample_pair = {}

        for i in range(retry):
            try:
                extract_info_response = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if extract_info_response:
                    extract_info_response = extract_brace_content(extract_info_response)
                    extract_info_response = convert_str_to_dict(extract_info_response)

                    if extract_info_response:
                        formatted_extracted_info = format_extracted_info(
                            extract_info_response,
                            metrics.keys(),
                            labeled_sentences.keys(),
                        )

                        if formatted_extracted_info:
                            sample_pair = generate_extracted_info_sample_pair(
                                formatted_extracted_info, labeled_sentences
                            )
                            if sample_pair:
                                break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue

        return formatted_extracted_info, sample_pair

    async def _extract_metric_info_from_structured_paper(
        self,
        topic: str,
        metrics: Dict[str, str],
        structured_paper: List,
        labeled_sentences: List,
        output_path: str,
        retry: int = 2,
    ):
        if not osp.exists(output_path):
            labeled_sentence_dict = {}
            for sentence in labeled_sentences:
                for key, value in sentence.items():

                    labeled_sentence_dict[key] = value

            finish_flag = False
            process_count = 0

            extracted_info_result = {}

            while not finish_flag:
                formatted_extracted_info, sample_pair = (
                    await self._extract_metric_info_calling(
                        topic=topic,
                        metrics=metrics,
                        structured_paper=structured_paper,
                        labeled_sentences=labeled_sentence_dict,
                        retry=retry,
                    )
                )

                if not formatted_extracted_info:
                    process_count += 1
                    if process_count >= 10:
                        finish_flag = True
                    continue

                extracted_info_result["extracted_info"] = formatted_extracted_info

                reflect_result_dict = {}
                finish_flag = True
                for metric, extracted_info in sample_pair.items():
                    if (
                        extracted_info["A"]["best_performance"]["statement"]
                        != "not_available"
                    ):
                        reflect_result = await self._reflect_extracted_info_sample(
                            metric=metric,
                            extracted_info=extracted_info,
                            retry=retry,
                        )

                        reflect_result_dict[metric] = reflect_result
                        if reflect_result["valid_group"] in ["None", "B"]:
                            finish_flag = False

                process_count += 1
                if process_count >= 10:
                    finish_flag = True

                extracted_info_result["reflect_result"] = reflect_result_dict

                if finish_flag:
                    save_json(output_path, extracted_info_result)

    async def _reflect_extracted_info_sample(
        self, metric: str, extracted_info: dict, retry: int = 10
    ):
        positive_reflect_content = METRIC_INFO_EXTRACT_REFLECT_PROMPT.format(
            metric=metric,
        )
        system_message = Message.system_message(positive_reflect_content)

        user_message = Message.user_message(
            "Extracted info from paper: {extracted_info}".format(
                extracted_info=json.dumps(extracted_info)
            )
        )

        reflect_response = {}

        for i in range(retry):
            try:
                reflect_response = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if reflect_response:
                    reflect_response = extract_brace_content(reflect_response)
                    reflect_response = convert_str_to_dict(reflect_response)

                    if reflect_response and check_sample_reflect_result(
                        reflect_response
                    ):
                        break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue

        return reflect_response
