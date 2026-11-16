# 验证记录与本地产物

仓库保留验收说明、功能清单、导入/迁移记录与 `release-summary.json` 发布摘要。

截图、JUnit XML、浏览器运行结果以及 `form-layout`、`remaining-browser` 目录为本地生成产物，由 `.gitignore` 排除；运行验证脚本可重新生成。文档中指向这些产物的路径用于本机查看，不保证 GitHub 中存在。

`backend/tests` 的自动化测试源码及 `scripts` 中可复用的验证工具继续版本管理。`docs/diagrams` 是正式流程图，不属于被排除的验收截图。

取消跟踪只影响后续提交，不删除本地文件，也不会清除 Git 历史中已经上传的旧产物。
