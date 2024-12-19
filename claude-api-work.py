import os
import json
import logging
import time
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Your Anthropic API key from environment variables
API_KEY = os.getenv("CLAUDE_API_KEY")
if not API_KEY:
    raise ValueError("API key not found. Please set CLAUDE_API_KEY in the .env file.")

LOG_DIR = "./claude-logs"
PROCESSED_JSON_DIR = "./processed-json"

anthropic = Anthropic(api_key=API_KEY)

# Create directories if they don't exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(PROCESSED_JSON_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a')  # Log to file
    ]
)

# Prompt for book name
book_name = input("Enter the name of the book: ")

def load_log(json_path):
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logging.info(f"Loading log for {json_path}")
            return json.load(f)
    logging.info(f"No log found for {json_path}. Starting fresh.")
    return {"processed_sections": []}

def save_log(json_path, log_data):
    log_file = os.path.join(LOG_DIR, f"{os.path.basename(json_path)}_log.json")
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=4)
    logging.info(f"Log saved for {json_path}")

def process_paragraph(client, paragraph, chapter_name, section_name):
    prompt = f"Here is a text snippet '{book_name}', Chapter '{chapter_name}', Section '{section_name}': {paragraph}. Please rewrite the following text to create a completely different version. Your new text should change the perspective and voice, use different examples and analogies, reorganize the structure, modify the tone and style, and employ different terminology and expressions. Focus on different aspects of the topic, incorporate recent developments, and consider changing the format if appropriate. Introduce personal insights or opinions, and avoid direct paraphrasing by crafting original sentences and paragraphs. Please present your rewritten text in paragraph form without using bullet points or any point-form lists."

    max_retries = 20
    retry_attempts = 0

    while retry_attempts < max_retries:
        try:
            logging.info(f"Sending text to Claude for chapter '{chapter_name}', section '{section_name}'")
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            logging.info(f"Received response for chapter '{chapter_name}', section '{section_name}'")
            return message.content[0].text

        except anthropic.APIConnectionError as e:
            retry_attempts += 1
            sleep_time = 3 * retry_attempts  # 3, 6, 9, ..., up to 60 seconds
            sleep_time = min(sleep_time, 60)
            logging.warning(f"API connection error for chapter '{chapter_name}', section '{section_name}': {e}")
            logging.info(f"Retrying after {sleep_time} seconds (Attempt {retry_attempts}/{max_retries})...")
            time.sleep(sleep_time)
            continue

        except anthropic.RateLimitError as e:
            retry_attempts += 1
            sleep_time = 3 * retry_attempts
            sleep_time = min(sleep_time, 60)
            logging.warning(f"Rate limit error for chapter '{chapter_name}', section '{section_name}': {e}")
            logging.info(f"Retrying after {sleep_time} seconds (Attempt {retry_attempts}/{max_retries})...")
            time.sleep(sleep_time)
            continue

        except anthropic.APIError as e:
            logging.error(f"API error for chapter '{chapter_name}', section '{section_name}': {e}")
            return None

        except anthropic.AuthenticationError as e:
            logging.error(f"Authentication error for chapter '{chapter_name}', section '{section_name}': {e}")
            return None

        except Exception as e:
            logging.exception(f"Unexpected error processing paragraph for chapter '{chapter_name}', section '{section_name}': {e}")
            return None

    logging.error(f"Failed to process paragraph for chapter '{chapter_name}', section '{section_name}' after {max_retries} attempts.")
    return None

def save_processed_json(data, original_json_path):
    processed_json_path = os.path.join(PROCESSED_JSON_DIR, os.path.basename(original_json_path))
    with open(processed_json_path, 'w') as f:
        json.dump(data, f, indent=4)
    logging.info(f"Updated JSON file saved to {processed_json_path}")

def process_section(client, chapter, section, log_data, data, original_json_path):
    section_identifier = f"{chapter['chapter_name']} - {section['section_name']}"
    if section_identifier in log_data["processed_sections"]:
        logging.info(f"Skipping already processed section: {section_identifier}")
        return

    if "extracted-text" in section:
        logging.info(f"Processing section '{section_identifier}'")
        processed_text = process_paragraph(client, section['extracted-text'], chapter['chapter_name'], section['section_name'])
        if processed_text:
            section["claude-text-processed"] = processed_text  # Changed from gpt-text-processed
            log_data["processed_sections"].append(section_identifier)
            logging.info(f"Processed and added claude-text-processed to section: {section_identifier}")

            # Save the updated JSON file after processing each section
            save_processed_json(data, original_json_path)
        else:
            logging.warning(f"Failed to process section: {section_identifier}")

def process_json_file(json_path):
    # Load JSON data
    logging.info(f"Loading JSON file from {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Load or initialize log
    log_data = load_log(json_path)

    # Process each chapter and section
    for chapter in data.get("chapters", []):
        logging.info(f"Processing chapter: {chapter['chapter_name']}")
        for section in chapter.get("sections", []):
            process_section(anthropic, chapter, section, log_data, data, json_path)

    # Save final log at the end
    save_log(json_path, log_data)
    logging.info("Processing complete.")

if __name__ == "__main__":
    # Request JSON file path
    json_path = input("Enter the path to your JSON file: ")

    # Check if the file exists
    if not os.path.exists(json_path):
        logging.error(f"File not found: {json_path}")
    else:
        process_json_file(json_path)
