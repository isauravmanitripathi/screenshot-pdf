import json
import os

def create_output_directories():
    txt_dir = "./txt-books"
    md_dir = "./markdown-books"
    
    if not os.path.exists(txt_dir):
        os.makedirs(txt_dir)
    if not os.path.exists(md_dir):
        os.makedirs(md_dir)
        
    return txt_dir, md_dir

def extract_content(json_data, txt_dir, md_dir, filename):
    txt_content = ""
    md_content = ""
    
    # Process each chapter
    for chapter in json_data['chapters']:
        chapter_name = chapter['chapter_name'].replace('\n', ' ').strip()
        
        # Add chapter to txt content
        txt_content += f"\nCHAPTER: {chapter_name}\n\n"
        
        # Add chapter to markdown content
        md_content += f"\n# {chapter_name}\n\n"
        
        # Process each section in the chapter
        for section in chapter['sections']:
            section_name = section['section_name'].replace('\n', ' ').strip()
            
            # Extract claude processed text
            content = section.get('claude-text-processed', '').strip()
            if not content:
                continue
                
            # Add section to txt content
            txt_content += f"SECTION: {section_name}\n\n"
            txt_content += f"{content}\n\n"
            
            # Add section to markdown content
            md_content += f"## {section_name}\n\n"
            md_content += f"{content}\n\n"
    
    # Write content to files
    txt_file = os.path.join(txt_dir, f"{filename}.txt")
    md_file = os.path.join(md_dir, f"{filename}.md")
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(txt_content)
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    return txt_file, md_file

def main():
    print("\nWelcome to JSON to Text/Markdown Converter!")
    print("------------------------------------------")
    
    # Get JSON file path from user
    while True:
        json_file_path = input("\nEnter the path to your JSON file: ").strip()
        if os.path.exists(json_file_path):
            break
        print("Error: File not found. Please enter a valid file path.")
    
    # Get filename from user (without extension)
    while True:
        filename = input("\nEnter the desired filename (without extension): ").strip()
        if filename:
            break
        print("Error: Filename cannot be empty.")
    
    try:
        # Create output directories
        txt_dir, md_dir = create_output_directories()
        
        # Read JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        # Extract content and create files
        txt_file, md_file = extract_content(json_data, txt_dir, md_dir, filename)
        
        print("\nFiles created successfully!")
        print(f"Text file: {txt_file}")
        print(f"Markdown file: {md_file}")
        
    except json.JSONDecodeError:
        print("\nError: Invalid JSON file format")
    except Exception as e:
        print(f"\nError: An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()