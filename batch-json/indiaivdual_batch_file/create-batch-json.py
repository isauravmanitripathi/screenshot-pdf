import os
import json
import logging
import uuid

# Directories for logs and output
LOG_DIR = "./gpt-logs"
JSONL_OUTPUT_DIR = "./jsonl-output"

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(JSONL_OUTPUT_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a', encoding='utf-8')
    ]
)

# Prompt for book name
book_name = input("Enter the name of the book: ").strip()

def load_json_file(json_path):
    """
    Loads a JSON file from the given path.

    Args:
        json_path (str): Path to the JSON file.

    Returns:
        dict or None: Parsed JSON data or None if an error occurs.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Error loading JSON file '{json_path}': {e}")
        return None

def save_jsonl_file(jsonl_data, output_path):
    """
    Saves a list of dictionaries to a JSONL file.

    Args:
        jsonl_data (list): List of dictionaries to save.
        output_path (str): Path to the output JSONL file.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as file:
            for entry in jsonl_data:
                file.write(json.dumps(entry, ensure_ascii=False) + '\n')
        logging.info(f"JSONL file saved: {output_path}")
    except Exception as e:
        logging.error(f"Error saving JSONL file '{output_path}': {e}")

def create_jsonl_entry(chapter_name, section_name, section_id, prompt_type, model="gpt-4o-mini-2024-07-18", max_tokens=15000):
    """
    Creates a JSONL entry with a custom_id based on section_id and prompt type.

    Args:
        chapter_name (str): Name of the chapter.
        section_name (str): Name of the section.
        section_id (float or int): ID of the section (e.g., 84.17).
        prompt_type (str): Type of prompt ('rewrite' or 'translate').
        model (str): The OpenAI model to use.
        max_tokens (int): Maximum tokens for the response.

    Returns:
        dict: A dictionary representing a single JSONL entry.
    """
    # Replace '.' with '-' in section_id to create base_custom_id
    base_custom_id = str(section_id).replace('.', '-')

    # Append prompt type to custom_id to differentiate entries
    custom_id = f"{base_custom_id}-{prompt_type}"

    # Define the system prompt based on the prompt_type
    if prompt_type == "rewrite":
        system_prompt = (
            f"You are an expert writer. Below is an excerpt from my book titled '{book_name}', "
            f"specifically from Chapter '{chapter_name}', Section '{section_name}'. "
            "Your task is to understand the content and the underlying message of the original text, "
            "rewrite the entire thing while keeping the original meaning intact. Expand the content by "
            "adding relevant and additional information to make the text more comprehensive, increase "
            "the length of text to maximum, and enhance its readability and engagement without altering "
            "its fundamental purpose."
        )
    elif prompt_type == "translate":
        system_prompt = (
            f"You are a professional translator. Below is an excerpt from my book titled '{book_name}', "
            f"specifically from Chapter '{chapter_name}', Section '{section_name}'. "
            "Translate the following text into Hindi accurately, preserving the original meaning and context."
        )
    else:
        logging.error(f"Unknown prompt type: {prompt_type}. Defaulting to rewrite prompt.")
        system_prompt = (
            f"You are an expert writer. Below is an excerpt from my book titled '{book_name}', "
            f"specifically from Chapter '{chapter_name}', Section '{section_name}'. "
            "Your task is to understand the content and the underlying message of the original text, "
            "rewrite the entire thing while keeping the original meaning intact. Expand the content by "
            "adding relevant and additional information to make the text more comprehensive, increase "
            "the length of text to maximum, and enhance its readability and engagement without altering "
            "its fundamental purpose."
        )

    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ""}  # Placeholder for the extracted text
            ],
            "max_tokens": max_tokens
        }
    }

def process_json_file(json_path):
    """
    Processes the input JSON file and creates corresponding JSONL files for OpenAI batch processing.

    Args:
        json_path (str): Path to the input JSON file.
    """
    logging.info(f"Processing JSON file: {json_path}")
    data = load_json_file(json_path)

    if not data:
        logging.error("Failed to load JSON data.")
        return

    # Initialize two separate lists for each JSONL file
    jsonl_data_rewrite = []
    jsonl_data_translate = []
    existing_custom_ids = set()  # To track and ensure uniqueness of custom_id

    # Iterate through chapters
    for chapter in data.get("New item", {}).get("chapters", []):
        chapter_name = chapter.get("chapter_name", "Unknown Chapter")

        # Iterate through sections within each chapter
        for section in chapter.get("sections", []):
            section_name = section.get("section_name", "Unknown Section")
            paragraph = section.get("extracted-text", "").strip()
            section_id = section.get("section_id", None)

            if paragraph and section_id is not None:
                # Process for both 'rewrite' and 'translate' prompts
                for prompt_type in ["rewrite", "translate"]:
                    # Create initial custom_id
                    base_custom_id = str(section_id).replace('.', '-')
                    custom_id = f"{base_custom_id}-{prompt_type}"

                    # Check for duplicate custom_id
                    if custom_id in existing_custom_ids:
                        unique_suffix = uuid.uuid4().hex[:8]  # Generate a short UUID suffix
                        custom_id = f"{base_custom_id}-{prompt_type}-{unique_suffix}"
                        logging.warning(f"Duplicate custom_id '{base_custom_id}-{prompt_type}' found. Assigned new custom_id '{custom_id}'.")
                    existing_custom_ids.add(custom_id)

                    # Create JSONL entry with the specified prompt_type
                    jsonl_entry = create_jsonl_entry(chapter_name, section_name, section_id, prompt_type)
                    
                    # Assign the extracted text to the user content
                    jsonl_entry["custom_id"] = custom_id  # Update custom_id if modified
                    jsonl_entry["body"]["messages"][1]["content"] = paragraph

                    # Append to the respective list based on prompt_type
                    if prompt_type == "rewrite":
                        jsonl_data_rewrite.append(jsonl_entry)
                        logging.info(f"Added rewrite entry for Section ID: {section_id} -> Custom ID: {custom_id}")
                    elif prompt_type == "translate":
                        jsonl_data_translate.append(jsonl_entry)
                        logging.info(f"Added translate entry for Section ID: {section_id} -> Custom ID: {custom_id}")
            else:
                if not paragraph:
                    logging.warning(f"Section ID {section_id} ('{section_name}') has no extracted text. Skipping.")
                if section_id is None:
                    logging.warning(f"Section '{section_name}' is missing 'section_id'. Skipping.")

    # Define the base name for output files
    base_filename = os.path.basename(json_path).replace('.json', '')
    
    # Define output paths
    output_path_rewrite = os.path.join(JSONL_OUTPUT_DIR, f"{base_filename}.jsonl")
    output_path_translate = os.path.join(JSONL_OUTPUT_DIR, f"hindi-{base_filename}.jsonl")

    # Save the JSONL files if there is data
    if jsonl_data_rewrite:
        save_jsonl_file(jsonl_data_rewrite, output_path_rewrite)
    else:
        logging.warning("No valid 'rewrite' entries found to process.")

    if jsonl_data_translate:
        save_jsonl_file(jsonl_data_translate, output_path_translate)
    else:
        logging.warning("No valid 'translate' entries found to process.")

    logging.info("Processing complete.")

if __name__ == "__main__":
    # Request JSON file path
    json_path = input("Enter the path to your JSON file: ").strip()

    # Check if the file exists
    if not os.path.isfile(json_path):
        logging.error(f"File not found: {json_path}")
    else:
        process_json_file(json_path)
