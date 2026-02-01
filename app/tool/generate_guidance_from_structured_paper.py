import asyncio
import json
import os
import os.path as osp
import re
import time
from functools import partial
from typing import List, Optional, Set

import matplotlib.pyplot as plt
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm_engine.llm import LLM
from app.logger import logger
from app.prompts.generate_guidance_from_structured_paper import (
    GUIDANCE_GENERATION_PROMPT,
    IN_DEPTH_ANALYSIS_PROMPT,
    INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT,
    REFLECT_GUIDANCE_PROMPT,
    REFLECT_IN_DEPTH_ANALYSIS_PROMPT,
    REFLECT_INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT,
)
from app.llm_engine.schema import Message, ToolChoice
from app.tool.base import BaseTool, ToolResult
from app.tool.generate_guidance_utils import (
    check_generated_guidance_reflect_result,
    check_in_depth_analysis_reflect_result,
    check_individual_guidance_support_reflect_result,
    format_generated_guidance_result,
    format_in_depth_analysis_result,
    format_individual_guidance_support_result,
    generate_guidance_sample_pair,
    generate_in_depth_analysis_sample_pair,
    generate_individual_guidance_support_sample_pair,
    get_in_depth_analysis_statement_info,
    get_overall_analysis_result,
)
from app.tool.utils import (
    convert_str_to_dict,
    extract_brace_content,
    extract_bracket_content,
    get_files,
    get_subdirs,
    load_json,
    save_json,
)


def load_to_process_files(file_path: str) -> List[str]:
    """Load the list of files to process from a JSON file."""
    if not osp.exists(file_path):
        return None

    data = load_json(file_path)

    to_process_files = []

    if isinstance(data, dict):
        for files in data.values():
            if isinstance(files, list):
                to_process_files.extend(files)
            else:
                raise ValueError("Invalid file format in JSON.")
    elif isinstance(data, list):
        to_process_files = data
    else:
        raise ValueError("Invalid file format in JSON.")

    return to_process_files


