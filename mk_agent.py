from sweagent.environment.swe_env import EnvironmentArguments, SWEEnv
from pathlib import Path
import json
from typing import Dict
import subprocess

# TODO: Make it persistent

with open('example.json') as f:
    example = json.load(f)
ISSUE_DESC = example['problem_statement']
SOLUTION_PATCH = example['patch']
REPO_PATH = Path("../mwaskom-seaborn-ae7acf0ce6e30ae773f513e0ccadbb7341cf5e90")

def run_tests(env: SWEEnv) -> Dict[str, str]:
    """
    Runs tests in the given environment and returns the results.

    Returns:
        Dict[str, str]: A dictionary with test names as keys and their status (passed, failed) as values.
    """
    try:
        env.communicate("pip install pytest-json-report")
        env.communicate("pytest --json-report --json-report-file=/tmp/report.json --json-report-omit collector", timeout_duration=300)
        pytest_report = env.communicate("cat /tmp/report.json")
        data = json.loads(pytest_report)

        tests = {}
        for test in data["tests"]:
            if test["outcome"] in ["passed", "failed"]:
                tests[test["nodeid"]] = test["outcome"].lower()
        
        return tests
    except Exception as e:
        print(f"Error running tests: {e}")
        return None

def apply_patch(env: SWEEnv, patch: str) -> bool:
    """
    Applies the given patch to the environment.

    Args:
        env (SWEEnv): The environment to apply the patch to.
        patch (str): The patch to apply.
    """
    try:
        env.communicate(f"echo '{patch}' > /root/patch.patch")
        env.communicate_with_handling("git apply /root/patch.patch", error_msg="Error applying patch")
        return True
    except Exception as e:
        print(f"Error applying patch: {e}")
        return False

env = SWEEnv(
    EnvironmentArguments(
        image_name="sweagent/swe-agent:latest",
        data_path="text://example.json",
        repo_path=str(REPO_PATH),
        verbose=True,
        # TODO: Change this in final version
        environment_setup="config/environment_setup/py310_default.yaml",
    )
)
_, _ = env.reset(0)

print(apply_patch(env, "TIGO"))