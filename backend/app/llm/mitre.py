import json
from pathlib import Path
from app.models import MitreTechnique

TECHNIQUES = {r['technique_id']:r for r in json.loads(Path(__file__).with_name('mitre_techniques.json').read_text())}


def validate_mitre(items: list[MitreTechnique]) -> list[MitreTechnique]:
    return [MitreTechnique(**TECHNIQUES[key]) for key in dict.fromkeys(x.technique_id for x in items) if key in TECHNIQUES]