class GenerateGuidanceTool(BaseTool):

    name: str = "generate_guidance"
    description: str = """
    Generate guidance based on structured paper content and labeled sentences.
    1. Perform in-depth analysis on selected papers based on the given topic.
    2. Summarize trends and generate guidance based on in-depth analysis results.
    3. Process guidance support based on in-depth analysis results.
    """

    # Dependency injection for easier testing
    retrieval_llm: LLM = Field(default_factory=partial(LLM, usage="retrieval"))
    reasoning_llm: LLM = Field(default_factory=partial(LLM, usage="reasoning"))

    async def execute(
        self,
        topic: str,
        structured_text_root: str,
        labeled_sentences_root: str,
        output_root: str,
        selected_file_info_path: str = None,
    ):
        in_depth_analysis_root = osp.join(output_root, "in_depth_analysis")
        if not osp.exists(in_depth_analysis_root):
            os.makedirs(in_depth_analysis_root, exist_ok=True)

        # Step 1. generate in-depth analysis based on the topic
        selected_file_info = load_json(selected_file_info_path)
        selected_file_list = []
        for _, file_list in selected_file_info.items():
            if isinstance(file_list, list):
                selected_file_list.extend(file_list)
            else:
                raise ValueError("Invalid file format in JSON.")

        await self._in_depth_analysis(
            topic=topic,
            selected_file_list=selected_file_list,
            structured_text_root=structured_text_root,
            labeled_sentences_root=labeled_sentences_root,
            output_root=in_depth_analysis_root,
        )

        # Step 2. Summarize trends based on in-depth analysis results
        guidance_path = osp.join(output_root, "guidance.json")
        await self._generate_guidance(
            topic=topic,
            selected_file_list=selected_file_list,
            in_depth_analysis_root=in_depth_analysis_root,
            output_path=guidance_path,
        )

        # Step 3. Process guidance support based on in-depth analysis results
        guidance_support_root = osp.join(output_root, "guidance_support")

        await self._process_guidance_support(
            topic=topic,
            guidance_file_path=guidance_path,
            in_depth_analysis_root=in_depth_analysis_root,
            guidance_support_root=guidance_support_root,
        )

        self._summerize_guidance_support(
            guidance_support_root,
            osp.join(output_root, "support_summary"),
        )

    async def _individual_in_depth_analysis_calling(
        self,
        topic: str,
        structured_paper: List,
        labeled_sentences: List,
        retry: int = 10,
    ):

        in_depth_analysis_prompt = IN_DEPTH_ANALYSIS_PROMPT.format(
            topic=topic,
        )

        in_depth_analysis_content = "Paper content: {paper_content}".format(
            paper_content=json.dumps(structured_paper)
        )[:60000]

        return await self._generate_calling(
            prompt=in_depth_analysis_prompt,
            content=in_depth_analysis_content,
            format_content=labeled_sentences,
            format_callback=format_in_depth_analysis_result,
            sample_pair_callback=generate_in_depth_analysis_sample_pair,
            preprocess_callback=extract_bracket_content,
            retry=retry,
        )

    async def _generate_calling(
        self,
        prompt: str,
        content: str,
        format_content: dict,
        format_callback=None,
        sample_pair_callback=None,
        preprocess_callback=None,
        retry: int = 10,
    ):

        system_message = Message.system_message(
            prompt,
        )
        user_message = Message.user_message(content[:60000])

        formatted_response = None
        sample_pair = None

        for i in range(retry):
            try:
                response = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if response:
                    response = preprocess_callback(response)
                    response = convert_str_to_dict(response)

                    if response:
                        formatted_response = format_callback(
                            response,
                            format_content.keys(),
                        )

                        if formatted_response:
                            sample_pair = sample_pair_callback(
                                formatted_response, format_content
                            )
                            if sample_pair:
                                break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue

        return formatted_response, sample_pair

    async def _individual_in_depth_analysis_reflection(
        self, statement: str, sample_pair: dict
    ):
        """Reflect on the in-depth analysis results."""
        statement_reflection_content = REFLECT_IN_DEPTH_ANALYSIS_PROMPT.format(
            statement=statement,
        )

        sample_pair_content = "Sample pair: {sample_pair}".format(
            sample_pair=json.dumps(sample_pair)
        )[:60000]
        return await self._reflect_sample_pair(
            statement_reflection_content,
            sample_pair_content,
            check_callback=check_in_depth_analysis_reflect_result,
        )

    async def _reflect_sample_pair(
        self, prompt: str, sample_pair_content: str, check_callback=None
    ):
        """Reflect on the in-depth analysis results."""
        system_message = Message.system_message(prompt)
        user_message = Message.user_message(sample_pair_content)
        reflection_result = {}
        for i in range(10):
            try:
                reflection_response = await self.reasoning_llm.ask(
                    messages=[user_message],
                    system_msgs=[system_message],
                    stream=True,
                )
                if reflection_response:
                    reflection_response = extract_brace_content(reflection_response)
                    reflection_response = convert_str_to_dict(reflection_response)

                    if reflection_response:
                        if check_callback:
                            reflection_result = check_callback(reflection_response)

                        if reflection_result:
                            break
            except Exception as e:
                logger.error(f"Error during LLM call: {e}")
                asyncio.sleep(1)
                continue
        return reflection_response

    async def _in_depth_analysis(
        self,
        topic: str,
        selected_file_list: List[str],
        structured_text_root: str,
        labeled_sentences_root: str,
        output_root: str,
    ):

        tasks = []
        batch_size = 50
        batch_count = 0
        for f in selected_file_list:
            structured_paper_path = osp.join(structured_text_root, f + ".json")

            labeled_sentences_path = osp.join(labeled_sentences_root, f + ".json")
            output_path = osp.join(output_root, f + ".json")
            if not osp.exists(structured_paper_path) or not osp.exists(
                labeled_sentences_path
            ):
                logger.warning(f"File {structured_paper_path} does not exist.")
                continue

            tasks.append(
                self._individual_in_depth_analysis(
                    topic=topic,
                    structured_paper_path=structured_paper_path,
                    labeled_sentences_path=labeled_sentences_path,
                    output_path=output_path,
                )
            )
            batch_count += 1
            if batch_count >= batch_size:
                await asyncio.gather(*tasks)
                tasks = []
                batch_count = 0
        if tasks:
            await asyncio.gather(*tasks)

    async def _individual_in_depth_analysis(
        self,
        topic: str,
        structured_paper_path: str,
        labeled_sentences_path: str,
        output_path: str,
    ):
        """Perform in-depth analysis on the selected files."""

        if not osp.exists(output_path):
            structured_paper = load_json(structured_paper_path)
            labeled_sentences = load_json(labeled_sentences_path)

            labeled_sentence_dict = {}
            for sentence in labeled_sentences:
                for key, value in sentence.items():

                    labeled_sentence_dict[key] = value

            finish_flag = False
            process_count = 0

            in_depth_analysis_result = {}
            reflection_results = []

            while not finish_flag:
                formatted_in_depth_analysis, sample_pair = (
                    await self._individual_in_depth_analysis_calling(
                        topic=topic,
                        structured_paper=structured_paper,
                        labeled_sentences=labeled_sentence_dict,
                    )
                )

                if not formatted_in_depth_analysis:
                    process_count += 1
                    if process_count >= 0:
                        finish_flag = True
                        in_depth_analysis_result = {
                            "formatted_in_depth_analysis": formatted_in_depth_analysis,
                            "reflection_results": reflection_results,
                        }
                        save_json(output_path, in_depth_analysis_result)
                        break
                    continue

                reflection_results = []
                finish_flag = True
                for analysis_item, item_pair in zip(
                    formatted_in_depth_analysis, sample_pair
                ):
                    statement = analysis_item["statement"]
                    statement_key = analysis_item["statement_key"]

                    reflection_result = (
                        await self._individual_in_depth_analysis_reflection(
                            statement=statement,
                            sample_pair=item_pair,
                        )
                    )

                    if reflection_result["valid_group"] in ["None", "B"]:
                        finish_flag = False

                    reflection_result["statement"] = statement
                    reflection_result["statement_key"] = statement_key

                    reflection_results.append(reflection_result)

                process_count += 1
                if process_count >= 0:
                    logger.warning("Reflection failed, retrying...")
                    finish_flag = True

                if finish_flag:
                    in_depth_analysis_result = {
                        "formatted_in_depth_analysis": formatted_in_depth_analysis,
                        "reflection_results": reflection_results,
                    }
                    save_json(output_path, in_depth_analysis_result)

    async def _generate_guidance_calling(
        self, topic: str, overall_in_depth_analysis_info: dict
    ):
        generate_guidance_prompt = GUIDANCE_GENERATION_PROMPT.format(
            topic=topic,
        )

        generate_guidance_content = "Overall in-depth analysis info: {info}".format(
            info=json.dumps(overall_in_depth_analysis_info)
        )[:60000]

        return await self._generate_calling(
            prompt=generate_guidance_prompt,
            content=generate_guidance_content,
            format_content=overall_in_depth_analysis_info,
            format_callback=format_generated_guidance_result,
            sample_pair_callback=generate_guidance_sample_pair,
            preprocess_callback=extract_bracket_content,
            retry=10,
        )

    async def _generate_guidance_reflection(
        self, topic: str, statement: str, sample_pair: dict
    ):
        """Reflect on the generated guidance."""
        statement_reflection_content = REFLECT_GUIDANCE_PROMPT.format(
            topic=topic,
            statement=statement,
        )
        sample_pair_content = "Sample pair: {sample_pair}".format(
            sample_pair=json.dumps(sample_pair)
        )[:60000]
        return await self._reflect_sample_pair(
            prompt=statement_reflection_content,
            sample_pair_content=sample_pair_content,
            check_callback=check_generated_guidance_reflect_result,
        )

    async def _generate_guidance(
        self,
        topic: str,
        selected_file_list: List[str],
        in_depth_analysis_root: str,
        output_path: str,
    ):
        if not osp.exists(output_path):
            overall_in_depth_analysis_info = get_overall_analysis_result(
                in_depth_analysis_root, selected_file_list
            )
            finish_flag = False
            while not finish_flag:
                generated_guidance, sample_pairs = (
                    await self._generate_guidance_calling(
                        topic=topic,
                        overall_in_depth_analysis_info=overall_in_depth_analysis_info,
                    )
                )
                finish_flag = True
                overall_reflect_generated_guidance = []
                if generated_guidance:
                    for guidance, sample_pair in zip(generated_guidance, sample_pairs):
                        statement = guidance["guidance"]

                        reflect_generated_guidance = (
                            await self._generate_guidance_reflection(
                                topic=topic,
                                statement=statement,
                                sample_pair=sample_pair,
                            )
                        )

                        if (
                            reflect_generated_guidance["valid_group"] in ["None", "B"]
                            or not reflect_generated_guidance["feasible"]
                        ):
                            finish_flag = False
                            logger.warning("Reflection failed, retrying...")
                            break
                        reflect_generated_guidance["guidance"] = statement
                        reflect_generated_guidance["guidance_key"] = guidance[
                            "guidance_key"
                        ]
                        overall_reflect_generated_guidance.append(
                            reflect_generated_guidance
                        )

                if finish_flag:
                    result = {
                        "generate_guidance": generated_guidance,
                        "reflect_result": overall_reflect_generated_guidance,
                    }
                    save_json(output_path, result)

    async def _individual_guidance_support_calling(
        self, statement: str, in_depth_analysis_info: dict
    ):
        """Call the LLM to support individual guidance."""
        individual_guidance_support_prompt = INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT.format(
            statement=statement,
        )
        individual_guidance_support_content = "In-depth analysis info: {info}".format(
            info=json.dumps(in_depth_analysis_info)
        )[:60000]
        return await self._generate_calling(
            prompt=individual_guidance_support_prompt,
            content=individual_guidance_support_content,
            format_content=in_depth_analysis_info,
            format_callback=format_individual_guidance_support_result,  # Define a format callback if needed
            sample_pair_callback=generate_individual_guidance_support_sample_pair,  # Define a sample pair callback if needed
            preprocess_callback=extract_brace_content,  # Define a pre-process callback if needed
            retry=10,
        )

    async def _individual_guidance_support_reflection(
        self, statement: str, sample_pair: dict
    ):
        """Reflect on the individual guidance support results."""
        statement_reflection_content = (
            REFLECT_INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT.format(
                statement=statement,
            )
        )
        sample_pair_content = "Sample pair: {sample_pair}".format(
            sample_pair=json.dumps(sample_pair)
        )[:60000]
        return await self._reflect_sample_pair(
            prompt=statement_reflection_content,
            sample_pair_content=sample_pair_content,
            check_callback=check_individual_guidance_support_reflect_result,  # Define a check callback if needed
        )

    async def _individual_guidance_support(
        self, guidance: str, in_depth_analysis_file: str, output_path: str
    ):
        if not osp.exists(output_path):
            in_depth_analysis_info = load_json(in_depth_analysis_file)
            if not in_depth_analysis_info:
                logger.warning(
                    f"In-depth analysis info for {in_depth_analysis_file} is empty."
                )
                return
            in_depth_analysis_list = get_in_depth_analysis_statement_info(
                in_depth_analysis_info
            )
            if not in_depth_analysis_list:
                logger.warning(
                    f"No in-depth analysis statements found for {in_depth_analysis_file}."
                )
                return
            finish_flag = False
            count = 0
            while not finish_flag:
                individual_support, sample_pair = (
                    await self._individual_guidance_support_calling(
                        statement=guidance,
                        in_depth_analysis_info=in_depth_analysis_list,
                    )
                )
                finish_flag = True
                reflect_individual_support = {}

                if individual_support:

                    reflect_individual_support = (
                        await self._individual_guidance_support_reflection(
                            statement=guidance,
                            sample_pair=sample_pair,
                        )
                    )

                    if reflect_individual_support["valid_group"] in ["None", "B"]:
                        finish_flag = False
                        logger.warning("Reflection failed, retrying...")
                        count += 1
                        if count >= 3:
                            logger.warning(
                                f"Reflection  shows invalid individual guidance support for '{guidance}' after 3 attempts."
                            )
                            finish_flag = True
                        break

                if finish_flag:
                    result = {
                        "generate_guidance": individual_support,
                        "reflect_result": reflect_individual_support,
                    }
                    save_json(output_path, result)

    async def _process_guidance_support(
        self,
        topic: str,
        guidance_file_path: str,
        in_depth_analysis_root: str,
        guidance_support_root: str,
    ):
        """Process the guidance support results."""
        if not osp.exists(guidance_file_path):
            logger.warning(f"File {guidance_file_path} does not exist.")
            return

        guidance = load_json(guidance_file_path)

        tasks = []

        all_files = get_files(in_depth_analysis_root, ".json")

        batch_size = 50
        batch_count = 0

        for g in guidance["generate_guidance"]:
            guidance_statement = g["guidance"]
            guidance_key = g["guidance_key"]

            individual_guidance_support_root = osp.join(
                guidance_support_root, guidance_key
            )
            if not osp.exists(individual_guidance_support_root):
                os.makedirs(individual_guidance_support_root, exist_ok=True)

            for f in all_files:
                file_name = osp.basename(f)
                in_depth_analysis_file = osp.join(in_depth_analysis_root, file_name)
                output_path = osp.join(individual_guidance_support_root, file_name)
                if not osp.exists(in_depth_analysis_file) or osp.exists(output_path):
                    continue
                tasks.append(
                    self._individual_guidance_support(
                        guidance=guidance_statement,
                        in_depth_analysis_file=in_depth_analysis_file,
                        output_path=output_path,
                    )
                )
                batch_count += 1
                if batch_count >= batch_size:
                    await asyncio.gather(*tasks)
                    tasks = []
                    batch_count = 0
        if tasks:
            await asyncio.gather(*tasks)

    def _summerize_guidance_support(
        self,
        guidance_support_root: str,
        support_summary_root: str,
    ):
        guidance_key_roots = get_subdirs(guidance_support_root)

        overall_summary = {}

        for guidance_key_root in guidance_key_roots:
            guidance_key = osp.basename(guidance_key_root)

            support_articles = get_files(guidance_key_root, ".json")

            support_summary = {"support_count": len(support_articles)}

            save_path = osp.join(support_summary_root, f"{guidance_key}_summary.json")
            if not osp.exists(support_summary_root):
                os.makedirs(support_summary_root, exist_ok=True)
            save_json(save_path, support_summary)
            overall_summary[guidance_key] = support_summary
