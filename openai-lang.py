import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

def process_json_and_rewrite(file_path, output_file):
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
                        # Send the extracted text to OpenAI API
                        completion = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant that rewrites content."},
                                {"role": "user", "content": extracted_text}
                            ]
                        )

                        # Extract the rewritten text from the response
                        if hasattr(completion.choices[0], 'message'):
                            rewritten_text = completion.choices[0].message.content
                        else:
                            raise AttributeError("Unexpected response structure: 'message' attribute is missing.")

                        # Write the rewritten text to the output file
                        output.write(f"Chapter: {chapter_name}\n")
                        output.write(f"Section: {section_name}\n")
                        output.write(f"Rewritten Text:\n{rewritten_text}\n")
                        output.write("\n" + "="*50 + "\n\n")  # Separator between sections
                        print(f"Processed: {chapter_name} -> {section_name}")

                    except Exception as e:
                        print(f"Error processing {chapter_name} -> {section_name}: {e}")

if __name__ == "__main__":
    input_json = input("Enter the path to the JSON file: ")
    output_txt = input("Enter the path for the output TXT file: ")
    process_json_and_rewrite(input_json, output_txt)
    print(f"Rewriting completed. Results saved in {output_txt}.")
