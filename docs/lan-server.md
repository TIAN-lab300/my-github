# 用本机作为局域网服务器

两台电脑连接同一Wi-Fi或局域网，在项目目录打开PowerShell执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-lan.ps1
```

默认使用8001端口，不影响原8000服务。把窗口显示的局域网网址发给同学，对方直接用浏览器访问，无需安装项目或复制数据库。账号按各自身份登录，共用同一套数据。不要让对方访问127.0.0.1。

保持本机开机、联网且不休眠，启动窗口不能关闭。按Ctrl+C停止。换网络后重新运行脚本获取新地址。

脚本沿用ZHIXING_DATA指定的数据目录；未指定时使用backend/data。不会自动迁移、重置或创建管理员账号。首次安装仍需按README初始化数据库。已有8000服务建议在确认8001可用后停止，减少重复后台任务。

无法连接时检查Windows防火墙，仅允许Python在“专用网络”通信。需要手动建立规则时，在管理员PowerShell执行（端口应与启动参数相同）：

```powershell
New-NetFirewallRule -DisplayName 'Zhixing LAN 8001' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8001 -Profile Private -RemoteAddress LocalSubnet
```

访客Wi-Fi、校园网客户端隔离可能禁止设备互访。多个地址时选择真实Wi-Fi或以太网地址，排除VPN和虚拟网卡。

此模式仅供可信局域网使用，采用HTTP，不进行路由器端口映射或公网发布。模型密钥仍只配置在服务器电脑，使用学生账号访问不会获得密钥。
