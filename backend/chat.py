import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from indexer import get_client

load_dotenv()

# Cairn tries these in order. If one is busy, it tries the next.
MODELS = ["gemini-3.8-flash", "gemini-flash-latest"]

SYSTEM = (
    "You are Cairn, a senior developer who explains codebases simply. "
    "Answer ONLY from the code snippets provided. Cite sources as "
    "path/to/file.py:START-END. If the snippets don't contain the answer, say so. "
    "Be concise and practical."
)


def retrieve(repo, question, n=8):
    col = get_client().get_collection(repo)
    res = col.query(query_texts=[question], n_results=40)   # fetch more
    hits = list(zip(res["metadatas"][0], res["documents"][0]))

    def is_test(meta):
        f = meta["file"].lower()
        return f.startswith("tests/") or "/tests/" in f or "test_" in f

    source = [h for h in hits if not is_test(h[0])]
    tests = [h for h in hits if is_test(h[0])]
    return (source + tests)[:n]                              # source code first


def call_ai(prompt):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    last_error = None
    for attempt in range(3):              # try up to 3 rounds
        for model in MODELS:              # each round tries every model
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"system_instruction": SYSTEM},
                )
                return response.text
            except Exception as e:
                last_error = e
        wait = 5 * (attempt + 1)
        print(f"  (Google is busy, retrying in {wait} seconds...)")
        time.sleep(wait)
    raise last_error


def ask(repo, question):
    hits = retrieve(repo, question)
    context = "\n\n".join(
        f"### {m['file']}:{m['start_line']}-{m['end_line']}\n{doc}" for m, doc in hits
    )
    prompt = f"Code snippets:\n\n{context}\n\nQuestion: {question}"
    return call_ai(prompt), hits


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python chat.py <repo-name>   e.g. python chat.py flask")
        sys.exit(1)
    repo = sys.argv[1]
    print(f"Chatting with '{repo}'. Type 'exit' to quit.\n")
    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        try:
            answer, hits = ask(repo, q)
        except Exception as e:
            print(f"\nSorry, the AI could not answer: {str(e)[:200]}\n")
            continue
        print("\nCairn:", answer)
        print("\nSources:", ", ".join(f"{m['file']}:{m['start_line']}-{m['end_line']}" for m, _ in hits[:4]))
        print()