import os
import json
import uuid
import threading
import subprocess  # For invoking screencapture command
from PIL import Image  # For image verification
import pytesseract  # For OCR

# Base directory to store screenshots
BASE_SCREENSHOTS_DIR = './screenshots-images-2'
os.makedirs(BASE_SCREENSHOTS_DIR, exist_ok=True)
JSON_DIR = './json-book'
os.makedirs(JSON_DIR, exist_ok=True)
TEMP_DIR = './temp_screenshots'
os.makedirs(TEMP_DIR, exist_ok=True)


class SharedState:
    def __init__(self):
        self.data = {"chapters": []}
        self.current_chapter_index = -1
        self.current_section_index = -1
        self.current_section_path = None
        self.lock = threading.Lock()


def process_section(shared_state, json_file_path, chapter_index, section_index):
    with shared_state.lock:
        section = shared_state.data["chapters"][chapter_index]["sections"][section_index]
        image_paths = section.get("images", [])
        code_image_paths = section.get("code_images", [])
        section_name = section["section_name"]
        chapter_name = shared_state.data["chapters"][chapter_index]["chapter_name"]
        image_paths = list(image_paths)
        code_image_paths = list(code_image_paths)

    print_box(f"Processing Section: '{section_name}' in Chapter: '{chapter_name}'")

    def extract_texts(image_list):
        texts = []
        for image_path in image_list:
            try:
                with Image.open(image_path) as img:
                    text = pytesseract.image_to_string(img)
                    texts.append(text)
            except Exception as e:
                error_message = f"Error extracting text from image {image_path}: {e}"
                print(error_message)
                with shared_state.lock:
                    section.setdefault("errors", []).append(error_message)
        return "\n".join(texts)

    # Extract text from images and code images
    section["extracted-text"] = extract_texts(image_paths)
    section["extracted-code"] = extract_texts(code_image_paths)

    with shared_state.lock:
        # Save the updated JSON data to the file
        with open(json_file_path, 'w') as f:
            json.dump(shared_state.data, f, indent=4)

    print_box(f"Finished Processing Section: '{section_name}'\n")


def capture_screenshot_mac(target_path):
    try:
        subprocess.run(['screencapture', '-i', target_path], check=True)
        return target_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to capture screenshot: {e}")
        return None


def extract_text_from_image(image_path):
    if not os.path.exists(image_path):
        print(f"Image file not found: {image_path}")
        return None
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img).strip()
            return text
    except Exception as e:
        print(f"Error extracting text from image {image_path}: {e}")
        return None


def get_name(prompt_instructions, capture_key, manual_key):
    while True:
        print_box(prompt_instructions)
        user_input = input("Your choice: ").strip()
        if user_input == capture_key:
            unique_name = f"{uuid.uuid4()}.png"
            image_path = os.path.join(TEMP_DIR, unique_name)
            if capture_screenshot_mac(image_path):
                name = extract_text_from_image(image_path)
                if name:
                    print(f"\nExtracted name: '{name}'\n")
                    return name
                else:
                    print("\nNo text extracted from image. Please try again.\n")
            else:
                print("\nFailed to capture screenshot. Please try again.\n")
        elif user_input == manual_key:
            name = input("Enter the name manually: ").strip()
            print(f"\nEntered name: '{name}'\n")
            return name
        else:
            print(f"\nInvalid input. Please enter '{capture_key}' or '{manual_key}'.\n")


def get_chapter_name():
    instructions = (
        "Enter the name of the chapter:\n"
        " - Press 'a' and Enter to capture a screenshot and extract the chapter name.\n"
        " - Type 'aa' and press Enter to manually type the chapter name."
    )
    return get_name(instructions, 'a', 'aa')


def get_section_name():
    instructions = (
        "Enter the name of the section:\n"
        " - Press 'd' and Enter to capture a screenshot and extract the section name.\n"
        " - Type 'dd' and press Enter to manually type the section name."
    )
    return get_name(instructions, 'd', 'dd')


def print_box(text):
    lines = text.strip().split('\n')
    width = max(len(line) for line in lines) + 4
    print("\n" + "=" * width)
    for line in lines:
        print(f"| {line.ljust(width - 4)} |")
    print("=" * width + "\n")


