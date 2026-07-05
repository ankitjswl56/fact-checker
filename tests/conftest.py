from __future__ import annotations

import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


def _scrub_api_key(request):
    if request.body:
        try:
            body = json.loads(request.body)
        except (ValueError, TypeError):
            return request
        if "api_key" in body:
            body["api_key"] = "REDACTED"
            request.body = json.dumps(body).encode()
    return request


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "before_record_request": _scrub_api_key,
        "filter_headers": ["authorization"],
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return os.path.join(os.path.dirname(__file__), "cassettes")