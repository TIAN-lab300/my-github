# 新增功能配置与验收说明

本说明适用于当前源码及迁移0017。四份主文档位于docx目录，功能状态以current-function-inventory.md及remaining-functions-acceptance.md为准。本轮未更新8000运行库，下面命令供后续部署时使用。

## 安装依赖和本地模型

在项目根目录执行以下PowerShell命令。

```powershell
Set-Location 'D:\卓越工程'
python -m pip --python .venv/Scripts/python.exe install -r backend/requirements-lock.txt
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe -m app.cli prepare-models
```

prepare-models下载本地中文向量、Whisper tiny语音模型及OCR权重。默认模型目录为backend/data/models，部署时可通过ZHIXING_MODEL_DIR指定。音视频解码使用PyAV，不需要额外的ffmpeg命令。PyAV须使用依赖锁中的兼容版本。

图片及扫描PDF在资料详情启动本地OCR，媒体启动自动转写。识别低于阈值时保存待复核正文，不加入正式检索；所有者校正后产生新版本，再审核发布。语音评分为序列概率代理值，不能解释为校准后的统计准确率。扫描PDF最多100页，本地处理15分钟超时；媒体转写最长60分钟。文档与图片20MiB/份、合计100MiB，音视频200MiB/份，每批最多10份、合计500MiB。

## 使用隔离演示数据

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe -m app.cli demo-sandbox backend/data/demo-review
$env:ZHIXING_DATA = Join-Path (Get-Location) 'backend/data/demo-review'
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9106
```

初始化仅一次输出随机临时密码，首次登录须改密。停止演示服务后，可在新终端执行受控重置。

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe -m app.cli demo-reset backend/data/demo-review --confirm demo-review
```

重置只接受带路径匹配标记的独立演示目录，将整个旧目录原子归档到相邻目录，再建立新演示数据。默认运行数据目录不能通过此命令重置。

## 配置真实云端四智能体

在启动服务的PowerShell进程设置DASHSCOPE_API_KEY，或配置记录中指定的其他密钥环境变量。密钥不写入前端和数据库。.env.example仅列出变量示例，启动脚本没有自动读取.env文件。

管理员在模型配置页面登记端点、模型、超时、温度、令牌上限和提示词版本，执行真实JSON能力试验，再运行60场景评价并在页面逐例复核，批准报告后激活。学生在目标页面选择真实云端四智能体。必要课程正文须由所有者明确勾选云端授权；缺少授权时云端规划明确拒绝提交，学生仍可选择本地规划。

四阶段分别进行目标分析、活动与学时生成、教学审查、学习调整解释。预算、先修、版本和引用仍由业务服务核验。配置冻结在每个运行记录，JSON格式最多修复两次，路径最多修复三次；取消或180秒提交时限到达时不生成正式候选。

当前JSON能力试验只验证连通与结构输出。完整60场景报告全部硬判据通过、管理员逐例勾选教学语义并填写依据后才可激活。升级时旧active配置转为approved待质量复核，已有路径历史保留。

## 配置联网与教师导入

默认使用Tavily，在服务进程设置TAVILY_API_KEY。也可设置ZHIXING_SEARCH_PROVIDER=dashscope，使用DASHSCOPE_API_KEY与ZHIXING_SEARCH_MODEL。当前百炼原生搜索适配器使用北京端点。

管理员页面显示服务配置状态，并可执行一次真实搜索能力试验。用户先检索本地正文，再主动补充外部网址。结构化覆盖接口在upload_only模式不发外部请求；结构问题不通过搜索掩盖，外部补充最多两轮。供应商必须返回来源URL元数据，模型自称已搜索不能算联网成功。

教师先登记网址，再确认抓取权并导入。抓取只访问公共网络，限制重定向、内容类型与2MiB正文。导入结果为草稿，发布后才供学生检索与路径引用。未知发布日期保持null；有HTML声明日期时记录原值，时效接口仍区分当前、过期和未知。

标题匹配和本地向量召回提供候选证据，教学语义充分性须由后续审查或人工确认。

## 新主题图谱与题库

