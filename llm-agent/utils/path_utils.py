import os

def get_project_path(relative_path: str) -> str:

    project_root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(project_root, relative_path)
