from passlib.hash import sha512_crypt


def hash_password(plain):
    return "{SHA512-CRYPT}" + sha512_crypt.hash(plain)
