from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def create_batch(file_id):
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set. Please check your .env file.")
        
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Create a batch process
        response = client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        
        # Print the response
        print("Batch created successfully!")
        print(response)
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    # File ID to be processed
    file_id = 'file-46gk4ACcLnmGX2K7PNGdtL'
    
    # Call the function to create a batch
    create_batch(file_id)
