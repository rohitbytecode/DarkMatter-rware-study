import sys
import os
import winreg
import ctypes

def is_admin():
    """Check if the script is running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def register_for_autostart():
    """Add the .exe to system-wide startup (HKLM)"""
    if not is_admin():
        print("Please run this program as Administrator (right-click → Run as administrator) once to enable system-wide auto-start.")
        return

    app_name = "MyPythonApp"
    exe_path = sys.executable

    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)

        try:
            value, _ = winreg.QueryValueEx(key, app_name)
            if os.path.normcase(value.strip('"')) == os.path.normcase(exe_path):
                winreg.CloseKey(key)
                return  
        except FileNotFoundError:
            pass

        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        print(f"Successfully added '{app_name}' to system-wide startup.")

    except Exception as e:
        print(f"Failed to add to registry: {e}")
        print("Make sure you are running as Administrator.")


register_for_autostart()


# main code...
