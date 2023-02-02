import os
from fnmatch import fnmatch
from typing import List


def get_pattern_paths(pattern: str, path: str) -> List[str]:
    """
    Find the OS paths to all files that match a pattern
    :param pattern: The regEx pattern to match the filename to
    :param path: The path where we should search for files
    :return: A list of paths to the found files,
    empty list when no files found
    """
    files_paths = []
    for subpath, subdirs, files in os.walk(path):
        for name in files:
            if fnmatch(name, pattern):
                files_paths.append(os.path.join(subpath, name))
    return files_paths
