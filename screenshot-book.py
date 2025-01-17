import os
import json
import uuid
import threading
import subprocess
from typing import Optional, List
from PIL import Image
import pytesseract
from pynput import keyboard
import queue
import signal
import time

# Constants
BASE_SCREENSHOTS_DIR = './screenshots-images-2'
JSON_DIR = './json-book'
TEMP_DIR = './temp_screenshots'

# Create necessary directories
for directory in [BASE_SCREENSHOTS_DIR, JSON_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)

class SharedState:
    def __init__(self):
        self.data = {"New item": {"chapters": []}}  # Modified structure
        self.current_chapter_index = -1
        self.current_section_index = -1
        self.current_section_path = None
        self.lock = threading.Lock()
        self.command_queue = queue.Queue()
        self.running = True

class KeyboardListener:
    def __init__(self, shared_state: SharedState):
        self.shared_state = shared_state
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.context = "main"  # Current context for commands
        self.name_capture_mode = False
        self.manual_input_buffer = ""
        self.last_key_time = 0
        self.double_press_threshold = 0.2
        self.single_press_timer = None

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def handle_delayed_single_press(self, char):
        if self.manual_input_buffer == char:
            self.shared_state.command_queue.put(char)
            self.manual_input_buffer = ""
            self.last_key_time = 0

    def on_press(self, key):
        if not self.shared_state.running:
            return False

        try:
            char = key.char if hasattr(key, 'char') else None

            if char:
                current_time = time.time()

                if self.context == "main":
                    if char in ['s', 'w', 'r', 'c', 'q']:
                        self.shared_state.command_queue.put(char)
                        self._show_contextual_help(f"Command registered: {char}")
                elif self.context == "name_capture":
                    if char in ['a', 'd']:
                        if self.single_press_timer:
                            self.single_press_timer.cancel()
                            self.single_press_timer = None

                        if (current_time - self.last_key_time <= self.double_press_threshold and 
                            self.manual_input_buffer == char):
                            self.shared_state.command_queue.put(char + char)
                            self.manual_input_buffer = ""
                            self.last_key_time = 0
                        else:
                            self.manual_input_buffer = char
                            self.last_key_time = current_time
                            self.single_press_timer = threading.Timer(
                                self.double_press_threshold,
                                self.handle_delayed_single_press,
                                args=[char]
                            )
                            self.single_press_timer.start()

        except AttributeError:
            pass

    def set_context(self, context: str):
        self.context = context
        self._show_contextual_help()

    def _show_contextual_help(self, message: str = None):
        if message:
            print(f"\n{message}")

        if self.context == "main":
            print("\nAvailable commands:")
            print(" s: Capture screenshot")
            print(" w: Capture code screenshot")
            print(" r: New section")
            print(" c: New chapter")
            print(" q: Quit program")
        elif self.context == "name_capture":
            print("\nCapture name:")
            print(" a: Capture chapter name")
            print(" d: Capture section name")
            print("Type 'aa' or 'dd' to enter name manually")

class ScreenshotHandler:
    def __init__(self, shared_state: SharedState, json_file_path: str):
        self.shared_state = shared_state
        self.json_file_path = json_file_path

    def add_image_to_section(self, file_path: str, image_type: str = 'images'):
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
            section = self.shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
            section.setdefault(image_type, []).append(new_file_path)
            section["status"] = "images testing in progress"

            with open(self.json_file_path, 'w') as f:
                json.dump(self.shared_state.data, f, indent=4)

        image_type_display = "code image" if image_type == "code_images" else "image"
        print(f"\nAdded {image_type_display} '{unique_name}' to section '{section['section_name']}' (ID: {section['section_id']})")
        threading.Thread(target=self.verify_image, args=(new_file_path, chapter_index, section_index)).start()

    def verify_image(self, image_path: str, chapter_index: int, section_index: int):
        try:
            with Image.open(image_path) as img:
                img.verify()
            print(f"Verified image: {os.path.basename(image_path)} - OK")

            with self.shared_state.lock:
                section = self.shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
                if not section.get("errors"):
                    section["status"] = "images tested ok"
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.shared_state.data, f, indent=4)
        except Exception as e:
            error_message = f"Error verifying image {image_path}: {e}"
            print(error_message)

            with self.shared_state.lock:
                section = self.shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
                section.setdefault("errors", []).append(error_message)
                section["status"] = "errors encountered"
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.shared_state.data, f, indent=4)

