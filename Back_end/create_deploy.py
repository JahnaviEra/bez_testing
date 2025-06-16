import os
import re

BUILDSPEC_TEMPLATE = """version: 0.2

phases:
  install:
    runtime-versions:
      python: 3.11
    commands:
      - pip install --upgrade pip
      - pip install -r requirements.txt -t package/
  build:
    commands:
      - cp -r *.py package/
{copy_block}
artifacts:
  files:
    - package/**
"""

def get_local_dependencies(lambda_folder, all_libs):
    """Parse lambda_function.py for local imports (folders in the repo)."""
    deps = set()
    lambda_file = os.path.join(lambda_folder, "lambda_function.py")
    if not os.path.exists(lambda_file):
        return deps
    with open(lambda_file, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r'\s*from\s+([A-Za-z0-9_]+)', line)
            if m and m.group(1) in all_libs:
                deps.add(m.group(1))
            m2 = re.match(r'\s*import\s+([A-Za-z0-9_]+)', line)
            if m2 and m2.group(1) in all_libs:
                deps.add(m2.group(1))
    return deps

def main():
    root = os.getcwd()
    all_folders = [f for f in os.listdir(root) if os.path.isdir(f)]
    lambda_folders = [f for f in all_folders if f[0].isupper() and os.path.isfile(os.path.join(f, "lambda_function.py"))]
    lib_folders = [f for f in all_folders if f not in lambda_folders]
    for folder in lambda_folders:
        deps = get_local_dependencies(folder, lib_folders)
        buildspec_copy_block = ""
        for dep in deps:
            buildspec_copy_block += f"      - cp -r ../{dep} package/\n"
        # Write buildspec.yml for CodePipeline
        buildspec_path = os.path.join(folder, "buildspec.yml")
        with open(buildspec_path, "w") as f:
            f.write(BUILDSPEC_TEMPLATE.format(
                copy_block=buildspec_copy_block.rstrip()
            ))
        print(f"Created {buildspec_path}")

if __name__ == "__main__":
    main()