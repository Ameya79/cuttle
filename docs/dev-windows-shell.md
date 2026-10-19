# Developer Guide: Windows 11 Shell Extension & Sparse Package

This guide explains how Cuttle integrates with the modern Windows 11 top-level context menu via `IExplorerCommand` and a Sparse MSIX Package.

---

## 1. Architecture Overview

On Windows 11, traditional registry shell verbs (`HKCU\Software\Classes\*\shell`) are placed inside the secondary **"Show more options"** menu (Shift+F10).

To appear directly on the modern top-level menu, an application must:
1. Implement the COM **`IExplorerCommand`** interface in an in-process DLL (`cuttle_shell.dll`).
2. Have **Package Identity**, provided via a **Sparse Package** (`AppxManifest.xml`). A sparse package allows standard un-packaged applications to declare modern WinRT/UAP extensions without being bundled as a full MSIX sandbox.
3. Delegate all conversion execution to the fast background worker via IPC named pipes without doing heavy computation inside Explorer.

---

## 2. Prerequisites for Development

1. **Operating System**: Windows 11 (Build 22000 or higher).
2. **Developer Mode**: Enabled in Windows:
   - Go to **Settings** $\rightarrow$ **System** $\rightarrow$ **For developers**
   - Toggle **Developer Mode** to **On** (allows registering unsigned manifests via `Add-AppxPackage -Register -AllowUnsigned`).
3. **C++ Compiler**: GCC (MinGW UCRT64) or MSVC (`cl.exe`).

---

## 3. Building the Binaries

Compile the native launcher and the shell COM extension:

```powershell
# Compile cuttlectl.exe (sub-25ms native launcher)
uv run python scripts/build_launcher.py

# Compile cuttle_shell.dll (IExplorerCommand in-process server)
uv run python scripts/build_shell_extension.py
```

---

## 4. Registration & Activation

Run the automated registration script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_sparse_package.ps1
```

This script:
1. Registers `cuttle_shell.dll` in `HKCU\Software\Classes\CLSID\{F4312356-5D3C-486B-8C92-72188A47559B}`.
2. Registers `packaging/AppxManifest.xml` using `Add-AppxPackage -Register -AllowUnsigned`.

---

## 5. Testing & Debugging

### Verifying Package Registration
To verify that Windows 11 has recognized Cuttle's package identity:
```powershell
Get-AppxPackage -Name "Cuttle.Converter"
```

### Inspecting Shell Logs
All shell events, command invocations, and any caught exceptions are logged safely to:
```text
%LOCALAPPDATA%\Cuttle\shell.log
```

### Refreshing File Explorer
When recompiling `cuttle_shell.dll`, File Explorer may hold a lock on the DLL. Restart Explorer to unload it:
```powershell
Stop-Process -Name explorer -Force
```

---

## 6. Unregistration

To cleanly remove the sparse package and unregister the COM server:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/unregister_sparse_package.ps1
```
