"""
Constrained text generation with a real language model (Hugging Face).

Same idea as constrained_gen.py, but the "logits" are now a real vocab-sized
tensor from a pretrained LM. A constraint is a LogitsProcessor: it edits the
scores tensor in place (masking disallowed tokens to -inf) before the sampler
picks. The constraint logic is identical to the toy version — only the model
underneath changed.

Uses distilgpt2 (~350MB) so it downloads fast. Run:

    python3 constrained_hf.py
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessor, LogitsProcessorList

MODEL_NAME = "distilgpt2"


def load_model():
    """Load pretrained distilgpt2, or fall back to a tiny random GPT-2 offline.

    The constraint mechanism is identical either way — only text quality
    differs. In a sandbox with no Hugging Face access you still see the masks
    enforced (e.g. no 'e' ever appears), just over gibberish tokens.
    """
    try:
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        print(f"[loaded pretrained {MODEL_NAME}]\n")
    except Exception as e:
        from transformers import GPT2Config, GPT2LMHeadModel, GPT2TokenizerFast
        print(f"[no HF access ({type(e).__name__}); using tiny random GPT-2 — "
              f"text is gibberish but constraints are real]\n")
        tok = _tiny_tokenizer()
        cfg = GPT2Config(vocab_size=tok.vocab_size, n_positions=128,
                         n_embd=64, n_layer=2, n_head=2)
        model = GPT2LMHeadModel(cfg)
    model.eval()
    return tok, model


def _tiny_tokenizer():
    """Build a byte-level BPE tokenizer offline (no download)."""
    from tokenizers import ByteLevelBPETokenizer
    from transformers import GPT2TokenizerFast
    corpus = ("the sun is bright and warm the sky is blue and clear "
              "weather today is calm cool and dry ") * 50
    inner = ByteLevelBPETokenizer()
    inner.train_from_iterator([corpus], vocab_size=500, min_frequency=1,
                              special_tokens=["<|endoftext|>"])
    tok = GPT2TokenizerFast(tokenizer_object=inner._tokenizer)
    tok.add_special_tokens({"eos_token": "<|endoftext|>", "pad_token": "<|endoftext|>"})
    # The trained special token sits inside the small vocab; point the ids at it
    # so config validation and stopping behave (defaults are the 50256 GPT-2 id).
    eos = inner.token_to_id("<|endoftext|>")
    tok.eos_token_id = tok.pad_token_id = tok.bos_token_id = eos
    return tok


tok, model = load_model()
if getattr(model.config, "vocab_size", None) and model.config.eos_token_id and \
        model.config.eos_token_id >= model.config.vocab_size:
    model.config.eos_token_id = model.config.bos_token_id = tok.eos_token_id
    model.generation_config.eos_token_id = tok.eos_token_id
    model.generation_config.pad_token_id = tok.eos_token_id


class TokenAllowProcessor(LogitsProcessor):
    """Mask any next-token whose decoded text fails `allowed_fn`.

    allowed_fn(text, step) -> bool. `text` is the decoded candidate token
    (often with a leading space, GPT-2 style), `step` is how many tokens
    we've generated so far — use it for stateful/positional constraints.

    Decoding every token id per step is expensive; we cache the allow-mask
    for stateless constraints (those that ignore `step`).
    """

    def __init__(self, allowed_fn, tokenizer, stateful=False):
        self.allowed_fn = allowed_fn
        self.tok = tokenizer
        self.stateful = stateful
        self._vocab_texts = [tokenizer.decode([i]) for i in range(tokenizer.vocab_size)]
        self._cached_mask = None
        self._step = 0

    def _build_mask(self, device):
        step = self._step
        allowed = torch.tensor(
            [self.allowed_fn(t, step) for t in self._vocab_texts],
            dtype=torch.bool,
            device=device,
        )
        return allowed

    def __call__(self, input_ids, scores):
        if self.stateful or self._cached_mask is None:
            self._cached_mask = self._build_mask(scores.device)
        scores = scores.masked_fill(~self._cached_mask, float("-inf"))
        self._step += 1
        return scores


def generate(prompt, allowed_fn=None, stateful=False, max_new_tokens=40, seed=0):
    torch.manual_seed(seed)
    inputs = tok(prompt, return_tensors="pt")
    processors = LogitsProcessorList()
    if allowed_fn is not None:
        processors.append(TokenAllowProcessor(allowed_fn, tok, stateful=stateful))
    out = model.generate(
        **inputs,
        do_sample=True,
        temperature=0.9,
        top_k=50,
        max_new_tokens=max_new_tokens,
        logits_processor=processors,
        pad_token_id=tok.eos_token_id,
    )
    return tok.decode(out[0], skip_special_tokens=True)


if __name__ == "__main__":
    prompt = "The weather today is"

    print("unconstrained:")
    print("  ", generate(prompt))

    # Lexical: never emit any token containing the letter 'e'.
    print("\nno token may contain the letter 'e':")
    print("  ", generate(prompt, allowed_fn=lambda t, step: "e" not in t.lower()))

    # Allowlist: restrict the vocabulary to a small themed set (+ punctuation).
    theme = {" the", " sun", " sky", " is", " bright", " and", " warm", " blue", "."}
    print("\nrestricted to a themed vocabulary:")
    print("  ", generate(prompt, allowed_fn=lambda t, step: t in theme or t.isspace()))

    # Stateful/positional: only ASCII, and force a hard stop after ~15 tokens
    # by allowing *only* the period once we're deep enough.
    def late_stop(t, step):
        if not t.isascii():
            return False
        if step >= 15:
            return t.strip() == "."
        return True

    print("\nstateful (ascii-only, must end with '.' after 15 tokens):")
    print("  ", generate(prompt, allowed_fn=late_stop, stateful=True))