def capture_screenshot_mac(target_path: str) -> Optional[str]:
    try:
        subprocess.run(['screencapture', '-i', target_path], check=True)
        return target_path
    except subprocess.CalledProcessError as e:
        print(f"Failed to capture screenshot: {e}")
        return None

def extract_text_from_image(image_path: str) -> Optional[str]:
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

def process_section(shared_state: SharedState, json_file_path: str, chapter_index: int, section_index: int):
    with shared_state.lock:
        section = shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
        image_paths = section.get("images", [])
        code_image_paths = section.get("code_images", [])
        section_name = section["section_name"]
        section_id = section["section_id"]
        chapter_name = shared_state.data["New item"]["chapters"][chapter_index]["chapter_name"]
        image_paths = list(image_paths)
        code_image_paths = list(code_image_paths)

    print(f"\nProcessing Section: '{section_name}' (ID: {section_id}) in Chapter: '{chapter_name}'")
    print(f"Found {len(image_paths)} images and {len(code_image_paths)} code images to process...")

    def extract_texts(image_list: List[str], type_name: str) -> str:
        texts = []
        total = len(image_list)
        for idx, image_path in enumerate(image_list, 1):
            try:
                print(f"Processing {type_name} {idx}/{total}: {os.path.basename(image_path)}")
                with Image.open(image_path) as img:
                    text = pytesseract.image_to_string(img)
                    texts.append(text)
            except Exception as e:
                error_message = f"Error extracting text from image {image_path}: {e}"
                print(error_message)
                with shared_state.lock:
                    section.setdefault("errors", []).append(error_message)
        return "\n".join(texts)

    print("\nExtracting text from regular images...")
    section["extracted-text"] = extract_texts(image_paths, "image")

    print("\nExtracting text from code images...")
    section["extracted-code"] = extract_texts(code_image_paths, "code image")

    with shared_state.lock:
        with open(json_file_path, 'w') as f:
            json.dump(shared_state.data, f, indent=4)

    print(f"\nFinished Processing Section: '{section_name}' (ID: {section_id})")
    print(f"Saved results to JSON file: {json_file_path}")

def get_name(shared_state: SharedState, capture_key: str, manual_key: str, prompt_instructions: str) -> Optional[str]:
    print(prompt_instructions)

    while True:
        try:
            cmd = shared_state.command_queue.get(timeout=0.1)

            if cmd == capture_key:
                unique_name = f"{uuid.uuid4()}.png"
                image_path = os.path.join(TEMP_DIR, unique_name)
                if capture_screenshot_mac(image_path):
                    name = extract_text_from_image(image_path)
                    if name:
                        print(f"\nExtracted name: '{name}'")
                        return name
                    else:
                        print("\nNo text extracted from image. Please try again.")
                else:
                    print("\nFailed to capture screenshot. Please try again.")
            elif cmd == manual_key:
                name = input("Enter the name manually: ").strip()
                print(f"\nEntered name: '{name}'")
                return name

        except queue.Empty:
            continue

def cleanup_and_quit(shared_state: SharedState, json_file_path: str, keyboard_listener: KeyboardListener):
    print("\nInitiating cleanup process...")

    with shared_state.lock:
        prev_chapter_index = shared_state.current_chapter_index
        prev_section_index = shared_state.current_section_index

        if prev_section_index >= 0:
            print("\nProcessing final section before quitting...")
            thread = threading.Thread(
                target=process_section,
                args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
            )
            thread.start()
            thread.join(timeout=20)
            if thread.is_alive():
                print("Processing final section is taking too long. Proceeding with cleanup.")

        print("\nSaving final state to JSON file...")
        with open(json_file_path, 'w') as f:
            json.dump(shared_state.data, f, indent=4)

    print("\nStopping keyboard listener...")
    keyboard_listener.stop()

    print("\nCleanup complete! Program terminated successfully.")
    shared_state.running = False

