import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

def process_json_and_handle_prompts(file_path, middle_file, output_file):
    # Open the JSON file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Open middle-answer file to save intermediate responses
    with open(middle_file, 'w') as middle_output:
        # Open final output file to save results
        with open(output_file, 'w') as final_output:
            # Iterate through chapters and sections
            chapters = data.get("New item", {}).get("chapters", [])
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

                            # Write the final response to the output file
                            final_output.write(f"Chapter: {chapter_name}\n")
                            final_output.write(f"Section: {section_name}\n")
                            final_output.write(f"Final Message:\n{final_message}\n")
                            final_output.write("\n" + "=" * 50 + "\n\n")
                            final_output.flush()

                            print(f"Finished processing: Chapter -> {chapter_name}, Section -> {section_name}")

                        except Exception as e:
                            print(f"Error processing Chapter -> {chapter_name}, Section -> {section_name}: {e}")

if __name__ == "__main__":
    input_json = input("Enter the path to the JSON file: ")
    middle_txt = "middle-answer.txt"  # Intermediate responses saved here
    output_txt = input("Enter the path for the final output TXT file: ")

    print("Starting processing...")
    process_json_and_handle_prompts(input_json, middle_txt, output_txt)
    print(f"Processing completed. Intermediate responses saved in {middle_txt}, final responses saved in {output_txt}.")
