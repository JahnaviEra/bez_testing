import os
import sys
import shutil
import re

def find_top_level_dependencies(lambda_folder, all_libs):
    """Parse lambda_function.py for top-level folder dependencies."""
    deps = set()
    lambda_file = os.path.join(lambda_folder, "lambda_function.py")
    if not os.path.exists(lambda_file):
        return deps
    with open(lambda_file, "r", encoding="utf-8") as f:
        for line in f:
            # Match: from bez_auth0_modules.bez_auth0_addmfa import ...
            m = re.match(r'\s*from\s+([A-Za-z0-9_]+)', line)
            if m and m.group(1) in all_libs:
                deps.add(m.group(1))
            # Match: import bez_auth0_modules.bez_auth0_addmfa
            m2 = re.match(r'\s*import\s+([A-Za-z0-9_]+)', line)
            if m2 and m2.group(1) in all_libs:
                deps.add(m2.group(1))
            # Match: from bez_auth0_modules import ...
            m3 = re.match(r'\s*from\s+([A-Za-z0-9_]+)\.', line)
            if m3 and m3.group(1) in all_libs:
                deps.add(m3.group(1))
            # Match: import bez_auth0_modules.bez_auth0_addmfa
            m4 = re.match(r'\s*import\s+([A-Za-z0-9_]+)\.', line)
            if m4 and m4.group(1) in all_libs:
                deps.add(m4.group(1))
    return deps

def main():
    lambda_folder = sys.argv[1]
    package_folder = sys.argv[2]
    root = os.getcwd()
    all_folders = [f for f in os.listdir(root) if os.path.isdir(f) and f != lambda_folder]
    if os.path.exists(package_folder):
        shutil.rmtree(package_folder)
    os.makedirs(package_folder, exist_ok=True)
    # Copy all .py files from lambda folder
    for fname in os.listdir(lambda_folder):
        if fname.endswith('.py'):
            shutil.copy(os.path.join(lambda_folder, fname), package_folder)
    # Detect and copy entire dependency folders
    deps = find_top_level_dependencies(lambda_folder, all_folders)
    for dep in deps:
        dep_path = os.path.join(root, dep)
        dest_path = os.path.join(package_folder, dep)
        if os.path.exists(dep_path):
            shutil.copytree(dep_path, dest_path)
    print(f"Packaged {lambda_folder} and dependency folders: {deps}")

if __name__ == "__main__":
    main()