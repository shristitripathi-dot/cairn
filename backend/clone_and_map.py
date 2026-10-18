import sys
from pathlib import Path
from git import Repo

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
               "dist", "build", ".idea", ".vscode"}

REPOS_DIR = Path("repos")


def clone_repo(url: str) -> Path:
    """Clone a GitHub repo into ./repos/<name> and return its path."""
    name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    target = REPOS_DIR / name

    if target.exists():
        print(f"Already cloned at {target}, skipping clone.")
        return target

    REPOS_DIR.mkdir(exist_ok=True)
    print(f"Cloning {url} ...")
    Repo.clone_from(url, target, depth=1)
    print("Done.\n")
    return target


def print_tree(folder: Path, prefix: str = "") -> None:
    """Print the folder structure like a tree."""
    items = [p for p in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
             if p.name not in IGNORE_DIRS]

    for i, item in enumerate(items):
        last = i == len(items) - 1
        branch = "└── " if last else "├── "
        print(prefix + branch + item.name)
        if item.is_dir():
            print_tree(item, prefix + ("    " if last else "│   "))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clone_and_map.py <github-url>")
        sys.exit(1)

    repo_path = clone_repo(sys.argv[1])
    print(repo_path.name)
    print_tree(repo_path)