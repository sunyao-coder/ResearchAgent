import os.path as osp
import random

from app.tool.utils import (
    convert_str_to_dict,
    get_files,
    load_json,
    load_txt,
    save_json,
    save_txt,
)


def extract_brace_content(s):
    start = s.find("{")
    end = s.rfind("}")

    if start != -1 and end != -1 and start < end:
        return s[start : end + 1]
    else:
        return None


def parse_code(code):
    prefix, num_str = code.split("_")
    result = f"{prefix}_{int(num_str):04d}"
    return result


def format_extracted_info(
    extracted_info: dict, metrics: list, labeled_sentences_keys: list
):
    """Check if the extracted information is in the correct format."""

    if (
        "positive" not in extracted_info.keys()
        or "negative" not in extracted_info.keys()
    ):
        return False

    if set(metrics) != set(extracted_info["positive"].keys()) or set(metrics) != set(
        extracted_info["negative"].keys()
    ):
        return False

    formatted_results = {}

    positive_info = extracted_info["positive"]

    negative_info = extracted_info["negative"]

    postive_result = format_extracted_info_helper(
        positive_info, metrics, labeled_sentences_keys
    )
    if not postive_result:
        return False

    negative_result = format_extracted_info_helper(
        negative_info, metrics, labeled_sentences_keys
    )
    if not negative_result:
        return False

    formatted_results["positive"] = postive_result
    formatted_results["negative"] = negative_result

    return formatted_results


def format_extracted_info_helper(
    to_process_info: dict,
    metrics: list,
    labeled_sentences_keys: list,
):
    results = {}
    for metric in metrics:
        metric_results = {
            "best_performance": {
                "key": "not_available",
                "supporting_statement_key": "not_available",
            },
            "better_direction": {
                "direction": "not_available",
                "supporting_statement_key": "not_available",
            },
        }

        if "best_performance" not in to_process_info[metric].keys():
            return False
        else:
            if (
                "key" not in to_process_info[metric]["best_performance"].keys()
                or "supporting_statement_key"
                not in to_process_info[metric]["best_performance"].keys()
            ):
                return False

            if to_process_info[metric]["best_performance"]["key"] != "not_available":
                key = parse_code(to_process_info[metric]["best_performance"]["key"])
                if key not in labeled_sentences_keys:
                    return False
                metric_results["best_performance"]["key"] = key

            if (
                to_process_info[metric]["best_performance"]["supporting_statement_key"]
                != "not_available"
            ):
                supporting_statement_key = parse_code(
                    to_process_info[metric]["best_performance"][
                        "supporting_statement_key"
                    ]
                )
                if supporting_statement_key not in labeled_sentences_keys:
                    supporting_statement_key = (
                        "not_available"  # be tolerant to supporting statement
                    )

                metric_results["best_performance"][
                    "supporting_statement_key"
                ] = supporting_statement_key

        if "better_direction" not in to_process_info[metric]:
            return False
        else:
            if (
                "direction" not in to_process_info[metric]["better_direction"].keys()
                or "supporting_statement_key"
                not in to_process_info[metric]["better_direction"].keys()
            ):
                return False

            if to_process_info[metric]["better_direction"]["direction"] in [
                "higher",
                "lower",
                "not_available",
            ]:
                metric_results["better_direction"]["direction"] = to_process_info[
                    metric
                ]["better_direction"]["direction"]
            else:
                return False

            if (
                to_process_info[metric]["better_direction"]["supporting_statement_key"]
                != "not_available"
            ):
                supporting_statement_key = parse_code(
                    to_process_info[metric]["better_direction"][
                        "supporting_statement_key"
                    ]
                )
                if supporting_statement_key not in labeled_sentences_keys:
                    supporting_statement_key = (
                        "not_available"  # be tolerant to supporting statement
                    )
                metric_results["better_direction"][
                    "supporting_statement_key"
                ] = supporting_statement_key

        results[metric] = metric_results
    return results


