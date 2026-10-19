#include "cuttle_command.h"

BOOL WINAPI DllMain(HINSTANCE hInstance, DWORD dwReason, LPVOID) {
    if (dwReason == DLL_PROCESS_ATTACH) {
        g_hInstance = hInstance;
        DisableThreadLibraryCalls(hInstance);
    }
    return TRUE;
}

STDAPI DllCanUnloadNow() {
    return (g_cRefModule == 0) ? S_OK : S_FALSE;
}

STDAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;

    if (IsEqualCLSID(rclsid, CLSID_CuttleExplorerCommand)) {
        CuttleClassFactory* factory = new (std::nothrow) CuttleClassFactory();
        if (!factory) return E_OUTOFMEMORY;
        return factory->QueryInterface(riid, ppv);
    }

    return CLASS_E_CLASSNOTAVAILABLE;
}

STDAPI DllRegisterServer() {
    // Sparse packages register via AppxManifest.xml, but DllRegisterServer
    // provides traditional InProcServer32 registry registration for fallback.
    wchar_t mod_path[MAX_PATH * 2] = {0};
    GetModuleFileNameW(g_hInstance, mod_path, MAX_PATH * 2);

    // Format CLSID string: {F4312356-5D3C-486B-8C92-72188A47559B}
    const wchar_t* clsid_key = L"Software\\Classes\\CLSID\\{F4312356-5D3C-486B-8C92-72188A47559B}";
    HKEY hKey = NULL;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, clsid_key, 0, NULL, REG_OPTION_NON_VOLATILE, KEY_ALL_ACCESS, NULL, &hKey, NULL) == ERROR_SUCCESS) {
        RegSetValueExW(hKey, NULL, 0, REG_SZ, (const BYTE*)L"Cuttle Context Menu Extension", (DWORD)(sizeof(wchar_t) * 30));
        
        HKEY hInProc = NULL;
        if (RegCreateKeyExW(hKey, L"InProcServer32", 0, NULL, REG_OPTION_NON_VOLATILE, KEY_ALL_ACCESS, NULL, &hInProc, NULL) == ERROR_SUCCESS) {
            RegSetValueExW(hInProc, NULL, 0, REG_SZ, (const BYTE*)mod_path, (DWORD)((wcslen(mod_path) + 1) * sizeof(wchar_t)));
            const wchar_t* threading = L"Apartment";
            RegSetValueExW(hInProc, L"ThreadingModel", 0, REG_SZ, (const BYTE*)threading, (DWORD)((wcslen(threading) + 1) * sizeof(wchar_t)));
            RegCloseKey(hInProc);
        }
        RegCloseKey(hKey);
    }
    return S_OK;
}

STDAPI DllUnregisterServer() {
    const wchar_t* clsid_key = L"Software\\Classes\\CLSID\\{F4312356-5D3C-486B-8C92-72188A47559B}";
    RegDeleteTreeW(HKEY_CURRENT_USER, clsid_key);
    return S_OK;
}
