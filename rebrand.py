import os
import re

# We will only replace 'Hermes' and 'HERMES'.
# Lowercase 'hermes' is avoided to prevent breaking imports and package structures.
REPLACEMENTS = {
    r'\bHermes\b': 'Moor',
    r'\bHERMES\b': 'MOOR'
}

# Exclude sensitive or binary directories
EXCLUDE_DIRS = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__',
    '.pytest_cache', '.ruff_cache', 'dist', 'build', '.github',
    'assets', 'docker', 'web', 'ui-tui'
}

# Exclude binary or generated files
EXCLUDE_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pyc', '.pyd',
    '.so', '.dll', '.exe', '.bin', '.db', '.sqlite', '.sqlite3',
    '.lock'
}

def rebrand_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        for pattern, replacement in REPLACEMENTS.items():
            new_content = re.sub(pattern, replacement, new_content)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {filepath}")
    except (UnicodeDecodeError, PermissionError) as e:
        # Skip files that are not text or not accessible
        pass

def rebrand_directory(root_dir):
    for root, dirs, files in os.walk(root_dir):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            # Skip excluded extensions
            if any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                continue
            # Skip the rebrand script itself
            if file == "rebrand.py":
                continue
                
            filepath = os.path.join(root, file)
            rebrand_file(filepath)

if __name__ == "__main__":
    current_dir = os.path.abspath(os.path.dirname(__file__))
    rebrand_directory(current_dir)
    print("Rebranding of user-facing text completed successfully!")
