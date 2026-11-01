import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_negation_conflict(claim: str, source: str) -> tuple[bool, str]:
    aux = r"(?:will|shall|can|could|should|must|may|might|do|does|did|is|are|was|were)"
    negated_in_src = set(re.findall(rf"\b{aux}\s+(?:not|never)\s+([a-z]+)\b", source.lower()))
    negated_in_claim = set(re.findall(rf"\b{aux}\s+(?:not|never)\s+([a-z]+)\b", claim.lower()))

    # also handle "cannot <verb>"
    negated_in_src |= set(re.findall(r"\bcannot\s+([a-z]+)\b", source.lower()))
    negated_in_claim |= set(re.findall(r"\bcannot\s+([a-z]+)\b", claim.lower()))

    affirmed_in_src = set(re.findall(rf"\b{aux}\s+([a-z]+)\b", source.lower())) - negated_in_src
    affirmed_in_claim = set(re.findall(rf"\b{aux}\s+([a-z]+)\b", claim.lower())) - negated_in_claim

    conflict_1 = (negated_in_src & affirmed_in_claim) - {"be", "have"}
    conflict_2 = (affirmed_in_src & negated_in_claim) - {"be", "have"}

    if conflict_1:
        return True, f"Claim affirms negated action: {conflict_1}"
    if conflict_2:
        return True, f"Claim negates affirmed action: {conflict_2}"
    return False, ""


def main():
    print("Testing negation conflict on test_wrong_10:")
    with open("data/eval/test_wrong_10.json", "r", encoding="utf-8") as f:
        wrongs = json.load(f)
    for w in wrongs:
        c = w["answer_text"]
        s = " ".join(chk["text"] for chk in w.get("cited_chunks", []))
        conflict, reason = check_negation_conflict(c, s)
        print(f"[{w['case_id']}] conflict={conflict} {reason}")

    print("\nTesting negation conflict on test_correct:")
    with open("data/eval/test_correct.json", "r", encoding="utf-8") as f:
        corrects = json.load(f)
    false_flags = 0
    for c in corrects:
        ans = c["answer_text"]
        s = " ".join(chk["text"] for chk in c.get("cited_chunks", []))
        conflict, reason = check_negation_conflict(ans, s)
        if conflict:
            false_flags += 1
            print(f"FALSE FLAG: [{c['case_id']}] conflict={conflict} {reason}")
    print(f"Total false flags on correct: {false_flags} / {len(corrects)}")

    print("\nTesting negation conflict on dev:")
    with open("data/eval/dev.json", "r", encoding="utf-8") as f:
        devs = json.load(f)
    for d in devs:
        ans = d["answer_text"]
        s = " ".join(chk["text"] for chk in d.get("cited_chunks", []))
        conflict, reason = check_negation_conflict(ans, s)
        print(f"[{d['case_id']}] conflict={conflict} {reason}")


if __name__ == "__main__":
    main()

