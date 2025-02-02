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
        self.data = {"New item": {"chapters": []}}
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
        self.context = "main"
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
                        print(f"Command registered: {char}")

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
        self.show_contextual_help()

    def show_contextual_help(self):
        if self.context == "main":
            print("\nAvailable commands:")
            print(" s  - Capture screenshot")
            print(" w  - Capture code screenshot")
            print(" r  - New section")
            print(" c  - New chapter")
            print(" q  - Quit program\n")
        elif self.context == "name_capture":
            print("\nCapture name:")
            print(" a  - Capture chapter name")
            print(" d  - Capture section name")
            print(" Type 'aa' or 'dd' to enter name manually\n")


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


def cleanup_and_quit(shared_state: SharedState, keyboard_listener: KeyboardListener):
    print("Initiating cleanup process...")
    keyboard_listener.stop()
    print("Cleanup complete! Program terminated successfully.")
    shared_state.running = False


def get_name(shared_state: SharedState, capture_key: str, manual_key: str, prompt: str) -> Optional[str]:
    print(prompt)

    while True:
        try:
            cmd = shared_state.command_queue.get(timeout=0.1)

            if cmd == capture_key:
                unique_name = f"{uuid.uuid4()}.png"
                image_path = os.path.join(TEMP_DIR, unique_name)
                if capture_screenshot_mac(image_path):
                    name = extract_text_from_image(image_path)
                    if name:
                        print(f"Extracted name: {name}")
                        return name
                    else:
                        print("No text extracted from image. Please try again.")
                else:
                    print("Failed to capture screenshot. Please try again.")
            elif cmd == manual_key:
                name = input("Enter the name manually: ").strip()
                print(f"Entered name: {name}")
                return name

        except queue.Empty:
            continue


def main():
    print("\nWelcome to the Screenshot and OCR Program!\n")

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
        chapter_name = get_name(shared_state, 'a', 'aa', "Capture chapter name (a / aa)")

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

        keyboard_listener.set_context("main")

        print(f"Started New Chapter: {chapter_name} (ID: {chapter_id})")

    else:
        print("Invalid choice. Please enter 'new' or 'existing'.")
        return

    signal.signal(signal.SIGINT, lambda signum, frame: cleanup_and_quit(shared_state, keyboard_listener))

    try:
        keyboard_listener.set_context("main")
        print("\nReady for commands! Press keys without Enter:\n")
        print(" s  - Screenshot")
        print(" w  - Code Screenshot")
        print(" r  - New Section")
        print(" c  - New Chapter")
        print(" q  - Quit\n")

        while shared_state.running:
            try:
                cmd = shared_state.command_queue.get(timeout=0.1)

                if cmd == 'q':
                    print("\nQuit command received. Starting cleanup process...")
                    cleanup_and_quit(shared_state, keyboard_listener)
                    break

            except queue.Empty:
                continue

    finally:
        if shared_state.running:
            print("\nUnexpected termination. Running emergency cleanup...")
            cleanup_and_quit(shared_state, keyboard_listener)


if __name__ == "__main__":
    main()
