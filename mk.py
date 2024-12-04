import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict

def run_tests(container_name: str) -> List[str]:
    """Run tests inside the container and return a list of test results."""
    subprocess.run(f"docker exec {container_name} pip install pytest-json-report", shell=True)
    cmd = f"docker exec {container_name} pytest --json-report --json-report-file=report_b.json"
    print("about to run tests")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result)
    tests_output = result.stdout
    # Parse the output to get the list of test names and their statuses
    # This is a simplified example; parsing may need to be adjusted based on output format
    tests = []
    for line in tests_output.splitlines():
        if "test" in line:
            tests.append(line.strip())
    return tests

def apply_patch(container_name: str, patch: str):
    """Apply a patch inside the container."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_patch:
        temp_patch.write(patch)
        temp_patch_path = temp_patch.name
    container_patch_path = f"/tmp/{Path(temp_patch_path).name}"
    subprocess.run(f"docker cp {temp_patch_path} {container_name}:{container_patch_path}", shell=True)
    subprocess.run(f"docker exec {container_name} git apply {container_patch_path}", shell=True)
    Path(temp_patch_path).unlink()

def compare_test_results(before: List[str], after: List[str]) -> Dict[str, List[str]]:
    """Compare test results before and after patches are applied."""
    pass_before = set(test for test in before if "OK" in test)
    fail_before = set(test for test in before if "FAIL" in test)
    pass_after = set(test for test in after if "OK" in test)
    fail_after = set(test for test in after if "FAIL" in test)

    return {
        "PASS_TO_PASS": list(pass_before & pass_after),
        "PASS_TO_FAIL": list(pass_before & fail_after),
        "FAIL_TO_PASS": list(fail_before & pass_after),
        "FAIL_TO_FAIL": list(fail_before & fail_after),
    }

def analyze_patches(code_patch: str, test_patch: str, codebase: Path) -> Dict[str, List[str]]:
    """Apply patches and analyze test results."""
    container_name = "test_container"
    image_name = "python:3.10"

    # Step 1: Clone the codebase into a container
    subprocess.run(f"docker run -d --name {container_name} {image_name} tail -f /dev/null", shell=True)
    subprocess.run(f"docker cp {codebase} {container_name}:/app", shell=True)
    # Step 2: Initialize the git repo in the container
    subprocess.run(f"docker exec {container_name} git init /app", shell=True)
    # Step 3: Initialize the python environment
    subprocess.run(f"docker exec {container_name} pip install -e /app", shell=True)
    # Step 4: Run the current tests
    tests_before = run_tests(container_name)
    print(tests_before)
    # Step 5: Apply the code and test patches
    apply_patch(container_name, code_patch)
    apply_patch(container_name, test_patch)
    # Step 6: Run the tests again
    tests_after = run_tests(container_name)
    # Step 7: Compare test results and return the outcome
    result = compare_test_results(tests_before, tests_after)
    # Clean up
    subprocess.run(f"docker rm -f {container_name}", shell=True)
    return result

if __name__ == "__main__":
    with open("submission.txt") as f:
        code_patch = f.read()

    with open("submission_test.txt") as f:
        test_patch = f.read()

    REPO_PATH = Path("../mwaskom-seaborn-ae7acf0ce6e30ae773f513e0ccadbb7341cf5e90")


    result = analyze_patches(code_patch, test_patch, REPO_PATH)
    print(result)

    