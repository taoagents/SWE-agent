from pathlib import Path
from sweagent.agent.agents import AgentArguments, Agent
from sweagent.agent.models import ModelArguments
from sweagent.environment.swe_env import EnvironmentArguments, SWEEnv
from run import ScriptArguments, ActionsArguments
import json

# Load the issue and repository
# Load example.json into example 
with open('example.json') as f:
    example = json.load(f)
ISSUE_DESC = example['problem_statement']
SOLUTION_PATCH = example['patch']
REPO_PATH = Path("../snok-asgi-correlation-id-c9927f37bebfeb5ac9ea94e99cf58d8a3d84cad8")

script_arguments = ScriptArguments(
        environment=EnvironmentArguments(
            image_name="sweagent/swe-agent:latest",
            data_path=f"text://{ISSUE_DESC}",
            repo_path=str(REPO_PATH),
            verbose=True,
            environment_setup="config/environment_setup/py310_default.yaml",
        ),
        skip_existing=False,
        agent=AgentArguments(
            solution_patch=SOLUTION_PATCH,
            mode="make_test",
            model=ModelArguments(
                model_name= "gpt4",
            ),
            config_file=Path("config/default.yaml"),
        ),
        actions=ActionsArguments(
            open_pr=False,
            skip_if_commits_reference_issue=False,
            apply_patch_locally=True,
        ),
        print_config=True,
    )

env = SWEEnv(script_arguments.environment)
observation, info = env.reset(0)

print(info)

agent = Agent("primary", script_arguments.agent)
trajectories_dir = Path.cwd() / "trajectories"
trajectories_dir.mkdir(exist_ok=True)

info, _ = agent.run(
    setup_args={"issue": getattr(env, "query", None), "files": [], "test_files": [], "tests": []},
    env=env,
    observation=observation,
    traj_dir=trajectories_dir,
    return_type="info_trajectory",
)

# Save info['submission'] to a file
submission = info['submission']
with open("submission.txt", "w") as f:
    f.write(submission)