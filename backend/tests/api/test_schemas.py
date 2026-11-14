"""Contract §§1,5,7: wire names, constraints and OpenAPI model coverage."""

import pytest
from pydantic import ValidationError

from app.schemas.api import CreateAuditRequest, PBOPoint


def test_request_defaults_and_seed_bounds():
    body = dict(
        start="2010-01-01",
        end="2025-12-31",
        strategy={"template": "ma_crossover", "grid": {"fast": [5, 10], "slow": [50]}},
    )
    request = CreateAuditRequest.model_validate(body)
    assert request.generator.n_histories == 1000
    assert request.costs_bps == 5
    with pytest.raises(ValidationError):
        CreateAuditRequest.model_validate({**body, "generator": {"seed": -1}})


def test_scatter_alias_is_wire_name():
    assert PBOPoint.model_validate({"is": 0.8, "oos": 0.2}).model_dump(by_alias=True) == {
        "is": 0.8,
        "oos": 0.2,
    }
