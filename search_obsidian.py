import toml
from openai import OpenAI
import chromadb

# --- IMPORTS ---
CONFIG = toml.load("config.toml")
OPENAI_API_KEY = CONFIG["openai"]["api"]
EMBEDDING_MODEL = "text-embedding-3-large"
DB_PATH = "./chroma_db"

def search(search_text, vault_label, top_k=5):

    # --- INIT ---
    client = OpenAI(api_key=OPENAI_API_KEY)
    chroma = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma.get_collection("vault_index")

    # Check if the vault exists
    all_metadata = collection.get(include=["metadatas"])["metadatas"]
    if vault_label not in {m.get("vault") for m in all_metadata if "vault" in m}:
        return f'"{vault_label}" is not a vault.'

    # --- EMBED QUERY ---
    def embed(text):
        result = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
        return result.data[0].embedding

    # --- OPTIMIZE INPUT ---
    user_query = search_text.strip()
    optimize_prompt = (
        "You are a query optimizer for a semantic search engine.\n"
        "Rewrite the user's input as a concise, standalone search query.\n"
        "Preserve meaning; omit filler.\n\n"
        f"User Input: {user_query}"
    )
    optimized = client.responses.create(
        model="gpt-4o-mini",
        input=optimize_prompt
    ).output_text.strip()

    print(f"Optimized Query: {optimized}")
    query_embedding = embed(optimized)

    # --- SEARCH DB ---
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas"],
        where={"vault": vault_label}
    )

    # --- COMPILE CHUNKS ---
    chunks = [
        f"Filename: {meta['filename']} (part {meta['part']})\n---\n{doc.strip()}"
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

    # --- ANSWER GENERATION ---
    answer_prompt = (
        "You are a document analysis AI. Based on the following excerpts, answer the user query clearly and completely.\n"
        "Some excerpts may be irrelevant—ignore them. Cite your source like:\nFILENAME:PART\n\n"
        "Use the filename and part shown above each excerpt.\n\n"
        + "\n\n".join(chunks)
        + f"\n\nUser Query: {user_query}"
    )

    response = client.responses.create(
        model="gpt-4o",
        input=answer_prompt
    )

    return response.output_text


if __name__ == "__main__":
    searches = [
    "Was I always like this, or did something change?",
    "What’s the connection between pyramids and civilization?"
]

    for search_tx in searches:
        print(f"Searching for: {search_tx}")
        print(search(search_tx, "wanderland"))
        print("-" * 40)

