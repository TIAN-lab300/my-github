# 联网搜索配置与验证

自动检索已接入 Tavily、百炼原生搜索，需要独立的搜索服务权限。DeepSeek/GPT 对话 API 配置并不等于已经启用联网搜索。未配置时仍可使用检索页的必应、百度、MOOC 搜索入口；这些入口不作为系统检索结果或已审核正文。

在项目目录打开 PowerShell，在同一窗口设置并启动后端：

```powershell
$env:ZHIXING_SEARCH_PROVIDER='tavily'
$searchSecret=Read-Host '输入 Tavily API Key' -AsSecureString
$env:TAVILY_API_KEY=[System.Net.NetworkCredential]::new('', $searchSecret).Password
.\.venv\Scripts\python.exe scripts/run.py --port 8000
```

启动前先关闭占用 8000 的旧后端；已有进程不会读取新窗口的环境变量。密钥仅保存在此进程环境中，不写入源码，不提交 GitHub。

若使用百炼，将 provider 改为 `dashscope`，密钥变量改为 `DASHSCOPE_API_KEY`；可设置 `ZHIXING_SEARCH_MODEL=qwen-plus`。需要相应北京地域服务与支持联网搜索的模型权限。

管理员登录 → 模型配置 → 联网搜索服务 → 刷新配置状态 → 执行真实搜索能力试验。配置状态仅说明变量存在，能力试验成功取得来源才证明本次服务可用。网络、额度或权限错误会明确失败，不能将模型回答冒充来源。

学生搜索结果可收藏为个人链接；教师登记班级链接后，需确认有权抓取，再导入正文并审核发布。网址与摘要不自动成为知识检测或路径规划的正文证据。