class ScreenshotHandler:
    def __init__(self, shared_state, json_file_path):
        self.shared_state = shared_state
        self.json_file_path = json_file_path

    def add_image_to_section(self, file_path, image_type='images'):
        with self.shared_state.lock:
            if self.shared_state.current_section_path is None:
                print("No active section to add the image.")
                return
            unique_name = f"{uuid.uuid4()}{os.path.splitext(file_path)[1]}"
            new_file_path = os.path.join(self.shared_state.current_section_path, unique_name)
            try:
                if os.path.abspath(file_path) != os.path.abspath(new_file_path):
                    os.rename(file_path, new_file_path)
            except Exception as e:
                print(f"Error moving file: {e}")
                return

            chapter_index = self.shared_state.current_chapter_index
            section_index = self.shared_state.current_section_index
            section = self.shared_state.data["chapters"][chapter_index]["sections"][section_index]
            section.setdefault(image_type, []).append(new_file_path)
            section["status"] = "images testing in progress"

            with open(self.json_file_path, 'w') as f:
                json.dump(self.shared_state.data, f, indent=4)

        image_type_display = "code image" if image_type == "code_images" else "image"
        print(f"\nAdded {image_type_display} '{unique_name}' to section '{section['section_name']}'\n")
        threading.Thread(target=self.verify_image, args=(new_file_path, chapter_index, section_index)).start()

    def verify_image(self, image_path, chapter_index, section_index):
        try:
            with Image.open(image_path) as img:
                img.verify()
            print(f"Verified image: {os.path.basename(image_path)} - OK\n")
            with self.shared_state.lock:
                section = self.shared_state.data["chapters"][chapter_index]["sections"][section_index]
                if not section.get("errors"):
                    section["status"] = "images tested ok"
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.shared_state.data, f, indent=4)
        except Exception as e:
            error_message = f"Error verifying image {image_path}: {e}"
            print(error_message)
            with self.shared_state.lock:
                section = self.shared_state.data["chapters"][chapter_index]["sections"][section_index]
                section.setdefault("errors", []).append(error_message)
                section["status"] = "errors encountered"
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.shared_state.data, f, indent=4)


def main():
    welcome_message = (
        "Welcome to the Screenshot and OCR Program!\n"
        "Instructions:\n"
        " - For chapter names:\n"
        "     - Press 'a' and Enter to capture a screenshot and extract the chapter name.\n"
        "     - Type 'aa' and Enter to manually type the chapter name.\n"
        " - For section names:\n"
        "     - Press 'd' and Enter to capture a screenshot and extract the section name.\n"
        "     - Type 'dd' and Enter to manually type the section name.\n"
        " - Commands during operation:\n"
        "     - Press Enter to continue.\n"
        "     - Type 's' to capture a screenshot for the current section.\n"
        "     - Type 'w' to capture a screenshot of code.\n"
        "     - Type 'n' to start a new section.\n"
        "     - Type 'c' to start a new chapter.\n"
        "     - Type 'exit' to quit the program.\n"
    )
    print_box(welcome_message)

    choice = input("Create a new JSON file or use an existing one? (new/existing): ").strip().lower()

    shared_state = SharedState()
    json_file_path = None

    if choice == 'new':
        json_file_name = input("Enter the name for the new JSON file (without extension): ").strip()
        json_file_path = os.path.join(JSON_DIR, json_file_name + '.json')
        shared_state.data = {"chapters": []}

        chapter_name = get_chapter_name()
        with shared_state.lock:
            shared_state.current_chapter_index += 1
            shared_state.current_section_index = -1
            chapter_dir = os.path.join(BASE_SCREENSHOTS_DIR, f"chapter_{shared_state.current_chapter_index+1}")
            os.makedirs(chapter_dir, exist_ok=True)
            shared_state.data["chapters"].append({
                "chapter_name": chapter_name,
                "chapter_path": chapter_dir,
                "sections": []
            })

        section_name = get_section_name()
        with shared_state.lock:
            shared_state.current_section_index += 1
            section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
            os.makedirs(section_dir, exist_ok=True)
            shared_state.current_section_path = section_dir
            shared_state.data["chapters"][-1]["sections"].append({
                "section_name": section_name,
                "section_path": section_dir,
                "images": [],
                "code_images": [],
                "status": "images testing in progress",
                "errors": []
            })

        print_box(f"Started New Chapter: '{chapter_name}'\nCurrent Section: '{section_name}'")

    elif choice == 'existing':
        json_file_path = input("Enter the path to the existing JSON file: ").strip()
        if not os.path.isfile(json_file_path):
            print(f"File not found: {json_file_path}")
            return
        with open(json_file_path, 'r') as f:
            try:
                shared_state.data = json.load(f)
            except json.JSONDecodeError:
                print("Invalid JSON file.")
                return
        if not shared_state.data.get("chapters"):
            print("The JSON file has no chapters.")
            return
        with shared_state.lock:
            shared_state.current_chapter_index = len(shared_state.data["chapters"]) - 1
            chapter = shared_state.data["chapters"][shared_state.current_chapter_index]
            if not chapter.get("sections"):
                print("The last chapter has no sections.")
                return
            shared_state.current_section_index = len(chapter["sections"]) - 1
            section = chapter["sections"][shared_state.current_section_index]
            shared_state.current_section_path = section["section_path"]
            if not os.path.exists(shared_state.current_section_path):
                os.makedirs(shared_state.current_section_path, exist_ok=True)
            print_box(f"Resuming from Chapter: '{chapter['chapter_name']}'\nCurrent Section: '{section['section_name']}'")
    else:
        print("Invalid choice. Please enter 'new' or 'existing'.")
        return

    event_handler = ScreenshotHandler(shared_state, json_file_path)
    user_input_loop(shared_state, json_file_path, event_handler)


