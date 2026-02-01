import os.path as osp
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.tool.utils import (
    load_json,
)


def check_format(data: Union[list, dict], data_type: str) -> bool:
    """
    Check if the data is in the correct format.
    """

    data_type_class = DATA_TYPE_MAPPING[data_type]
    try:
        return data_type_class(**data)
    except Exception as e:
        print(f"Error in checking format: {e}")
        return False


class IndividualGuidanceSupportReflectItem(BaseModel):
    """
    Individual guidance support reflect item for the individual guidance support task.
    """

    valid_group: Literal["A", "B", "None"] = Field(
        ..., description="A / B / None", example="A"
    )


class InDepthAnalysisReflectItem(BaseModel):
    """
    In-depth analysis reflect item for the in-depth analysis task.
    """

    valid_group: Literal["A", "B", "None"] = Field(
        ..., description="A / B / None", example="A"
    )
    experiment_data_support: bool = Field(
        ...,
        description="Whether the experiment data supports the analysis",
        example=True,
    )
    calculation_data_support: bool = Field(
        ...,
        description="Whether the calculation data supports the analysis",
        example=True,
    )
    mechanism_analysis_support: bool = Field(
        ...,
        description="Whether the mechanism analysis supports the analysis",
        example=True,
    )


class IndividualGuidanceSupport(BaseModel):
    """
    Individual statement support for the guidance.
    """

    positive_keys: List[str] = Field(
        ...,
        description="The keys of the positive sentences",
        example=["T_0048", "T_0050"],
    )

    negative_statements: List[str] = Field(
        ..., description="The keys of the negative sentences", example=["T_0051"]
    )

    def key_validate(self, analysis_dict: List[str]) -> bool:
        """
        Validate the keys in the item against the overall analysis dictionary.
        """
        for key in self.positive_keys:
            if key not in analysis_dict:
                return False
        return True


class InDepthAnalysisItem(BaseModel):
    """
    In-depth analysis item for the in-depth analysis task.
    """

    statement: str = Field(
        ...,
        description="The statement of the in-depth analysis",
        example="The catalytic activity of the catalyst is higher than that of the control group.",
    )
    positive_keys: List[str] = Field(
        ...,
        description="The keys of the positive sentences",
        example=["T_0048", "T_0050"],
    )
    negative_keys: List[str] = Field(
        ..., description="The keys of the negative sentences", example=["T_0051"]
    )

    def key_validate(self, labeled_sentences_keys: List[str]) -> bool:
        """
        Validate the keys in the item against the labeled sentences keys.
        """
        for key in self.positive_keys:
            if key not in labeled_sentences_keys:
                return False
        for key in self.negative_keys:
            if key not in labeled_sentences_keys:
                return False
        return True


class GeneratedGuidanceItem(BaseModel):
    """
    Generated guidance item for the generate guidance task.
    """

    guidance: str = Field(
        ...,
        description="The generated guidance",
        example="Fe is good",
    )
    positive_keys: List[str] = Field(
        ...,
        description="The keys of the positive sentences",
        example=["T_0048", "T_0050"],
    )
    negative_keys: List[str] = Field(
        ..., description="The keys of the negative sentences", example=["T_0051"]
    )

    def key_validate(self, overall_analysis_dict: List[str]) -> bool:
        """
        Validate the keys in the item against the labeled sentences keys.
        """
        for key in self.positive_keys:
            if key not in overall_analysis_dict:
                return False
        for key in self.negative_keys:
            if key not in overall_analysis_dict:
                return False
        return True


class GeneratedGuidanceReflectItem(BaseModel):
    """
    Generated guidance reflect item for the generate guidance task.
    """

    valid_group: Literal["A", "B", "None"] = Field(
        ..., description="A / B / None", example="A"
    )
    feasible: bool = Field(
        ...,
        description="Whether the generated guidance is feasible",
        example=True,
    )


DATA_TYPE_MAPPING = {
    "in_depth_analysis_reflect_item": InDepthAnalysisReflectItem,
    "in_depth_analysis_item": InDepthAnalysisItem,
    "generated_guidance_item": GeneratedGuidanceItem,
    "generated_guidance_reflect_item": GeneratedGuidanceReflectItem,
    "individual_guidance_support": IndividualGuidanceSupport,
    "individual_guidance_support_reflect_item": IndividualGuidanceSupportReflectItem,
}


def generate_sample_pair(item_list: list, contente_dict: dict):
    """
    Generate sample pairs from the item list and content dictionary.
    Sample output:
    [
        {
            "A": [
                "The catalytic activity of the catalyst is higher than that of the control group."
            ],
            "B": [
                "The catalytic activity of the catalyst is lower than that of the control group."
            ],
        }
    ]
    """
    sample_pair = []
    for item in item_list:
        positive_keys = item["positive_keys"]
        negative_keys = item["negative_keys"]

        A = []
        B = []

        for key in positive_keys:
            if key in contente_dict.keys():
                A.append(contente_dict[key])

        for key in negative_keys:
            if key in contente_dict.keys():
                B.append(contente_dict[key])

        sample_pair.append(
            {
                "A": A,
                "B": B,
            }
        )
    return sample_pair


