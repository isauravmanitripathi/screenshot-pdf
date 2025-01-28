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

# --- Rich Imports ---
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track

# Create a console object for Rich
console = Console()

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
                        self._show_contextual_help(
                            f"[bold green]Command registered:[/bold green] [yellow]{char}[/yellow]"
                        )
                elif self.context == "name_capture":
                    if char in ['a', 'd']:
                        # If there's a timer, cancel it because we are about to track a double-press
                        if self.single_press_timer:
                            self.single_press_timer.cancel()
                            self.single_press_timer = None

                        if (current_time - self.last_key_time <= self.double_press_threshold and 
                            self.manual_input_buffer == char):
                            # Double press
                            self.shared_state.command_queue.put(char + char)
                            self.manual_input_buffer = ""
                            self.last_key_time = 0
                        else:
                            # Single press start
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
        """Prints instructions based on context, using Rich for styling."""
        if message:
            console.print(Panel(message, title="Info", style="bold cyan"))

        if self.context == "main":
            console.print(Panel(
                "\n[bold]Available commands:[/bold]\n"
                " [green]s[/green]: Capture screenshot\n"
                " [green]w[/green]: Capture [italic]code[/italic] screenshot\n"
                " [green]r[/green]: New section\n"
                " [green]c[/green]: New chapter\n"
                " [green]q[/green]: Quit program\n",
                title="Main Context",
                style="bold magenta"
            ))

        elif self.context == "name_capture":
            console.print(Panel(
                "\n[bold]Capture name:[/bold]\n"
                " [green]a[/green]: Capture chapter name\n"
                " [green]d[/green]: Capture section name\n\n"
                " [italic]Type 'aa' or 'dd' to enter name manually[/italic]",
                title="Name Capture",
                style="bold magenta"
            ))


class ScreenshotHandler:
    def __init__(self, shared_state: SharedState, json_file_path: str):
        self.shared_state = shared_state
        self.json_file_path = json_file_path

    def add_image_to_section(self, file_path: str, image_type: str = 'images'):
        with self.shared_state.lock:
            if self.shared_state.current_section_path is None:
                console.print("[bold red]No active section to add the image.[/bold red]")
                return

            unique_name = f"{uuid.uuid4()}{os.path.splitext(file_path)[1]}"
            new_file_path = os.path.join(self.shared_state.current_section_path, unique_name)

            try:
                if os.path.abspath(file_path) != os.path.abspath(new_file_path):
                    os.rename(file_path, new_file_path)
            except Exception as e:
                console.print(f"[bold red]Error moving file:[/bold red] {e}")
                return

            chapter_index = self.shared_state.current_chapter_index
            section_index = self.shared_state.current_section_index
            section = self.shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
            section.setdefault(image_type, []).append(new_file_path)
            section["status"] = "images testing in progress"

            with open(self.json_file_path, 'w') as f:
                json.dump(self.shared_state.data, f, indent=4)

        image_type_display = "code image" if image_type == "code_images" else "image"
        console.print(
            Panel(
                f"Added [bold]{image_type_display}[/bold] '[cyan]{unique_name}[/cyan]' "
                f"to section '[bold]{section['section_name']}[/bold]' (ID: {section['section_id']})",
                title="Image Added",
                style="green"
            )
        )
        threading.Thread(
            target=self.verify_image,
            args=(new_file_path, chapter_index, section_index)
        ).start()

    def verify_image(self, image_path: str, chapter_index: int, section_index: int):
        try:
            with Image.open(image_path) as img:
                img.verify()
            console.log(f"Verified image: {os.path.basename(image_path)} - [green]OK[/green]")

            with self.shared_state.lock:
                section = self.shared_state.data["New item"]["chapters"][chapter_index]["sections"][section_index]
                if not section.get("errors"):
                    section["status"] = "images tested ok"
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.shared_state.data, f, indent=4)
        except Exception as e:
            error_message = f"Error verifying image {image_path}: {e}"
            console.log(f"[red]{error_message}[/red]")

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
        console.print(f"[bold red]Failed to capture screenshot:[/bold red] {e}")
        return None


