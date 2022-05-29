# wordle_helper

A python-based solver for NYT's popular Wordle game

### Ethical Disclaimer

I wrote this, so it's not cheating if I use it, but it is if you do!
Also credit me if you use this code for anything other than personal puzzle-solving use.

## Installation and setup

This repository can be cloned by `git clone...` or you can just copy and paste it.

You need python 3 installed, that's non-negotiable.

Install the following packages to build the dictionary:

`pip install nltk`

`python -m nltk.downloader corpus`

`python -m nltk.downloader brown`

`pip install math`

Invoke the python code from your terminal of choice assuming you have `python` installed:

`python wordle_helper.py`

I don't currently care enough to make it an installer, etc, and I think this code's as good as it's getting

Python's `nltk` dictionary is not perfectly symmetrical with the Wordle author's dictionary, so not all games are solvable. It doesn't know the words `gamer` or `fewer`, from games in the last month or so as I've been testing it on my own.

## How it works

First, the code uses the dictionary you installed in the download step to get a list of 8497 distinct five-letter words

For the initial move I suggest `raise`, which I've determined is the best first move. It was a very computational process for the same thing every time, so it's hardcoded.

### The main loop
 
 A word is suggested by the algorithm
 
 The user then enters this word into the game
 
 The game then returns a five-color sequence (where each letter becomes green or yellow or remains black)
 
 Using the code's shorthand the user enters this color data
 
 Based on the color data the algorithm can narrow down the list of valid words
 
 From there a new best word is determined from the remaining list of words
 
### How is the best word determined?

If it sounds subjective, think again.

This code is a much more advanced, resource-intensive version of a binary search algorithm with words.

The code goes through the list of possible words twice, once for guesses and once for answers. In each case, the answer gives a color response that can narrow down the list. We can't know what the answer is for a long list, but we *can* pick the word that will, on average, narrow down the list the most.

Luckily since the data we give and receive is much more complicated than a simple binary search, we can narrow down the list of possible answers much faster than just in half. Often best plays cut down lists by 90-95%. 

Unfortunately this solution is O(n^2). For large cases it becomes slow. My workaround was to take a bunch of random subsets and play those and look for the most common winner among them. Still slow, but in a much more reasonable time-scale for the impatient human player.

In rare cases the remaining lists of words will not be effectively narrowed down by picking the best among the list, consider the following difficult remaining word list:

`bould, could, gould, hould, mould, nould, tould, vould, would`

In this case picking any one word would only eliminate itself. The algorithm can detect this! We can determine the bit value of the best play by how comparing the logarithms of input and mean output lists. My code's rule of thumb is that the guess should eliminate at least 1.2 bits of data, which means reducing the list by more than 57% of its previous length. That value was slightly hand-tuned.

Anyway, if we find that the best play from the list has a terrible expected bit delivery, we instead look back at the whole corpus of words and see if it can do better. In the above case it'd suggest something like `chant` which could act as a determinant on `could`, `hould`, `nould` and `tould`, either determining if any of them are the answer or eliminating them and leaving only five words left over from the original nine. In the latter case a different determining word would have to be found, if it's not the last round.


## Sample game output

```
$ python wordle_helper.py
building dictionary...
Guess # 1
For your first guess, try 'raise'
Input a 5-letter sequence following based on your results:
    g = letter is green
    y = letter is yellow
    b = letter is black
    xxxxx = word is invalid
    yyybb
narrowning down word list
out of  8497  words, only  89  remain
calculating next best play...
Guess # 2
next guess:  glair
Input a 5-letter sequence following based on your results:
    g = letter is green
    y = letter is yellow
    b = letter is black
    xxxxx = word is invalid
    bbgyy
narrowning down word list
out of  89  words, only  10  remain
remaining words: ['diary', 'tiara', 'ziara', 'acari', 'ajari', 'inarm', 'urari',
 'fiard', 'arati', 'izard']
calculating next best play...
Guess # 3
next guess:  ziara
Input a 5-letter sequence following based on your results:
    g = letter is green
    y = letter is yellow
    b = letter is black
    xxxxx = word is invalid
    xxxxx
I'll remove that one and find the next best
narrowning down word list
out of  9  words, only  9  remain
remaining words: ['diary', 'tiara', 'acari', 'ajari', 'inarm', 'urari', 'fiard',
 'arati', 'izard']
calculating next best play...
Guess # 3
next guess:  tiara
Input a 5-letter sequence following based on your results:
    g = letter is green
    y = letter is yellow
    b = letter is black
    xxxxx = word is invalid
    ggggg


```