def handle_section_creation(shared_state: SharedState, keyboard_listener: KeyboardListener, json_file_path: str):
    prev_chapter_index = shared_state.current_chapter_index
    prev_section_index = shared_state.current_section_index

    if prev_section_index >= 0:
        threading.Thread(
            target=process_section,
            args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
        ).start()

    keyboard_listener.set_context("name_capture")
    section_name = get_name(shared_state, 'd', 'dd', "Capture section name (d/dd)")
    keyboard_listener.set_context("main")

    with shared_state.lock:
        shared_state.current_section_index += 1
        chapter_id = shared_state.data["New item"]["chapters"][shared_state.current_chapter_index]["chapter_id"]
        section_id = float(f"{chapter_id}.{shared_state.current_section_index + 1}")
        
        chapter_dir = shared_state.data["New item"]["chapters"][shared_state.current_chapter_index]["chapter_path"]
        section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
        os.makedirs(section_dir, exist_ok=True)
        shared_state.current_section_path = section_dir
        
        shared_state.data["New item"]["chapters"][shared_state.current_chapter_index]["sections"].append({
            "section_id": section_id,
            "section_name": section_name,
            "section_path": section_dir,
            "images": [],
            "code_images": [],
            "status": "images testing in progress",
            "errors": [],
            "extracted-text": "",
            "extracted-code": ""
        })
    print(f"\nMoved to New Section: '{section_name}' (ID: {section_id})")

def handle_chapter_creation(shared_state: SharedState, keyboard_listener: KeyboardListener, json_file_path: str):
    prev_chapter_index = shared_state.current_chapter_index
    prev_section_index = shared_state.current_section_index

    if prev_section_index >= 0:
        threading.Thread(
            target=process_section,
            args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
        ).start()

    keyboard_listener.set_context("name_capture")
    chapter_name = get_name(shared_state, 'a', 'aa', "Capture chapter name (a/aa)")
    keyboard_listener.set_context("main")

    with shared_state.lock:
        shared_state.current_chapter_index += 1
        chapter_id = shared_state.current_chapter_index + 1
        shared_state.current_section_index = -1
        chapter_dir = os.path.join(BASE_SCREENSHOTS_DIR, f"chapter_{chapter_id}")
        os.makedirs(chapter_dir, exist_ok=True)
        
        shared_state.data["New item"]["chapters"].append({
            "chapter_id": chapter_id,
            "chapter_name": chapter_name,
            "chapter_path": chapter_dir,
            "sections": []
        })

    keyboard_listener.set_context("name_capture")
    section_name = get_name(shared_state, 'd', 'dd', "Capture section name (d/dd)")
    keyboard_listener.set_context("main")

    with shared_state.lock:
        shared_state.current_section_index += 1
        section_id = float(f"{chapter_id}.{shared_state.current_section_index + 1}")
        section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
        os.makedirs(section_dir, exist_ok=True)
        shared_state.current_section_path = section_dir
        
        shared_state.data["New item"]["chapters"][-1]["sections"].append({
            "section_id": section_id,
            "section_name": section_name,
            "section_path": section_dir,
            "images": [],
            "code_images": [],
            "status": "images testing in progress",
            "errors": [],
            "extracted-text": "",
            "extracted-code": ""
        })
    print(f"\nMoved to New Chapter: '{chapter_name}' (ID: {chapter_id})\nCurrent Section: '{section_name}' (ID: {section_id})")