def extract_text_from_image(image_path: str) -> Optional[str]:
    if not os.path.exists(image_path):
        console.print(f"[bold red]Image file not found:[/bold red] {image_path}")
        return None
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img).strip()
            return text
    except Exception as e:
        console.print(f"[bold red]Error extracting text from image[/bold red] {image_path}: {e}")
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

    console.print(Panel(
        f"Processing Section: '[bold]{section_name}[/bold]' (ID: {section_id})\n"
        f"In Chapter: '[bold]{chapter_name}[/bold]'",
        title="Section Processing",
        style="bold cyan"
    ))
    console.print(f"Found {len(image_paths)} images and {len(code_image_paths)} code images to process...")

    def extract_texts(image_list: List[str], type_name: str) -> str:
        texts = []
        total = len(image_list)
        # Use Rich track() to show progress:
        for idx, image_path in track(enumerate(image_list, 1), total=total, description=f"Extracting {type_name}"):
            try:
                filename = os.path.basename(image_path)
                console.log(f"Processing {type_name} {idx}/{total}: [cyan]{filename}[/cyan]")
                with Image.open(image_path) as img:
                    text = pytesseract.image_to_string(img)
                    texts.append(text)
            except Exception as e:
                error_message = f"Error extracting text from image {image_path}: {e}"
                console.log(f"[bold red]{error_message}[/bold red]")
                with shared_state.lock:
                    section.setdefault("errors", []).append(error_message)
        return "\n".join(texts)

    console.print("[bold green]\nExtracting text from regular images...[/bold green]")
    section["extracted-text"] = extract_texts(image_paths, "image")

    console.print("[bold green]\nExtracting text from code images...[/bold green]")
    section["extracted-code"] = extract_texts(code_image_paths, "code image")

    with shared_state.lock:
        with open(json_file_path, 'w') as f:
            json.dump(shared_state.data, f, indent=4)

    console.print(Panel(
        f"Finished Processing Section: '[bold]{section_name}[/bold]' (ID: {section_id})\n"
        f"Saved results to JSON file: {json_file_path}",
        title="Section Processing Completed",
        style="bold green"
    ))


def get_name(shared_state: SharedState, capture_key: str, manual_key: str, prompt_instructions: str) -> Optional[str]:
    console.print(Panel(prompt_instructions, style="bold magenta"))

    while True:
        try:
            cmd = shared_state.command_queue.get(timeout=0.1)

            if cmd == capture_key:
                unique_name = f"{uuid.uuid4()}.png"
                image_path = os.path.join(TEMP_DIR, unique_name)
                if capture_screenshot_mac(image_path):
                    name = extract_text_from_image(image_path)
                    if name:
                        console.print(f"\n[bold green]Extracted name:[/bold green] '[yellow]{name}[/yellow]'")
                        return name
                    else:
                        console.print("\n[bold red]No text extracted from image. Please try again.[/bold red]")
                else:
                    console.print("\n[bold red]Failed to capture screenshot. Please try again.[/bold red]")
            elif cmd == manual_key:
                name = input("Enter the name manually: ").strip()
                console.print(f"[bold green]\nEntered name:[/bold green] '[yellow]{name}[/yellow]'")
                return name

        except queue.Empty:
            continue


def cleanup_and_quit(shared_state: SharedState, json_file_path: str, keyboard_listener: KeyboardListener):
    console.print(Panel("Initiating cleanup process...", style="bold yellow"))

    with shared_state.lock:
        prev_chapter_index = shared_state.current_chapter_index
        prev_section_index = shared_state.current_section_index

        if prev_section_index >= 0:
            console.print(Panel(
                "Processing final section before quitting...",
                style="bold cyan", title="Final Section"
            ))
            thread = threading.Thread(
                target=process_section,
                args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
            )
            thread.start()
            thread.join(timeout=20)
            if thread.is_alive():
                console.print("[bold red]Processing final section is taking too long. Proceeding with cleanup.[/bold red]")

        console.print("[bold]Saving final state to JSON file...[/bold]")
        with open(json_file_path, 'w') as f:
            json.dump(shared_state.data, f, indent=4)

    console.print("[bold]Stopping keyboard listener...[/bold]")
    keyboard_listener.stop()

    console.print(Panel("Cleanup complete! Program terminated successfully.", style="bold green"))
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
    section_name = get_name(shared_state, 'd', 'dd', "Capture section name ([bold green]d[/bold green]/[bold green]dd[/bold green])")
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

    console.print(Panel(
        f"Moved to New Section: '[bold]{section_name}[/bold]' (ID: {section_id})",
        style="bold green"
    ))


def handle_chapter_creation(shared_state: SharedState, keyboard_listener: KeyboardListener, json_file_path: str):
    prev_chapter_index = shared_state.current_chapter_index
    prev_section_index = shared_state.current_section_index

    if prev_section_index >= 0:
        threading.Thread(
            target=process_section,
            args=(shared_state, json_file_path, prev_chapter_index, prev_section_index)
        ).start()

    keyboard_listener.set_context("name_capture")
    chapter_name = get_name(shared_state, 'a', 'aa', "Capture chapter name ([bold green]a[/bold green]/[bold green]aa[/bold green])")
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
    section_name = get_name(shared_state, 'd', 'dd', "Capture section name ([bold green]d[/bold green]/[bold green]dd[/bold green])")
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

    console.print(Panel(
        f"Moved to New Chapter: '[bold]{chapter_name}[/bold]' (ID: {chapter_id})\n"
        f"Current Section: '[bold]{section_name}[/bold]' (ID: {section_id})",
        style="bold green"
    ))


