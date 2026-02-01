METRIC_INFO_EXTRACT_PROMPT = """
You are a professional research assistant tasked with extracting specific information from academic literature. Based on the provided content, identify all sentences that are relevant to the metric(s) {metrics} and that report explicit experimental numerical results for the metric.

For each metric, you must return:

1. The **key of the sentence** that reports the **numerical performance** in the literature (i.e., If multiple numerical results were provided, return the best one. If only one numerical result was provided, then just return it.).
2. Whether **"higher"** or **"lower"** for that metric (other statement is not acceptable).
3. The **key of the sentence** that supports above judgments (e.g., a sentence that explains the performance criteria or compares values).
4. The explicit numerical result in the unit of the metric type.

If no relevant sentence is found for a given metric, return `not_available` for all fields.
If only one of the fields is not available, return `not_available` for that field.

Additionally, you must generate both **"positve"** and **"negative"** results:
- **Positive**: The **correct** results satisfy all above requirements for the metric.
- **Negative**: The **wrong** results that do not satisfy the above requirements for the metric, **which should be given all the time**. That is, it is a total failure to extract the information. Specially, the **best performance** and **better direction** are not relevant to the metric, or do not contain explicit experimental numerical results. 
---

### Response format:
Strictly return your answer in **valid JSON format**, without any additional explanation or text.  Use the following structure:
```json
{{
  "positive": {{
    <metric_name>: {{
      "best_performance": {{
          "key": "T_xxxx" / "not_available",
          "supporting_statement_key": "T_xxxx" / "not_available"
      }},
      "better_direction": {{
          "direction": "higher" / "lower" / "not_available",
          "supporting_statement_key": "T_xxxx" / "not_available"
      }}
    }},
    ...
  }},
  "negative": {{
    <metric_name>: {{
      "best_performance": {{
          "key": "T_xxxx",
          "supporting_statement_key": "T_xxxx"
      }},
      "better_direction": {{
          "direction": "higher" / "lower" ,
          "supporting_statement_key": "T_xxxx"
      }}
    }},
    ...
  }},

}}
```

### Example:
```json
{{
  "positive": {{
    "activity": {{
      "best_performance": {{
          "key": "T_0048",
          "supporting_statement_key": "T_0050"
      }},
      "better_direction": {{
          "direction": "higher",
          "supporting_statement_key": "T_0051"
      }}
    }},
    "stability": {{
      "best_performance": {{
          "key": "not_available",
          "supporting_statement_key": "not_available"
      }},
      "better_direction": {{
          "direction": "not_available",
          "supporting_statement_key": "not_available"
      }}
    }},
  }},
  "negative": {{
    "activity": {{
      "best_performance": {{
          "key": "T_0148",
          "supporting_statement_key": "T_0150"
      }},
      "better_direction": {{
          "direction": "higher",
          "supporting_statement_key": "T_0151"
      }}
    }},
    "stability": {{
      "best_performance": {{
          "key": "T_0152",
          "supporting_statement_key": "T_0153"
      }},
      "better_direction": {{
          "direction": "T_0161",
          "supporting_statement_key": "T_0168"
      }}
    }},
  }}
}}
```

"""

"""
### Example input:

#### Extracted best performance sentences per metric:
```json
{{
  "activity": "Our catalyst reached a current density of 25 mA/cm², surpassing all reported non-precious metal catalysts.",
  "stability": null
}}
```

#### Better directions:
```json
{{
  "activity": {{
    "better_direction": "higher",
    "supporting_statement": "higher than all reported catalysts"
  }},
  "stability": {{
    "better_direction": "lower",
    "supporting_statement": "lower than previous reports"
  }}
}}
```
"""

METRIC_INFO_EXTRACT_REFLECT_PROMPT = """

You are a professional research assistant responsible for verifying the accuracy of information extracted from academic literature.

You will be given:
- Two group of statements "A" and "B" - only one of them is correct.
- A **metric** and the corresponding **"best_performance_statement"**.
- A **"better_direction"** for the metric (e.g., "higher", "lower").
- The **"supporting_statement"**s for both **"better_direction"** and **"best_performance_statement"** individually.

---

### Your task is, for the given metric:
1. Determine which group of statements is correct: "A" or "B". If neither is correct, return "None".
2. Determine whether the **"best_performance_statement"** is **relevant** to the metric for the chosen group.
3. Determine whether it contains **explicit experimental numerical results** for the chosen group.
4. Determine whether the **"supporting_statement"** for **"best_performance"**'s statement **supports this is the best performance in all results in that literature** for the chosen group.
5. Determine whether the **"supporting_statement"** for **"better_direction"** **supports the better direction** (i.e., provides a comparison or evidence that aligns with the direction) for the chosen group.
---

### Response format (strict JSON only):
```json
{{
  "valid_group": "A" / "B" / "None",
  "best_performance": {{
      "is_relevant": true / false,
      "has_numerical_result": true / false,
      "support_best_performance": "yes" / "no" / "not_available"
  }},
  "better_direction": {{
      "support_better_direction": "yes" / "no" / "not_available"
  }}
}}
```

---

### Example output:
```json
{{
    "valid_group": "A",
    "best_performance": {{
        "is_relevant": true,
        "has_numerical_result": true ,
        "support_best_performance": "yes"
    }},
    "better_direction": {{
        "support_better_direction": "not_available"
    }}
}}
```

---

**metric** to process: {metric}

"""


