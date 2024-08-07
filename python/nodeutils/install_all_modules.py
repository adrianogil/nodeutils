import os
import re
import subprocess


def get_all_files(dir_path):
    """Recursively get all JS files in a directory."""
    js_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith('.js'):
                js_files.append(os.path.join(root, file))
    return js_files

def get_required_modules(file_path):
    """Extract required modules from a JS file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    require_regex = re.compile(r'require\(["\'](.*?)["\']\)')
    modules = set(require_regex.findall(content))
    return modules

def install_modules(dir_path):
    """Parse all JS files and install required modules."""
    files = get_all_files(dir_path)
    modules = set()

    for file in files:
        required_modules = get_required_modules(file)
        for module in required_modules:
            if not module.startswith('.') and not module.startswith('/'):
                modules.add(module)

    if modules:
        print('Installing modules:', ', '.join(modules))
        subprocess.run(['npm', 'install', *modules], check=True)
    else:
        print('No modules to install.')

if __name__ == '__main__':
    from pyutils.cli.flags import get_flag
    target_dir = get_flag(['-d', '--dir'], default_value=os.getcwd())
    install_modules(target_dir)
