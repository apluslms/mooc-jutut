import os
import logging
import subprocess


logger = logging.getLogger("core.utils")


def check_system_service_status(command):
    """
    Trivial helper to execute subprocess.
    Targeted only for checking system services status outputs
    """
    env = os.environ.copy()
    env.update({
        'SYSTEMD_COLORS': '1',
    })

    logger.info("Executing system command: %s", command)
    out = subprocess.run(
        command,
        shell=isinstance(command, str),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        universal_newlines=True,
        check=False,
    )
    return out.returncode == 0, out.stdout
