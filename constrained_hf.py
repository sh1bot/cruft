"""
Load the language model the constrained decoder runs on.

Provides module-level `tok` and `model`: pretrained distilgpt2 (~350MB, fast to
download) when Hugging Face is reachable, or a tiny random GPT-2 built offline
otherwise. Only the text quality differs -- the constraint machinery in
backtracking_hf.py is identical either way (in the offline case the cover text
is gibberish but every constraint is still enforced).
"""

from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "distilgpt2"


def load_model():
    """Load pretrained distilgpt2, or fall back to a tiny random GPT-2 offline."""
    try:
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
        print(f"[loaded pretrained {MODEL_NAME}]\n")
    except Exception as e:
        from transformers import GPT2Config, GPT2LMHeadModel
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
