@echo off
chcp 65001 >nul
echo 🐾 毛孩子翻译官 - 启动中...
echo.

:: 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ 未检测到虚拟环境，尝试使用系统 Python
)

:: 安装依赖
pip install -r server\requirements.txt -q 2>nul

:: 启动服务
echo.
echo 🚀 启动 API 服务 (http://localhost:8000)
echo 📊 前端面板: 直接打开 frontend\index.html
echo.
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
