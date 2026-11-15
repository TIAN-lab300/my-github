@echo off
set ZHIXING_SEARCH_PROVIDER=dashscope
set ZHIXING_SEARCH_MODEL=qwen-plus
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-cloud.ps1"
pause
