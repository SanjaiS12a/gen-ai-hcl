"""Local JSON token constraints; no model, networking, or Transformers imports."""
from lmformatenforcer import (CharacterLevelParserConfig, JsonSchemaParser,
                              TokenEnforcer, TokenEnforcerTokenizerData)


SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['summary', 'why_it_matters', 'verify_first', 'next_steps'],
    'properties': {
        'summary': {'type': 'string', 'minLength': 1, 'maxLength': 350},
        'why_it_matters': {'type': 'string', 'minLength': 1, 'maxLength': 250},
        'verify_first': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                         'items': {'type': 'string', 'minLength': 1, 'maxLength': 120}},
        'next_steps': {'type': 'array', 'minItems': 3, 'maxItems': 3,
                       'items': {'type': 'string', 'minLength': 1, 'maxLength': 160}},
    },
}


def build_tokenizer_data(tokenizer):
    # Same contextual decoding as LMFE's official Transformers adapter. Use its
    # public core API because release 0.11.3's adapter imports a pre-v5 class path.
    # Batches bound temporary allocations for Qwen's large vocabulary.
    zero = tokenizer.encode('0')[-1]
    special = set(tokenizer.all_special_ids)
    regular = []
    for start in range(0, len(tokenizer), 1024):
        ids = [x for x in range(start, min(start+1024, len(tokenizer))) if x not in special]
        contextual = tokenizer.batch_decode([[zero, x] for x in ids], clean_up_tokenization_spaces=False)
        standalone = tokenizer.batch_decode([[x] for x in ids], clean_up_tokenization_spaces=False)
        regular.extend((x, after[1:], len(after[1:]) > len(single))
                       for x, after, single in zip(ids, contextual, standalone))
    def decode(ids):
        return tokenizer.decode(ids, clean_up_tokenization_spaces=False).rstrip('\ufffd')
    return TokenEnforcerTokenizerData(regular, decode, tokenizer.eos_token_id, False, len(tokenizer))


def json_filter(data, prefix):
    config = CharacterLevelParserConfig(alphabet=data.tokenizer_alphabet,
                                        force_json_field_order=True, max_consecutive_whitespaces=1)
    parser = JsonSchemaParser(SCHEMA, config)
    for char in prefix:
        if char not in parser.get_allowed_characters():
            raise ValueError('Assistant prefill does not match the narrative JSON schema.')
        parser = parser.add_character(char)
    enforcer = TokenEnforcer(data, parser)
    parser.config = config  # TokenEnforcer initializes its own default config.
    def allowed(batch_id, sent):
        return enforcer.get_allowed_tokens(sent.tolist()).allowed_tokens
    return allowed
