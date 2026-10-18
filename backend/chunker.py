import ast
import os
import sys
from pathlib import Path

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
               "dist", "build", ".idea", ".vscode"}

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                   ".rs", ".c", ".cpp", ".h", ".cs", ".rb", ".php",
                   ".html", ".css", ".md"}

MAX_FILE_BYTES = 200_000   # skip huge files
WINDOW_LINES = 40          # fallback chunk size
OVERLAP_LINES = 5          # fallback overlap between chunks


def make_chunk(path, start, end, name, kind, lines):
    """Build one chunk. start/end are 1-based line numbers."""
    return {
        "file": path,
        "start_line": start,
        "end_line": end,
        "name": name,
        "kind": kind,
        "text": "\n".join(lines[start - 1:end]),
    }


def chunk_python(source, path):
    """Split a Python file into functions, and split classes into their methods."""
    lines = source.splitlines()
    tree = ast.parse(source)
    chunks = []
    func_types = (ast.FunctionDef, ast.AsyncFunctionDef)

    def start_of(node):
        starts = [node.lineno] + [d.lineno for d in node.decorator_list]
        return min(starts)

    for node in tree.body:
        if isinstance(node, func_types):
            chunks.append(make_chunk(path, start_of(node), node.end_lineno,
                                     node.name, "function", lines))
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, func_types)]
            if not methods:
                chunks.append(make_chunk(path, start_of(node), node.end_lineno,
                                         node.name, "class", lines))
                continue
            # the top of the class, before its first method
            header_end = max(start_of(node), start_of(methods[0]) - 1)
            chunks.append(make_chunk(path, start_of(node), header_end,
                                     node.name, "class", lines))
            # each method becomes its own chunk
            for m in methods:
                chunks.append(make_chunk(path, start_of(m), m.end_lineno,
                                         f"{node.name}.{m.name}", "method", lines))
    return chunks


def chunk_by_lines(source, path):
    """Fallback: overlapping windows of lines."""
    lines = source.splitlines()
    chunks = []
    step = WINDOW_LINES - OVERLAP_LINES
    for start in range(1, len(lines) + 1, step):
        end = min(start + WINDOW_LINES - 1, len(lines))
        chunks.append(make_chunk(path, start, end, f"lines {start}-{end}", "block", lines))
        if end == len(lines):
            break
    return chunks


def chunk_file(file_path: Path, repo_root: Path):
    if file_path.stat().st_size > MAX_FILE_BYTES:
        return []
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    if not source.strip():
        return []

    rel = file_path.relative_to(repo_root).as_posix()

    if file_path.suffix == ".py":
        try:
            chunks = chunk_python(source, rel)
            if chunks:
                return chunks
        except SyntaxError:
            pass  # fall through to line-based chunking
    return chunk_by_lines(source, rel)


def iter_code_files(repo_root: Path):
    for folder, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]  # skip ignored folders
        for f in files:
            p = Path(folder) / f
            if p.suffix in CODE_EXTENSIONS:
                yield p


def chunk_repo(repo_root: Path):
    all_chunks = []
    for file_path in iter_code_files(repo_root):
        all_chunks.extend(chunk_file(file_path, repo_root))
    return all_chunks


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python chunker.py <path-to-cloned-repo>")
        sys.exit(1)

    root = Path(sys.argv[1])
    chunks = chunk_repo(root)

    files = {c["file"] for c in chunks}
    print(f"Files processed : {len(files)}")
    print(f"Chunks created  : {len(chunks)}\n")

    for c in chunks[:5]:
        print(f"{c['file']}  [{c['kind']}] {c['name']}  (lines {c['start_line']}-{c['end_line']})")
        print("   " + c["text"].splitlines()[0][:80])
        print()