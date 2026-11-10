# 知行 · 智能学习规划助手

基于 `docs/superpowers/specs/zhixing-prototype_1.1.html` 的可运行前后端，原型文件保留不改。React/TypeScript/Vite、FastAPI、SQLAlchemy/SQLite、Alembic 与 LangGraph。

## 已接入功能

真实账号登录、首次改密、本人改密、会话过期、失败冷却、账号停用/恢复/重置及审计；班级、邀请码、入退班、成员移除与归档；资料上传/发布/下架、文本PDF、音视频附件与字幕、网址登记、私有资料、授权下载、阅读记录和FTS5检索；教师任务、分配、撤回、学生作答、即时反馈、主观复核及评分更正；目标、诊断、BKT、预算、路径接受、打卡测验、重规划预览与画像历史。

本地规划支持原有主题及已审核的新主题图谱与独立题库。已接入离线OCR、语音转写、FastEmbed本地中文向量、Tavily/百炼原生搜索适配器、教师授权网页导入和云端四Agent分支。云端需服务端密钥，代码自动判题需Docker。真实供应商调用、60场景语义评价与独立电脑试用仍待环境就绪。完整状态见 [实现记录](docs/evidence/implementation/implementation-status.md)。

## Windows安装与启动

推荐Python 3.11+；项目提供本地Node 22开发依赖，不修改系统Node。生产构建完成后只需Python。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements-lock.txt
$env:PYTHONPATH = 'backend'
.venv/Scripts/python -m app.cli demo
Set-Location frontend
npm ci --registry=https://registry.npmjs.org
npm run build
Set-Location ..
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

打开 [本机平台](http://127.0.0.1:8000)，接口文档为 [OpenAPI](http://127.0.0.1:8000/docs)，停止服务按Ctrl+C。默认只允许本机访问。开发前端可在frontend运行 `npm run dev`，5173端口代理API到8000。

初始化只显示一次随机临时密码，账号为admin、teacher、teacher2、student、student2，首次登录必须改密。demo可重复执行，不覆盖已有密码。只需要管理员时使用 `app.cli init`。

本工作区的初始账号已保存到未提交的 `backend/data/initial-accounts.txt`；浏览器验证已更改student/teacher/admin密码并同步回该文件。此文件含凭据，勿公开或提交。

若Anaconda的venv未能安装pip，可用系统pip：`python -m pip --python .venv/Scripts/python.exe install -r backend/requirements-lock.txt`。

## 操作流程

1. 教师登录，建班并生成邀请码；学生用另一浏览器会话登录入班。样例学生已入样例班。
2. 教师上传并发布资料，在任务管理保存草稿后发布任务。
3. 学生阅读并记录实际时长，提交任务后查看真实评分反馈；教师查询班级进度。
4. 学生创建Python函数与递归目标，设置未来截止时间，完成六题诊断，生成并接受路径。
5. 路径任务支持学习打卡与知识测验；打卡不直接提升掌握度，后续节点检查先修。
6. 生成重规划预览后可接受或拒绝；预算/目标/证据变化使旧预览失效，返回409后重新生成。

## 模型配置

在启动服务的PowerShell配置 `$env:DASHSCOPE_API_KEY = '<你的密钥>'`，管理员登记对应地域的兼容Base URL和模型后，先运行真实能力试验再激活。密钥不通过页面保存或回显；无密钥返回明确503，本地教学链仍可用。

连接方式参考 [阿里云官方兼容接口说明](https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope)。端点和模型权限以账号实际配置为准。JSON连通不代表搜索或完整AI质量评估通过。

## 验证与备份

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/python -m app.cli backup <不存在的备份目录>
.venv/Scripts/python -m app.cli restore <备份目录> --destination <不存在的恢复目录>
.venv/Scripts/python -m app.cli reindex <独立离线恢复目录>
```

测试使用backend/data/tests独立数据库。备份采用SQLite一致性备份，清单包括数据库与附件SHA-256、迁移版本、记录数量及模型配置引用。恢复先核对哈希、外键与记录数量，再写入新目录。reindex可在独立离线恢复目录重建全文索引，并更新数据库校验值。停服后通过ZHIXING_DATA环境变量选择恢复目录；密钥环境独立交接。测试报告与截图在docs/evidence/implementation。

`frontend/browser-smoke.mjs`适用于初始临时账号，验证首次改密并更新本机凭据文件；`browser-flow.mjs`在已改密账号上验证完整页面流程，会创建演示任务与目标。它们使用本机Edge，不是生产数据操作脚本。

源码入口：frontend/src为三端页面；backend/app/api为业务接口；services为BKT/排期/规划；core为持久化与权限；migrations为数据库版本；cli.py为初始化和备份恢复。

127项子功能仍是最终需求范围，本版本未逐项宣称完成；实际能力与限制以实现状态表和真实验证记录为准。


## 项目主文档

四份主文档统一在 `docx` 文件夹维护，保留 Markdown 格式。编码前分析已合并第三、第四周基础设计。

- [需求规格说明书](docx/2026-10-27-smart-learning-planner-requirements-spec.md)
- [项目设计方案](docx/2026-10-27-smart-learning-planner-design.md)
- [技术设计说明书](docx/2026-10-27-smart-learning-planner-technical-design.md)
- [编码前分析与技术设计](docx/2026-11-02-zhixing-followup-preimplementation-technical-design.md)


## 新增能力配置与验收

完整配置步骤见[运行与验收说明](docs/evidence/implementation/remaining-functions-setup.md)，当前逐模块范围见[功能清单](docs/evidence/implementation/current-function-inventory.md)。依赖锁已包含本地处理依赖，模型需通过prepare-models命令单独准备。
