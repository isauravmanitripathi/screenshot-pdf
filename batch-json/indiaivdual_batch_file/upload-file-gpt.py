from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def upload_file(file_path, purpose):
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set. Please check your .env file.")
        
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Open the file in binary read mode and upload
        with open(file_path, "rb") as file:
            response = client.files.create(
                file=file,
                purpose=purpose
            )
        
        # Print the response from the API
        print("File uploaded successfully!")
        print(response)
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    # Get the file path from the user
    file_path = input("Enter the path to the .jsonl file: ").strip()
    
    # Get the purpose from the user
    purpose = input("Enter the purpose of the file upload (e.g., fine-tune, assistants, batch): ").strip()
    
    # Call the upload function
    upload_file(file_path, purpose)