def generate_extracted_info_sample_pair(extracted_info: dict, labeled_sentence: dict):
    """Generate sample pairs from extracted information for each metric.

    Output sample:
    {
        "activity": {
            "A": {
                "best_performance": {
                    "statement": "The best performance of the catalyst is 0.5 A/mg.",
                    "supporting_statement": "The catalyst shows a high activity."
                },
                "better_direction": {
                    "statement": "higher",
                    "supporting_statement": "The higher the activity, the better."
                }
            }
        }
    }
    """
    sample_pair = {}
    metrics = extracted_info["positive"].keys()

    for metric in metrics:
        metric_sample_pair = {"A": {}, "B": {}}

        # Extract positive and negative samples
        positive_sample = generate_extracted_info_sample_pair_helper(
            extracted_info["positive"][metric], labeled_sentence
        )

        if positive_sample:
            metric_sample_pair["A"].update(positive_sample)
        else:
            continue

        # Extract negative samples
        negative_sample = generate_extracted_info_sample_pair_helper(
            extracted_info["negative"][metric], labeled_sentence
        )
        if negative_sample:
            metric_sample_pair["B"].update(negative_sample)
        sample_pair[metric] = metric_sample_pair

    return sample_pair


def generate_extracted_info_sample_pair_helper(
    metric_item: dict, labeled_sentence: dict
):
    result = {}
    metric_best_performance_info = metric_item["best_performance"]
    if metric_best_performance_info["key"] == "not_available":
        return False

    best_performance_statement = labeled_sentence[metric_best_performance_info["key"]]

    if metric_best_performance_info["supporting_statement_key"] == "not_available":
        best_performance_support_statement = "not_available"
    else:
        best_performance_support_statement = labeled_sentence[
            metric_best_performance_info["supporting_statement_key"]
        ]

    metric_better_direction_info = metric_item["better_direction"]
    if metric_better_direction_info["direction"] == "not_available":
        better_direction_statement = "not_available"
        better_direction_support_statement = "not_available"

    else:
        better_direction_statement = metric_better_direction_info["direction"]
        if metric_better_direction_info["supporting_statement_key"] == "not_available":
            better_direction_support_statement = "not_available"
        else:
            better_direction_support_statement = labeled_sentence[
                metric_better_direction_info["supporting_statement_key"]
            ]
    result["best_performance"] = {
        "statement": best_performance_statement,
        "supporting_statement": best_performance_support_statement,
    }
    result["better_direction"] = {
        "statement": better_direction_statement,
        "supporting_statement": better_direction_support_statement,
    }
    return result


def check_sample_reflect_result(sample_reflect_result: dict):
    """Format the sample reflect result to match the expected output format."""
    if (
        "best_performance" not in sample_reflect_result
        or "better_direction" not in sample_reflect_result
        or "valid_group" not in sample_reflect_result
    ):
        return False

    valid_group_info = sample_reflect_result["valid_group"]
    if valid_group_info not in ["A", "B", "None"]:
        return False

    best_performance_info = sample_reflect_result["best_performance"]

    if (
        "is_relevant" not in best_performance_info.keys()
        or "has_numerical_result" not in best_performance_info.keys()
        or "support_best_performance" not in best_performance_info.keys()
    ):
        return False
    else:
        is_relevant = best_performance_info["is_relevant"]
        has_numerical_result = best_performance_info["has_numerical_result"]
        support_best_performance = best_performance_info["support_best_performance"]

        if not (
            isinstance(is_relevant, bool)
            and isinstance(has_numerical_result, bool)
            and support_best_performance in ["yes", "no", "not_available"]
        ):
            return False

    better_direction_info = sample_reflect_result["better_direction"]
    if "support_better_direction" not in better_direction_info:
        return False
    else:
        support_better_direction = better_direction_info["support_better_direction"]
        if support_better_direction not in ["yes", "no", "not_available"]:
            return False

    return True