def user_input_loop(shared_state, json_file_path, event_handler):
    command_instructions = (
        "Listening for commands...\n"
        "Available commands:\n"
        " - Press Enter to continue.\n"
        " - Type 's' to capture a screenshot for the current section.\n"
        " - Type 'w' to capture a screenshot of code.\n"
        " - Type 'n' to start a new section.\n"
        " - Type 'c' to start a new chapter.\n"
        " - Type 'exit' to quit the program.\n"
    )
    print_box(command_instructions)

    try:
        while True:
            user_input = input(f"Chapter '{shared_state.data['chapters'][shared_state.current_chapter_index]['chapter_name']}', Section '{shared_state.data['chapters'][shared_state.current_chapter_index]['sections'][shared_state.current_section_index]['section_name']}'\nEnter command: ").strip().lower()

            if user_input in ['n', 'next']:
                with shared_state.lock:
                    prev_chapter_index = shared_state.current_chapter_index
                    prev_section_index = shared_state.current_section_index

                if prev_section_index >= 0:
                    threading.Thread(
                        target=process_section,
                        args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
                    ).start()

                section_name = get_section_name()
                with shared_state.lock:
                    shared_state.current_section_index += 1
                    chapter_dir = shared_state.data["chapters"][shared_state.current_chapter_index]["chapter_path"]
                    section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
                    os.makedirs(section_dir, exist_ok=True)
                    shared_state.current_section_path = section_dir
                    shared_state.data["chapters"][shared_state.current_chapter_index]["sections"].append({
                        "section_name": section_name,
                        "section_path": section_dir,
                        "images": [],
                        "code_images": [],
                        "status": "images testing in progress",
                        "errors": []
                    })
                print_box(f"Moved to New Section: '{section_name}'")

            elif user_input in ['c', 'chapter']:
                with shared_state.lock:
                    prev_chapter_index = shared_state.current_chapter_index
                    prev_section_index = shared_state.current_section_index

                if prev_section_index >= 0:
                    threading.Thread(
                        target=process_section,
                        args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
                    ).start()

                chapter_name = get_chapter_name()
                with shared_state.lock:
                    shared_state.current_chapter_index += 1
                    shared_state.current_section_index = -1
                    chapter_dir = os.path.join(BASE_SCREENSHOTS_DIR, f"chapter_{shared_state.current_chapter_index+1}")
                    os.makedirs(chapter_dir, exist_ok=True)
                    shared_state.data["chapters"].append({
                        "chapter_name": chapter_name,
                        "chapter_path": chapter_dir,
                        "sections": []
                    })

                section_name = get_section_name()
                with shared_state.lock:
                    shared_state.current_section_index += 1
                    section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
                    os.makedirs(section_dir, exist_ok=True)
                    shared_state.current_section_path = section_dir
                    shared_state.data["chapters"][-1]["sections"].append({
                        "section_name": section_name,
                        "section_path": section_dir,
                        "images": [],
                        "code_images": [],
                        "status": "images testing in progress",
                        "errors": []
                    })
                print_box(f"Moved to New Chapter: '{chapter_name}'\nCurrent Section: '{section_name}'")

            elif user_input == 's':
                unique_name = f"{uuid.uuid4()}.png"
                with shared_state.lock:
                    if shared_state.current_section_path is None:
                        print("No active section to add the image.")
                        continue
                    image_path = os.path.join(shared_state.current_section_path, unique_name)
                if capture_screenshot_mac(image_path):
                    threading.Thread(target=event_handler.add_image_to_section, args=(image_path,)).start()
                else:
                    print("Failed to capture the screenshot.")

            elif user_input == 'w':
                unique_name = f"{uuid.uuid4()}.png"
                with shared_state.lock:
                    if shared_state.current_section_path is None:
                        print("No active section to add the image.")
                        continue
                    image_path = os.path.join(shared_state.current_section_path, unique_name)
                if capture_screenshot_mac(image_path):
                    threading.Thread(
                        target=event_handler.add_image_to_section,
                        args=(image_path, 'code_images')
                    ).start()
                else:
                    print("Failed to capture the screenshot.")

            elif user_input == 'exit':
                print("Exiting the program.")
                with shared_state.lock:
                    prev_chapter_index = shared_state.current_chapter_index
                    prev_section_index = shared_state.current_section_index
                if prev_section_index >= 0:
                    process_section(shared_state, json_file_path, prev_chapter_index, prev_section_index)
                break

            elif os.path.isfile(user_input):
                threading.Thread(target=event_handler.add_image_to_section, args=(user_input,)).start()

            elif user_input == '':
                continue

            else:
                print(f"Invalid command or file not found: '{user_input}'")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")

    finally:
        with shared_state.lock:
            with open(json_file_path, 'w') as f:
                json.dump(shared_state.data, f, indent=4)
        print("\nJSON file saved. Goodbye!\n")


if __name__ == "__main__":
    main()
