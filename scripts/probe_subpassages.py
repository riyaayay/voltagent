import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voltagent.retrieval.dense_qdrant import get_embedder
from sentence_transformers import util

embedder = get_embedder()

with open('data/eval/test_wrong_10.json', 'r', encoding='utf-8') as f:
    wrongs = json.load(f)

for w in wrongs:
    if w['case_id'] in ['W01_wrong_error_code_meaning', 'W02_swapped_numeric_value', 'W04_negation_flip']:
        claim = re.sub(r'\[\d+\]', '', w['answer_text']).strip()
        chunk = w['cited_chunks'][0]['text']
        c_emb = embedder.encode(claim, convert_to_tensor=True)
        chunk_sim = float(util.cos_sim(c_emb, embedder.encode(chunk, convert_to_tensor=True))[0][0])
        
        lines = [line.strip() for line in re.split(r'[\n\r]+|\.\s+', chunk) if line.strip()]
        line_sims = []
        for line in lines:
            l_emb = embedder.encode(line, convert_to_tensor=True)
            line_sims.append((float(util.cos_sim(c_emb, l_emb)[0][0]), line))
        line_sims.sort(reverse=True)
        print(f"=== {w['case_id']} ===")
        print(f"Whole chunk: {chunk_sim:.3f}")
        for sim, line in line_sims[:3]:
            print(f"   ({sim:.3f}): {line}")
