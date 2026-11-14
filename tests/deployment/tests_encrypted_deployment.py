from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from redis_dict import RedisDict


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(REPO_ROOT / "src")
TUTORIAL_PATH = REPO_ROOT / "docs" / "tutorials" / "encrypted_storage_deployment.md"

SCRYPT_WORKER = """
import json
import os
import sys
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from redis_dict import EncryptedRedisDict

mode = sys.argv[1]
namespace = os.environ["REDIS_NAMESPACE"]
salt = os.urandom(16) if mode == "unpersisted_salt_read" else bytes.fromhex(os.environ["APP_SCRYPT_SALT_HEX"])
key = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(
    os.environ["APP_SECRET_PASSPHRASE"].encode("utf-8")
)
vault = EncryptedRedisDict(namespace=namespace, key=key)

if mode == "write":
    vault["customer:1"] = {"name": "Alice", "roles": ["admin", "billing"]}
    vault["deploy_version"] = 1
elif mode in ("read", "unpersisted_salt_read"):
    print(json.dumps({"customer": vault["customer:1"], "version": vault["deploy_version"]}))
"""

RAW_KEY_WORKER = """
import base64
import json
import os
import sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from redis_dict import EncryptedRedisDict

mode = sys.argv[1]
namespace = os.environ["REDIS_NAMESPACE"]
key = (
    AESGCM.generate_key(bit_length=256)
    if mode == "ephemeral_key_read"
    else base64.b64decode(os.environ["APP_ENCRYPTION_KEY_B64"])
)
vault = EncryptedRedisDict(namespace=namespace, key=key)

if mode == "write":
    vault["session"] = {"uid": 99, "active": True}
else:
    print(json.dumps(vault["session"]))
"""


def _extract_tutorial_python_blocks() -> dict[str, str]:
    text = TUTORIAL_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"### `([^`]+\.py)`.*?```python\n(.*?)```", re.DOTALL)
    return {name: code for name, code in pattern.findall(text)}