def get_valid_metric_info(
    metric_name: str, extracted_info: dict, labeled_sentences: dict
):
    valid_metric_info = {"statement": None, "better_direction": None}
    positive_extracted_info = extracted_info["extracted_info"]["positive"]
    reflect_result = extracted_info["reflect_result"]
    metric_extracted_info = positive_extracted_info[metric_name]

    metric_best_performance_key = metric_extracted_info["best_performance"]["key"]

    if (
        metric_best_performance_key == "not_available"
        or metric_best_performance_key not in labeled_sentences
    ):
        return False

    if metric_name not in reflect_result:
        return False

    metric_reflect_result = reflect_result[metric_name]

    if metric_reflect_result["valid_group"] in ["None", "B"]:
        return False

    metric_best_performance_reflect_result = metric_reflect_result["best_performance"]
    if (
        metric_best_performance_reflect_result["is_relevant"] == False
        or metric_best_performance_reflect_result["has_numerical_result"] == False
    ):
        return False

    best_performance_statement = labeled_sentences[metric_best_performance_key]
    valid_metric_info["statement"] = best_performance_statement

    metric_better_direction_reflect_result = metric_reflect_result["better_direction"][
        "support_better_direction"
    ]

    if metric_better_direction_reflect_result == "yes":
        metric_better_direction = metric_extracted_info["better_direction"]["direction"]
        valid_metric_info["better_direction"] = metric_better_direction
    else:
        valid_metric_info["better_direction"] = "not_available"

    return valid_metric_info


def get_metric_overall_text(
    metric_name: str,
    extract_info_root: str,
    labeled_sentences_root: str,
    num_thres: int = 500,
):
    """
    Output example:
    [
        {
            "doi": "10.1000/xyz123",
            "better_direction": "higher",
            "statement": "The higher the activity, the better."
        }
    ]
    """

    extract_info_files = get_files(extract_info_root)
    extract_info_files = random.sample(extract_info_files, len(extract_info_files))
    overall_metric_dict = {}
    doi_mapping = {}
    overall_metric_info = []
    count = 0
    for f in extract_info_files:
        extracted_info = load_json(f)
        file_name_ele = f.split("/")[-1].split(".")[:-1]
        doi = ".".join(file_name_ele)

        labeled_sentences_path = osp.join(labeled_sentences_root, f"{doi}.json")
        labeled_sentences = load_json(labeled_sentences_path)

        labeled_sentences_dict = {}
        for sentence in labeled_sentences:
            for key, value in sentence.items():
                labeled_sentences_dict[key] = value

        valid_info = get_valid_metric_info(
            metric_name=metric_name,
            extracted_info=extracted_info,
            labeled_sentences=labeled_sentences_dict,
        )
        if valid_info:
            valid_info["doi_key"] = f"{count:04d}"
            doi_mapping[f"{count:04d}"] = doi
            count += 1

            overall_metric_info.append(valid_info)
            overall_metric_dict[doi] = valid_info

            if count >= num_thres:
                break

    return overall_metric_info, overall_metric_dict, doi_mapping


def format_genereted_metrics(
    generated_metrics: dict, doi_mapping: dict, overall_metric_dict: dict
):
    """
    Sample: [
        {
            "type_name": "half-wave potential",
            "description": "The potential at which the current is half of the maximum current.",
            "unit": "V",
            "better_direction": "higher" / "lower"
            "abbreviation": "HWP",
            "sample": {
                "positive": <doi_1>,
                "negative": <doi_2>
            }
        }
    ]
    """
    result = {}
    sample_pair = {}
    for type_name, metric_info in generated_metrics.items():
        if (
            "description" not in metric_info
            or "unit" not in metric_info
            or "better_direction" not in metric_info
            or "abbreviation" not in metric_info
            or "sample" not in metric_info
        ):
            return False, sample_pair

        if metric_info["better_direction"] not in ["higher", "lower"]:
            return False, sample_pair

        if (
            "positive" not in metric_info["sample"]
            or "negative" not in metric_info["sample"]
        ):
            return False, sample_pair

        if (
            metric_info["sample"]["positive"] not in doi_mapping.keys()
            or metric_info["sample"]["negative"] not in doi_mapping.keys()
        ):
            return False, sample_pair

        positive_doi = doi_mapping[metric_info["sample"]["positive"]]
        negative_doi = doi_mapping[metric_info["sample"]["negative"]]
        sample_pair[type_name] = {
            "positive": overall_metric_dict[positive_doi],
            "negative": overall_metric_dict[negative_doi],
        }

        result[type_name] = {
            "description": metric_info["description"],
            "unit": metric_info["unit"],
            "better_direction": metric_info["better_direction"],
            "abbreviation": metric_info["abbreviation"],
            "sample": {
                "positive": positive_doi,
                "negative": negative_doi,
            },
        }

    return result, sample_pair


