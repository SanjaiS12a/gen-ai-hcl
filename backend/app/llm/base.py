from typing import Protocol


class Provider(Protocol):
    name: str
    model_name: str
    status: str

    def generate(self, messages: list[dict[str, str]], deadline: float) -> str: ...
