import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm.answer_generator import generate_answer

def main():
    print("Testing generate_answer('market_signals')...")
    res1 = generate_answer("market_signals")
    print(res1.get("_meta"))

    print("\nTesting generate_answer('entry_strategy')...")
    res2 = generate_answer("entry_strategy")
    print(res2.get("_meta"))

    print("\nTesting generate_answer('avoid_warnings')...")
    res3 = generate_answer("avoid_warnings")
    print(res3.get("_meta"))

    print("\nTesting generate_answer('idea_validator')...")
    res4 = generate_answer("idea_validator", neighbourhood="Dusit", room_type="Entire home/apt", target_price=1500)
    print(res4.get("_meta"))
    print("Concept evaluation:", res4.get("concept_evaluation"))

if __name__ == "__main__":
    main()
