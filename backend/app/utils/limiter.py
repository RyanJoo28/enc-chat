from slowapi import Limiter
from slowapi.util import get_remote_address


def get_auth_or_remote_address(request):
    """优先按认证凭据限流，缺失时回退到客户端 IP。"""
    auth_header = request.headers.get("authorization")
    if auth_header:
        return auth_header
    return get_remote_address(request)


# 使用客户端 IP 作为限流统计维度。
limiter = Limiter(key_func=get_remote_address)
