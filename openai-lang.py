import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

def process_json_and_extract_keypoints(file_path, output_file):
    # Open the JSON file
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Open output file to save results
    with open(output_file, 'w') as output:
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
                        # Send the extracted text to OpenAI API with updated prompt
                        completion = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are an assistant that extracts key points from the provided text."},
                                {"role": "user", "content": f"Please read the following text and provide the main key points:\n\n{extracted_text}"}
                            ]
                        )

                        # Extract the key points from the response
                        key_points = completion.choices[0].message.content

                        # Write the key points to the output file
                        output.write(f"Chapter: {chapter_name}\n")
                        output.write(f"Section: {section_name}\n")
                        output.write(f"Key Points:\n{key_points}\n")
                        output.write("\n" + "="*50 + "\n\n")  # Separator between sections
                        print(f"Processed: {chapter_name} -> {section_name}")

                    except Exception as e:
                        print(f"Error processing {chapter_name} -> {section_name}: {e}")

if __name__ == "__main__":
    input_json = input("Enter the path to the JSON file: ")
    output_txt = input("Enter the path for the output TXT file: ")
    process_json_and_extract_keypoints(input_json, output_txt)
    print(f"Key points extraction completed. Results saved in {output_txt}.")
