import json
import os
import google.generativeai as genai
import copy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API (API key now read from .env file)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Select the Gemini model (using the experimental one as per previous discussion)
model_name = "gemini-2.0-flash-lite-preview-02-05" # or "gemini-pro" for more stable version
generation_config_key_points = { # Configuration for key points extraction - may need to be less verbose
    "temperature": 0.3, # Lower temperature for more focused key points
    "top_p": 0.9,
    "top_k": 30,
    "max_output_tokens": 500, # Limit tokens for key points
}

generation_config_detailed_explanation = { # Configuration for detailed explanation - allows longer and more creative output
    "temperature": 0.7, # Higher temperature for more creative text
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192, # Increased max tokens for detailed text
}


def process_json_and_update_with_checks_gemini(file_path, middle_file):
    # Derive the path for the updated JSON file
    base_dir = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    updated_json_path = os.path.join(base_dir, base_name.replace(".json", "-gemini-written.json"))

    # Check if the updated JSON file already exists
    if os.path.exists(updated_json_path):
        print(f"Found existing processed file: {updated_json_path}. Resuming from where it left off.")
        with open(updated_json_path, 'r') as f:
            updated_data = json.load(f)
    else:
        print(f"No processed file found. Starting fresh processing.")
        with open(file_path, 'r') as f:
            updated_data = json.load(f)

    # Open middle-answer file to save intermediate responses
    with open(middle_file, 'w') as middle_output:
        # Iterate through chapters and sections
        chapters = updated_data.get("New item", {}).get("chapters", [])
        for chapter in chapters:
            chapter_name = chapter.get("chapter_name", "Unknown Chapter")
            sections = chapter.get("sections", [])

            for section in sections:
                section_name = section.get("section_name", "Unknown Section")
                extracted_text = section.get("extracted-text", "")

                # Skip already processed sections
                if "gpt-processed-text" in section: # Keeping the same key name for processed text for consistency, can be renamed to "gemini-processed-text" if preferred
                    print(f"Skipping already processed: Chapter -> {chapter_name}, Section -> {section_name}")
                    continue

                if extracted_text:
                    try:
                        print(f"Processing: Chapter -> {chapter_name}, Section -> {section_name}")

                        # Step 1: Extract Key Points using Gemini
                        print("Sending first prompt to extract key points using Gemini...")
                        model_key_points = genai.GenerativeModel(model_name=model_name, generation_config=generation_config_key_points) # Model for key points
                        key_points_prompt = f"You are an expert at identifying the absolute most critical and essential points in any given text. Your task is to read the text I provide and extract only the core essence.  Focus solely on identifying the absolute core message, primary arguments, key facts, and crucial conclusions – the information that is absolutely necessary to grasp the text's meaning. Ignore supporting details, examples, background information, anecdotes, and any information that is not fundamentally critical to understanding the main point.  Think of it as stripping away everything but the bare minimum needed to convey the central idea. Present these absolute most important points as a concise, bulleted list. Each bullet point should be a single, extremely clear, and highly informative sentence summarizing a core piece of absolutely essential information from the text. \n\n{extracted_text}"
                        key_points_response = model_key_points.generate_content(key_points_prompt)
                        key_points = key_points_response.text
                        print("Received response for key points from Gemini.")

                        # Write the key points to the middle-answer file
                        middle_output.write(f"Chapter: {chapter_name}\n")
                        middle_output.write(f"Section: {section_name}\n")
                        middle_output.write(f"Key Points (Gemini):\n{key_points}\n")
                        middle_output.write("\n" + "=" * 50 + "\n\n")
                        middle_output.flush()

                        # Step 2: Perform Second Prompt (Detailed Explanation) using Gemini
                        print("Sending second prompt to process key points using Gemini...")
                        model_detailed = genai.GenerativeModel(model_name=model_name, generation_config=generation_config_detailed_explanation) # Model for detailed explanation
                        detailed_prompt = f"You are an expert at elaborating on concise points and transforming them into richly detailed and informative paragraphs.  Your task is to take each point I provide below and develop it into a stand-alone paragraph that is deeply informative, insightful, and comprehensive. Expand with Details:  Provide extensive details, explanations, and supporting information related to the point.  Think about the who, what, when, where, why, and how of the point.  Include specific examples, relevant facts, underlying mechanisms, processes, or contributing factors. Add Depth and Context: Explore the point in depth.  Consider its significance, implications, and broader context. Explain its importance, its impact, and its connections to related concepts or areas.  Elaborate on nuances and complexities. Make it Informative and Engaging: Use clear, precise, and descriptive language.  Ensure the paragraph is highly informative and keeps the reader engaged with the depth of information provided. Aim to make each paragraph a substantial and self-contained exploration of the given point. No Introductions, Conclusions, or Headings:  Focus solely on developing each point into a detailed paragraph.  Do not include any introductory paragraphs, concluding summaries, titles, section headings, or any framing language. Each output should be just a series of in-depth paragraphs, one for each point provided. Write about 2000 words.\n\n{key_points}"
                        second_response = model_detailed.generate_content(detailed_prompt)
                        final_message = second_response.text
                        print("Received response for detailed explanation from Gemini.")

                        # Update the JSON with the GPT processed text (keeping the original key name)
                        section["gpt-processed-text"] = final_message # You can change this to "gemini-processed-text" if you want to differentiate

                        # Save the updated JSON in real-time
                        with open(updated_json_path, 'w') as updated_file:
                            json.dump(updated_data, updated_file, indent=4)

                        print(f"Finished processing: Chapter -> {chapter_name}, Section -> {section_name} using Gemini")

                    except Exception as e:
                        print(f"Error processing Chapter -> {chapter_name}, Section -> {section_name} using Gemini: {e}")

    print(f"Updated JSON saved at: {updated_json_path}")

if __name__ == "__main__":
    input_json = input("Enter the path to the JSON file: ")
    middle_txt = "middle-answer-gemini.txt"  # Intermediate responses saved here, changed name to differentiate

    print("Starting processing with Gemini...")
    process_json_and_update_with_checks_gemini(input_json, middle_txt)
    print(f"Processing completed using Gemini. Intermediate responses saved in {middle_txt}.")