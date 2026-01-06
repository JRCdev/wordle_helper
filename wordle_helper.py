# wordle_1.3 - Improved version with fixes
import nltk
from nltk.corpus import words, brown
import hashlib
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from tqdm import tqdm
import math
import statistics
import sys
import re
from typing import List, Dict, Set, Tuple
import os

menutext = """Input a 5-letter sequence following based on your results:
g = letter is green
y = letter is yellow
b = letter is black
xxxxx = word is invalid
"""

# Configuration constants
RARE_GUESSES = [
    "glyph", "lymph", "quite", "nymph", "chuck", "yucky", "whomp", "vouch",
    "pudgy", "moody", "mooch", "jumpy", "howdy", "guppy", "fuzzy", "goofy",
    "cuddy", "cocky", "helix", "latex", "zaxes", "kylix", "bemix", "capax",
    "capex", "minxy", "oxbow", "xylyl", "pyxes", "proxy"
]

MEMORY_FILE = ".wordle_mem.txt"
SCALING_CONSTANT = 1220
FREQ_WEIGHT_BASE = 0.8
WORD_LIST_WEIGHT = 5
INPUT_PATTERN = re.compile(r'^[byg]{5}$')

# Global frequency distribution (cached)
_freq_dist = None


def get_frequency_distribution():
    """Get or create the cached frequency distribution."""
    global _freq_dist
    if _freq_dist is None:
        _freq_dist = nltk.FreqDist([w.lower() for w in brown.words()])
    return _freq_dist


def sort_by_freq(word_list: List[str]) -> List[str]:
    """Sort words by frequency in English text (most common first)."""
    freqs = get_frequency_distribution()
    return sorted(word_list, key=lambda x: freqs[x.lower()], reverse=True)


def generate_answer_list() -> List[str]:
    """Generate all 3^5 possible combinations of black/yellow/green feedback."""
    prod = product(*['byg' for _ in range(5)])
    return [''.join(x) for x in prod]


def full_list_scaling(word_list_len: int, full_list_len: int) -> int:
    """
    Calculate how many words to include in scoring.
    Returns fewer words for long lists, all words as list shrinks.
    """
    if word_list_len <= 2:
        return full_list_len
    scaled = full_list_len - int(SCALING_CONSTANT * math.log(word_list_len - 2))
    return max(10, min(scaled, full_list_len))  # Bounds checking


def score_arr(word: str, arr: List[int], full_word_list: List[str], guess_list: List[str]) -> float:
    """
    Score a guess word based on partition qualities.
    Higher score = worse guess (smaller partitions on average).
    """
    if not arr:
        return float('inf')

    mean_return_val = statistics.mean(arr)
    variance_val = (100000 if len(arr) < 2 else statistics.variance(arr))
    max_grp_val = max(arr)

    # Prefer guesses that are later in the frequency-sorted list
    later_word_wgt = FREQ_WEIGHT_BASE + (len(full_word_list) - full_word_list.index(word)) / (len(full_word_list) * 5)

    # Penalize non-answer words slightly
    possible_answer_wgt = 1 if word not in guess_list else 1 - (1 / (len(guess_list) + 1))

    # Heavily penalize words not in the original word list
    word_list_wgt = WORD_LIST_WEIGHT if word not in full_word_list else 1

    return (mean_return_val + variance_val + max_grp_val) * later_word_wgt * possible_answer_wgt * word_list_wgt


def sort_results(arrays: List[Tuple], full_word_list: List[str], target_list: List[str]) -> List[Tuple]:
    """Sort scored guess results by quality (lower score is better)."""
    sorted_arrays = sorted(arrays, key=lambda x: score_arr(x[0], x[1], full_word_list, target_list))
    return sorted_arrays


def remove_green(word: str, sequence: str) -> str:
    """Return letters from word that are not green (i.e., unknown positions)."""
    return ''.join([word[x] if sequence[x] != "g" else "" for x in range(len(word))])


def count_instance(word: str, letter: str, sequence: str = "ggggg") -> int:
    """Count occurrences of a letter in word, excluding black-marked positions."""
    return sum([1 for x in range(len(word)) if word[x] == letter and sequence[x] != "b"])


def validate_feedback(feedback: str) -> bool:
    """Validate that feedback is exactly 5 characters of b/y/g."""
    return bool(INPUT_PATTERN.match(feedback))


def filter_out_words(word_list: List[str], guess: str, sequence: str) -> List[str]:
    """
    Filter word list based on feedback from a guess.

    Args:
        word_list: Words to filter
        guess: The guessed word
        sequence: Feedback string (b/y/g for each position)
    """
    if not validate_feedback(sequence):
        print(f"Invalid feedback format: {sequence}")
        return word_list

    for x, feedback in enumerate(sequence):
        letter = guess[x]

        if feedback == "b":
            # Black: letter not in word (unless it appears elsewhere marked green/yellow)
            word_list = list(filter(
                lambda word: word[x] != letter and count_instance(guess, letter, sequence) >= count_instance(word, letter),
                word_list
            ))
        elif feedback == "y":
            # Yellow: letter in word but not this position
            word_list = list(filter(
                lambda word: word[x] != letter and letter in remove_green(word, sequence),
                word_list
            ))
        elif feedback == "g":
            # Green: letter at this exact position
            word_list = list(filter(lambda word: word[x] == letter, word_list))

    return word_list


