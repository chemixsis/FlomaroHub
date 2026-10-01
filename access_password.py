"""Password hashes for the additional private testing gate."""
import hashlib
import hmac
import secrets


def make_hash(password):
    if len(password) < 16:
        raise ValueError("Hasło testowe musi mieć co najmniej 16 znaków.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'


def valid_hash(encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split('$')
        return (algorithm == 'pbkdf2_sha256' and int(rounds) == 600000
                and len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(digest)) == 32)
    except (ValueError, AttributeError):
        return False


def verify(password, encoded):
    if not valid_hash(encoded) or len(password) > 1024:
        return False
    _, rounds, salt, expected = encoded.split('$')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
    return hmac.compare_digest(actual, expected)
