# ResearchAgent

**ResearchAgent** is an open-source tool that leverages large language models (LLMs) to extract research trends from scientific literature. It performs structured text extraction, sentence labeling, metric-based filtering, and LLM-guided guidance generation to identify high-impact research directions.

---

## 🖥️ 1. System Requirements

- **Operating System**: Ubuntu 22.04 LTS  
- **Python Version**: 3.12  
- **Tested Hardware**:
  - **CPU**: AMD Ryzen 5 5600
  - **GPU**: NVIDIA RTX 4070 (recommended for faster LLM inference)
- **Tested Software Versions**:
  - Conda 23.11.0
  - MinerU 2.5
  - spaCy 3.8.7
- **Non-standard Dependencies**:
  - [Mineru](https://github.com/opendatalab/mineru) (for multimodal PDF parsing)
  - LLM API access (e.g., Qwen3-235B)

---

## 📦 2. Installation Guide

**Estimated install time**: ~30 minutes on a standard desktop with GPU.

### Step 1: Install Conda  
Follow: https://docs.conda.io/en/latest/

### Step 2: Create and activate the environment
```bash
conda create -n research_agent python=3.12
conda activate research_agent
```

### Step 3: Install MinerU (tested with version 2.5)
```bash
pip install --upgrade pip
pip install uv
uv pip install -U "mineru[all]"
```

### Step 4: Install other dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Download the spaCy model
```bash
python -m spacy download en_core_web_trf
```

---

## ⚙️ 3. LLM API Configuration

Edit your config file (e.g., `config.yaml`) to include LLM access:

```yaml
llm:
  default:
    model_name: qwen3-235b-a22b
    max_tokens: 2048
    temperature: 0.1
    api_type: openai
    api_key: "<your_api_key>"
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  reasoning:
    ...
  retrieval:
    ...
```

- `default`: for general LLM use  
- `reasoning`: for LLMs with strong reasoning capabilities used in **guidance**  
- `retrieval`: for models with function-calling capabilities

> ⚠️ Replace `<your_api_key>` with your valid API key. Do **not** commit API keys to public repositories.

---

## 📂 4. Demo

### Sample Data

- Place sample PDFs in: `workspace/raw_pdf/`
- Sample files are provided for quick testing

### Run the Pipeline

```bash
python main.py
```

### Output Structure

| Stage | Output Path | Description |
|-------|-------------|-------------|
| PDF Parsing & Sentence Labeling | `workspace/structured_text/` | Labeled sentences extracted from PDFs |
| Info Extraction | `workspace/extract_info/` | Metric-related statements (activity, stability) |
| Filtering | `workspace/filtering/` | High-performance papers selected by metrics |
| Guidance | `workspace/guidance/` | Final trend insights and supporting summaries |

### Runtime Estimates

- **Small demo (5–10 PDFs)**: ~2 hours  
- **Larger datasets (~700 PDFs)**: < 24 hours (parallelized)

---

## 🧪 5. How It Works

The pipeline (`main.py`) runs the following steps:

### Step 1: Structured Text Extraction & Sentence Labeling

- `run_get_structured_text()` uses Mineru to convert PDFs into structured text
- Applies spaCy to split text into sentences
- Labels sentences for downstream LLM processing

Output:  
- `workspace/structured_text/labeled_sentences/`  
- `workspace/structured_text/text/`

### Step 2: Metric Extraction

- `run_extract_info_tool()` extracts metric-related sentences
- Categorizes into `activity` and `stability`
- Aggregates metrics at both individual and overall levels

Output:  
- `workspace/extract_info/metrics_info/`  
- `workspace/extract_info/individual_metrics/`  
- `workspace/extract_info/overall_metrics/`

### Step 3: Metric-Based Filtering

- `run_filtering_tool()` filters high-performance papers
- Configurable parameters:
  - `ratio`: proportion of top papers to retain
  - `primary_filtering_thres`: minimum metric threshold

Output:  
- `workspace/filtering/overall_high_performance_papers.json`

### Step 4: LLM-Guided Guidance Generation

- `run_generate_guidance_tool()` performs trend mining
- Uses high-performance papers to generate **guidance**
- Outputs trend types and supporting evidence

Output:  
- `workspace/guidance/guidance.json`  
- `workspace/guidance/support_summary/`

---

## ▶️ 6. Running on Your Own Data

1. Place your PDFs in `workspace/raw_pdf/`  
2. Ensure filenames are unique (DOI-based naming recommended)  
3. Run the full pipeline:

```bash
python main.py
```



---

## 📄 License

This project is licensed under the **MIT License**.  

---

## 🔗 Repository

Source code is available at:  
👉 [https://github.com/sunyao-coder/ResearchAgent](https://github.com/sunyao-coder/ResearchAgent)

