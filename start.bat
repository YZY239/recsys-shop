@echo off
chcp 65001 >nul
title RecSys-Shop Launcher
cd /d "%~dp0"

echo ============================================
echo   暖物集 RecSys-Shop 一键启动
echo ============================================
echo.
echo  [1/3] 启动后端 Flask @ 127.0.0.1:5000 ...
start "recsys-backend" cmd /k "cd /d %~dp0backend && python app.py"

echo  [2/3] 启动前端 Vite @ localhost:5173 ...
start "recsys-frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo  [3/3] 等待服务就绪，自动打开浏览器 ...
timeout /t 8 /nobreak >nul
start http://localhost:5173

echo.
echo  已启动！浏览器未自动打开时，请手动访问 http://localhost:5173
echo  关闭方法：关闭弹出的两个命令行窗口（recsys-backend / recsys-frontend）
echo.
pause
