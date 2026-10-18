import sys
from pathlib import Path
import chromadb
from chunker import chunk_repo

DB_DIR = "chroma_db"
BATCH = 100


def get_client():
    return chromadb.PersistentClient(path=DB_DIR)


def index_repo(repo_path: str):
    root = Path(repo_path)
    chunks = chunk_repo(root)
    print(f"Indexing {len(chunks)} chunks from {root.name} ...")

    client = get_client()
    try:
        client.delete_collection(root.name)   # start fresh
    except Exception:
        pass
    col = client.create_collection(root.name)

    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        col.add(
            ids=[f"{c['file']}:{c['start_line']}-{c['end_line']}" for c in batch],
            documents=[f"{c['file']} | {c['name']}\n{c['text'][:2000]}" for c in batch],
            metadatas=[{"file": c["file"], "start_line": c["start_line"],
                        "end_line": c["end_line"], "name": c["name"],
                        "kind": c["kind"]} for c in batch],
        )
        print(f"  {min(i + BATCH, len(chunks))}/{len(chunks)}")
    print("Done.")


def search(repo_name: str, question: str, n: int = 5):
    col = get_client().get_collection(repo_name)
    res = col.query(query_texts=[question], n_results=n)
    for meta, doc in zip(res["metadatas"][0], res["documents"][0]):
        print(f"{meta['file']}  [{meta['kind']}] {meta['name']}  "
              f"(lines {meta['start_line']}-{meta['end_line']})")
        print("   " + doc.splitlines()[1][:80] if len(doc.splitlines()) > 1 else "")
        print()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "index":
        index_repo(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "search":
        search(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        print("Usage:")
        print("  python indexer.py index repos/flask")
        print("  python indexer.py search flask how are routes registered")