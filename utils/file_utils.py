"""File system utilities"""

import os
from pathlib import Path


def ensure_directory_exists(directory_path):
    """Ensure that a directory exists, create it if it doesn't"""
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def get_file_extension(file_path):
    """Get file extension in lowercase"""
    return Path(file_path).suffix.lower()


def is_image_file(file_path):
    """Check if file is an image based on extension"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    return get_file_extension(file_path) in image_extensions


def get_files_by_extension(directory, extensions):
    """Get all files in directory with specified extensions"""
    files = []
    for file_path in Path(directory).iterdir():
        if file_path.is_file() and get_file_extension(file_path) in extensions:
            files.append(str(file_path))
    return sorted(files)


def safe_filename(filename):
    """Make filename safe for filesystem"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
