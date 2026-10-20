import json
import pytest
from app.llm.structured import build_tokenizer_data, json_filter


class CharacterTokenizer:
    eos_token_id = 128
    all_special_ids = [128]
    def __len__(self): return 129
    def encode(self, text): return [ord(x) for x in text]
    def batch_decode(self, rows, **kwargs): return [self.decode(row) for row in rows]
    def decode(self, ids, **kwargs): return ''.join(chr(x) for x in ids)


def test_schema_blocks_premature_close_and_second_object():
    tokenizer = CharacterTokenizer()
    prefix = '{"summary": "The alert reports '
    allow = json_filter(build_tokenizer_data(tokenizer), prefix)
    # Full prompt tokens are deliberately unrelated to the generated JSON.
    class Tensor(list):
        def tolist(self): return list(self)
    sent = Tensor([999])
    continuation = 'phishing.","why_it_matters":"Possible credential theft.","verify_first":["Check email logs","Check clicks"],"next_steps":["Review delivery logs","Verify user activity","Contain if confirmed"]}'
    for char in continuation:
        allowed = allow(0, sent)
        if char == ',' and 'verify_first' in tokenizer.decode(sent[1:]):
            assert ord('}') not in allowed
        assert ord(char) in allowed, (char, tokenizer.decode(sent[1:]))
        sent.append(ord(char))
    allowed = allow(0, sent)
    assert tokenizer.eos_token_id in allowed
    assert ord('{') not in allowed
    assert len(json.loads(prefix+continuation)['next_steps']) == 3


def test_prefill_must_match_schema():
    with pytest.raises(ValueError):
        json_filter(build_tokenizer_data(CharacterTokenizer()), '{"unexpected":')
