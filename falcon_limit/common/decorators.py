# coding=utf-8
"""
falcon_limit.common.decorators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

频率限制装饰器: limit, limit_exempt

"""

from __future__ import absolute_import

import functools

from falcon_limit.common.wrapper import LimitWrapper


LIMITEDS = {}
LIMITED_EXEMPT = {}


def limit(limit_value, key_function=None, scope=None, per_method=True):
    """
    用于falcon资源的装饰器，通常用于on_method函数上.
    以key + scope 作为限制器的唯一标识
    ::

        eg.
        @limit('365/year;1/day')
        def on_post(self, req, resp)
            pass

    :param limit_value: 字符串或者一个返回字符串的函数，字符串是rate limit string notation(from limits).
    :type limit_value: `string` or `function`
    :param key_func: 一个返回标识字符串的函数，函数定义：function(request, resource).
    :type key_func: `function`
    :param scope: 频率限制范围的命名空间字符串或者返回此字符串的函数，函数定义：function(request, resource); 默认scope是module+resource.
    :type scope: `function` or `string`
    :param bool per_method: 将http method追加到scope作为命名空间，即每个方法使用不同的限制器.
    """
    def _inner(fn):
        @functools.wraps(fn)
        def __inner(*args, **kwargs):
            return fn(*args, **kwargs)
        if fn in LIMITEDS:
            LIMITEDS.setdefault(__inner, LIMITEDS.pop(fn))
        LIMITEDS.setdefault(__inner, []).append(
            LimitWrapper(limit_value, key_function, scope, per_method=per_method)
        )
        return __inner
    return _inner


def limit_exempt(fn):
    """
    标识一个函数不受频率限制.
    """
    @functools.wraps(fn)
    def __inner(*args, **kwargs):
        return fn(*args, **kwargs)
    LIMITED_EXEMPT[__inner] = None
    return __inner
