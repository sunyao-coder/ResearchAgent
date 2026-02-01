import json
import os


def get_files(dir: str, extension: str = None):
    """
    Get all files under a directory.

    :param dir: Directory path
    :param extension: Optional file extension filter
    :return: List of file paths
    """
    files = []
    for root, _, filenames in os.walk(dir):
        for filename in filenames:
            if extension is None or filename.endswith(extension):
                files.append(os.path.join(root, filename))
    return files


def load_json(file_path: str):
    """
    Read a JSON file and return its content.

    :param file_path: Path to the JSON file
    :return: Content of the JSON file
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def save_json(file_path: str, data: dict):
    """
    Save data to a JSON file.

    :param file_path: Path to the JSON file
    :param data: Data to be saved
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def save_txt(file_path: str, data: str):
    """
    Save data to a TXT file.

    :param file_path: Path to the TXT file
    :param data: Data to be saved
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(data)


def load_txt(file_path: str):
    """
    Read a TXT file and return its content.

    :param file_path: Path to the TXT file
    :return: Content of the TXT file
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = f.read()
    return data


def convert_str_to_dict(data: str):
    """
    Convert a string to a dictionary.

    :param data: String to be converted
    :return: Converted dictionary
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {}


def extract_brace_content(s):
    """
    Extract content within the outermost curly braces.

    :param s: Input string
    :return: Extracted content or None
    """
    start = s.find("{")
    end = s.rfind("}")

    if start != -1 and end != -1 and start < end:
        return s[start : end + 1]
    else:
        return None


def extract_bracket_content(s):
    """
    Extract content within the outermost square brackets.

    :param s: Input string
    :return: Extracted content or None
    """
    start = s.find("[")
    end = s.rfind("]")

    if start != -1 and end != -1 and start < end:
        return s[start : end + 1]
    else:
        return None


# def get_subdirs(dir: str):
#     """
#     Get all immediate subdirectories under a directory.


#     :param dir: Directory path
#     :return: List of subdirectory paths
#     """
#     subdirs = []
#     for root, dirs, _ in os.walk(dir):
#         for d in dirs:
#             subdirs.append(os.path.join(root, d))
#     return subdirs
def get_subdirs(dir: str):
    """
    Get all immediate subdirectories under a directory.

    :param dir: Directory path
    :return: List of subdirectory paths
    """
    subdirs = []
    for entry in os.listdir(dir):
        full_path = os.path.join(dir, entry)
        if os.path.isdir(full_path):
            subdirs.append(full_path)
    return subdirs