def generate_metric_sample_pair(
    generated_metrics: list, overall_metric_dict: dict, doi_mapping: dict
):
    """
    Sample: [
        {
            "type_name": "half-wave potential",
            "description": "The potential at which the current is half of the maximum current.",
            "unit": "V",
            "better_direction": "higher" / "lower"
            "Abbreviation": "HWP",
            "sample": {
                "positive": <doi_1>,
                "negative": <doi_2>
            }
        }
    ]
    """
    metric_sample_pair = {}
    for metric in generated_metrics:
        positive_doi_key = metric["sample"]["positive"]
        negative_doi_key = metric["sample"]["negative"]

        positive_doi = doi_mapping[positive_doi_key]
        negative_doi = doi_mapping[negative_doi_key]

        positive_content = overall_metric_dict[positive_doi]
        negative_content = overall_metric_dict[negative_doi]

        metric_sample_pair[metric["type_name"]] = {
            "A": positive_content,
            "B": negative_content,
        }

    return metric_sample_pair


def check_metric_sample_reflect_result(
    metric_sample_reflect_result: dict,
):
    """Check if the metric sample reflect result is in the correct format."""
    if (
        "valid_group" not in metric_sample_reflect_result.keys()
        or "clarity_assessment" not in metric_sample_reflect_result.keys()
        or "effectiveness_assessment" not in metric_sample_reflect_result.keys()
    ):
        return False

    valid_group_info = metric_sample_reflect_result["valid_group"]
    if valid_group_info not in ["A", "B", "None"]:
        return False

    return True


def check_individual_metric_analysis_result(
    individual_metric_analysis_result: dict,
):
    """Check if the individual metric analysis result is in the correct format."""
    if (
        "positive" not in individual_metric_analysis_result.keys()
        or "negative" not in individual_metric_analysis_result.keys()
    ):
        return False

    positive_sample = individual_metric_analysis_result["positive"]
    if (
        "metric_type" not in positive_sample.keys()
        or "metric_value" not in positive_sample.keys()
    ):
        return False
    negative_sample = individual_metric_analysis_result["negative"]
    if (
        "metric_type" not in negative_sample.keys()
        or "metric_value" not in negative_sample.keys()
    ):
        return False

    return True


def generate_individual_metric_analysis_sample_pair(
    individual_metric_analysis_result: dict,
    labeled_sentences: dict,
):
    """Generate sample pairs from individual metric analysis result."""
    sample_pair = {}
    positive_sample = individual_metric_analysis_result["positive"]
    negative_sample = individual_metric_analysis_result["negative"]

    positive_key = positive_sample["metric_type"]
    negative_key = negative_sample["metric_type"]

    if positive_key not in labeled_sentences or negative_key not in labeled_sentences:
        return False

    sample_pair["A"] = labeled_sentences[positive_key]
    sample_pair["B"] = labeled_sentences[negative_key]

    return sample_pair


def check_individual_metric_analysis_reflect_result(
    individual_metric_analysis_reflect_result: dict,
):
    """Check if the individual metric analysis reflect result is in the correct format."""
    if (
        "valid_group" not in individual_metric_analysis_reflect_result.keys()
        or "metric_value" not in individual_metric_analysis_reflect_result.keys()
    ):
        return False

    valid_group_info = individual_metric_analysis_reflect_result["valid_group"]
    if valid_group_info not in ["A", "B", "None"]:
        return False

    metric_value_info = individual_metric_analysis_reflect_result["metric_value"]
    if metric_value_info not in [True, False]:
        return False

    return True
