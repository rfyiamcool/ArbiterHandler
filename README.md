#ArbiterHandler

新版本
方便的用来管理python下的工作进程,并且可以接受Signal,自动管理异常退出的进程. 上次也分享了类Master Worker的框架，但因为抄袭了部分gunicorn结构, 所以代码显得很是复杂.

| 信号|功能|
| ---- |:-------------:|
|SIGTTIN| 增加进程|
|SIGTTOU| 减少进程|
|SIGTERM| 关闭进程|
|SIGQUIT| 关闭进程(ctrl c)|
|SIGINT | 关闭进程(break)|
|SIGHUP | 重启进程|

>跟ProcessHandler不同,他(ArbiterHandler)是更加简化的gunicorn, 在信号处理向gunicorn看起. 

####源码中使用
```
import os
import time
from ArbiterHandler import BaseHandler
def task():
    while 1:
        print os.getpid()
        time.sleep(1)

ruler = BaseHandler(task, num_workers=1)
ruler.run()
```

####命令行中的用法
```
python -m ArbiterHandler.main --num-workers=2 test:task
```
