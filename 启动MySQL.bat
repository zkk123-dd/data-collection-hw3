@echo off
chcp 65001 >nul
echo ================================================
echo  启动 MySQL 8.0.28（第三次作业专用实例）
echo  端口 3306    账号 root / 123456    库 spider_db
echo  数据目录 E:\mysql8\mysql-8.0.28-winx64\data
echo ================================================
echo.
echo 提示：这个窗口不能关，关掉 MySQL 就停了。
echo       要停止服务，直接关窗口或按 Ctrl+C。
echo.
E:\mysql8\mysql-8.0.28-winx64\bin\mysqld.exe --defaults-file=E:\mysql8\my.ini --console
pause
