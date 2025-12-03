import json
from pathlib import Path


def test_processes_json_valid():
    """Test that processes.json is valid JSON."""
    processes_path = Path(__file__).parent.parent / "config" / "processes.json"
    with open(processes_path, "r") as f:
        config = json.load(f)
    assert isinstance(config, dict)


def test_service_review_process_exists():
    """Test that Service Review Process is defined."""
    processes_path = Path(__file__).parent.parent / "config" / "processes.json"
    with open(processes_path, "r") as f:
        config = json.load(f)
    assert "Service Review Process" in config
    assert "wiki_url" in config["Service Review Process"]


def test_wiki_url_is_valid():
    """Test that wiki_url is a valid URL string."""
    processes_path = Path(__file__).parent.parent / "config" / "processes.json"
    with open(processes_path, "r") as f:
        config = json.load(f)
    wiki_url = config["Service Review Process"]["wiki_url"]
    assert isinstance(wiki_url, str)
    assert wiki_url.startswith("http")