def main():
    console.print(Panel(
        "Welcome to the [bold magenta]Screenshot and OCR Program![/bold magenta]\n"
        "This version supports single-key commands (no need to press Enter)!",
        title="Startup",
        style="bold cyan"
    ))

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
        chapter_name = get_name(shared_state, 'a', 'aa', "Capture chapter name ([bold green]a[/bold green]/[bold green]aa[/bold green])")

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

        section_name = get_name(shared_state, 'd', 'dd', "Capture section name ([bold green]d[/bold green]/[bold green]dd[/bold green])")
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

        console.print(Panel(
            f"Started New Chapter: '[bold]{chapter_name}[/bold]' (ID: {chapter_id})\n"
            f"Current Section: '[bold]{section_name}[/bold]' (ID: {section_id})",
            style="bold green"
        ))

    elif choice == 'existing':
        json_file_path = input("Enter the path to the existing JSON file: ").strip()
        if not os.path.isfile(json_file_path):
            console.print(f"[bold red]File not found:[/bold red] {json_file_path}")
            return

        with open(json_file_path, 'r') as f:
            try:
                shared_state.data = json.load(f)
            except json.JSONDecodeError:
                console.print("[bold red]Invalid JSON file.[/bold red]")
                return

        if not shared_state.data.get("New item", {}).get("chapters"):
            console.print("[bold red]The JSON file has no chapters or invalid format.[/bold red]")
            return

        keyboard_listener = KeyboardListener(shared_state)
        keyboard_listener.start()

        with shared_state.lock:
            shared_state.current_chapter_index = len(shared_state.data["New item"]["chapters"]) - 1
            chapter = shared_state.data["New item"]["chapters"][shared_state.current_chapter_index]
            if not chapter.get("sections"):
                console.print("[bold red]The last chapter has no sections.[/bold red]")
                return
            shared_state.current_section_index = len(chapter["sections"]) - 1
            section = chapter["sections"][shared_state.current_section_index]
            shared_state.current_section_path = section["section_path"]
            if not os.path.exists(shared_state.current_section_path):
                os.makedirs(shared_state.current_section_path, exist_ok=True)
            console.print(Panel(
                f"Resuming from Chapter: '[bold]{chapter['chapter_name']}[/bold]' (ID: {chapter['chapter_id']})\n"
                f"Current Section: '[bold]{section['section_name']}[/bold]' (ID: {section['section_id']})",
                style="bold green"
            ))
    else:
        console.print("[bold red]Invalid choice. Please enter 'new' or 'existing'.[/bold red]")
        return

    event_handler = ScreenshotHandler(shared_state, json_file_path)

    def signal_handler(signum, frame):
        console.print("\n[bold red]Received interrupt signal. Cleaning up...[/bold red]")
        cleanup_and_quit(shared_state, json_file_path, keyboard_listener)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        keyboard_listener.set_context("main")
        console.print(Panel(
            "[bold]Ready for commands! Press keys without Enter:[/bold]\n\n"
            " [green]s[/green]: Screenshot\n"
            " [green]w[/green]: Code Screenshot\n"
            " [green]r[/green]: New Section\n"
            " [green]c[/green]: New Chapter\n"
            " [green]q[/green]: Quit",
            title="Command Overview",
            style="bold magenta"
        ))

        while shared_state.running:
            try:
                cmd = shared_state.command_queue.get(timeout=0.1)

                if cmd == 'q':
                    console.print("[bold red]\nQuit command received. Starting cleanup process...[/bold red]")
                    cleanup_and_quit(shared_state, json_file_path, keyboard_listener)
                    break

                elif cmd == 's':
                    unique_name = f"{uuid.uuid4()}.png"
                    with shared_state.lock:
                        if shared_state.current_section_path is None:
                            console.print("[bold red]No active section to add the image.[/bold red]")
                            continue
                        image_path = os.path.join(shared_state.current_section_path, unique_name)
                    if capture_screenshot_mac(image_path):
                        threading.Thread(
                            target=event_handler.add_image_to_section,
                            args=(image_path,)
                        ).start()
                    else:
                        console.print("[bold red]Failed to capture the screenshot.[/bold red]")

                elif cmd == 'w':
                    unique_name = f"{uuid.uuid4()}.png"
                    with shared_state.lock:
                        if shared_state.current_section_path is None:
                            console.print("[bold red]No active section to add the image.[/bold red]")
                            continue
                        image_path = os.path.join(shared_state.current_section_path, unique_name)
                    if capture_screenshot_mac(image_path):
                        threading.Thread(
                            target=event_handler.add_image_to_section,
                            args=(image_path, 'code_images')
                        ).start()
                    else:
                        console.print("[bold red]Failed to capture the screenshot.[/bold red]")

                elif cmd == 'r':
                    handle_section_creation(shared_state, keyboard_listener, json_file_path)

                elif cmd == 'c':
                    handle_chapter_creation(shared_state, keyboard_listener, json_file_path)

            except queue.Empty:
                continue

    finally:
        if shared_state.running:
            console.print("[bold red]\nUnexpected termination. Running emergency cleanup...[/bold red]")
            cleanup_and_quit(shared_state, json_file_path, keyboard_listener)


if __name__ == "__main__":
    main()
