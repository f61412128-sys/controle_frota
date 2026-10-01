from datetime import date, datetime


def agora() -> str:
    """Data e hora atuais no formato do banco: 'AAAA-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hoje() -> str:
    """Data de hoje no formato do banco: 'AAAA-MM-DD'."""
    return date.today().strftime("%Y-%m-%d")