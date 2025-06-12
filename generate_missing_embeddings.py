import json
import toml
from openai import OpenAI

# ---- Config ----
CONFIG = toml.load("../config.toml")
OPENAI_API_KEY = CONFIG["openai"]["api"]
EMBEDDING_MODEL = "text-embedding-3-large"
FILE_PATH = "../examples.jsonl"

client = OpenAI(api_key=OPENAI_API_KEY)

# ---- Read and parse file ----
with open(FILE_PATH, "r", encoding="utf-8") as f:
    original_lines = f.readlines()

parsed_lines = []
line_indexes = []

for i, line in enumerate(original_lines):
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        continue
    try:
        obj = json.loads(stripped)
        parsed_lines.append(obj)
        line_indexes.append(i)
    except json.JSONDecodeError:
        continue

# ---- Find and update lines missing embeddings ----
for j, entry in enumerate(parsed_lines):
    if "embedding" not in entry or not entry["embedding"]:
        text = entry["text"]
        print(f"Embedding line {line_indexes[j]}: {text}")
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        parsed_lines[j]["embedding"] = response.data[0].embedding

# ---- Write updated file, preserving comments ----
for obj, i in zip(parsed_lines, line_indexes):
    original_lines[i] = json.dumps(obj) + "\n"

with open(FILE_PATH, "w", encoding="utf-8") as f:
    f.writelines(original_lines)

print("Embedding generation complete.")
