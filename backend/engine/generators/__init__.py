"""Generator registry; untrained challengers remain explicitly unavailable."""

from engine.common import GeneratorNotTrained
from engine.generators.base import Generator
from engine.generators.garch import GarchGenerator


def is_available(type: str) -> bool:
    return type == "garch"


def get_generator(type: str) -> Generator:
    if type == "garch":
        return GarchGenerator()
    raise GeneratorNotTrained(f"Generator {type!r} has no trained weights")
