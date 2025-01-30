import json
import os
from openai import OpenAI
import copy

# Initialize OpenAI client
client = OpenAI()

def process_json_and_update_with_checks(file_path, middle_file):
    # Derive the path for the updated JSON file
    base_dir = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    updated_json_path = os.path.join(base_dir, base_name.replace(".json", "-gpt-written.json"))

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
                if "gpt-processed-text" in section:
                    print(f"Skipping already processed: Chapter -> {chapter_name}, Section -> {section_name}")
                    continue

                if extracted_text:
                    try:
                        print(f"Processing: Chapter -> {chapter_name}, Section -> {section_name}")

                        # Step 1: Extract Key Points
                        print("Sending first prompt to extract key points...")
                        key_points_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are an assistant that extracts key points from the provided text."},
                                {"role": "user", "content": f"Please read the following text, understand it, and in key points tell what the text is talking about. Ignore examples, just focus on the main message:\n\n{extracted_text}"}
                            ]
                        )
                        key_points = key_points_response.choices[0].message.content
                        print("Received response for key points.")

                        # Write the key points to the middle-answer file
                        middle_output.write(f"Chapter: {chapter_name}\n")
                        middle_output.write(f"Section: {section_name}\n")
                        middle_output.write(f"Key Points:\n{key_points}\n")
                        middle_output.write("\n" + "=" * 50 + "\n\n")
                        middle_output.flush()

                        # Step 2: Perform Second Prompt (Detailed Explanation)
                        print("Sending second prompt to process key points...")
                        second_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are an assistant that expands on the key points to provide a detailed explanation."},
                                {"role": "user", "content": f"Based on these key points, please write paragraphs as if they are part of an article. Exclude introductions or summaries, focus only on detailed, informative content:\n\n{key_points}"}
                            ]
                        )
                        final_message = second_response.choices[0].message.content
                        print("Received response for detailed explanation.")

                        # Update the JSON with the GPT processed text
                        section["gpt-processed-text"] = final_message

                        # Save the updated JSON in real-time
                        with open(updated_json_path, 'w') as updated_file:
                            json.dump(updated_data, updated_file, indent=4)

                        print(f"Finished processing: Chapter -> {chapter_name}, Section -> {section_name}")

                    except Exception as e:
                        print(f"Error processing Chapter -> {chapter_name}, Section -> {section_name}: {e}")

    print(f"Updated JSON saved at: {updated_json_path}")

if __name__ == "__main__":
    input_json = input("Enter the path to the JSON file: ")
    middle_txt = "middle-answer.txt"  # Intermediate responses saved here

    print("Starting processing...")
    process_json_and_update_with_checks(input_json, middle_txt)
    print(f"Processing completed. Intermediate responses saved in {middle_txt}.")
