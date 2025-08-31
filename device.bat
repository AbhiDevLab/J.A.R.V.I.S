@echo off
echo Disconnecting old connections...
adb disconnect
echo Setting up connected device
adb tcpip 5555
echo Waiting for device to initialize
timeout 3 >nul

REM Clear any previous IP values
set ip=

REM Get IPv4 address using ip command
FOR /F "tokens=2" %%G IN ('adb shell ip -4 addr show wlan0 2^>NUL ^| findstr "inet "') DO set ipfull=%%G
FOR /F "tokens=1 delims=/" %%G IN ("%ipfull%") DO set ip=%%G

REM If Method 1 failed, try using ifconfig
if "%ip%"=="" (
    FOR /F "tokens=2" %%G IN ('adb shell ifconfig wlan0 2^>NUL ^| findstr "inet "') DO set ipfull=%%G
    FOR /F "tokens=2 delims=:" %%G IN ("%ipfull%") DO set ip=%%G
)

REM If both methods failed, try to get IP from connected network info
if "%ip%"=="" (
    FOR /F "tokens=3" %%G IN ('adb shell netstat -rn 2^>NUL ^| findstr "0.0.0.0"') DO set ip=%%G
)

echo Device IP address: %ip%
echo Connecting to the device with IP %ip%...
adb connect %ip%:5555

REM Verify connection
adb devices