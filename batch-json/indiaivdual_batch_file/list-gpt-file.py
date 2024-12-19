from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve the API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def list_uploaded_files():
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set. Please check your .env file.")
        
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # List all uploaded files
        response = client.files.list()
        
        # Iterate over the file objects in the response
        print("List of uploaded files:")
        for file in response:
            print(f"ID: {file.id}, Filename: {file.filename}, Purpose: {file.purpose}, Created At: {file.created_at}, Status: {file.status}")
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    # Call the function to list all files
    list_uploaded_files()
