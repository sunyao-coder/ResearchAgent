import os
import os.path as osp
import subprocess
import json

import spacy

from app.tool.utils import get_subdirs, load_json, save_json


def run_mineru_command(pdf_path, output_path):
    """Run the mineru command to extract text from a PDF file."""
    command = ["mineru", "-p", pdf_path, "-o", output_path]
    subprocess.run(command, check=True)


def extract_texts_from_pdfs(pdf_root: str, output_root: str):
    """
    Extract text from all PDF files in the given directory using mineru.

    :param pdf_root: Directory containing PDF files
    :param output_root: Directory to save extracted text files
    """
    if not osp.exists(output_root):
        os.makedirs(output_root)

    pdf_files = [f for f in os.listdir(pdf_root) if f.lower().endswith(".pdf")]
    for pdf_file in pdf_files:
        pdf_path = osp.join(pdf_root, pdf_file)
        # output_path = osp.join(output_root, osp.splitext(pdf_file)[0])
        run_mineru_command(pdf_path, output_root)


class TextProcessor:
    def __init__(self, model_name="en_core_web_trf"):
        self.nlp = spacy.load(model_name)

    def get_segmented_sentences(self, raw_text):
        doc = self.nlp(raw_text)
        sentences = [sent.text for sent in doc.sents]
        return sentences


def get_labeled_text(text_processor, raw_text_list):

    labeled_text = []

    title_count = 0
    content_count = 0
    image_caption_count = 0
    equation_count = 0
    table_count = 0

    for raw_text in raw_text_list:
        labeled_sentence = []
        text_type = raw_text["type"]
        result_content = {}

        if (
            text_type == "text"
            and "text_level" in raw_text
            and raw_text["text_level"] == 1
        ):
            text = raw_text["text"]
            if not text:
                continue
            labeled_sentence.append({f"T_{title_count:04d}": text})
            text_type = "title"
            title_count += 1

        elif text_type == "text":
            text = raw_text["text"]
            if not text:
                continue
            seg_sentence = text_processor.get_segmented_sentences(text)
            for sentence in seg_sentence:
                labeled_sentence.append({f"C_{content_count:04d}": sentence})
                content_count += 1
        elif text_type == "image":
            if raw_text["image_caption"]:
                text = raw_text["image_caption"][0]
            else:
                continue
            seg_sentence = text_processor.get_segmented_sentences(text)
            for sentence in seg_sentence:
                labeled_sentence.append({f"I_{image_caption_count:04d}": sentence})
                image_caption_count += 1
        elif text_type == "equation":
            text = raw_text["text"]
            if not text:
                continue
            labeled_sentence.append({f"E_{equation_count:04d}": text})
            equation_count += 1
        elif text_type == "table":
            if raw_text["table_caption"]:
                text = raw_text["table_caption"][0]
            else:
                continue
            labeled_sentence.append({f"B_{table_count:04d}": text})
            result_content["table_body"] = raw_text["table_body"]
            table_count += 1
        else:
            print(f"Unknown text type: {text_type}")

        result_content["content"] = labeled_sentence
        result_content["type"] = text_type
        labeled_text.append(result_content)
    return labeled_text


def get_labeled_sentences(labeled_text):
    labeled_sentences = []
    for item in labeled_text:
        content = item["content"]
        for sentence in content:
            for key, value in sentence.items():
                labeled_sentences.append({key: value})
    return labeled_sentences


def get_raw_text(raw_text_root, file_name):
    file_path = f"{raw_text_root}/{file_name}/hybrid_auto/{file_name}_content_list.json"
    content_list = load_json(file_path)
    return content_list


def split_and_label_sentences(raw_text_root, output_root, labeled_sentences_root):
    text_processor = TextProcessor()

    subdir_list = get_subdirs(raw_text_root)
    for file_path in subdir_list:
        print(f"Processing {file_path}...")
        file_name = ".".join(os.path.basename(file_path).split("."))
        output_file_path = f"{output_root}/{file_name}.json"
        if not os.path.exists(output_file_path):
            os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
            raw_text_list = get_raw_text(raw_text_root, file_name)
            labeled_text = get_labeled_text(text_processor, raw_text_list)

            save_json(output_file_path, labeled_text)

        labeled_sentences_file_path = f"{labeled_sentences_root}/{file_name}.json"
        if not os.path.exists(labeled_sentences_file_path):
            os.makedirs(os.path.dirname(labeled_sentences_file_path), exist_ok=True)
            labeled_text = load_json(output_file_path)
            labeled_sentences = get_labeled_sentences(labeled_text)
            save_json(labeled_sentences_file_path, labeled_sentences)
