import json
import os
from openai import OpenAI
import copy

# Initialize OpenAI client
client = OpenAI()

def process_json_and_update(file_path, middle_file):
    # Open the JSON file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Create a copy of the JSON to avoid modifying the original
    updated_data = copy.deepcopy(data)

    # Derive the path for the updated JSON file
    base_dir = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    updated_json_path = os.path.join(base_dir, base_name.replace(".json", "-gpt-written.json"))

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

                if extracted_text:
                    try:
                        print(f"Processing: Chapter -> {chapter_name}, Section -> {section_name}")

                        # Step 1: Extract Key Points
                        print("Sending first prompt to extract key points...")
                        key_points_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are an assistant that extracts key points from the provided text."},
                                {"role": "user", "content": f"Please read the following text and provide the main key points:\n\n{extracted_text}"}
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

                        # Step 2: Perform Second Prompt (e.g., Detailed Explanation)
                        print("Sending second prompt to process key points...")
                        second_response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are an assistant that expands on the key points to provide a detailed explanation."},
                                {"role": "user", "content": f"Based on these key points, provide a detailed explanation:\n\n{key_points}"}
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
    process_json_and_update(input_json, middle_txt)
    print(f"Processing completed. Intermediate responses saved in {middle_txt}.")
