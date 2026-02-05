import re
import os
import argparse
from datetime import datetime

# --- CONFIGURATION ---
CONSTANTS_PATH = os.path.join("src", "constants.py")
INSTALLER_PATH = os.path.join("builder", "Installer.iss")
REL_NOTES_PATH = "release_notes.txt"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def format_version_code(version_float):
    # Converts 3.37 -> "0337", 4.0 -> "0400"
    return f"{int(version_float * 100):04d}"


def calculate_new_version(current_ver, mode, manual_ver=None):
    if manual_ver is not None:
        return manual_ver

    if mode == "major":
        # 3.37 -> 4.0
        return float(int(current_ver) + 1)

    # Default is patch: 3.37 -> 3.38
    return round(current_ver + 0.01, 2)


def bump_constants(content, new_ver):
    # Regex to find APPLICATION_VERSION = 3.37
    ver_match = re.search(r"APPLICATION_VERSION\s*=\s*(\d+\.\d+)", content)
    if not ver_match:
        raise ValueError("Could not find APPLICATION_VERSION in constants.py")

    current_ver = float(ver_match.group(1))

    # If we haven't calculated new_ver yet (logic separation), this helps validate
    # But here we pass new_ver in. We still need current_ver for the "PREVIOUS" field.

    # Format versions for PREVIOUS_APPLICATION_VERSION (e.g., "0337")
    current_ver_code = format_version_code(current_ver)

    print(f"Bumping version: {current_ver} -> {new_ver}")

    # 1. Update APPLICATION_VERSION
    new_content = re.sub(
        r"APPLICATION_VERSION\s*=\s*\d+\.\d+",
        f"APPLICATION_VERSION = {new_ver}",
        content,
    )

    # 2. Update PREVIOUS_APPLICATION_VERSION
    # We replace the existing string value with the CURRENT version code (before bump)
    new_content = re.sub(
        r'PREVIOUS_APPLICATION_VERSION\s*=\s*"(\d+)"',
        f'PREVIOUS_APPLICATION_VERSION = "{current_ver_code}"',
        new_content,
    )

    return new_content, current_ver


def bump_installer(content, new_ver):
    new_ver_code = format_version_code(new_ver)

    # 1. Update AppVersion=3.37
    new_content = re.sub(r"AppVersion=\d+\.\d+", f"AppVersion={new_ver}", content)

    # 2. Update OutputBaseFilename=MTGA_Draft_Tool_V0337
    new_content = re.sub(
        r"OutputBaseFilename=MTGA_Draft_Tool_V\d+",
        f"OutputBaseFilename=MTGA_Draft_Tool_V{new_ver_code}",
        new_content,
    )

    return new_content


def prepend_release_notes(path, new_ver):
    if not os.path.exists(path):
        print("Release notes file not found, creating new one.")
        existing_content = ""
    else:
        existing_content = read_file(path)

    header = f"===================== RELEASE NOTES {new_ver} ====================="
    template = f"{header}\n* [TODO]: Add release notes here\n\n"

    write_file(path, template + existing_content)


def get_current_version_from_file():
    content = read_file(CONSTANTS_PATH)
    ver_match = re.search(r"APPLICATION_VERSION\s*=\s*(\d+\.\d+)", content)
    if not ver_match:
        raise ValueError("Could not find current version.")
    return float(ver_match.group(1)), content


def main():
    parser = argparse.ArgumentParser(description="Automate version bumping.")
    parser.add_argument(
        "mode",
        choices=["patch", "major"],
        nargs="?",
        default="patch",
        help="Increment mode (patch=+0.01, major=+1.0)",
    )
    parser.add_argument(
        "--set", type=float, help="Manually set a specific version number (e.g., 3.50)"
    )
    args = parser.parse_args()

    try:
        # 1. Determine Versions
        current_ver, constants_content = get_current_version_from_file()
        new_ver = calculate_new_version(current_ver, args.mode, args.set)

        # 2. Process constants.py
        print(f"Reading {CONSTANTS_PATH}...")
        new_constants, _ = bump_constants(constants_content, new_ver)
        write_file(CONSTANTS_PATH, new_constants)
        print(f"Updated {CONSTANTS_PATH}")

        # 3. Process Installer.iss
        print(f"Reading {INSTALLER_PATH}...")
        installer_content = read_file(INSTALLER_PATH)
        new_installer = bump_installer(installer_content, new_ver)
        write_file(INSTALLER_PATH, new_installer)
        print(f"Updated {INSTALLER_PATH}")

        # 4. Process Release Notes
        print(f"Updating {REL_NOTES_PATH}...")
        prepend_release_notes(REL_NOTES_PATH, new_ver)
        print(f"Prepended header to {REL_NOTES_PATH}")

        print(f"\nSUCCESS! Version bumped: {current_ver} -> {new_ver}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
