"""Hash de senha (PBKDF2-HMAC, stdlib) e geração de tokens de convite."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGO = "sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_senha(senha: str) -> str:
    """Gera um hash no formato ``pbkdf2_sha256$iter$salt_hex$hash_hex``."""

    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(_ALGO, senha.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_{_ALGO}${_ITERATIONS}${salt.hex()}${derived.hex()}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica a senha contra um hash gerado por :func:`hash_senha`."""

    try:
        algoritmo, iteracoes_str, salt_hex, hash_hex = senha_hash.split("$")
        algo = algoritmo.removeprefix("pbkdf2_")
        iteracoes = int(iteracoes_str)
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    derived = hashlib.pbkdf2_hmac(algo, senha.encode("utf-8"), salt, iteracoes)
    return hmac.compare_digest(derived, esperado)


def gerar_token() -> str:
    """Token opaco e URL-safe para links de convite."""

    return secrets.token_urlsafe(32)
