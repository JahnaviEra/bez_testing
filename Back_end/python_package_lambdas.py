import os
import re
import shutil
import zipfile

def get_local_dependencies(lambda_folder, all_libs):
    deps = set()
    lambda_file = os.path.join(lambda_folder, "lambda_function.py")
    if not os.path.exists(lambda_file):
        return deps

    with open(lambda_file, "r", encoding="utf-8") as f:
        content = f.read()
        # 1. Standard imports
        for line in content.splitlines():
            m = re.match(r'\s*from\s+([A-Za-z0-9_]+)', line)
            if m and m.group(1) in all_libs:
                deps.add(m.group(1))
            m2 = re.match(r'\s*import\s+([A-Za-z0-9_]+)', line)
            if m2 and m2.group(1) in all_libs:
                deps.add(m2.group(1))
        # 2. Dynamic imports via mappings (e.g., "bez_mda_expert._mda_expert_response")
        for match in re.findall(r'["\']([a-zA-Z0-9_]+)\.', content):
            if match in all_libs:
                deps.add(match)
        # 3. Dynamic import_module calls (e.g., import_module(f"bez_mda_modules.{module_path}"))
        for match in re.findall(r'import_module\(\s*f?["\']([a-zA-Z0-9_]+)', content):
            if match in all_libs:
                deps.add(match)
    return deps

def ensure_folder_exists(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"Created missing folder: {folder}")

def zip_lambda(lambda_folder, deps, output_dir):
    temp_dir = os.path.join(output_dir, f"{lambda_folder}_temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    # Copy Lambda .py files
    for fname in os.listdir(lambda_folder):
        src = os.path.join(lambda_folder, fname)
        dst = os.path.join(temp_dir, fname)
        if os.path.isfile(src):
            shutil.copy(src, dst)
    # Copy dependency folders
    for dep in deps:
        dep_src = dep
        dep_dst = os.path.join(temp_dir, dep)
        ensure_folder_exists(dep_src)
        if os.path.exists(dep_dst):
            shutil.rmtree(dep_dst)
        shutil.copytree(dep_src, dep_dst)
    # Zip everything
    zip_path = os.path.join(output_dir, f"{lambda_folder}.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, temp_dir)
                zf.write(abs_path, rel_path)
    shutil.rmtree(temp_dir)
    print(f"Created {zip_path}")

def main():
    root = os.getcwd()
    output_dir = os.path.join(root, "output")
    ensure_folder_exists(output_dir)
    all_folders = [f for f in os.listdir(root) if os.path.isdir(f)]
    lambda_folders = [f for f in all_folders if f[0].isupper() and os.path.isfile(os.path.join(f, "lambda_function.py"))]
    lib_folders = [f for f in all_folders if f not in lambda_folders]
    for folder in lambda_folders:
        ensure_folder_exists(folder)
        deps = get_local_dependencies(folder, lib_folders)
        for dep in deps:
            ensure_folder_exists(dep)
        zip_lambda(folder, deps, output_dir)

if __name__ == "__main__":
    main()