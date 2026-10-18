from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from clone_and_map import clone_repo
from indexer import index_repo
from chat import ask

app = FastAPI(title="Cairn")

# Lets the web page (running on another address) talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
               "dist", "build", ".idea", ".vscode"}


class RepoRequest(BaseModel):
    url: str


class ChatRequest(BaseModel):
    repo: str
    question: str


def build_tree(folder: Path):
    """Turn a folder into nested data the browser can draw."""
    items = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    result = []
    for p in items:
        if p.name in IGNORE_DIRS:
            continue
        if p.is_dir():
            result.append({"name": p.name, "type": "folder", "children": build_tree(p)})
        else:
            result.append({"name": p.name, "type": "file"})
    return result


@app.get("/")
def home():
    return {"message": "Cairn is running"}


@app.post("/load")
def load_repo(req: RepoRequest):
    """Clone and index a repo, then return its file tree."""
    if not req.url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only https://github.com/ links are allowed")
    path = clone_repo(req.url)
    index_repo(str(path))
    return {"repo": path.name, "tree": build_tree(path)}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        answer, hits = ask(req.repo, req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])
    sources = [
        {"file": m["file"], "start_line": m["start_line"], "end_line": m["end_line"]}
        for m, _ in hits
    ]
    return {"answer": answer, "sources": sources}


@app.get("/file")
def get_file(repo: str, path: str):
    """Return the text of one file, for the code viewer."""
    root = (Path("repos") / repo).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="ignore")}