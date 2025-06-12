import os
from tqdm import tqdm
import toml
import xxhash
from pathlib import Path
from openai import OpenAI
import chromadb
import tiktoken



DB_PATH = "./chroma_db"
CONFIG = toml.load("config.toml")
OPENAI_API_KEY = CONFIG["openai"]["api"]
EMBEDDING_MODEL = "text-embedding-3-large"

# --- INIT ---
client = OpenAI(api_key=OPENAI_API_KEY)
chroma = chromadb.PersistentClient(path=DB_PATH)
collection = chroma.get_or_create_collection(name="vault_index")
enc = tiktoken.encoding_for_model("gpt-4o")

# --- HELPERS ---
def is_valid_path(path, VAULT):
    parts = path.relative_to(VAULT).parts
    for part in parts:
        if part.startswith("."):
            return False
        if part.startswith("_") and part != "_Personal":
            return False
    return True

def embed(text):
    if not isinstance(text, str):
        raise ValueError("Text must be a string")
    text = text.strip()
    if not text:
        raise ValueError("Refusing to embed empty or whitespace-only string")
    if len(enc.encode(text)) > 8192:
        text = text[:8192 * 4]
        print(f"Text too long to embed (likely >8192 tokens). Dividing by 4.\n{text[:100]}...")
        if len(enc.encode(text)) > 8192:
            text = text[:8192 * 2]
            print(f"Still too long. Dividing again.\n{text[:100]}...")
            if len(enc.encode(text)) > 8192:
                text = text[:8192]
                print(f"Still too long. Truncating.\n{text[:100]}...")
    result = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return result.data[0].embedding

def intake(VAULT, vault_label, bot=None, chat_id=None):

    def update(message, bot):
        if bot and chat_id:
            bot.send_message(chat_id, message)
        else:
            print(message)

    VAULT = Path(VAULT)
    # --- LOAD EXISTING METADATA ---
    vault_files = {str(f.relative_to(VAULT)) for f in VAULT.rglob("*.md")}
    existing = collection.get(include=["metadatas", "documents"])
    existing_files = {
        meta["filename"]
        for meta in existing["metadatas"]
        if meta["part"] == 0
    }

    # --- DELETE MISSING FILES ---
    deleted = existing_files - vault_files
    for f in deleted:
        collection.delete(where={"filename": f})

    # --- DETECTION PHASE ---
    update_queue = []

    for file in VAULT.rglob("*.md"):
        if not is_valid_path(file, VAULT):
            continue

        relpath = str(file.relative_to(VAULT))
        content = file.read_text(encoding="utf-8")
        h = xxhash.xxh3_64_hexdigest(content)

        file_entry = [
            m for m in existing["metadatas"]
            if m["filename"] == relpath and m["part"] == 0
        ]

        if not file_entry or file_entry[0].get("xxhash") != h:
            update_queue.append((file, relpath, content, h))

    # --- INDEXING PHASE ---
    total_files = len(update_queue)
    if total_files == 0:
        update("No files to update.", bot)
    else:
        update(f"Starting to process {total_files} modified file(s)...", bot)

    percent_step = max(1, total_files // 10)
    next_threshold = percent_step

    for index, (file, relpath, content, h) in enumerate(update_queue, start=1):
        collection.delete(where={"filename": relpath})

        # --- Part 0: Full file ---
        full_input = f"Filename: {relpath}\nContent:\n{content}"
        full_emb = embed(full_input)
        collection.add(
            documents=[content],
            embeddings=[full_emb],
            metadatas=[{"filename": relpath, "part": 0, "xxhash": h, "vault": vault_label}],
            ids=[f"{relpath}::0"]
        )

        # --- Chunking ---
        raw_chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
        chunks = []
        for chunk in raw_chunks:
            if len(chunk) < 10 and chunks:
                chunks[-1] += "\n\n" + chunk
            else:
                chunks.append(chunk)

        for i, chunk in enumerate(chunks, start=1):
            try:
                chunk_input = f"Filename: {relpath}\nContent:\n{chunk}"
                e = embed(chunk_input)
                collection.add(
                    documents=[chunk],
                    embeddings=[e],
                    metadatas=[{"filename": relpath, "part": i, "vault": vault_label}],
                    ids=[f"{relpath}::{i}"]
                )
            except ValueError as err:
                update(f"Skipping chunk in {relpath} (part {i}): {err}", bot)

        if index >= next_threshold or index == total_files:
            percent = int(100 * index / total_files)
            update(f"Progress: {percent}% ({index}/{total_files} files indexed)", bot)
            next_threshold += percent_step


if __name__ == "__main__":
    vault = "/Users/graylott/Obsidian/Wanderland/Wanderland/"

    intake(vault, "wanderland")