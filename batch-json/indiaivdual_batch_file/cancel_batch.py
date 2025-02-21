import os
import argparse
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in the .env file.")

client = OpenAI(api_key=api_key)

def cancel_batch(batch_id):
    try:
        response = client.batches.cancel(batch_id)
        print(f"Canceled batch {batch_id} with new status: {response.status}")
    except Exception as e:
        print(f"Failed to cancel batch {batch_id}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cancel an OpenAI batch by ID")
    parser.add_argument("batch_id", help="The batch ID to cancel")
    args = parser.parse_args()

    cancel_batch(args.batch_id)
