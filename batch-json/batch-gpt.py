import os
import json
import logging
import openai
from dotenv import load_dotenv

def create_batch_json():
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
            logging.FileHandler(os.path.join(LOG_DIR, "processing.log"), mode='a')
        ]
    )

    # Prompt for book name
    book_name = input("Enter the name of the book: ")

    def load_json_file(json_path):
        try:
            with open(json_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            logging.error(f"Error loading JSON file: {e}")
            return None

    def save_jsonl_file(jsonl_data, output_path):
        try:
            with open(output_path, 'w') as file:
                for entry in jsonl_data:
                    file.write(json.dumps(entry) + '\n')
                logging.info(f"JSONL file saved: {output_path}")
        except Exception as e:
            logging.error(f"Error saving JSONL file: {e}")

    def create_jsonl_entry(paragraph, chapter_name, section_name, custom_id):
        prompt = f"You are an expert writer. Below is an excerpt from my book titled '{book_name}', specifically from Chapter '{chapter_name}', Section '{section_name}'. The original text is: '{paragraph}'. Your task is to understand the content and the underlying message of the original text, rewrite the entire thing while keeping the original meaning remains intact. Expand the content by adding relevant and additional information to make the text more comprehensive and make the text long, and enhance its readability and engagement without altering its fundamental purpose."

        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini-2024-07-18",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": paragraph}
                ],
                "max_tokens": 40000
            }
        }

    def process_json_file(json_path):
        logging.info(f"Processing JSON file: {json_path}")
        data = load_json_file(json_path)

        if not data:
            logging.error("Failed to load JSON data.")
            return

        jsonl_data = []
        custom_id_counter = 1

        # Process each chapter and section
        for chapter in data.get("chapters", []):
            chapter_name = chapter.get("chapter_name", "Unknown Chapter")
            for section in chapter.get("sections", []):
                section_name = section.get("section_name", "Unknown Section")
                paragraph = section.get("extracted-text", "")
                if paragraph:
                    # Create a unique custom_id for each request
                    custom_id = f"request-{custom_id_counter}"
                    custom_id_counter += 1

                    # Create JSONL entry
                    jsonl_entry = create_jsonl_entry(paragraph, chapter_name, section_name, custom_id)
                    jsonl_data.append(jsonl_entry)

        # Save the .jsonl file
        output_path = os.path.join(JSONL_OUTPUT_DIR, os.path.basename(json_path).replace('.json', '.jsonl'))
        save_jsonl_file(jsonl_data, output_path)
        logging.info("Processing complete.")
        print(f"JSONL file saved to: {output_path}")

    # Request JSON file path
    json_path = input("Enter the path to your JSON file: ")

    # Check if the file exists
    if not os.path.exists(json_path):
        logging.error(f"File not found: {json_path}")
        print(f"File not found: {json_path}")
    else:
        process_json_file(json_path)

def upload_file():
    try:
        # Get the file path from the user
        file_path = input("Enter the path to the .jsonl file: ").strip()

        # Get the purpose from the user
        purpose = input("Enter the purpose of the file upload (e.g., fine-tune, answers, search, embeddings): ").strip()

        # Open the file in binary read mode and upload
        with open(file_path, "rb") as file:
            response = openai.File.create(
                file=file,
                purpose=purpose
            )

        # Print the response from the API
        print("File uploaded successfully!")
        print(response)
    except Exception as e:
        print("An error occurred:", e)

def main():
    # Load environment variables from the .env file
    load_dotenv()

    # Get the API key from the environment
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        print("API key is required to proceed. Set it in the .env file.")
        return

    openai.api_key = OPENAI_API_KEY

    while True:
        print("\nSelect an option:")
        print("1. Create batch JSON file")
        print("2. Upload file to OpenAI")
        print("9. Exit")
        choice = input("Enter the number of your choice: ").strip()

        if choice == "1":
            create_batch_json()
        elif choice == "2":
            upload_file()
        elif choice == "9":
            print("Exiting.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
