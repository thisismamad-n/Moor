import os
import re
import sys

# Regex pattern to match 'hermes <subcommand>' inside strings or display text.
# It matches 'hermes' preceded by quote, space, or backtick, and followed by a known subcommand.
# It explicitly avoids matching 'hermes-agent' or 'hermes_' or '.hermes'.
CLI_COMMANDS = (
    "auth|model|setup|config|gateway|dashboard|debug|doctor|cron|claw|sessions|"
    "logs|update|profile|tools|fallback|checkpoints|chat|import|export|whatsapp|"
    "tui|portal|skills|dump|mcp|completion|memory|webhook|security|slack|send|"
    "uninstall|kanban|models|run_agent"
)
CLI_PATTERN = re.compile(rf'(?<=[\'"`\s\n(>\[])hermes\s+({CLI_COMMANDS})\b')

# Pattern for the slash command '/hermes' specifically
SLASH_COMMAND_PATTERN = re.compile(r'(?<=[\'"`\s\n(])\/hermes\b(?!-)')

# Pattern for the bare 'hermes' command name in specific contexts like prog="hermes"
PROG_PATTERN = re.compile(r'prog=["\']hermes["\']')

# Pattern for process titles
PROCTITLE_PATTERN = re.compile(r'setproctitle\(b?["\']hermes["\']\)')
PTHREAD_PATTERN = re.compile(r'pthread_setname_np\(b?["\']hermes["\']\)')
PR_SET_NAME_PATTERN = re.compile(r'libc\.prctl\(15,\s*b["\']hermes["\']')

# Specific string literal patterns for i18n/locales
LOCALE_HERMES_CMD = re.compile(r'([\'"`\s(>\[])hermes\b(?![-_\.])')

EXCLUDE_DIRS = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__',
    '.pytest_cache', '.ruff_cache', 'dist', 'build', '.github',
    'assets', 'docker', 'web', 'hermes_agent.egg-info'
}

INCLUDE_EXTS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.yaml', '.yml', '.md', '.txt', '.json', '.sh', '.ps1', '.toml'
}

def is_safe_to_replace_bare_hermes(filepath, content):
    """Specific targeted replacements for bare 'hermes' that are safe."""
    new_content = content
    
    # 1. Replace argparse prog="hermes" -> prog="moor"
    new_content = PROG_PATTERN.sub(lambda m: m.group(0).replace('hermes', 'moor'), new_content)
    
    # 2. Replace setproctitle("hermes") -> setproctitle("moor")
    new_content = PROCTITLE_PATTERN.sub(lambda m: m.group(0).replace('hermes', 'moor'), new_content)
    new_content = PTHREAD_PATTERN.sub(lambda m: m.group(0).replace('hermes', 'moor'), new_content)
    new_content = PR_SET_NAME_PATTERN.sub(lambda m: m.group(0).replace('hermes', 'moor'), new_content)
    
    # 3. Replace slash commands '/hermes' -> '/moor'
    new_content = SLASH_COMMAND_PATTERN.sub('/moor', new_content)
    
    # 4. Replace specific locale/i18n phrases
    filepath_norm = filepath.replace('\\', '/')
    if '/locales/' in filepath_norm or '/i18n/' in filepath_norm or 'commands.py' in filepath_norm or '/ui-tui/' in filepath_norm:
        def safe_locale_replace(match):
            prefix = match.group(1)
            return f"{prefix}moor"
            
        new_content = LOCALE_HERMES_CMD.sub(safe_locale_replace, new_content)
        
    return new_content

def rebrand_file(filepath):
    try:
        # Avoid huge files > 2MB
        if os.path.getsize(filepath) > 2 * 1024 * 1024:
            return False
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        
        # Safe replacement 1: CLI commands
        new_content = CLI_PATTERN.sub(lambda m: f"moor {m.group(1)}", new_content)
        
        # Safe replacement 2: Specific safe patterns
        new_content = is_safe_to_replace_bare_hermes(filepath, new_content)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {filepath}")
            return True
            
    except (UnicodeDecodeError, PermissionError) as e:
        # Skip files that are not text or not accessible
        pass
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return False

def rebrand_directory(root_dir):
    updated_files = 0
    for root, dirs, files in os.walk(root_dir):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            # Only process included extensions
            if not any(file.endswith(ext) for ext in INCLUDE_EXTS):
                continue
                
            # Skip the rebrand scripts themselves
            if file in ("rebrand.py", "rebrand_phase2.py"):
                continue
                
            filepath = os.path.join(root, file)
            if rebrand_file(filepath):
                updated_files += 1
                
    print(f"\nRebranding Phase 2 completed! Updated {updated_files} files.")

if __name__ == "__main__":
    current_dir = os.path.abspath(os.path.dirname(__file__))
    print(f"Starting Phase 2 rebranding in {current_dir}...")
    rebrand_directory(current_dir)
