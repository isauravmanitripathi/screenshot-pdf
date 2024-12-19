import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in the .env file.")

client = OpenAI(api_key=api_key)

def delete_completed_or_failed_batches():
    try:
        batches = client.batches.list()
        for batch in batches:
            if batch.status in ["completed", "failed"]:
                try:
                    response = client.batches.delete(batch.id)
                    print(f"Deleted batch {batch.id} with status {batch.status}")
                except Exception as e:
                    print(f"Failed to delete batch {batch.id}: {e}")
    except Exception as e:
        print(f"Error listing batches: {e}")

if __name__ == "__main__":
    delete_completed_or_failed_batches()
