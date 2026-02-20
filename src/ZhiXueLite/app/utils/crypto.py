from cryptography.fernet import Fernet

from app.config import config

ENCRYPTION_KEY = config.ENCRYPTION_KEY
f = Fernet(ENCRYPTION_KEY)


def encrypt(plaintext: str) -> str:
    """加密数据"""
    encrypted_text = f.encrypt(plaintext.encode())
    return encrypted_text.decode()


def decrypt(ciphertext: str) -> str:
    """解密数据"""
    decrypted_text = f.decrypt(ciphertext.encode())
    return decrypted_text.decode()
