## 一个自动化获取任何网站信息的工具

### 项目结构

```shell
|- extensions               浏览器插件目录（主要是屏蔽站点的监控脚本）
|- userdata                 浏览器用户数据目录
|- data                     持久化数据目录
|- src                      代码目录
    |- core                 浏览器引擎配置
    |- handler              站点处理器
    |- js                   需要执行的 js 脚本
    |- schema               数据结构
    |- const.py             全局变量
    |- settings.py          系统设置
    |- utils.py             工具方法
|- .env.example     需要设置的环境变量实例
```