class TestEncryptedDeploymentPersistence(unittest.TestCase):
    NAMESPACE = "__test_encrypted_deployment__"

    def setUp(self) -> None:
        RedisDict(namespace=self.NAMESPACE).clear()

    def tearDown(self) -> None:
        RedisDict(namespace=self.NAMESPACE).clear()

    def _run_subprocess(
        self,
        args: list[str],
        extra_env: dict[str, str],
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else SRC_DIR
        env["REDIS_NAMESPACE"] = self.NAMESPACE
        env.update(extra_env)
        return subprocess.run(args, env=env, cwd=cwd, text=True, capture_output=True, check=False)

    def test_scrypt_persisted_salt_survives_redeploy_while_regenerated_salt_locks_out(self) -> None:
        secret_env = {
            "APP_SECRET_PASSPHRASE": "deploy-secret-passphrase",
            "APP_SCRYPT_SALT_HEX": os.urandom(16).hex(),
        }

        # Deployment 1 (separate OS process): writes encrypted state and exits
        deploy_1 = self._run_subprocess([sys.executable, "-c", SCRYPT_WORKER, "write"], secret_env)
        self.assertEqual(deploy_1.returncode, 0, msg=deploy_1.stderr)

        # Deployment 2 (fresh OS process with same persisted salt + passphrase): reads state cleanly
        deploy_2 = self._run_subprocess([sys.executable, "-c", SCRYPT_WORKER, "read"], secret_env)
        self.assertEqual(deploy_2.returncode, 0, msg=deploy_2.stderr)
        self.assertEqual(
            json.loads(deploy_2.stdout),
            {"customer": {"name": "Alice", "roles": ["admin", "billing"]}, "version": 1},
        )

        # Misconfigured deployment: regenerating os.urandom(16) on boot (even with the SAME passphrase) locks out!
        lockout_deploy = self._run_subprocess(
            [sys.executable, "-c", SCRYPT_WORKER, "unpersisted_salt_read"],
            secret_env,
        )
        self.assertNotEqual(lockout_deploy.returncode, 0)
        self.assertIn("InvalidTag", lockout_deploy.stderr)

        # Misconfigured deployment: wrong passphrase with persisted salt also fails closed
        wrong_pw_deploy = self._run_subprocess(
            [sys.executable, "-c", SCRYPT_WORKER, "read"],
            {**secret_env, "APP_SECRET_PASSPHRASE": "wrong-passphrase"},
        )
        self.assertNotEqual(wrong_pw_deploy.returncode, 0)
        self.assertIn("InvalidTag", wrong_pw_deploy.stderr)

    def test_raw_key_persisted_across_deploys_vs_regenerated_key_lockout(self) -> None:
        secret_env = {
            "APP_ENCRYPTION_KEY_B64": base64.b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii"),
        }

        deploy_1 = self._run_subprocess([sys.executable, "-c", RAW_KEY_WORKER, "write"], secret_env)
        self.assertEqual(deploy_1.returncode, 0, msg=deploy_1.stderr)

        deploy_2 = self._run_subprocess([sys.executable, "-c", RAW_KEY_WORKER, "read"], secret_env)
        self.assertEqual(deploy_2.returncode, 0, msg=deploy_2.stderr)
        self.assertEqual(json.loads(deploy_2.stdout), {"uid": 99, "active": True})

        # Calling AESGCM.generate_key() on restart instead of loading persisted key locks out existing data
        lockout_deploy = self._run_subprocess([sys.executable, "-c", RAW_KEY_WORKER, "ephemeral_key_read"], secret_env)
        self.assertNotEqual(lockout_deploy.returncode, 0)
        self.assertIn("InvalidTag", lockout_deploy.stderr)

    def test_tutorial_deployment_and_key_rotation_scripts_end_to_end(self) -> None:
        blocks = _extract_tutorial_python_blocks()
        self.assertIn("app.py", blocks)
        self.assertIn("rotate_key.py", blocks)

        with tempfile.TemporaryDirectory() as tmpdir:
            app_script = Path(tmpdir) / "app.py"
            rotate_script = Path(tmpdir) / "rotate_key.py"
            app_script.write_text(blocks["app.py"], encoding="utf-8")
            rotate_script.write_text(blocks["rotate_key.py"], encoding="utf-8")

            env_v1 = {
                "APP_SECRET_PASSPHRASE": "passphrase-generation-v1",
                "APP_SCRYPT_SALT_HEX": os.urandom(16).hex(),
            }

            # Deploy #1 & Deploy #2 with persisted env_v1 increment deploy_count without lockout
            run_1 = self._run_subprocess([sys.executable, str(app_script)], env_v1, cwd=tmpdir)
            self.assertEqual(run_1.returncode, 0, msg=run_1.stderr)
            self.assertIn("Deploy #1 read/write OK", run_1.stdout)

            run_2 = self._run_subprocess([sys.executable, str(app_script)], env_v1, cwd=tmpdir)
            self.assertEqual(run_2.returncode, 0, msg=run_2.stderr)
            self.assertIn("Deploy #2 read/write OK", run_2.stdout)

            # Rotate credentials (v1 -> v2) using the tutorial's rotate_key.py script
            env_v2 = {
                "APP_SECRET_PASSPHRASE": "passphrase-generation-v2",
                "APP_SCRYPT_SALT_HEX": os.urandom(16).hex(),
            }
            rotation_env = {
                "OLD_SECRET_PASSPHRASE": env_v1["APP_SECRET_PASSPHRASE"],
                "OLD_SCRYPT_SALT_HEX": env_v1["APP_SCRYPT_SALT_HEX"],
                **env_v2,
            }
            rotate_run = self._run_subprocess([sys.executable, str(rotate_script)], rotation_env, cwd=tmpdir)
            self.assertEqual(rotate_run.returncode, 0, msg=rotate_run.stderr)
            self.assertIn("Rotated 2 keys", rotate_run.stdout)

            # Deploy #3 runs with ONLY env_v2 (OLD_* removed) and reads Deploy #2's state seamlessly
            run_3 = self._run_subprocess([sys.executable, str(app_script)], env_v2, cwd=tmpdir)
            self.assertEqual(run_3.returncode, 0, msg=run_3.stderr)
            self.assertIn("Deploy #3 read/write OK", run_3.stdout)

            # Old credentials (env_v1) can no longer decrypt rotated data
            old_creds_run = self._run_subprocess([sys.executable, str(app_script)], env_v1, cwd=tmpdir)
            self.assertNotEqual(old_creds_run.returncode, 0)
            self.assertIn("InvalidTag", old_creds_run.stderr)


if __name__ == "__main__":
    unittest.main()
