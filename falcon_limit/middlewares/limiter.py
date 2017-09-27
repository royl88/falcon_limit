# coding=utf-8
"""
falcon_limit.middlewares.limiter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

频率限制中间件

"""
from __future__ import absolute_import

import copy
import inspect
import time

import falcon
from limits.errors import ConfigurationError
from limits.storage import storage_from_string
from limits.strategies import STRATEGIES

from falcon_limit.common.decorators import LIMITEDS, LIMITED_EXEMPT
from falcon_limit.common.wrapper import LimitWrapper


def get_ipaddr(request, resource):
    return request.access_route[0]


class Limiter(object):
    """
    falcon频率限制中间件类
    """

    def __init__(self,
                 global_limits,
                 enabled=True,
                 key_function=None, per_method=True,
                 strategy='fixed-window', storage_url='memory://',
                 header_reset='X-RateLimit-Reset',
                 header_remaining='X-RateLimit-Remaining',
                 header_limit='X-RateLimit-Limit',
                 callback=None):
        """
        初始化中间件

        :param global_limits: 传入有效字符串(rate limit string notation)表示使用全局限制器，
                               或者None表示无全局限制，全局限制会被函数级装饰器限制覆盖
        :type global_limits: `None` or `string`
        :param enabled: 启用或禁用频率限制
        :type enabled: `boolean`
        :param key_function: 一个返回标识字符串的函数，函数定义：function(request, resource);
                              默认是使用客户端地址(request.access_route[0]),
                              如果decorator/LimitWrapper没有设置key_function，则fallback使用全局key_function
        :type key_function: `function`
        :param per_method: 将http method追加到scope作为命名空间，即每个方法使用不同的限制器. 仅作用于全局限制器
        :type per_method: `boolean`
        :param strategy: 符合limits的策略字符串
        :type strategy: `string`
        :param storage_url: 符合limits的存储后端url
        :type storage_url: `string`
        :param header_reset: 频率限制响应头(response header)，按当前速率发送后，发送窗口重置的时间
        :type header_reset: `string`
        :param header_remaining: 频率限制响应头(response header)，在当前发送窗口内还可以发送的请求数
        :type header_remaining: `string`
        :param header_limit: 频率限制响应头(response header)，当前用户被允许的请求数
        :type header_limit: `string`
        :param callback: 当超过频率限制后，出发此调用，默认是抛出HTTP 429异常
                          函数定义: function(limit)
        :type callback: `function`
        """
        self.enabled = enabled
        self.strategy = strategy
        if self.strategy not in STRATEGIES:
            raise ConfigurationError("invalid rate limiting strategy: %(strategy)s" % {'strategy': self.strategy})
        self.storage = storage_from_string(storage_url)
        self.limiter = STRATEGIES[self.strategy](self.storage)
        self.key_function = key_function or get_ipaddr
        self.per_method = per_method
        self.global_limits = []
        if global_limits:
            self.global_limits = [
                LimitWrapper(
                    global_limits, None, None, self.per_method
                )
            ]
        self.header_mapping = {
            'header_reset': header_reset,
            'header_remaining': header_remaining,
            'header_limit': header_limit,
        }
        self.callback = callback or self.__raise_exceeded

    def __raise_exceeded(self, limit):
        raise falcon.HTTPTooManyRequests(title='Rate Limit Exceeded',
                                         description='rate limit exceeded, %s' % limit)

    def get_extra_limits(self, request, resource, params):
        """
        用于自定义追加的频率限制器(不会覆盖全局限制器或者装饰器限制器)

        :param request: 参照process_resource
        :param resource: 参照process_resource
        :param params: 参照process_resource
        :returns: None或者1~N个LimitWrapper
        :rtype: `None` or `list`
        """
        return None

    def process_resource(self, request, response, resource, params):
        limiter_key = getattr(resource, "on_" + request.method.lower(), None)
        if limiter_key and inspect.ismethod(limiter_key):
            limiter_key = limiter_key.__func__
        limits = self.global_limits
        if limiter_key is None or not self.enabled or limiter_key in LIMITED_EXEMPT:
            return
        if limiter_key in LIMITEDS:
            limits = LIMITEDS[limiter_key]
        extra_limits = self.get_extra_limits(request, resource, params)
        if extra_limits:
            limits = copy.copy(limits)
            if isinstance(extra_limits, (list, tuple)):
                limits.extend(extra_limits)
            else:
                limits.append(extra_limits)
        limit_for_header = None
        failed_limit = None
        for lim in limits:
            limit_scope = lim.get_scope(request, resource)
            cur_limits = lim.get_limits(request, resource)
            for cur_limit in cur_limits:
                if not limit_for_header or cur_limit < limit_for_header[0]:
                    limit_for_header = (cur_limit, (lim.key_func or self.key_function)(request, resource), limit_scope)
                if not self.limiter.hit(cur_limit, (lim.key_func or self.key_function)(request, resource), limit_scope):
                    failed_limit = cur_limit
                    limit_for_header = (cur_limit, (lim.key_func or self.key_function)(request, resource), limit_scope)
                    break
            if failed_limit:
                break
        request.x_rate_limit = limit_for_header
        if failed_limit:
            return self.callback(failed_limit)

    def process_response(self, request, response, resource):
        limit = getattr(request, "x_rate_limit", None)
        if self.enabled and limit:
            window_stats = self.limiter.get_window_stats(*limit)
            response.set_header(self.header_mapping['header_limit'], str(limit[0].amount))
            response.set_header(self.header_mapping['header_remaining'], window_stats[1])
            response.set_header(self.header_mapping['header_reset'], int(window_stats[0] - time.time()))
        return response
