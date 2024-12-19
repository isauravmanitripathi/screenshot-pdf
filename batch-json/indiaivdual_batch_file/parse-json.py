import json
import os

def parse_and_save_as_text(jsonl_file, output_folder):
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        output_text_file = os.path.join(output_folder, os.path.basename(jsonl_file).replace(".jsonl", ".txt"))
        
        with open(jsonl_file, "r") as jsonl, open(output_text_file, "w") as text_file:
            for line in jsonl:
                try:
                    data = json.loads(line)
                    content = data.get("response", {}).get("body", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        clean_content = content.replace("-", "").replace("#", "").replace("*", "")
                        text_file.write(clean_content + "\n\n")
                except json.JSONDecodeError as e:
                    print(f"Error decoding line: {line.strip()} - {e}")
        
        print(f"Content successfully saved to {output_text_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    input_file_path = input("Enter the path to your JSONL file: ")
    output_folder = "./Txt-files"
    parse_and_save_as_text(input_file_path, output_folder)
