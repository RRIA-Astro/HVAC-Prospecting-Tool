"""Read the app release without importing GUI or ML dependencies."""
import ast
import re
from pathlib import Path


def release_identity(app_path=None):
    path = Path(app_path) if app_path else Path(__file__).with_name("app.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    versions = [ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets)]
    if len(versions) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", versions[0]):
        raise ValueError("app.py must declare exactly one semantic APP_VERSION string.")
    version = versions[0]
    tag = "v" + version.replace(".", "")
    return {"APP_VERSION": version, "APP_TAG": tag, "APP_NAME": "HVAC_Territory_Discovery_" + tag}


if __name__ == "__main__":
    for key, value in release_identity().items():
        print(f"{key}={value}")
