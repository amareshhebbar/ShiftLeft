import ast
import os

def generate_function_map(directory_path: str = ".") -> dict:
    """Scans a directory for Python files and maps their classes/functions using AST."""
    repo_map = {}
    
    for root, _, files in os.walk(directory_path):
        if 'venv' in root or '/.' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        node = ast.parse(file_content)
                    
                    functions = [n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
                    classes = [n.name for n in ast.walk(node) if isinstance(n, ast.ClassDef)]
                    
                    if functions or classes:
                        repo_map[file_path] = {"classes": classes, "functions": functions}
                except Exception as e:
                    print(f"⚠️ Failed to parse {file_path}: {e}")
                    
    return repo_map