"""Module 1.1.3  Credential Reader.

Responsibility : turn a presented credential into a user identity.
Secret         : the credential technology and its encoding.

4-variable model mapping
    monitored m_credentialPresented -> input i_credentialToken: bytes

Anticipated change: the hospital moves from magnetic card to PIN or to a
biometric reader. Only this module changes, because clients receive a user id
and never a token. Implements FR-AUTH-01.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional


class CredentialReader(ABC):
    @abstractmethod
    def read_user_id(self, presented: str) -> Optional[str]:
        """Return the user id for a presented credential, or None if it is not valid.

        Effects : none. This module never records anything and never stores
                  the token, which keeps NFR-SEC-01 enforceable.
        """


class SimulatedCredentialReader(CredentialReader):
    """Simulated reader.

    The mapping from token to user id is the secret. Changing it to a PIN
    hash table or a biometric template store does not change the interface.
    """

    def __init__(self, token_to_user: Dict[str, str]):
        self._tokens = dict(token_to_user)

    def read_user_id(self, presented: str) -> Optional[str]:
        return self._tokens.get(presented)
