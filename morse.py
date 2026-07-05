"""
Morse round-trip helpers for the constrained decoders.

Two reverse parsers, plus the one symbol-mapping the encoder and decoder share:

  * wordtomorse(token)  -> '.' | '-' | ' '   (the SINGLE source of truth used
    both by the morse_then_end constraint and by the reversal below: a token
    is a dot if it ends in a vowel, a dash if it ends in a consonant other
    than 'y', and a space otherwise -- 'y' and empty/punct tokens included).

  * tokens_to_morse(pieces) : generator OUTPUT -> morse string. Maps each
    generated token back through wordtomorse and joins the symbols. Reverses
    exactly *because* it works on the per-token pieces, not the decoded text
    (decoding then re-tokenizing does not preserve token boundaries).

  * morse_to_text(morse)    : morse string -> plain text, via the International
    Morse table. Letters are single-space separated; words by ' / ' or 3+ spaces.

text_to_morse is included too, so the round trip is checkable both directions.

Run:  python3 morse.py
"""

import re

ENDERS = {".", "?", "!"}

# International Morse: letters + digits. (The message only uses letters.)
MORSE = {
    "A": ".-",    "B": "-...",  "C": "-.-.",  "D": "-..",   "E": ".",
    "F": "..-.",  "G": "--.",   "H": "....",  "I": "..",    "J": ".---",
    "K": "-.-",   "L": ".-..",  "M": "--",    "N": "-.",    "O": "---",
    "P": ".--.",  "Q": "--.-",  "R": ".-.",   "S": "...",   "T": "-",
    "U": "..-",   "V": "...-",  "W": ".--",   "X": "-..-",  "Y": "-.--",
    "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}
MORSE_INV = {code: letter for letter, code in MORSE.items()}


def wordtomorse(word):
    """Map a token to its morse symbol: '.', '-', or ' '.

    Dot   = ends in a vowel.
    Dash  = ends in a consonant EXCEPT 'y'.
    Space = ends in 'y', or is empty / whitespace / punctuation.
    """
    word = word.strip()
    if not word:
        return " "
    last = word[-1].lower()
    if last in "aeiou":
        return "."
    if last in "bcdfghjklmnpqrstvwxz":       # note: no 'y'
        return "-"
    return " "


def tokens_to_morse(pieces, strip_ender=True):
    """Reverse generator output back to the morse string.

    pieces      : the list of decoded generated tokens (no prompt), e.g. the
                  `pieces` returned by backtrack().
    strip_ender : drop a trailing sentence-ender token (the postcondition slot);
                  it is not part of the morse message.
    """
    toks = list(pieces)
    if strip_ender and toks and toks[-1].strip() in ENDERS:
        toks = toks[:-1]
    return "".join(wordtomorse(t) for t in toks)


def morse_to_text(morse):
    """Decode a morse string to text. Words split on ' / ' or 3+ spaces;
    letters within a word split on single spaces. Unknown codes -> '?'."""
    words = []
    for word in re.split(r"\s*/\s*|\s{3,}", morse.strip()):
        if not word:
            continue
        words.append("".join(MORSE_INV.get(code, "?") for code in word.split()))
    return " ".join(words)


def normalize(text):
    """Uppercase and keep only morse-encodable characters, collapsing whitespace
    to single word breaks. This is exactly what a decoded round trip can
    reproduce (morse is case-insensitive and has only the table's characters)."""
    words = []
    for word in text.upper().split():
        kept = "".join(c for c in word if c in MORSE)
        if kept:
            words.append(kept)
    return " ".join(words)


def text_to_morse(text, word_sep=" / "):
    """Encode text to a morse string (letters space-separated, words by word_sep).

    Default word_sep is ' / '. Pass '   ' (three spaces) when the string must
    consist of only dots, dashes and spaces -- e.g. to drive a token-per-symbol
    constraint that has no way to emit a '/'. morse_to_text decodes both."""
    words = []
    for word in text.upper().split():
        words.append(" ".join(MORSE.get(ch, "?") for ch in word))
    return word_sep.join(words)


if __name__ == "__main__":
    message = "... . -.-. .-. . - -- . ... ... .- --. ."
    print("message: ", message)
    print("decoded: ", morse_to_text(message))
    print("re-encoded matches:", text_to_morse(morse_to_text(message)) == message)
