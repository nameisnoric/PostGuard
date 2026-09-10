from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

#hash 
def hash_password(password: str) -> str:
    return password_hash.hash(password)

#เช็คว่า password ตรงมั้ย
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)