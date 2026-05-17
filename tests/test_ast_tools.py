
from tools.ast_tools import extract_functions, extract_classes, analyse_file
import tempfile, os, textwrap

SAMPLE = textwrap.dedent("""
    \"\"\"Sample module for testing.\"\"\"

    def add(a: int, b: int) -> int:
        \"\"\"Return the sum of a and b.\"\"\"
        return a + b

    class Greeter:
        \"\"\"Produces greeting strings.\"\"\"
        def hello(self, name: str) -> str:
            \"\"\"Return a hello message.\"\"\"
            return f"Hello, {name}"
""")

def test_extract_functions():
    fns = extract_functions(SAMPLE)
    assert len(fns) == 1
    assert fns[0]["name"] == "add"
    assert "a: int" in fns[0]["takes"]
    assert fns[0]["returns"] == "int"
    assert fns[0]["does"] == "Return the sum of a and b."

def test_extract_classes():
    cls = extract_classes(SAMPLE)
    assert len(cls) == 1
    assert cls[0]["name"] == "Greeter"
    assert any(m["name"] == "hello" for m in cls[0]["methods"])

def test_analyse_file_end_to_end():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SAMPLE)
        path = f.name
    try:
        result = analyse_file(path)
        assert result["purpose"] == "Sample module for testing."
        assert len(result["functions"]) == 1
        assert len(result["classes"]) == 1
    finally:
        os.unlink(path)