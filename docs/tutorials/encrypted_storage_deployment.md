# Encrypted Storage Deployment Guide (Docker)

When deploying `EncryptedRedisDict` in production, encryption protects data at rest in Redis — **but if your container generates a new key or random KDF salt on every startup, redeploying or restarting the container will derive a different key and lock you out of existing Redis data (`InvalidTag`).**

This guide sets up a minimal two-container Docker Compose deployment (`redis` + `app`) showing how to:
1. Provision and persist your secret passphrase and `Scrypt` salt **once** before first deploy.
2. Redeploy or restart containers while keeping full access to existing encrypted Redis data.
3. Rotate encryption keys across deployments without losing data.

---

## 1. Project Files

Create a directory with `Dockerfile`, `docker-compose.yml`, `app.py`, and `rotate_key.py`:

### `Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "redis-dict[crypto]"
COPY app.py rotate_key.py ./
CMD ["python", "app.py"]
```

### `docker-compose.yml`
```yaml
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data

  app:
    build: .
    depends_on:
      - redis
    env_file:
      - .env
    environment:
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_NAMESPACE: app_vault

volumes:
  redis_data:
```

### `app.py`
Uses [`Scrypt`](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#cryptography.hazmat.primitives.kdf.scrypt.Scrypt) and [`EncryptedRedisDict`](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM), loading the persisted salt and passphrase from environment variables so every deployment derives the exact same 256-bit key:

```python
import os
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from redis_dict import EncryptedRedisDict


def load_key(passphrase_var: str = "APP_SECRET_PASSPHRASE", salt_var: str = "APP_SCRYPT_SALT_HEX") -> bytes:
    # Load the persisted salt — NEVER call os.urandom(16) here on startup,
    # or every container restart will derive a new key and lock out existing data.
    salt = bytes.fromhex(os.environ[salt_var])
    kdf = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1)
    return kdf.derive(os.environ[passphrase_var].encode("utf-8"))


def main() -> None:
    vault = EncryptedRedisDict(
        namespace=os.environ.get("REDIS_NAMESPACE", "app_vault"),
        key=load_key(),
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )
    deploy_count = int(vault.get("deploy_count", 0)) + 1
    vault["deploy_count"] = deploy_count
    vault["service_config"] = {"tier": "production", "deploy_count": deploy_count}
    print(f"Deploy #{deploy_count} read/write OK:", vault["service_config"])


if __name__ == "__main__":
    main()
```

### `rotate_key.py`
When rotating credentials (`OLD_*` -> `NEW_*`), re-encrypt existing namespace entries before removing the old secret:

```python
import os
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from redis_dict import EncryptedRedisDict


def derive_key(passphrase: str, salt_hex: str) -> bytes:
    kdf = Scrypt(salt=bytes.fromhex(salt_hex), length=32, n=2**17, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


def main() -> None:
    namespace = os.environ.get("REDIS_NAMESPACE", "app_vault")
    redis_kwargs = {
        "host": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", "6379")),
    }
    old_vault = EncryptedRedisDict(
        namespace=namespace,
        key=derive_key(os.environ["OLD_SECRET_PASSPHRASE"], os.environ["OLD_SCRYPT_SALT_HEX"]),
        **redis_kwargs,
    )
    new_vault = EncryptedRedisDict(
        namespace=namespace,
        key=derive_key(os.environ["APP_SECRET_PASSPHRASE"], os.environ["APP_SCRYPT_SALT_HEX"]),
        **redis_kwargs,
    )
    snapshot = old_vault.to_dict()
    new_vault.update(snapshot)
    print(f"Rotated {len(snapshot)} keys in namespace {namespace!r}.")


if __name__ == "__main__":
    main()
```

---

## 2. Provision Secrets Once & Deploy

Generate `.env` **once** before the first deployment (in production, store both values in your secret manager and back them up):

```sh
python3 -c '
import os, secrets
with open(".env", "w") as f:
    f.write(f"APP_SECRET_PASSPHRASE={secrets.token_urlsafe(32)}\n")
    f.write(f"APP_SCRYPT_SALT_HEX={os.urandom(16).hex()}\n")
'
```

Run the first deployment, then rebuild/restart to verify data survives across deployments:

```sh
docker compose up --build
# Output: Deploy #1 read/write OK: {'tier': 'production', 'deploy_count': 1}

docker compose up --build
# Output: Deploy #2 read/write OK: {'tier': 'production', 'deploy_count': 2}
```

---

## 3. Rotating Keys Across Deployments Without Lockout

1. Move current credentials to `OLD_SECRET_PASSPHRASE` / `OLD_SCRYPT_SALT_HEX` and add new `APP_SECRET_PASSPHRASE` / `APP_SCRYPT_SALT_HEX` in `.env`.
2. Run the rotation job once:
   ```sh
   docker compose run --rm app python rotate_key.py
   ```
3. Remove `OLD_*` from `.env` and start the next deployment:
   ```sh
   docker compose up --build
   # Output: Deploy #3 read/write OK: {'tier': 'production', 'deploy_count': 3}
   ```
