import json
import os
import re

def sanitize_filename(name):
    """Sanitize the filename by replacing spaces and special characters with dashes."""
    # Replace spaces and special characters with dashes
    sanitized_name = re.sub(r'[^a-zA-Z0-9]', '-', name)
    # Remove consecutive dashes
    sanitized_name = re.sub(r'-+', '-', sanitized_name).strip('-')
    return sanitized_name

def count_words_and_characters(file_path):
    """Count the total number of words and characters in a file"""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    words = content.split()
    return len(words), len(content)

def extract_chapters_to_files(json_file_path, output_directory):
    # Read and parse the JSON file
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Get chapters from the JSON structure
    chapters = data.get("New item", {}).get("chapters", [])

    # Iterate through each chapter
    for chapter in chapters:
        raw_chapter_name = chapter.get("chapter_name", "Unnamed Chapter")
        chapter_name = sanitize_filename(raw_chapter_name)
        chapter_path = os.path.join(output_directory, f"{chapter_name}.txt")

        with open(chapter_path, 'w', encoding='utf-8') as chapter_file:
            # Write chapter content
            chapter_file.write(f"Chapter Name: {raw_chapter_name}\n\n")
            
            # Iterate through sections in the chapter
            sections = chapter.get("sections", [])
            for section in sections:
                section_name = section.get("section_name", "Unnamed Section")
                section_text = section.get("extracted-text", "No content available")

                # Write section content
                chapter_file.write(f"Section Name: {section_name}\n")
                chapter_file.write(f"Content:\n{section_text}\n\n")

        # Count words and characters in the created text file
        words, characters = count_words_and_characters(chapter_path)
        print(f"File: {chapter_path} - Words: {words}, Characters: {characters}")

if __name__ == "__main__":
    json_file_path = input("Enter the path of the JSON file: ").strip()
    output_directory = 'txt-pro-file'
    extract_chapters_to_files(json_file_path, output_directory)
