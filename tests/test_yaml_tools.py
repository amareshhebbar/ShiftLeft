import os, tempfile
from tools.yaml_tools import write_config, write_file_yaml, collect_yaml_files
import yaml

def test_write_config_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = write_config(tmp)
        assert os.path.exists(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["version"] == 1
        assert "auto_pr" in data

def test_write_config_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        p1 = write_config(tmp, {"schedule": "0 3 * * *"})
        p2 = write_config(tmp, {"schedule": "0 4 * * *"})  # should NOT overwrite
        with open(p1) as f:
            data = yaml.safe_load(f)
        assert data["schedule"] == "0 3 * * *"

def test_write_file_yaml_and_collect():
    with tempfile.TemporaryDirectory() as tmp:
        meta = {
            "purpose": "Test file",
            "functions": [{"name": "fn", "takes": ["x: int"], "returns": "int", "does": "..."}],
            "classes": [],
            "lines": 10,
        }
        write_file_yaml(tmp, "agents/test.py", meta)
        collected = collect_yaml_files(tmp)
        assert any("agents/test.py.yaml" in k for k in collected)