def format_in_depth_analysis_result(
    analysis_result: list,
    labeled_sentences_keys: list,
) -> str:
    """
    Sample output:
    [
        {
            "statement_key": "S_0",
            "statement": "The catalytic activity of the catalyst is higher than that of the control group.",
            "positive_keys": ["T_0048", "T_0050"],
            "negative_keys": ["T_0051"],
        }
    ]
    """
    result = []
    for i, item in enumerate(analysis_result):
        statement_key = f"S_{i}"
        item = check_format(item, "in_depth_analysis_item")
        if item and item.key_validate(labeled_sentences_keys):
            item_dict = item.dict()
            item_dict["statement_key"] = statement_key
            result.append(item_dict)
        else:
            return False

    return result


def generate_in_depth_analysis_sample_pair(
    result: list,
    labeled_sentences_dict: dict,
):
    """
    sample output:
    [
        {

            "A": [
            "The catalytic activity of the catalyst is higher than that of the control group."],
            "B": [
            "The catalytic activity of the catalyst is lower than that of the control group."
            ],
        }
    ]
    """
    return generate_sample_pair(
        item_list=result,
        contente_dict=labeled_sentences_dict,
    )


def check_in_depth_analysis_reflect_result(
    result: dict,
):
    """
    sample: {
        "valid_group": "A" / "B" / "None"
        "experiment_data_support": true / false,
        "calculation_data_support": true / false,
        "mechanism_analysis_support": true / false,
    }
    """

    return check_format(result, "in_depth_analysis_reflect_item")


def check_in_depth_analysis_item(in_depth_analysis_item: dict):
    """
    sample: {
        "valid_group": "A" / "B" / "None"
        "experiment_data_support": true / false,
        "calculation_data_support": true / false,
        "mechanism_analysis_support": true / false,
    """

    if in_depth_analysis_item["valid_group"] in ["B", "None"]:
        return False

    return True


def get_overall_analysis_result(analysis_root: str, selected_file_list: list):
    """
    sample: {
        "valid_group": "A" / "B" / "None"
        "experiment_data_support": true / false,
        "calculation_data_support": true / false,
        "mechanism_analysis_support": true / false,
        }
    """

    overall_analysis_result = {}
    for doi in selected_file_list:

        file_path = osp.join(analysis_root, doi + ".json")

        in_depth_analysis_result = load_json(file_path)
        in_depth_analysis_result_reflect = in_depth_analysis_result[
            "reflection_results"
        ]

        in_depth_analysis_result = in_depth_analysis_result[
            "formatted_in_depth_analysis"
        ]

        if not in_depth_analysis_result:
            continue

        for analysis_item, reflect_item in zip(
            in_depth_analysis_result, in_depth_analysis_result_reflect
        ):
            if reflect_item["valid_group"] == "A":
                key = doi + "+" + analysis_item["statement_key"]
                overall_analysis_result[key] = analysis_item["statement"]
    return overall_analysis_result


def format_generated_guidance_result(
    guidance_result: list, overall_analysis_dict_keys: list
):
    """
    sample: [
        {
            "guidance": "Fe is good",
            "positive_keys": ["T_0048", "T_0050"],
            "negative_keys": ["T_0051"],
        }
    ]
    """

    if not isinstance(guidance_result, list):
        return False

    result = []

    for i, item in enumerate(guidance_result):
        item = check_format(item, "generated_guidance_item")
        if not item or not item.key_validate(overall_analysis_dict_keys):
            return False
        item_dict = item.dict()
        item_dict["guidance_key"] = f"G_{i}"

        result.append(item_dict)

    return result


def generate_guidance_sample_pair(
    result: list,
    overall_analysis_dict: dict,
):
    """
    sample output:
    [
        {
            "A": [
                "Fe is good",
            ],
            "B": [
                "Fe is bad",
            ],
        }
    ]
    """
    return generate_sample_pair(
        item_list=result,
        contente_dict=overall_analysis_dict,
    )


def check_generated_guidance_reflect_result(
    result: dict,
):
    """
    sample: {
        "valid_group": "A" / "B" / "None"
        "feasible": true / false,
    }
    """

    return check_format(result, "generated_guidance_reflect_item")


def format_individual_guidance_support_result(
    individual_guidance_support_result: dict,
    individual_analysis_dict: dict,
):
    """
    Sample output:

    {
        "positive_keys": ["T_0048", "T_0050"],
        "negative_statements": ["T_0051"],
    }

    """

    result = check_format(
        individual_guidance_support_result, "individual_guidance_support"
    )
    if not result or not result.key_validate(individual_analysis_dict):
        return False

    return result.dict()


def get_in_depth_analysis_statement_info(in_depth_analysis_result: dict):
    result = {}
    analysis_result = in_depth_analysis_result["formatted_in_depth_analysis"]
    if not analysis_result:
        return result
    for item in analysis_result:

        result[item["statement_key"]] = item["statement"]

    return result


def generate_individual_guidance_support_sample_pair(
    result: dict,
    individual_analysis_dict: dict,
):
    """
    Sample output:
    {
        "A": [
            "Fe is good",
        ],
        "B": [
            "Fe is bad",
        ],
    }
    """
    positive_keys = result["positive_keys"]
    negative_statements = result["negative_statements"]

    A = []

    for key in positive_keys:
        if key in individual_analysis_dict.keys():
            A.append(individual_analysis_dict[key])
    return {
        "A": A,
        "B": negative_statements,
    }


def check_individual_guidance_support_reflect_result(
    result: dict,
):
    """
    Sample output:
    {
        "valid_group": "A" / "B" / "None",
    }
    """

    return check_format(result, "individual_guidance_support_reflect_item")
