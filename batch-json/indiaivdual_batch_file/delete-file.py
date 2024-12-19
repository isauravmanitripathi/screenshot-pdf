import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in the .env file.")

def delete_file(file_id):
    try:
        # Initialize the OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Delete the file
        response = client.files.delete(file_id)
        
        # Print the response
        print("File deleted successfully!")
        print(response)
    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    # Prompt for the file ID to delete
    file_id = input("Enter the file ID to delete: ").strip()
    
    # Call the delete function
    delete_file(file_id)
