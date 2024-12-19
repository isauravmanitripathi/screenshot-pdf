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

def retrieve_batch(batch_id):
    """
    Retrieve and display details of a batch from OpenAI's API.
    """
    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Retrieve the batch details
        response = client.batches.retrieve(batch_id)

        # Print the response
        print("Batch details retrieved successfully!")
        print(response)
    except Exception as e:
        logging.exception(f"Failed to retrieve batch details for batch ID {batch_id}: {e}")

def list_batches():
    """
    List all batches from OpenAI's API.
    """
    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # List all batches
        batches = client.batches.list()
        for batch in batches:
            print(f"Batch ID: {batch.id}, Status: {batch.status}, Created At: {batch.created_at}")
    except Exception as e:
        logging.exception(f"Error listing batches: {e}")

if __name__ == "__main__":
    action = input("Enter 'fetch' to fetch file content, 'retrieve' to retrieve batch details, or 'list' to list all batches: ").strip().lower()

    if action == 'fetch':
        # Specify the file ID to fetch content
        file_id = input("Enter the file ID to fetch content: ").strip()
        fetch_file_content(file_id)
    elif action == 'retrieve':
        # Specify the batch ID to retrieve details
        batch_id = input("Enter the batch ID to retrieve details: ").strip()
        retrieve_batch(batch_id)
    elif action == 'list':
        # List all batches
        list_batches()
    else:
        print("Invalid action. Please enter 'fetch', 'retrieve', or 'list'.")


"""from openai import OpenAI

# Set your OpenAI API key
api_key =
client = OpenAI(api_key=api_key)

# List all batches
try:
    batches = client.batches.list()
    for batch in batches:
        print(f"Batch ID: {batch.id}, Status: {batch.status}, Created At: {batch.created_at}")
except Exception as e:
    print(f"Error listing batches: {e}")


	
	"""