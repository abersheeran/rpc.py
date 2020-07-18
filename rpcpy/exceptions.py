class ClientError(Exception):
    """
    Base Exception for Client
    """


class ServerImplementationError(ClientError):
    """
    Wrong server implementation
    """
