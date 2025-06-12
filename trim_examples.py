import json
import numpy as np

def load_examples(path):
    examples = []
    with open(path, "r") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                item = json.loads(line)
                examples.append(item)
            except json.JSONDecodeError as e:
                print(f"Line {idx} JSON error: {e}")
    return examples

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def find_redundant_pairs(examples, threshold=0.75):
    pairs = []
    for i in range(len(examples)):
        for j in range(i + 1, len(examples)):
            emb_i = examples[i]["embedding"]
            emb_j = examples[j]["embedding"]
            sim = cosine_similarity(emb_i, emb_j)
            if sim >= threshold:
                pairs.append((i, j, sim))
    return pairs

def recommend_removal(examples, pairs):
    for i, j, sim in sorted(pairs, key=lambda x: -x[2]):
        ex_i = examples[i]["text"]
        ex_j = examples[j]["text"]
        keep, drop = (i, j) if len(ex_i) <= len(ex_j) else (j, i)
        print(f"\nSimilarity: {sim:.4f}")
        print(f"[KEEP ] {examples[keep]['text']}")
        print(f"[DROP ] {examples[drop]['text']}")

if __name__ == "__main__":
    examples = load_examples("../examples.jsonl")
    redundant = find_redundant_pairs(examples)
    recommend_removal(examples, redundant)