管理员可以根据已授权的共享课程资料生成待审图谱，也可在知识图谱页面登记完整JSON。新主题每个节点必须具备不同的初测、重测和练习题，题目包含正确选项及解析。管理员核对后才可启用。新目标页面自动读取已启用知识点，路径保存独立练习题版本，旧路径不因题库更换而改写。

## Docker代码自动判题

在部署电脑安装并启动Docker，然后由部署者准备镜像。

```powershell
docker pull python:3.12-slim
```

服务进程可用ZHIXING_CODE_IMAGE指定已准备的受控Python镜像。运行时使用--pull=never，不自动下载镜像。教师创建Python代码任务并设置最多10个标准输入输出用例，发布后用例冻结。学生在任务入口提交程序，测试结果保存为一次正式评分；运行环境故障允许重试，重复成功提交返回同一记录。

容器禁网、只读根、无宿主目录挂载、无特权、非root、128MiB内存、0.5CPU、最多32进程、每用例5秒墙钟时限及64KiB输出上限。只有Docker执行器运行学生程序。当前本机未安装Docker，已验证适配器参数和业务边界，真实执行仍待部署后验收。

## 60场景评价与个人记录

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe -m app.cli evaluate-cloud docs/evidence/implementation/quality-run.json --config-id 实际模型配置ID --operator 实际执行人
```

命令要求有效服务端密钥和新的输出文件，保存60个合成场景的真实供应商响应、错误及自动判据。场景覆盖函数、递归、调用栈的预算、资料缺失、学习水平与偏好变化，不代表任意主题泛化。自动判据覆盖结构与预算，教学正确性需要人工复核。

独立电脑部署试用、真实参与人贡献及语义评分需由实际参与者填写，尚未登记为通过。

## 升级与故障检查

后续升级8000服务前，先停止相关写入、生成一致性备份，再执行启动脚本中的迁移。迁移0010至0017新增识别、向量、搜索运行、模型参数、审计、路径题库、代码判题与模型质量报告表。本轮只在隔离测试库执行。

健康接口报告数据库、文件目录、模型、OCR、ASR、向量和搜索的配置状态。管理员审计可按结果筛选。资料详情可重建当前全文及向量索引，备份恢复仍可使用既有离线命令。

官方接口参考见[RapidOCR](https://github.com/RapidAI/RapidOCR)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[百炼联网搜索](https://help.aliyun.com/en/model-studio/web-search)和[Tavily搜索](https://docs.tavily.com/documentation/api-reference/endpoint/search)。


## 2026年11月8日OpenAI GPT接入

模型配置支持OpenAI官方Base URL https://api.openai.com/v1，默认密钥环境变量为OPENAI_API_KEY。管理员页面可选择OpenAI GPT，再填写账号实际可用且支持Chat Completions与JSON输出的模型ID。

GPT请求使用max_completion_tokens和模型默认采样参数。模型配置、授权正文、四Agent编排、60场景质量报告与逐例人工复核沿用现有流程。千问配置继续使用原参数。

本次完成接口配置与响应契约验证，尚未配置真实OpenAI密钥或发起供应商调用。运行服务需重启后加载新接口代码。

接口依据见[OpenAI官方Chat Completions文档](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。


## 2026年11月8日DeepSeek配置支持

管理员的云端模型配置新增DeepSeek选项，默认Base URL为https://api.deepseek.com，模型预设为deepseek-flash，密钥环境变量为DEEPSEEK_API_KEY。模型名称仍可按账号实际权限修改。

本轮默认采用非思考模式、JSON对象输出、max_tokens长度上限及可配置温度。空白或非法JSON沿用最多两次格式修复；四Agent、资料授权、60场景质量评价及人工复核门槛沿用现有流程。

模型接入不自动切换联网搜索服务。当前代码支持千问、OpenAI GPT与DeepSeek三种配置。运行服务重启后加载新增选项，尚未设置真实DeepSeek密钥或执行供应商调用。

接口依据见[DeepSeek官方接入说明](https://api-docs.deepseek.com/)与[JSON输出说明](https://api-docs.deepseek.com/guides/json_mode/)。
