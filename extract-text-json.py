import json
import re

def extract_gpt_text(file_path, output_file):
    try:
        # Open and load the JSON file
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Prepare to collect all extracted text
        collected_text = []

        # Navigate the JSON structure to extract the desired text
        chapters = data.get("New item", {}).get("chapters", [])

        for chapter in chapters:
            chapter_name = chapter.get("chapter_name", "Unknown Chapter")
            collected_text.append(f"--- {chapter_name} ---\n")

            for section in chapter.get("sections", []):
                section_name = section.get("section_name", "Unknown Section")
                gpt_text = section.get("extracted-text", "No text available.")

                # Clean Markdown symbols from the text
                cleaned_text = re.sub(r'[\#\*`_\-]', '', gpt_text)

                # Append cleaned text to the collected text list
                collected_text.append(f"Section: {section_name}\n\n{cleaned_text}\n")

        # Write the collected text to the output file
        with open(output_file, 'w', encoding='utf-8') as output:
            output.writelines(collected_text)

        print(f"Extracted text has been saved to {output_file}")

    except FileNotFoundError:
        print("The file path provided does not exist. Please check and try again.")
    except json.JSONDecodeError:
        print("The file is not a valid JSON file. Please check the content.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Ask the user for the JSON file path
    file_path = input("Please enter the path to your JSON file: ").strip()

    # Specify the output text file name
    output_file = input("Please enter the name for the output text file (e.g., output.txt): ").strip()

    extract_gpt_text(file_path, output_file)