def main():
    print("\nWelcome to the Screenshot and OCR Program!")
    print("\nThis version supports single-key commands - no need to press Enter!")

    choice = input("Create a new JSON file or use an existing one? (new/existing): ").strip().lower()

    shared_state = SharedState()
    json_file_path = None
    keyboard_listener = None

    if choice == 'new':
        json_file_name = input("Enter the name for the new JSON file (without extension): ").strip()
        json_file_path = os.path.join(JSON_DIR, f"{json_file_name}.json")

        keyboard_listener = KeyboardListener(shared_state)
        keyboard_listener.start()

        keyboard_listener.set_context("name_capture")
        chapter_name = get_name(shared_state, 'a', 'aa', "Capture chapter name (a/aa)")

        with shared_state.lock:
            shared_state.current_chapter_index += 1
            chapter_id = shared_state.current_chapter_index + 1
            chapter_dir = os.path.join(BASE_SCREENSHOTS_DIR, f"chapter_{chapter_id}")
            os.makedirs(chapter_dir, exist_ok=True)
            
            shared_state.data["New item"]["chapters"].append({
                "chapter_id": chapter_id,
                "chapter_name": chapter_name,
                "chapter_path": chapter_dir,
                "sections": []
            })

        section_name = get_name(shared_state, 'd', 'dd', "Capture section name (d/dd)")
        keyboard_listener.set_context("main")

        with shared_state.lock:
            shared_state.current_section_index += 1
            section_id = float(f"{chapter_id}.{shared_state.current_section_index + 1}")
            section_dir = os.path.join(chapter_dir, f"section_{shared_state.current_section_index+1}")
            os.makedirs(section_dir, exist_ok=True)
            shared_state.current_section_path = section_dir
            
            shared_state.data["New item"]["chapters"][-1]["sections"].append({
                "section_id": section_id,
                "section_name": section_name,
                "section_path": section_dir,
                "images": [],
                "code_images": [],
                "status": "images testing in progress",
                "errors": [],
                "extracted-text": "",
                "extracted-code": ""
            })

        print(f"\nStarted New Chapter: '{chapter_name}' (ID: {chapter_id})\nCurrent Section: '{section_name}' (ID: {section_id})")

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

        if not shared_state.data.get("New item", {}).get("chapters"):
            print("The JSON file has no chapters or invalid format.")
            return

        keyboard_listener = KeyboardListener(shared_state)
        keyboard_listener.start()

        with shared_state.lock:
            shared_state.current_chapter_index = len(shared_state.data["New item"]["chapters"]) - 1
            chapter = shared_state.data["New item"]["chapters"][shared_state.current_chapter_index]
            if not chapter.get("sections"):
                print("The last chapter has no sections.")
                return
            shared_state.current_section_index = len(chapter["sections"]) - 1
            section = chapter["sections"][shared_state.current_section_index]
            shared_state.current_section_path = section["section_path"]
            if not os.path.exists(shared_state.current_section_path):
                os.makedirs(shared_state.current_section_path, exist_ok=True)
            print(f"\nResuming from Chapter: '{chapter['chapter_name']}' (ID: {chapter['chapter_id']})")
            print(f"Current Section: '{section['section_name']}' (ID: {section['section_id']})")
    else:
        print("Invalid choice. Please enter 'new' or 'existing'.")
        return

    event_handler = ScreenshotHandler(shared_state, json_file_path)

    def signal_handler(signum, frame):
        print("\nReceived interrupt signal. Cleaning up...")
        cleanup_and_quit(shared_state, json_file_path, keyboard_listener)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        keyboard_listener.set_context("main")
        print("\nReady for commands! Press keys without Enter:")
        print(" s: Screenshot")
        print(" w: Code Screenshot")
        print(" r: New Section")
        print(" c: New Chapter")
        print(" q: Quit")

        while shared_state.running:
            try:
                cmd = shared_state.command_queue.get(timeout=0.1)

                if cmd == 'q':
                    print("\nQuit command received. Starting cleanup process...")
                    cleanup_and_quit(shared_state, json_file_path, keyboard_listener)
                    break

                elif cmd == 's':
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

                elif cmd == 'w':
                    unique_name = f"{uuid.uuid4()}.png"
                    with shared_state.lock:
                        if shared_state.current_section_path is None:
                            print("No active section to add the image.")
                            continue
                        image_path = os.path.join(shared_state.current_section_path, unique_name)
                    if capture_screenshot_mac(image_path):
                        threading.Thread(target=event_handler.add_image_to_section, args=(image_path, 'code_images')).start()
                    else:
                        print("Failed to capture the screenshot.")

                elif cmd == 'r':
                    handle_section_creation(shared_state, keyboard_listener, json_file_path)

                elif cmd == 'c':
                    handle_chapter_creation(shared_state, keyboard_listener, json_file_path)

            except queue.Empty:
                continue

    finally:
        if shared_state.running:
            print("\nUnexpected termination. Running emergency cleanup...")
            cleanup_and_quit(shared_state, json_file_path, keyboard_listener)

if __name__ == "__main__":
    main()