def word_evaluate(word: str, word_list: List[str], byg_combos: List[str]) -> Tuple[str, List[int]]:
    """
    Evaluate how well a guess word partitions the word list.
    Returns partition sizes for each possible feedback.
    """
    results = []
    for sequence in byg_combos:
        remaining = filter_out_words(word_list, word, sequence)
        if len(remaining) > 0:
            results.append(len(remaining))

    return [word, results]


def dictionary_evaluate(full_word_list: List[str], word_list: List[str], byg_combos: List[str]) -> List[str]:
    """
    Score all candidate guess words and return them sorted by quality.
    Uses ThreadPoolExecutor for parallelization.
    """
    with tqdm(total=len(full_word_list), desc="Evaluating words") as pbar:
        results = []
        # Use actual parallelization with reasonable worker count
        with ThreadPoolExecutor(max_workers=None) as executor:
            futures = [executor.submit(word_evaluate, word, word_list, byg_combos) for word in full_word_list]
            for future in futures:
                results.append(future.result())
                pbar.update(1)

        sorted_results = sort_results(results, full_word_list, word_list)
        return [x[0] for x in sorted_results]


def generate_blind_prev_guess_list(prev_guess_list: Dict[str, str]) -> List[str]:
    """
    Generate candidate words when standard dictionary is exhausted.
    Creates all combinations consistent with previous feedback.
    """
    alphabet = set("abcdefghijklmnopqrstuvwxyz")

    # Remove letters that got black feedback everywhere
    for word in prev_guess_list:
        for letter in set(word):
            if count_instance(word, letter, prev_guess_list[word]) == 0:
                alphabet.discard(letter)

    # Find known green letters
    known_letters = list("!" * 5)
    for word in prev_guess_list:
        for x, feedback in enumerate(prev_guess_list[word]):
            if feedback == "g":
                known_letters[x] = word[x]

    known_letters_str = "".join(known_letters)

    # Generate all combinations
    def recursive_fill(word: str) -> List[str]:
        if "!" not in word:
            return [word]
        results = []
        for letter in alphabet:
            new_word = word.replace("!", letter, 1)
            results.extend(recursive_fill(new_word))
        return results

    flat_list = recursive_fill(known_letters_str)

    # Filter by previous guesses
    for word in prev_guess_list:
        flat_list = filter_out_words(flat_list, word, prev_guess_list[word])

    return sorted(list(set(flat_list)))


def create_hash(word_list: List[str]) -> str:
    """Create SHA256 hash of word list for memoization."""
    data = b"".join(word.encode() for word in sorted(word_list))
    return hashlib.sha256(data).hexdigest()


