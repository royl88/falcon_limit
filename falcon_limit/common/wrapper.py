# coding=utf-8
"""
falcon_limit.common.limitwrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

频率限制上下文包装

"""

from __future__ import absolute_import

from limits.util import parse_many
import six


def get_scope(resource, request):
    """取module + resource名称作为默认命名空间"""
    return (resource.__module__ + "." + resource.__class__.__name__).lower()


class LimitWrapper(object):
    """封装频率限制所需的上下文"""

    def __init__(self, limits, key_func=None, scope=None, per_method=True):
        """
        解析并保存上下文信息

        :param limit_value: 字符串或者一个返回字符串的函数，字符串是rate limit string notation(from limits).
        :type limit_value: `string` or `function`
        :param key_func: 一个返回标识字符串的函数，函数定义：function(request, resource).
        :type key_func: `function`
        :param scope: 频率限制范围的命名空间字符串或者返回此字符串的函数，函数定义：function(request, resource); 默认scope是module+resource.
        :type scope: `function` or `string`
        :param bool per_method: 将http method追加到scope作为命名空间，即每个方法使用不同的限制器.
        """
        if isinstance(limits, six.string_types):
            self._limits = list(parse_many(limits))
        else:
            self._limits = limits
        self._scope = scope or get_scope
        self.per_method = per_method
        self.key_func = key_func

    def get_limits(self, request, resource):
        """获取解析后的rate limits"""
        return list(parse_many(self._limits(request, resource))) if callable(self._limits) else self._limits

    def get_scope(self, request, resource):
        """获取rate limit命名空间"""
        scope = self._scope(request, resource) if callable(self._scope) else self._scope
        if self.per_method:
            scope = ':'.join([scope, request.method.lower()])
        return scope
