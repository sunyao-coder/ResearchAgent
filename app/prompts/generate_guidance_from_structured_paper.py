IN_DEPTH_ANALYSIS_PROMPT = """
You are a research assistant. Based on the given topic: **{topic}**, your task is to extract the most thematically relevant and instructive highlights from each user-provided article. The output should be in **JSON format**, structured as a **list** where each item follows the specifications below:

1. Each article can have **two** highlights.
3. Each highlight must be supported by at least one of the following types of evidence: **experimental data**, **computational data**, or **mechanistic analysis**. Select supporting statements from the user's provided text.
4. Each highlight must include a list of **positive supporting statement keys** and **negative supporting statement keys**. Negative keys refer to statements that are unrelated or irrelevant to the highlight.
5. All supporting statements (positive and negative) must be directly sourced from the user's provided article content.

**Output format (for each item in the list):**
```json
{{
    "statement": "Fe is good",
    "positive_keys": ["T_0048", "T_0050"],
    "negative_keys": ["T_0051"]
}}
```
"""

REFLECT_IN_DEPTH_ANALYSIS_PROMPT = """
You are a research assistant. Based on the user-provided **highlight statement**: **{statement}**, your task is to evaluate **two groups of supporting statements** provided by the user and determine which group better supports the highlight. Additionally, assess whether the selected group provides evidence from the following perspectives:

1. **Experimental data support**
2. **Computational data support**
3. **Mechanistic analysis support**

Your output should be in **JSON format**.

**Output format:**
```json
{{
    "valid_group": "A" / "B" / "None",
    "experiment_data_support": true / false,
    "calculation_data_support": true / false,
    "mechanism_analysis_support": true / false
}}
```

**Notes:**
- `"valid_group"` should be `"A"` if Group A is more supportive, `"B"` if Group B is more supportive, or `"None"` if neither group provides meaningful support.
- The boolean values for the three support types should reflect whether the selected group contains relevant evidence from that perspective.


"""

GUIDANCE_GENERATION_PROMPT = """
You are a research assistant. Based on the given **topic**: **{topic}**, and a set of **highlight statements** summarized from multiple articles, your task is to generate **feasible and topic-relevant guidance**. The output should be in **JSON format**, structured as a **list**, where each item follows the specifications below:

1. Generate **up to 8** guidance items.
2. Each guidance must include:
   - A list of **positive supporting statement keys**, which are statements relevant to the guidance.
   - A list of **negative supporting statement keys**, which are statements unrelated or irrelevant to the guidance.
3. Different guidance items should be distinct and actionable, providing clear direction based on the topic.
4. Each guidance aims to reflect specific practices mentioned in the literature.

**Output format (for each item in the list):**
```json
{{
    "guidance": "Fe is good",
    "positive_keys": ["T_0048", "T_0050"],
    "negative_keys": ["T_0051"]
}}
```

**Notes:**
- The guidance should be actionable or instructive, aligning with the given topic.
- Supporting statement keys must come from the highlight statements provided by the user.
"""
"""
你是一个科研助手，需要根据用户提供的guidance陈述{statement}，从用户提供的两组支持语句中，判断符合guidance陈述的支持语句，在此基础上，你需要判断guidance是否具备可行性，要求输出json格式：
output format:
{{
    "valid_group": "A" / "B" / "None",
    "feasible": true / false
}}
"""  # {topic} {statement}

REFLECT_GUIDANCE_PROMPT = """
You are a research assistant. Based on the user-provided **guidance statement**: **{statement}**, and **two groups of supporting statements**, your task is to:

1. Determine which group (A, B, or None) better supports the guidance statement.
2. Evaluate whether the guidance statement is **feasible**.

Your output should be in **JSON format** as follows:

**Output format:**
```json
{{
    "valid_group": "A" / "B" / "None",
    "feasible": true / false
}}
```

**Notes:**
- `"valid_group"` should be `"A"` if Group A provides stronger and more relevant support, `"B"` if Group B does, or `"None"` if neither group meaningfully supports the guidance.
- `"feasible"` should be `true` if the guidance appears actionable and realistic based on the supporting evidence, otherwise `false`.
"""

INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT = """
You are a research assistant. Based on the user-provided **guidance statement**: **{statement}**, and a set of **highlight statements** extracted from scientific articles, your task is to:

1. Identify supporting highlights:
    Select only **highlight** keys that directly and strongly support the **guidance statement**. A highlight is valid only if it provides **explicit evidence** for the guidance's core claim. **Exclude indirect or weakly related highlights**.
2. For each supporting highlight, provide:
   - A list of **positive supporting statement keys** (i.e., keys of statements relevant to and supportive of the guidance).
   - A list of **negative supporting statements** (i.e., statements that are clearly irrelevant or contradictory to the guidance). These negative statements should be **generated by you** and not taken from the user input.

The output should be a **JSON list**, where each item corresponds to a set of supporting highlights for the guidance.

**Output format (for each item in the list):**
```json
{{
    "positive_keys": ["T_0048", "T_0050"],
    "negative_statements": ["Fe is bad", "Fe is not good"]
}}
```

**Notes:**
- Only include highlights that meaningfully support the guidance.
- Negative statements should be logically unrelated or contradictory to the guidance, and should be created based on your understanding.
- Ensure the output is concise and scientifically coherent.
"""

REFLECT_INDIVIDUAL_GUIDANCE_SUPPORT_PROMPT = """
You are a research assistant. Based on the user-provided **guidance statement**: **{statement}**, and **two groups of supporting statements**, your task is to:

- Determine which group (**A**, **B**, or **None**) better supports the guidance statement.

Your output should be in **JSON format** as follows:

**Output format:**
```json
{{
    "valid_group": "A" / "B" / "None"
}}
```

**Instructions:**
- Choose `"A"` if Group A provides stronger and more relevant support for the guidance.
- Choose `"B"` if Group B provides stronger and more relevant support.
- Choose `"None"` if neither group adequately supports the guidance statement.

"""
