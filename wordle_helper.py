import nltk
from nltk.corpus import words, brown
import random
import math as m

random.seed()
print("building dictionary...")
word_list = []
for word in words.words():
    if len(word) == 5 and word == word.lower():
        word_list.append(word)
word_list = set(word_list)
full_word_list = set(word_list)

freqs = nltk.FreqDist([w.lower() for w in brown.words()])
word_list = sorted(word_list, key=lambda x: freqs[x.lower()], reverse=True)

def remove_green(word, sequence):
    "removes green letters for filtering purposes"
    out = ""
    for x in range(len(word)):
        if sequence[x] != 'g':
            out = out + word[x]
    return out

def count_instance(word, letter, sequence = "ggggg"):
    "returns number of letter in word as indicated by sequence"
    c = 0
    for x in range(len(word)):
        if word[x] == letter and (sequence[x] == 'g' or sequence[x] == 'y'):
            c = c + 1
    return c

def filter_out_words(word_list, guess, sequence):
    """
    word_list: old word dictionary
    guess: the guess
    sequence: results of guess, 'gybbg' etc
    """
    out_list = list(word_list)
    for x, l in enumerate(sequence):
        letter = guess[x]
        for word in word_list:
            if (l == "b" and (word[x] == letter or count_instance(guess, letter, sequence) < count_instance(word, letter)) )\
            or (l == "y" and  (word[x] == letter or letter not in remove_green(word, sequence))) \
            or (l == "g" and word[x] != letter):
                while word in out_list:
                    out_list.remove(word)
    if sequence != "ggggg":
        while guess in out_list:
            out_list.remove(guess)
    return out_list

def expected_bit_delivery(guess, word_list):
    "returns bit difference in information between current list and mean of returned filtered lists"
    total_len = 0.0
    for actual in word_list:
        total_len = total_len + len(filter_out_words(word_list, guess, give_answer(guess, actual)))
    mean_len = total_len / len(word_list)
    return m.log(len(word_list), 2) - m.log(mean_len, 2)

def give_answer(guess, actual):
    "returns byg sequence"
    out = list("xxxxx")
    # add gs
    for x in range(len(out)):
        if actual[x] == guess[x]:
            out[x] = "g"
    # add ys and bs
    for x in range(len(out)):
        if out[x] != "g":
            if count_instance(guess, guess[x], out) < count_instance(actual, guess[x]):
                out[x] = "y"
            else:
                out[x] = "b"
    return "".join(out)

def find_next_best_play_two(guess_list, possibility_list):
    min_word = possibility_list[0]
    min_score = len(guess_list) * len(possibility_list)
    for guess in guess_list:
        #print(guess, str(datetime.datetime.now()))
        total = 0
        for actual in possibility_list:
            total = total + len(filter_out_words(possibility_list, guess, give_answer(guess, actual)))
        if min_score > total:
            #print("new min: ", guess, " with score of ", total, str(datetime.datetime.now()))
            min_score = total
            min_word = guess
    return min_word

def find_next_best_play(word_list):
    "word_list: a dictionary of remaining words"
    return find_next_best_play_two(word_list, word_list)

def next_best_play_aggregator(word_list, attempts = 100, size = 50):
    "makes a good guess of a best guess with sampling, more performant for large data sets"
    guess_dict = {}
    for x in range(attempts):
        sub_list = random.sample(word_list, size)
        new_guess = find_next_best_play(sub_list)
        if new_guess in guess_dict:
            guess_dict[new_guess] = guess_dict[new_guess] + 1
        else:
            guess_dict[new_guess] = 1
    guess_dict = sorted(guess_dict.items(), key=lambda x:x[1], reverse=True)
    return guess_dict[0][0]

def play_full_game(word_list):
    turn = 1
    suggestion = "raise"
    print("Guess #", turn)
    print("For your first guess, try 'raise'")
    menutext = """Input a 5-letter sequence following based on your results:
    g = letter is green
    y = letter is yellow
    b = letter is black
    xxxxx = word is invalid
    """
    x = ""
    while True:
        while(len(x)!=5):
            x = input(menutext)
        if x == "xxxxx":
            print("I'll remove that one and find the next best")
            turn = turn - 1
            if suggestion in word_list:
                word_list.remove(suggestion)
            full_word_list.remove(suggestion)
        if x == "ggggg":
            return
        print("narrowning down word list")
        old_len = len(word_list)
        word_list = filter_out_words(word_list, suggestion, x)
        new_len = len(word_list)
        print("out of ", old_len, " words, only ", new_len, " remain")
        if len(word_list) <= 20:
            print("remaining words:", word_list)
        print("calculating next best play...")
        if len(word_list) > 200:
            suggestion = next_best_play_aggregator(word_list)
        else:
            suggestion = find_next_best_play(word_list)
        if len(word_list) <= 50 and len(word_list) > 2 and turn != 5 and expected_bit_delivery(suggestion, word_list) < 1.2:
            print("The best word won't narrow the list down very much")
            print("Looking for a word that will narrow things down more...")
            suggestion = find_next_best_play_two(full_word_list, word_list)
        turn = turn + 1
        print("Guess #", turn)
        print("next guess: ", suggestion)
        x = ""

play_full_game(word_list)
