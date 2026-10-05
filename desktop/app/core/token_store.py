class TokenStore:
    _access_token: str | None = None

    @classmethod
    def set_token(cls, token: str) -> None:
        cls._access_token = token

    @classmethod
    def get_token(cls) -> str | None:
        return cls._access_token

    @classmethod
    def clear_token(cls) -> None:
        cls._access_token = None