def load_memory_file(memory_file: str) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Load memoized guesses and word lists from file."""
    excludes, includes, answers = [], [], {}

    if not os.path.exists(memory_file):
        return excludes, includes, answers

    try:
        with open(memory_file, "r") as f:
            for line in f:
                if not line or len(line) < 2:
                    continue
                line = line.strip()
                prefix = line[0]
                content = line[1:]

                if prefix == "-":
                    word = content[:5].lower()
                    if len(word) == 5 and word.isalpha():
                        excludes.append(word)
                elif prefix == "+":
                    word = content[:5].lower()
                    if len(word) == 5 and word.isalpha():
                        includes.append(word)
                elif prefix == "@":
                    try:
                        hash_val, word = content.split("|", 1)
                        word = word[:5].lower()
                        if len(word) == 5 and word.isalpha():
                            answers[hash_val] = word
                    except ValueError:
                        continue

        print("Memory file loaded successfully")
    except Exception as e:
        print(f"Error loading memory file: {e}")

    return excludes, includes, answers


def save_memory_file(memory_file: str, new_answers: Dict[str, str], new_excludes: List[str], new_includes: List[str]) -> None:
    """Append new memoized data to memory file."""
    try:
        with open(memory_file, 'a') as f:
            for hash_val, word in new_answers.items():
                f.write(f"@{hash_val}|{word}\n")
            for word in new_excludes:
                f.write(f"-{word}\n")
            for word in new_includes:
                f.write(f"+{word}\n")
    except Exception as e:
        print(f"Error writing memory file: {e}")


def get_user_feedback() -> str:
    """Get and validate user feedback."""
    while True:
        x = input("Enter feedback (5 chars: b/y/g, or 'xxxxx' for invalid): ").lower().strip()
        if x == "xxxxx" or validate_feedback(x):
            return x
        print("Invalid input. Please enter exactly 5 characters (b, y, or g).")


def play_full_game(word_list: List[str], history: Dict[str, str] = None, out_of_guesses: bool = False, 
                   mem_excludes: List[str] = None, mem_includes: List[str] = None, mem_answers: Dict[str, str] = None,
                   byg_combos: List[str] = None) -> Tuple[List[str], Dict[str, str]]:
    """Main game loop for Wordle solver."""
    if history is None:
        history = {}
    if mem_excludes is None:
        mem_excludes = []
    if mem_includes is None:
        mem_includes = []
    if mem_answers is None:
        mem_answers = {}
    if byg_combos is None:
        byg_combos = generate_answer_list()

    turn = 1 + len(history)
    guess_list = []
    prev_guess_list = dict(history)
    new_answers, new_excludes, new_includes = {}, [], []

    while True:
        print(f"\n{'='*60}")
        print(f"Turn {turn}")
        if prev_guess_list:
            print(f"Previous guesses: {prev_guess_list}")
        print(f"Remaining candidates: {len(word_list) if len(word_list) <= 50 else len(word_list)}")

        # Determine best suggestion
        list_hash = create_hash(word_list)

        if turn == 1:
            suggestion = "raise"
        elif turn >= 6:
            suggestion = word_list[0] if word_list else "dread"
        elif len(word_list) < 3:
            suggestion = word_list[-1] if word_list else "dread"
        elif list_hash in mem_answers:
            suggestion = mem_answers[list_hash]
        elif len(guess_list) > 99:
            suggestion = guess_list.pop(0)
        else:
            print("Calculating best play...")
            target_word_list = word_list[:max(1, len(word_list)//5)] if len(word_list) > 200 and not out_of_guesses else word_list

            if not out_of_guesses:
                scaling = full_list_scaling(len(word_list), len(word_list))
                guess_word_list = list(set(word_list[:scaling] + target_word_list))
            else:
                guess_word_list = list(set(list(mem_answers.values()) + RARE_GUESSES))

            guess_word_list = sort_by_freq(guess_word_list)
            guess_list = dictionary_evaluate(guess_word_list, target_word_list, byg_combos)
            suggestion = guess_list.pop(0) if guess_list else word_list[0] if word_list else "dread"

        print(f"Suggestion: {suggestion}")

        # Get user feedback
        feedback = get_user_feedback()

        if feedback == "xxxxx":
            # Guess was invalid
            if suggestion in word_list:
                word_list.remove(suggestion)
            if suggestion not in mem_excludes:
                new_excludes.append(suggestion)

        elif feedback == "ggggg":
            # Game won!
            print(f"Correct! The word was {suggestion}.")
            if out_of_guesses:
                new_includes.append(suggestion)
            return word_list, new_answers, new_excludes, new_includes

        else:
            # Game continues
            guess_list = []
            turn += 1
            word_list = filter_out_words(word_list, suggestion, feedback)
            word_list = sort_by_freq(word_list)
            prev_guess_list[suggestion] = feedback

            if suggestion not in word_list and suggestion not in mem_includes:
                new_includes.append(suggestion)

            if list_hash not in mem_answers:
                new_answers[list_hash] = suggestion

            # Check if word list is empty
            if len(word_list) == 0:
                print("No words match the feedback. Generating blind guess list...")
                out_of_guesses = True
                word_list = generate_blind_prev_guess_list(prev_guess_list)

                for word in mem_excludes:
                    if word in word_list:
                        word_list.remove(word)

                if not word_list:
                    print("ERROR: No possible words found. The feedback may be inconsistent.")
                    return [], new_answers, new_excludes, new_includes

                guess_list = []


def main():
    """Initialize and run the Wordle solver."""
    # Parse command-line arguments for input history
    input_history = {}
    if len(sys.argv) > 1:
        print("Input history detected")
        keys = sys.argv[1::2]
        vals = sys.argv[2::2]
        input_history = dict(zip(keys, vals))

    # Load memory
    mem_excludes, mem_includes, mem_answers = load_memory_file(MEMORY_FILE)

    # Generate word list
    word_list = [w for w in words.words() if len(w) == 5 and w == w.lower()]

    # Add included words
    word_list.extend(mem_includes)

    # Remove excluded words
    word_list = [w for w in word_list if w not in mem_excludes]

    word_list = list(set(word_list))  # Remove duplicates
    full_word_list = list(word_list)

    # Apply input history if provided
    for word in input_history:
        word_list = filter_out_words(word_list, word, input_history[word])

    if len(word_list) == 0:
        print("Input guesses eliminated all words. Generating from scratch...")
        word_list = generate_blind_prev_guess_list(input_history)
        out_of_guesses = True
    else:
        out_of_guesses = False

    word_list = sort_by_freq(word_list)

    # Pre-generate answer combinations
    byg_combos = generate_answer_list()

    # Play the game
    word_list, new_answers, new_excludes, new_includes = play_full_game(
        word_list, input_history, out_of_guesses, mem_excludes, mem_includes, mem_answers, byg_combos
    )

    # Save memory
    save_memory_file(MEMORY_FILE, new_answers, new_excludes, new_includes)
    print("\nMemory file updated.")


if __name__ == "__main__":
    main()
