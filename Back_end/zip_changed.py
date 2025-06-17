import os
import sys
import re
import zipfile
from subprocess import check_output

# def get_changed_files():
#     """Retrieve the list of files changed in the last commit."""
#     try:
#         changed_files = check_output(
#             ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'],
#             universal_newlines=True
#         )
#         return [f.strip().replace("\\", "/").lstrip("./") for f in changed_files.splitlines() if f.endswith(".py")]
#     except Exception as e:
#         print(f"Error retrieving changed files: {e}")
#         return []

def get_lambda_folders(root):
    return [
        f for f in os.listdir(root)
        if os.path.isdir(os.path.join(root, f))
        and f[0].isupper()
        and os.path.isfile(os.path.join(root, f, "lambda_function.py"))
    ]

def get_local_dependencies(lambda_folder, all_libs):
    deps = set()
    lambda_file = os.path.join(lambda_folder, "lambda_function.py")
    if not os.path.exists(lambda_file):
        return deps
    with open(lambda_file, "r", encoding="utf-8") as f:
        content = f.read()
        for line in content.splitlines():
            m = re.match(r'\s*from\s+([A-Za-z0-9_]+)', line)
            if m and m.group(1) in all_libs:
                deps.add(m.group(1))
            m2 = re.match(r'\s*import\s+([A-Za-z0-9_]+)', line)
            if m2 and m2.group(1) in all_libs:
                deps.add(m2.group(1))
        for lib in all_libs:
            # Match 'lib', "lib", or bare word lib (not part of a larger word)
            if re.search(rf"(['\"])?\b{re.escape(lib)}\b(['\"])?", content):
                deps.add(lib)
    return deps


def resolve_all_dependencies(folder, all_libs, root, seen=None, path=None, dep_paths=None):
    if seen is None:
        seen = set()
    if path is None:
        path = [folder]
    if dep_paths is None:
        dep_paths = {}
    direct_deps = get_local_dependencies(os.path.join(root, folder), all_libs)
    for dep in direct_deps:
        if dep not in seen:
            seen.add(dep)
            dep_paths[dep] = list(path) + [dep]
            resolve_all_dependencies(dep, all_libs, root, seen, path + [dep], dep_paths)
    return seen, dep_paths



def main():
    root = sys.argv[1]
    changed_files = [cf.strip().replace("\\", "/").lstrip("./") for cf in sys.argv[2].splitlines()]
    # changed_files = get_changed_files()
    # if not changed_files:
    #     print("No changed Python files detected in last commit.")
    #     sys.exit(0)
    # print("Changed files list:",changed_files)
    all_folders = [f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f))]
    lambda_folders = get_lambda_folders(root)
    lib_folders = [f for f in all_folders if f not in lambda_folders]
    impacted = []
    lambda_to_files = {}
    lambda_to_file_paths = {}

    for lf in lambda_folders:
        all_deps, dep_paths = resolve_all_dependencies(lf, lib_folders, root)
        relevant_paths = [lf] + list(all_deps)
        impacted_files = []
        file_paths = {}
        lambda_code_path = os.path.join(root, lf, "lambda_function.py")

        if os.path.exists(lambda_code_path):
            with open(lambda_code_path, "r", encoding="utf-8") as f:
                lambda_code = f.read()

            for cf in changed_files:
                # Case 1: File is directly in the Lambda folder
                if cf.startswith(lf + "/"):
                    impacted_files.append(cf)
                    file_paths[cf] = [lf]
                    continue

                # Case 2: File is in a dependency folder and actually used in the lambda code
                for dep in all_deps:
                    if cf.startswith(dep + "/"):
                        filename = os.path.splitext(os.path.basename(cf))[0]
                        if re.search(rf'\b{re.escape(filename)}\b', lambda_code):
                            impacted_files.append(cf)
                            file_paths[cf] = dep_paths.get(dep, [lf, dep])
                        break  # matched one dep, skip others

        if impacted_files:
            impacted.append(lf)
            lambda_to_files[lf] = impacted_files
            lambda_to_file_paths[lf] = file_paths

    if impacted:
        print("## Lambda functions that will be deployed if this PR is merged:")
        for lf in impacted:
            print(f"- {lf}")
        print("\n### Impacted files per Lambda function (with dependency path):")
        for lf, files in lambda_to_files.items():
            print(f"\n{lf}:")
            for f in files:
                dep_path = " -> ".join(lambda_to_file_paths[lf][f])
                print(f"  - {f} (via {dep_path})")

        # --- Zipping functionality ---
        for lf, files in lambda_to_files.items():
            output_dir = os.path.join("output", lf)
            os.makedirs(output_dir, exist_ok=True)
            zip_path = os.path.join(output_dir, "changed_files.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        zf.write(file_path, arcname=file)
            print(f"Created {zip_path} with changed files for {lf}.")
    else:
        print("No Lambda functions will be deployed by this PR.")


if __name__ == "__main__":
    main()