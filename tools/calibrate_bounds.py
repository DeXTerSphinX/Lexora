import os
import sys
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from core.complexity.scorer import compute_complexity


def load_corpus(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return blocks


def print_stats(name, values):
    arr = np.array(values)

    print(f"\n--- {name} ---")
    print(f"Min: {arr.min():.4f}")
    print(f"Max: {arr.max():.4f}")
    print(f"Mean: {arr.mean():.4f}")
    print(f"5th percentile: {np.percentile(arr, 5):.4f}")
    print(f"95th percentile: {np.percentile(arr, 95):.4f}")


def main():
    corpus_path = os.path.join(PROJECT_ROOT, "data", "sample_corpus.txt")

    if not os.path.exists(corpus_path):
        print("Corpus file not found.")
        return

    texts = load_corpus(corpus_path)

    sentence_lengths = []
    depths = []
    lexicals = []
    infos = []

    for text in texts:
        result = compute_complexity(text)

        for sent in result["sentences"]:
            sentence_lengths.append(sent["sentence"])
            depths.append(sent["depth"])
            lexicals.append(sent["lexical"])
            infos.append(sent["info_density"])

    print_stats("Sentence Length", sentence_lengths)
    print_stats("Dependency Depth", depths)
    print_stats("Lexical Difficulty", lexicals)
    print_stats("Information Density", infos)


if __name__ == "__main__":
    main()