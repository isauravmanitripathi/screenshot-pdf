import os
import json
import openai
import logging
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in your .env file.")

openai.api_key = API_KEY

LOG_DIR = "./gpt-logs"
PROCESSED_JSON_DIR = "./processed-json"

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PROCESSED_JSON_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a')
    ]
)

def load_log(json_path: str) -> dict:
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logging.info(f"Loading log for {json_path}")
            return json.load(f)
    logging.info(f"No log found for {json_path}. Starting fresh.")
    return {"processed_sections": []}

def save_log(json_path: str, log_data: dict):
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=4)
    logging.info(f"Log saved for {json_path}")

def save_processed_json(data: dict, original_json_path: str):
    processed_json_path = os.path.join(PROCESSED_JSON_DIR, os.path.basename(original_json_path))
    with open(processed_json_path, 'w') as f:
        json.dump(data, f, indent=4)
    logging.info(f"Processed JSON saved to {processed_json_path}")

def process_section_text(client, chunk: str, chapter_name: str, section_name: str, book_name: str) -> str:
    prompt = (
        f"You are an expert writer. Below is an excerpt from the book titled '{book_name}', "
        f"specifically from Chapter '{chapter_name}', Section '{section_name}'. The original text is:\n\n'{chunk}'\n\n"
        f"Rewrite this text, like we are explaining it to someone from a non-computational background."
    )

    max_retries = 5
    retry_attempts = 0

    while retry_attempts < max_retries:
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": chunk}
                ],
                max_tokens=12000
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            retry_attempts += 1
            sleep_time = min(3 * retry_attempts, 60)
            logging.warning(f"Error processing section: {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    
    logging.error("Failed to process section after multiple attempts.")
    return None

def process_section(client, chapter: dict, section: dict, log_data: dict, data: dict, original_json_path: str, book_name: str):
    section_identifier = f"{chapter['chapter_name']} - {section['section_name']}"

    if section_identifier in log_data["processed_sections"]:
        logging.info(f"Skipping already processed section: {section_identifier}")
        return

    if "extracted-text" in section:
        logging.info(f"Processing section '{section_identifier}'")

        processed_text = process_section_text(
            client,
            section['extracted-text'],
            chapter['chapter_name'],
            section['section_name'],
            book_name
        )
        
        if processed_text:
            section["gpt-text-processed"] = processed_text
            log_data["processed_sections"].append(section_identifier)
            save_processed_json(data, original_json_path)
            logging.info(f"Successfully processed section: {section_identifier}")
        else:
            logging.warning(f"No processed text for section: {section_identifier}")

def process_json_file(json_path: str, book_name: str):
    logging.info(f"Loading JSON file from {json_path}")
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        chapters = data.get("New item", {}).get("chapters", [])
        log_data = load_log(json_path)
        client = openai

        for chapter in chapters:
            logging.info(f"Processing chapter: {chapter['chapter_name']}")
            for section in chapter.get("sections", []):
                process_section(client, chapter, section, log_data, data, json_path, book_name)
        
        save_log(json_path, log_data)
        logging.info("Processing complete.")
    except Exception as e:
        logging.error(f"Error processing file: {e}")

if __name__ == "__main__":
    try:
        book_name = input("Enter the name of the book: ")
        json_path = input("Enter the path to your JSON file: ")
        
        if not os.path.exists(json_path):
            logging.error(f"File not found: {json_path}")
        else:
            process_json_file(json_path, book_name)
    except KeyboardInterrupt:
        logging.info("Processing interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