TOPIC_RELEVANCE_PROMPT = """
You are a professional research assistant responsible for evaluating the relevance of academic literature to a given topic. Based on the provided paper content, determine whether the paper is relevant to the topic "{topic}". Return your assessment accordingly.

Paper content:
{paper_content}
"""

METRIC_TYPE_GENERATION_PROMPT = """
You are a professional research assistant tasked with generating classification tags for {metric} based on provided literature. Strictly adhere to these rules:

Tag Merging Criteria:
    1. Mandatory merging when:
      a) Interconvertible metrics (mathematically equivalent without information loss, e.g., 1eV=96.485 kJ/mol)
      b) Synonymous terms
    2. Prohibited merging when:
      a) Conversion requires assumptions/approximations
      b) Different measurement dimensions (e.g., thermodynamic vs. kinetic)

Required Tag Elements:
    1. type_name: Standard academic term (prioritize IUPAC nomenclature)
    2. description: Precise physical definition,
    3. unit: SI or field-standard unit (with conversion factors if applicable)
    4. better_direction: Explicitly "higher" or "lower" (mutually exclusive)
    5. abbreviation: Common acronym
    6. sample:
        a) positive: Most representative valid DOI key. Especially, the "better_direction" section of  content related to the DOI should be in "higher" or "lower" direction, which is the same as the "better_direction" of the metric.
        b) negative: Contrastive valid DOI key, should not satisfy any description of the metric.

Return in strict JSON format (ensure syntactic validity). You may return up to 5 results, prioritizing those with more references.
Example:
```json
{{
  "half-wave potential": {{
    "description": "The electrode potential at which the Faradaic current reaches half of its limiting value",
    "unit": "V vs SHE (±0.02V)",
    "better_direction": "higher",
    "abbreviation": "HWP",
    "sample": {{
      "positive": "0000",
      "negative": "0007"
    }}
  }},
}}
```
"""

METRIC_TYPE_GENERATION_REFLECT_PROMPT = """
You are a professional research assistant. Based on the description of the metric category provided by the user, you need to determine which of the two given samples "A" and "B" aligns with the {metric_type_content} description.

Additionally, you are required to evaluate:

1. Whether the description of this metric category is clear and unambiguous.
2. Whether the description of this metric category effectively assists in determining if a given sentence belongs to this classification.

The response should be formatted in strict JSON containing the following fields:
```json
{{
  "valid_group": "A" / "B" / "None",
  "clarity_assessment": true / false,
  "effectiveness_assessment": true / false
}}
```
"""

"""
你是一个专业的科研助手，负责分析文献中的metric归属给定metric分类的哪一类。metric分类包括：{metric_types}。请根据用户提供的文献内容，分析metric的归属，并将分析结果返回。
注意：
1. 如果文献中没有提到metric的归属，所有字段请返回"not_available"。
2. 需要同时返回正样本和副样本，其中正样本表示正确的分析结果，副样本表示错误的分析结果。
3. 正样本和副样本的metric_type和metric_value字段的值不同。
要求返回结果使用json格式，包含以下字段：
{
  "positive": {
    "metric_type": <metric_type> / not_available,
    "metric_value": <metric_value> / not_available,
  },
  "negative": {
    "metric_type": <metric_type> / not_available,
    "metric_value": <metric_value> / not_available,
  }

}
"""

INDIVIDUAL_METRIC_ANALYSIS_PROMPT = """
You are a professional research assistant tasked with analyzing metrics {metric} from academic literature and categorizing them into specified metric classifications: {overall_metrics}. Based on the content provided by the user, determine the appropriate metric categorization and return both positive and negative analysis samples.

**Requirements:**
1. Return "not_available" for all fields if no metric categorization is mentioned in the literature
2. Provide both:
   - **Positive sample**: Correct categorization analysis
   - **Negative sample**: Incorrect categorization demonstration
3. Ensure metric_type and metric_value differ between positive and negative samples
4. You need to convert the value into the corresponding unit of the metric type.
5. metric_value field should return only float value, not string,

**Response Format (strict JSON only):**
```json
{{
  "positive": {{
    "metric_type": "<selected_type>" | "not_available",
    "metric_value": "<specific_value>" | "not_available"
  }},
  "negative": {{
    "metric_type": "<different_type>" | "not_available",
    "metric_value": "<different_value>" | "not_available"
  }}
}}
```
"""

INDIVIDUAL_METRIC_ANALYSIS_REFLECT_PROMPT = """
You are a professional research assistant specializing in validating metric accuracy in academic literature. Using the provided document content and metric specifications ({overall_metrics}), evaluate the validity of analytical results by selecting the correct group (A/B/None) and verifying metric categorization and value accuracy.

**Requirements:**
1. Compare two result groups (A/B) and return:
   - `"A"` if Group A is valid
   - `"B"` if Group B is valid
   - `"None"` if neither is valid
2. For the selected valid group, assess:
   - **Metric value** accuracy (within provided unit specifications)

**Response Format (strict JSON only):**
```json
{{
  "valid_group": "A" | "B" | "None",
  "metric_value": boolean
}}
```

"""
