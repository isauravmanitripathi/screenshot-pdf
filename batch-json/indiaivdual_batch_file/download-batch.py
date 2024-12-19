import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in the .env file.")

# Directory for saving results
RESULTS_DIR = "./batch-results"
os.makedirs(RESULTS_DIR, exist_ok=True)

def fetch_file_content(file_id):
    """
    Fetch and save the content of a file from OpenAI's API.
    """
    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Fetch the content of the file
        response = client.files.content(file_id)

        # Extract the content properly as bytes
        content = response.read()

        # Save the raw content as a .jsonl file
        file_path = os.path.join(RESULTS_DIR, f"{file_id}_output.jsonl")
        with open(file_path, "wb") as f:
            f.write(content)
        logging.info(f"Raw file content saved to {file_path}")

        print(f"File content downloaded successfully:\n{file_path}")
        return file_path

    except Exception as e:
        logging.exception(f"Failed to fetch file content for file ID {file_id}: {e}")
        return None

if __name__ == "__main__":
    # Specify the file ID to fetch content
    file_id = input("Enter the file ID to fetch content: ").strip()

    # Fetch and save file content
    fetch_file_content(file_id)