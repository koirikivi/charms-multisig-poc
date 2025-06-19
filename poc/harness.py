import os
import subprocess
import sys

THIS_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.abspath(os.path.join(THIS_DIR, '..'))
BIN_DIR = os.path.abspath(os.path.join(THIS_DIR, '..', 'bin'))
CHARMS_TOKEN_DIR = os.path.abspath(os.path.join(THIS_DIR, '..', 'my-token'))

ENV = {
    **os.environ,
}
ENV['PATH'] = f"{BIN_DIR}:{ENV['PATH']}"
ENV['RUST_LOG'] = 'info'
ENV['RUST_BACKTRACE'] = 'full'

CHARMS_BIN = "charms"

def restart_docker_compose():
    """Restart the Docker Compose services."""
    try:
        subprocess.run(
            ['docker-compose', 'down'],
            cwd=BASE_DIR,
            check=False,
            env=ENV
        )
        subprocess.run(
            ['docker-compose', 'up', '-d'],
            cwd=THIS_DIR,
            check=True,
            env=ENV
        )
        subprocess.run(
            ['wait-for-bitcoin'],
            cwd=BASE_DIR,
            check=True,
            env=ENV
        )
        print("Docker Compose services restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error restarting Docker Compose services: {e}")


CURRENT_WORKING_DIR = BASE_DIR

def shell(
    command,
    *,
    check: bool = True,
    cwd: str = None,
    echo: bool = False,
    show_stderr: bool = True,
    env: dict[str, str] = None,
    input: str | None = None
) -> str:
    if env is None:
        env = {}
    else:
        env = env.copy()
    env.update(ENV)
    result = subprocess.run(
        [
            "bash",
            "-c",
            command,
        ],
        # command
        # shell=True,
        cwd=cwd or CURRENT_WORKING_DIR,
        env=env,
        # capture_output=True,
        stdout=subprocess.PIPE,
        stderr=sys.stderr if show_stderr else subprocess.DEVNULL,
        check=False,
        text=True,
        encoding="utf-8",
        input=input,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {command}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        # raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
        sys.exit()
    ret = result.stdout.strip()
    if echo:
        print(ret)
    return ret


def cd(path: str):
    """Change the current working directory."""
    global CURRENT_WORKING_DIR
    new_path = os.path.abspath(os.path.join(CURRENT_WORKING_DIR, path))
    if not os.path.isdir(new_path):
        raise NotADirectoryError(f"{new_path} is not a directory")
    CURRENT_WORKING_DIR = new_path
    print(f"Changed directory to: {CURRENT_WORKING_DIR}")


def charms(
    command: str,
    *,
    input: str | None = None,
    echo: bool = True,
):
    """Run a charms command in the my-token directory."""
    # if not os.path.exists(CHARMS_BIN):
    #     raise FileNotFoundError(f"Charms binary not found at {CHARMS_BIN}")
    return shell(
        f"{CHARMS_BIN} {command}",
        cwd=CHARMS_TOKEN_DIR,
        input=input,
        echo=echo,
    )
