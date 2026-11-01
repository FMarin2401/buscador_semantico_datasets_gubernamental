# Este archivo centraliza el cifrado y la verificacion de contraseñas para toda la aplicacion

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

# El primer hasher (Argon2) se usa para todas las contraseñas nuevas.
# BcryptHasher solo queda para reconocer los hashes creados antes con passlib; al iniciar sesión se migran a Argon2.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

_LIMITE_BYTES_BCRYPT = 72 # bcrypt solo usa los primeros 72 bytes; la versión 5 lanza error si recibe más

# Hash de una contraseña que nadie conoce. Se verifica contra él cuando el usuario no existe,
# para que la respuesta tarde lo mismo y no se pueda adivinar qué usuarios existen midiendo tiempos.
_HASH_FICTICIO = _password_hash.hash("contraseña-ficticia-para-igualar-tiempos")


def cifrar_password(password: str) -> str:
    return _password_hash.hash(password)


def verificar_password(password: str, hash_guardado: str | None) -> tuple[bool, str | None]:
    """
    Devuelve (es_valida, hash_nuevo). Si hash_nuevo no es None, hay que guardarlo en la base:
    significa que el hash era antiguo (bcrypt) y se recalculó con Argon2.
    Si hash_guardado es None (usuario inexistente) se verifica contra un hash ficticio y siempre devuelve False.
    """
    if hash_guardado is None:
        _password_hash.verify(password, _HASH_FICTICIO)
        return False, None

    if BcryptHasher.identify(hash_guardado):
        # Los hashes bcrypt antiguos se crearon truncando a 72 bytes; replicamos eso para que las contraseñas largas sigan funcionando
        password_bcrypt = password.encode("utf-8")[:_LIMITE_BYTES_BCRYPT]
        if not _password_hash.verify(password_bcrypt, hash_guardado):
            return False, None
        return True, cifrar_password(password)

    return _password_hash.verify_and_update(password, hash_guardado)
