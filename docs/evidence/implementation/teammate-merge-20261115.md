# 队友更新合并记录（2026-11-15）

已将“知行_2026-11-15/知行_队友代码更新包_2026-11-15”按共同基线0d541a2与当前项目比较合并。104个文件实质相同，46个包含新增或变化，3个双方修改文件手工合并：frontend/src/main.tsx、backend/app/main.py、backend/app/cli.py。

## 合并内容

- 云端四智能体输出契约、授权资料片段及引用校验、供应商错误分类。
- 学生云端状态与可用性控制，教师题库管理和管理员题库审核。
- 路径测验会话、作答恢复与曝光记录，质量评价可复用输入未变的已通过场景。
- 联网搜索及来源验证脚本、统一启动器与版本标识。

既有中文资料、36门课程、377个候选知识点、待审核题答及课程学习—单选测验—评价流程保留。队友题库面向现有图谱与路径；课程级题库仍独立，本次不自动重复导入题目或合并学习证据。

## 数据及运行适配

队友0019、0020重编号为0022、0023，接在本机0021后。启动默认继续使用backend/data，尊重ZHIXING_DATA，取消强制切换runtime-data的行为。评价脚本要求传入本机配置编号，不再使用队友个人配置ID。

队友的旧电脑一次性源码覆盖及自动发布样例脚本未纳入当前脚本目录，原件保留在交付包。密钥、业务数据库、账号、上传附件、质量报告均未从交付包导入。

数据库备份：backend/data/backups/before-teammate-merge-20261115。代码备份：backend/data/merge-backups/teammate-20261115。迁移前后关键业务表逐行对比一致。

## 使用

普通启动：`powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`。

云端启动：`powershell -ExecutionPolicy Bypass -File .\scripts\start-cloud.ps1 -Provider DeepSeek`；Provider也支持DashScope和OpenAI。密钥在本机安全输入，仅供新服务进程使用；网页中仍需登记自己的配置、能力验证、质量评价和人工批准后激活。

质量评价：`powershell -ExecutionPolicy Bypass -File .\scripts\evaluate-cloud.ps1 -ConfigId 当前配置编号 -Provider DeepSeek`。此命令会调用付费服务，本次未执行。

## 验证

229项后端回归全部通过，前端构建通过；统一启动器在隔离库验证单一迁移头0023和版本一致。三身份页面、新题库及云端状态、原有课程学习与测验评价流程浏览器检查通过，无脚本错误。本轮真实模型和搜索调用均为0，不把队友成功调用的结果当作本机凭据已验证。

详细记录见[合并清单](teammate-merge-20261115.json)。
