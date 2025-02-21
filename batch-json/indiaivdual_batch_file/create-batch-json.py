import os
import json
import logging
import uuid
import re

# Directories for logs and output
LOG_DIR = "./gpt-logs"
JSONL_OUTPUT_DIR = "./jsonl-output"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(JSONL_OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a', encoding='utf-8')
    ]
)

def load_json_file(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Error loading JSON file '{json_path}': {e}")
        return None

def save_jsonl_file(jsonl_data, output_path):
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            for entry in jsonl_data:
                file.write(json.dumps(entry, ensure_ascii=False) + '\n')
        logging.info(f"JSONL file saved: {output_path}")
    except Exception as e:
        logging.error(f"Error saving JSONL file '{output_path}': {e}")

def clean_text(text):
    """
    Clean and normalize text by removing unwanted characters.
    """
    if not text:
        return ""
    text = str(text)
    # Remove some specific characters and unwanted patterns
    text = text.replace('{', '').replace('}', '')
    text = text.replace('[', '').replace(']', '')
    text = text.replace('\\', '')
    text = text.replace('`', '')
    text = text.replace('|', '')
    text = re.sub(r'[^\w\s\.,;:!?"\'-]', ' ', text)
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    text = ' '.join(text.split())
    return text.strip()

def generate_prompt(chapter_name, section_name, text):
    """
    Generates the system prompt using the provided template.
    The {previous_context} is left empty in this batch processing.
    """
    previous_context = ""  # In this batch process, no previous sections are provided.
    cleaned_text = clean_text(text)
    prompt = (
        "You are provided with a piece of text which can be of any format—be it bullet points, paragraphs, or a mix of both. "
        "Your first task is to thoroughly read and understand the text and identify the underlying subject matter and details it conveys. "
        "After gaining a clear comprehension of the material, you are to write a long, detailed article in proper markdown format.\n\n"
        "The article must be comprehensive and should include an introduction, detailed analysis, and a conclusion or summary where applicable. "
        "Every detail mentioned in the original text must be covered and elaborated upon. It is essential that you add relevant additional information, "
        "context, and insights to expand upon the given content. Your explanation should be aimed at an expert audience, using precise language and technical "
        "terminology where appropriate. Structure your response with proper markdown elements such as headings, subheadings, and lists if needed, ensuring that "
        "it is both clear and well-organized.\n\n"
        f"You are addressing a topic from Chapter: '{chapter_name}', Section: '{section_name}'. The current text to analyze is presented below. "
        "Avoid repeating any information that might have been covered in previous sections, as indicated by the context provided.\n\n"
        f"{previous_context}\n"
        f"Current Text to Analyze:\n{cleaned_text}\n\n"
        "[System/Instruction to the AI Model]:\n"
        "First, analyze the provided text carefully to extract all key points and details. Then, compose a detailed markdown article that explains the subject matter comprehensively. "
        "Ensure that every aspect of the text is discussed, enriched with additional context and insights, and presented in a clear and structured manner suitable for an expert audience.\n\n"
        "I need it to write articles long lengthy articles"
    )
    return prompt

def create_jsonl_entry(chapter_name, section_name, section_id, section_number, text, model="gpt-4o-mini-2024-07-18", max_tokens=15000):
    # Use section_id if available; otherwise, fall back to section_number or an index-based identifier.
    base_custom_id = str(section_id) if section_id is not None and str(section_id).strip() != "" else str(section_number)
    if not base_custom_id or base_custom_id.strip() == "":
        base_custom_id = "request"
    custom_id = f"{base_custom_id}-rewrite"
    system_prompt = generate_prompt(chapter_name, section_name, text)
    entry = {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": max_tokens
        }
    }
    return entry

def process_json_file(json_path):
    logging.info(f"Processing JSON file: {json_path}")
    data = load_json_file(json_path)
    if not data:
        logging.error("Failed to load JSON data.")
        return

    # Determine if the JSON is a list or if it contains an "articles" key.
    sections = None
    if isinstance(data, list):
        sections = data
    elif isinstance(data, dict):
        if "articles" in data and isinstance(data["articles"], list):
            sections = data["articles"]
        else:
            logging.error("Input JSON file does not contain a list of sections or an 'articles' key.")
            return
    else:
        logging.error("Input JSON file is not in a recognized format (list or dict with 'articles').")
        return

    jsonl_data = []
    existing_custom_ids = set()
    for idx, section in enumerate(sections, 1):
        chapter_name = section.get("chapter_name", "Chapter")
        section_name = section.get("section_name", "Section")
        section_number = section.get("section_number", "")
        text = section.get("text", "").strip()

        # Use section_id if provided; otherwise, use section_number or index.
        section_id = section.get("section_id", idx)
        if not text:
            logging.warning(f"Section '{section_name}' (ID: {section_id}) has no text. Skipping.")
            continue

        jsonl_entry = create_jsonl_entry(chapter_name, section_name, section_id, section_number, text)
        base_custom_id = jsonl_entry["custom_id"]
        if base_custom_id in existing_custom_ids:
            unique_suffix = uuid.uuid4().hex[:8]
            jsonl_entry["custom_id"] = f"{base_custom_id}-{unique_suffix}"
            logging.warning(f"Duplicate custom_id '{base_custom_id}' found. Assigned new custom_id '{jsonl_entry['custom_id']}'.")
        existing_custom_ids.add(jsonl_entry["custom_id"])
        jsonl_data.append(jsonl_entry)
        logging.info(f"Added entry for Section (ID: {section_id}) -> Custom ID: {jsonl_entry['custom_id']}")

    base_filename = os.path.basename(json_path).replace('.json', '')
    output_path = os.path.join(JSONL_OUTPUT_DIR, f"{base_filename}.jsonl")
    if jsonl_data:
        save_jsonl_file(jsonl_data, output_path)
    else:
        logging.warning("No valid entries found to process.")

    logging.info("Processing complete.")

if __name__ == "__main__":
    json_path = input("Enter the path to your JSON file: ").strip()
    if not os.path.isfile(json_path):
        logging.error(f"File not found: {json_path}")
    else:
        process_json_file(json_path)
