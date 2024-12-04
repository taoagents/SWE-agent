from pathlib import Path
from sweagent.agent.agents import AgentArguments, Agent
from sweagent.agent.models import ModelArguments
from sweagent.environment.swe_env import EnvironmentArguments, SWEEnv
from run import ScriptArguments, ActionsArguments
import json

import subprocess
import os
import sys
import unittest
import shutil
import tempfile

class TestResultWithSuccesses(unittest.TextTestResult):
    """
    Custom TestResult class that tracks successes.
    """
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)

def clone_codebase(original_dir):
    """
    Clones the codebase directory into a temporary directory.

    Args:
        original_dir (str): Path to the original codebase directory.

    Returns:
        str: Path to the cloned codebase directory.
    """
    temp_dir = tempfile.mkdtemp()
    codebase_clone_dir = os.path.join(temp_dir, 'codebase_clone')
    shutil.copytree(original_dir, codebase_clone_dir)
    print(f"Codebase cloned to {codebase_clone_dir}")
    return codebase_clone_dir

def initialize_git_repository(repo_dir):
    """
    Initializes a Git repository in the given directory.

    Args:
        repo_dir (str): Path to the repository directory.
    """
    try:
        subprocess.run(['git', 'init'], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['git', 'commit', '-m', 'Initial commit', '--allow-empty'], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Initialized Git repository in {repo_dir}")
    except Exception as e:
        print(f"Failed to initialize Git repository: {e}")
        sys.exit(1)

def initialize_environment(codebase_dir, environment_setup):
    """
    Initializes the virtual environment and installs packages.

    Args:
        codebase_dir (str): Path to the codebase directory.
        environment_setup (dict): Environment setup configuration.
    """
    python_version = environment_setup.get('python', '3.10')
    install_command = environment_setup.get('install', '')
    pip_packages = environment_setup.get('pip_packages', [])

    venv_dir = os.path.join(codebase_dir, 'venv')
    python_executable = f'python{python_version}'

    # Create virtual environment
    try:
        subprocess.run(['python3', '-m', 'venv', venv_dir], check=True)
        print(f"Virtual environment created at {venv_dir} using Python {python_version}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create virtual environment: {e.stderr.decode().strip()}")
        sys.exit(1)

    # Paths to executables in the virtual environment
    if os.name == 'nt':
        python_bin = os.path.join(venv_dir, 'Scripts', 'python.exe')
        pip_bin = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        python_bin = os.path.join(venv_dir, 'bin', 'python')
        pip_bin = os.path.join(venv_dir, 'bin', 'pip')

    # Install pip packages
    try:
        for package in pip_packages:
            subprocess.run([pip_bin, 'install', package], check=True)
        print(f"Installed pip packages: {', '.join(pip_packages)}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install pip packages: {e.stderr.decode().strip()}")
        sys.exit(1)

    # Run install command
    if install_command:
        # Modify the PATH and VIRTUAL_ENV environment variables
        env = os.environ.copy()
        env['VIRTUAL_ENV'] = venv_dir
        env['PATH'] = os.path.dirname(python_bin) + os.pathsep + env['PATH']
        try:
            subprocess.run(install_command, shell=True, cwd=codebase_dir, check=True, executable='/bin/bash', env=env)
            print("Install command executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to execute install command: {e.stderr.decode().strip()}")
            sys.exit(1)

    return python_bin



def apply_patch(patch_file: Path, codebase_dir):
    """
    Applies the patch to the codebase.

    Args:
        patch_file (str): Path to the patch file.
        codebase_dir (str): Path to the codebase directory.
    """
    try:
        subprocess.run(['git', 'apply', str(patch_file)], cwd=codebase_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Patch applied successfully.")
    except Exception as e:
        print(f"Failed to apply patch: {e}")
        sys.exit(1)

def get_test_ids(suite):
    """
    Recursively collects test IDs from a test suite.

    Args:
        suite (unittest.TestSuite): The test suite to collect test IDs from.

    Returns:
        set: A set of test IDs.
    """
    test_ids = set()
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            test_ids.update(get_test_ids(test))
        else:
            test_ids.add(test.id())
    return test_ids

def discover_tests(codebase_dir, python_bin):
    """
    Discovers all test cases in the codebase using the specified Python interpreter.

    Args:
        codebase_dir (str): Path to the codebase directory.
        python_bin (str): Path to the Python interpreter in the virtual environment.

    Returns:
        set: A set of test IDs.
    """
    # Run a custom script to list test IDs
    list_tests_script = """
import unittest
import json

loader = unittest.TestLoader()
suite = loader.discover(start_dir='.')
test_ids = []

def collect_test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            collect_test_ids(test)
        else:
            test_ids.append(test.id())

collect_test_ids(suite)
print(json.dumps(test_ids))
"""
    script_file = os.path.join(codebase_dir, 'list_tests.py')
    with open(script_file, 'w') as f:
        f.write(list_tests_script)

    try:
        result = subprocess.run(['python', script_file], cwd=codebase_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        test_ids = json.loads(result.stdout)
        return set(test_ids)
    except subprocess.CalledProcessError as e:
        print(f"Failed to discover tests: {e.stderr}")
        sys.exit(1)

def run_tests(codebase_dir, python_bin):
    """
    Runs the tests in the codebase using the specified Python interpreter and collects their statuses.

    Args:
        codebase_dir (str): Path to the codebase directory.
        python_bin (str): Path to the Python interpreter in the virtual environment.

    Returns:
        dict: A dictionary with test names as keys and their statuses as values.
    """
    # Run a custom script to execute tests and collect results
    run_tests_script = """
import unittest
import json
import sys

class TestResultWithSuccesses(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)

loader = unittest.TestLoader()
suite = loader.discover(start_dir='.')

stream = sys.stdout
runner = unittest.TextTestRunner(stream=stream, resultclass=TestResultWithSuccesses)
result = runner.run(suite)

test_statuses = {}
for test in result.successes:
    test_id = test.id()
    test_statuses[test_id] = {'status': 'success', 'message': ''}
for test, err in result.failures:
    test_id = test.id()
    test_statuses[test_id] = {'status': 'failure', 'message': err}
for test, err in result.errors:
    test_id = test.id()
    test_statuses[test_id] = {'status': 'error', 'message': err}
for test, reason in result.skipped:
    test_id = test.id()
    test_statuses[test_id] = {'status': 'skipped', 'message': reason}

print(json.dumps(test_statuses))
"""
    script_file = os.path.join(codebase_dir, 'run_tests.py')
    with open(script_file, 'w') as f:
        f.write(run_tests_script)

    try:
        result = subprocess.run(['python', script_file], cwd=codebase_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(result)
        test_statuses = json.loads(result.stdout)
        return test_statuses
    except subprocess.CalledProcessError as e:
        print(f"Failed to run tests: {e.stderr}")
        sys.exit(1)


# Load the issue and repository
# Load example.json into example 
with open('example.json') as f:
    example = json.load(f)
ISSUE_DESC = example['problem_statement']
SOLUTION_PATCH = example['patch']
REPO_PATH = Path("../mwaskom-seaborn-ae7acf0ce6e30ae773f513e0ccadbb7341cf5e90")

# script_arguments = ScriptArguments(
#         environment=EnvironmentArguments(
#             image_name="sweagent/swe-agent:latest",
#             data_path=f"text://{ISSUE_DESC}",
#             repo_path=str(REPO_PATH),
#             verbose=True,
#             environment_setup="config/environment_setup/py310_default.yaml",
#         ),
#         skip_existing=False,
#         agent=AgentArguments(
#             solution_patch=SOLUTION_PATCH,
#             mode="make_test",
#             model=ModelArguments(
#                 model_name= "gpt-4o-mini",
#             ),
#             config_file=Path("config/default.yaml"),
#         ),
#         actions=ActionsArguments(
#             open_pr=False,
#             skip_if_commits_reference_issue=False,
#             apply_patch_locally=True,
#         ),
#         print_config=True,
#     )

# env = SWEEnv(script_arguments.environment)
# observation, info = env.reset(0)

# print(info)

# agent = Agent("primary", script_arguments.agent)
# trajectories_dir = Path.cwd() / "trajectories"
# trajectories_dir.mkdir(exist_ok=True)

# info, _ = agent.run(
#     setup_args={"issue": getattr(env, "query", None), "files": [], "test_files": [], "tests": []},
#     env=env,
#     observation=observation,
#     traj_dir=trajectories_dir,
#     return_type="info_trajectory",
# )

# # Save info['submission'] to a file
# submission = info['submission']
# with open("submission.txt", "w") as f:
#     f.write(submission)

if __name__ == '__main__':
    patch_file = Path.cwd() / Path('submission.txt')
    original_codebase_dir = str(REPO_PATH)

    # Read environment setup configuration
    # Assuming the environment_setup is provided as a JSON string in the script
    environment_setup = {
        "python": "3.10",
        "install": "pip install -e . || (python -m pip install --upgrade pip && python -m pip install -e .)",
        "pip_packages": [
          "starlette"
        ]
    }

    # Step 1: Clone the codebase and initialize it as a Git repository
    codebase_dir = clone_codebase(original_codebase_dir)
    initialize_git_repository(codebase_dir)

    # Step 2: Initialize the environment (virtualenv and package installation)
    python_bin = initialize_environment(codebase_dir, environment_setup)

    # Step 3: Discover tests before applying the patch
    print("Discovering tests before applying the patch...")
    tests_before_patch = discover_tests(codebase_dir, python_bin)
    print(f"Found {len(tests_before_patch)} tests before applying the patch.")

    # Step 4: Apply the patch
    apply_patch(patch_file, codebase_dir)

    # Step 5: Discover tests after applying the patch
    print("Discovering tests after applying the patch...")
    tests_after_patch = discover_tests(codebase_dir, python_bin)
    print(f"Found {len(tests_after_patch)} tests after applying the patch.")

    # Step 6: Determine which tests are new
    new_tests = tests_after_patch - tests_before_patch
    existing_tests = tests_after_patch & tests_before_patch

    # Step 7: Run the tests and get statuses
    test_statuses = run_tests(codebase_dir, python_bin)

    # Step 8: Annotate test statuses with introduction status
    for test_id in test_statuses.keys():
        if test_id in new_tests:
            test_statuses[test_id]['introduced_in_patch'] = True
        else:
            test_statuses[test_id]['introduced_in_patch'] = False

    # Output the test statuses
    print("\nTest Results:")
    for test_id, info in test_statuses.items():
        intro_status = "New Test" if info['introduced_in_patch'] else "Existing Test"
        print(f"{test_id}: {info['status']} ({intro_status})")
        if info['message']:
            print(f"Message: {info['message']}")

    # Cleanup (Optional)
    # shutil.rmtree(os.path.dirname(codebase_dir))