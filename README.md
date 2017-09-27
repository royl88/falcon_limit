#
falcon-limit project

基于falcon+limits的rate limit，提供中间件和装饰器方式进行频率限制，也可以继承并扩展原有中间件以达到用户要求。

## 基础教程

让我们基于falcon官方基础教程的例子来进行演示

* 定义Resource
* 使用装饰器装饰要进行rate limit的函数，必须是on\_method的函数
* 定义app，并加载我们的中间件；中间件可以设置全局的limit，此limit对全局没有定义的on\_method函数生效，函数级装饰器的limit会覆盖全局limit

```py
# coding=utf-8

from wsgiref import simple_server
# Let's get this party started!
import falcon
from falcon_limit.common import decorators as deco
from falcon_limit.common import wrapper
from falcon_limit.middlewares import limiter

# Falcon follows the REST architectural style, meaning (among
# other things) that you think in terms of resources and state
# transitions, which map to HTTP verbs.
class ThingsResource(object):
    @deco.limit('1/second')
    def on_get(self, req, resp):
        """Handles GET requests, using 1/second limit"""
        resp.status = falcon.HTTP_200 # This is the default status
        resp.body = ('\nTwo things awe me most, the starry sky '
                     'above me and the moral law within me.\n'
                     '\n'
                     ' ~ Immanuel Kant\n\n')
    def on_post(self, req, resp):
        """Handles POST requests, using global limit(if any)"""
        resp.status = falcon.HTTP_200 # This is the default status
        resp.body = ('\nTwo things awe me most, the starry sky '
                     'above me and the moral law within me.\n'
                     '\n'
                     ' ~ Immanuel Kant\n\n')


# falcon.API instances are callable WSGI apps
app = falcon.API(middleware=[
limiter.Limiter('3/second'),
])

# Resources are represented by long-lived class instances
things = ThingsResource()

# things will handle all requests to the '/things' URL path
app.add_route('/things', things)


if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    httpd.serve_forever()
```

这样我们就有了一个应用，GET /things时最多1请求/秒, POST /things则是3请求/秒，每次请求后我们可以从response的header中获取rate limit的信息，x-ratelimit-limit，x-ratelimit-remaining，x-ratelimit-reset都是通用的header，此处不多解释

```
HTTP/1.0 200 OK
Date: Tue, 26 Sep 2017 09:06:26 GMT
Server: WSGIServer/0.1 Python/2.7.13
x-ratelimit-remaining: 2
x-ratelimit-limit: 3
x-ratelimit-reset: 0
content-type: application/json; charset=UTF-8
content-length: 100

Two things awe me most, the starry sky above me and the moral law within me.

~ Immanuel Kant
```

当超过限制后会返回HTTP 429\(实际上是调用默认中间件callback，callback则默认是抛出http 429异常\)

```
HTTP/1.0 429 Too Many Requests
Date: Tue, 26 Sep 2017 09:08:25 GMT
Server: WSGIServer/0.1 Python/2.7.13
x-ratelimit-remaining: 0
x-ratelimit-reset: 0
x-ratelimit-limit: 3
vary: Accept
content-length: 86
content-type: application/json; charset=UTF-8


{"title": "Rate Limit Exceeded", "description": "rate limit exceeded, 3 per 1 second"}
```

## 进阶教程

如上所示，rate limit需要在函数上安装装饰器，这能满足大部分应用场景。但有时候我们需要更加动态的加载limit组件，比如联合外部配置文件(conf files)，动态设置limit，在这种情况下我们可以继承原有的中间件，根据特定的参数返回额外的limit组件

```py
class MyLimiter(limiter.Limiter):
    def __init__(self, *args, **kwargs):
        super(MyLimiter, self).__init__(*args, **kwargs)
        self.mylimits = {'module.apps.res1': [wrapper.LimitWrapper('2/second')]}
    def get_extra_limits(self, request, resource, params):
        if request.method.lower() == 'post':
            return self.mylimits['module.apps.res1']

app = falcon.API(middleware=[
    MyLimiter('3/second'),
])
```

通过重写中间件的get\_extra\_limits函数，我们可以根据request，resource，params判断及返回我们的特定的limit组件，此limit是追加到全局或函数级limit之后，不会造成覆盖
