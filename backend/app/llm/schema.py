"""Shared JSON contract; importing this must not load an inference library."""
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['summary', 'why_it_matters', 'verify_first', 'next_steps'],
    'properties': {
        'summary': {'type': 'string', 'minLength': 1, 'maxLength': 350},
        'why_it_matters': {'type': 'string', 'minLength': 1, 'maxLength': 250},
        'verify_first': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                         'items': {'type': 'string', 'minLength': 1, 'maxLength': 120,
                                   'pattern': '^(Check|Review|Verify|Inspect|Confirm|Correlate|Ask|Compare) .+'}},
        'next_steps': {'type': 'array', 'minItems': 3, 'maxItems': 3,
                       'items': {'type': 'string', 'minLength': 1, 'maxLength': 220}},
    },
}
