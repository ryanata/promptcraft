#!/usr/bin/env python3
"""
promptcraft.py

An interactive prompt crafting tool with auto-completion.
Type your prompt text. When you type a command starting with `/`,
you get a dropdown with available commands. For `/file` and `/folder`
commands, it will show available files or directories.

Special key binding: When a completion menu is visible, pressing the down arrow
and then Enter will accept the current selection.
"""

import os
import sys
import stat
import subprocess
import webbrowser
import pyperclip
from datetime import datetime
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from gitignore_parser import parse_gitignore

# The base commands available.
# Update BASE_COMMANDS to include the new command
BASE_COMMANDS = ["/file", "/folder", "/all", ":q"]

def is_hidden(path):
    """Check if a file or directory is hidden in a cross-platform way."""
    folder_name = os.path.basename(path)
    
    if sys.platform.startswith('win'):
        # Windows: Check for the hidden attribute
        try:
            attributes = os.stat(path).st_file_attributes
            return attributes & stat.FILE_ATTRIBUTE_HIDDEN
        except (FileNotFoundError, AttributeError):
            return False
    elif sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
        # macOS/Linux: Check if the name starts with a dot
        return folder_name.startswith('.')
    else:
        # Unknown platform, assume not hidden
        return False

class PromptCraftCompleter(Completer):
    def __init__(self, base_dir):
        self.base_dir = base_dir
        # Initialize gitignore matcher
        gitignore_path = os.path.join(base_dir, '.gitignore')
        self.matches_gitignore = (
            parse_gitignore(gitignore_path)
            if os.path.exists(gitignore_path)
            else lambda x: False
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/"):
            if text.startswith("/folder "):
                arg = text[len("/folder "):]
                arg_doc = Document(text=arg, cursor_position=len(arg))
                folder_completer = PathCompleter(
                    expanduser=True,
                    file_filter=lambda path: (
                        os.path.isdir(path) and 
                        not self.matches_gitignore(path) and
                        not is_hidden(path)
                    ),
                    get_paths=lambda: [self.base_dir]
                )
                for comp in folder_completer.get_completions(arg_doc, complete_event):
                    yield Completion(
                        comp.text,
                        start_position=-len(arg),  # This is correct, keep it
                        display=comp.display,
                    )

            elif text.startswith("/file "):
                arg = text[len("/file "):]
                arg_doc = Document(text=arg, cursor_position=len(arg))
                file_completer = PathCompleter(
                    expanduser=True,
                    file_filter=lambda path: (
                        os.path.isfile(path) and 
                        not self.matches_gitignore(path)
                    ),
                    get_paths=lambda: [self.base_dir]
                )
                for comp in file_completer.get_completions(arg_doc, complete_event):
                    # Calculate how much of the completion matches the current input
                    common_prefix = os.path.commonprefix([arg.lower(), comp.text.lower()])
                    # Yield only the part that needs to be added
                    yield Completion(
                        comp.text[len(common_prefix):],
                        start_position=0,
                        display=comp.display,
                    )
            else:
                # If the user is typing a command (starting with "/"), offer the base commands.
                for cmd in BASE_COMMANDS:
                    if cmd.startswith(text):
                        yield Completion(cmd, start_position=-len(text))

def process_file_command(filepath, prompt_lines, base_dir):
    # Convert relative path to absolute path based on base_dir
    if not os.path.isabs(filepath):
        filepath = os.path.join(base_dir, filepath)
    
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        print(f"Error: File not found: {filepath}")
        return
    try:
        with open(filepath, "r") as f:
            content = f.read()
        prompt_lines.append(f"<!-- Begin file: {filepath} -->\n")
        prompt_lines.append(content)
        prompt_lines.append(f"<!-- End file: {filepath} -->\n\n")
        print(f"Added file: {filepath}")
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

def process_folder_command(folderpath, prompt_lines, base_dir):
    if not os.path.isabs(folderpath):
        folderpath = os.path.join(base_dir, folderpath)
    
    if not os.path.exists(folderpath) or not os.path.isdir(folderpath):
        print(f"Error: Folder not found: {folderpath}")
        return

    # Initialize gitignore matcher
    gitignore_path = os.path.join(base_dir, '.gitignore')
    matches_gitignore = (
        parse_gitignore(gitignore_path)
        if os.path.exists(gitignore_path)
        else lambda x: False
    )

    for root, dirs, files in os.walk(folderpath):
        # Filter out hidden and ignored directories
        dirs[:] = [d for d in dirs 
                  if not is_hidden(os.path.join(root, d)) 
                  and not matches_gitignore(os.path.join(root, d))]
        
        # Filter out hidden and ignored files
        for filename in files:
            file_path = os.path.join(root, filename)
            if matches_gitignore(file_path):
                continue
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                prompt_lines.append(f"<!-- Begin file: {file_path} -->\n")
                prompt_lines.append(content)
                prompt_lines.append(f"<!-- End file: {file_path} -->\n\n")
                print(f"Added file: {file_path}")
            except Exception as e:
                print(f"Could not read {file_path}: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: promptcraft <target_folder>")
        sys.exit(1)

    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    target_folder = os.path.abspath(sys.argv[1])
    if not os.path.exists(target_folder) or not os.path.isdir(target_folder):
        print(f"Error: target folder does not exist or is not a folder: {target_folder}")
        sys.exit(1)

    print("Welcome to PromptCraft Editor!")
    print("Type your prompt text below. Available commands:")
    print("  /file <filepath>   -> insert file contents")
    print("  /folder <folder>   -> insert folder contents (recursively)")
    print("  /all              -> insert all files in current directory")
    print("  :q                 -> finish editing and save prompt")
    print("  Ctrl+C            -> finish editing and save prompt")
    print("Use Tab or Down+Enter to autocomplete commands and paths.\n")

    # Create custom key bindings.
    bindings = KeyBindings()

    @bindings.add("enter")
    def handle_enter(event):
        """
        If the completion menu is visible, accept the current selection;
        otherwise, handle Enter normally (which accepts the input line).
        """
        buf = event.current_buffer
        if buf.complete_state and buf.complete_state.current_completion:
            buf.apply_completion(buf.complete_state.current_completion)
        else:
            buf.validate_and_handle()

    # Initialize the PromptSession with our custom completer and key bindings.
    session = PromptSession(
        completer=PromptCraftCompleter(target_folder),  # Pass target_folder to the completer
        complete_while_typing=True,
        key_bindings=bindings
    )

    prompt_lines = []

    try:
        # Continue reading lines until the user types ':q' on a line by itself.
        while True:
            try:
                line = session.prompt("> ")
            except KeyboardInterrupt:
                # Ctrl-C: exit the program
                print("\nExiting...")
                break
            except EOFError:
                break

            stripped = line.strip()
            if stripped == ":q":
                break
            elif stripped == "/all":
                process_folder_command(".", prompt_lines, target_folder)
            elif stripped.startswith("/file "):
                filepath = stripped[len("/file "):].strip()
                process_file_command(filepath, prompt_lines, target_folder)
            elif stripped.startswith("/folder "):
                folderpath = stripped[len("/folder "):].strip()
                process_folder_command(folderpath, prompt_lines, target_folder)
            else:
                prompt_lines.append(line)
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")

    # Save the prompt as a Markdown file with a timestamp.
    # Save the prompt in a single date folder within the script's directory
    current_date = datetime.now()
    date_folder = os.path.join(
        script_dir,
        current_date.strftime("%Y-%m-%d")
    )
    
    # Create the date folder if it doesn't exist
    os.makedirs(date_folder, exist_ok=True)

    timestamp = current_date.strftime("%H%M%S")
    output_filename = f"prompt_{timestamp}.md"
    output_filepath = os.path.join(date_folder, output_filename)

    # Save the prompt and copy to clipboard
    prompt_content = "\n".join(prompt_lines)
    
    try:
        # Copy to clipboard
        pyperclip.copy(prompt_content)
        print("\nPrompt content copied to clipboard!")
        
        # Save to file
        with open(output_filepath, "w") as f:
            f.write(prompt_content)
        print(f"Prompt saved to {output_filepath}")
    except Exception as e:
        print(f"Error saving prompt: {e}")
        sys.exit(1)

    # Open the file in VS Code if available.
    # Try to open the file with VS Code first, if that fails use system default
    try:
        subprocess.run(["code", output_filepath], check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        try:
            webbrowser.open(output_filepath)
        except Exception as e:
            print(f"Error opening file: {e}")

if __name__ == "__main__":
    main()
