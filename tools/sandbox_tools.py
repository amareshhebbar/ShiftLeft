import tempfile
import subprocess
import os

def run_code_in_sandbox(code_string: str) -> dict:
    """Executes code in a temporary file and captures the stdout/stderr."""
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(code_string)
        
        result = subprocess.run(
            ["python", path], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        passed = result.returncode == 0
        logs = result.stdout + "\n" + result.stderr
        
        return {
            "passed": passed,
            "logs": logs.strip()
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "logs": "Execution timed out after 10 seconds."}
    except Exception as e:
        return {"passed": False, "logs": f"System error during execution: {str(e)}"}
    finally:
        if os.path.exists(path):
            os.remove(path)