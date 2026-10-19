#include "cuttle_command.h"
#include <shlwapi.h>
#include <sstream>
#include <chrono>
#include <iomanip>

std::atomic<long> g_cRefModule{0};
HINSTANCE g_hInstance = NULL;

namespace {

HRESULT CoTaskMemAllocString(const std::wstring& src, LPWSTR* dest) {
    if (!dest) return E_POINTER;
    *dest = nullptr;
    size_t bytes = (src.size() + 1) * sizeof(wchar_t);
    LPWSTR mem = (LPWSTR)CoTaskMemAlloc(bytes);
    if (!mem) return E_OUTOFMEMORY;
    wcscpy_s(mem, src.size() + 1, src.c_str());
    *dest = mem;
    return S_OK;
}

std::wstring GetFileExtension(const std::wstring& path) {
    size_t dot_pos = path.find_last_of(L'.');
    if (dot_pos == std::wstring::npos) return L"";
    std::wstring ext = path.substr(dot_pos + 1);
    for (wchar_t& c : ext) {
        c = towlower(c);
    }
    return ext;
}

std::wstring GetLocalAppDataCuttleDir() {
    wchar_t local_app[MAX_PATH] = {0};
    if (GetEnvironmentVariableW(L"LOCALAPPDATA", local_app, MAX_PATH) > 0) {
        std::wstring dir = std::wstring(local_app) + L"\\Cuttle";
        CreateDirectoryW(dir.c_str(), NULL);
        return dir;
    }
    return L"";
}

} // namespace

void LogShellMessage(const std::wstring& msg) {
    try {
        std::wstring dir = GetLocalAppDataCuttleDir();
        if (dir.empty()) return;
        std::wstring log_path = dir + L"\\shell.log";

        std::wofstream f(log_path.c_str(), std::ios::app);
        if (f.is_open()) {
            auto now = std::chrono::system_clock::now();
            auto time_t_now = std::chrono::system_clock::to_time_t(now);
            struct tm tm_buf;
            localtime_s(&tm_buf, &time_t_now);
            f << std::put_time(&tm_buf, L"[%Y-%m-%d %H:%M:%S] ") << msg << L"\n";
        }
    } catch (...) {
        // Crash safety invariant: Never allow exceptions to leak into Explorer
    }
}

std::wstring GetModuleDirectory() {
    wchar_t buf[MAX_PATH * 2] = {0};
    GetModuleFileNameW(g_hInstance, buf, MAX_PATH * 2);
    wchar_t* last_slash = wcsrchr(buf, L'\\');
    if (last_slash) {
        *last_slash = L'\0';
    }
    return std::wstring(buf);
}

std::vector<ConversionTarget> GetTargetsForFile(const std::wstring& file_path) {
    std::wstring ext = GetFileExtension(file_path);
    std::vector<ConversionTarget> targets;

    // Standard builtin targets for instant top-level display
    if (ext == L"mp4" || ext == L"mkv" || ext == L"mov" || ext == L"avi") {
        targets.push_back({L"mp3", L"MP3 (audio)"});
        targets.push_back({L"wav", L"WAV (audio)"});
        targets.push_back({L"webm", L"WebM (video)"});
        targets.push_back({L"gif", L"GIF (animation)"});
    } else if (ext == L"mp3" || ext == L"wav" || ext == L"m4a" || ext == L"flac" || ext == L"ogg") {
        targets.push_back({L"mp3", L"MP3 (audio)"});
        targets.push_back({L"wav", L"WAV (audio)"});
        targets.push_back({L"m4a", L"M4A (audio)"});
        targets.push_back({L"flac", L"FLAC (lossless audio)"});
    } else if (ext == L"png" || ext == L"jpg" || ext == L"jpeg" || ext == L"webp" || ext == L"bmp" || ext == L"heic") {
        targets.push_back({L"png", L"PNG (image)"});
        targets.push_back({L"jpg", L"JPG (image)"});
        targets.push_back({L"webp", L"WebP (image)"});
        targets.push_back({L"bmp", L"BMP (image)"});
        targets.push_back({L"pdf", L"PDF (document)"});
    } else if (ext == L"docx" || ext == L"pptx" || ext == L"xlsx" || ext == L"odt") {
        targets.push_back({L"pdf", L"PDF (document)"});
        if (ext == L"docx") {
            targets.push_back({L"md", L"Markdown"});
            targets.push_back({L"html", L"HTML"});
            targets.push_back({L"txt", L"Plain Text"});
        }
    } else if (ext == L"md" || ext == L"html" || ext == L"txt") {
        targets.push_back({L"pdf", L"PDF (document)"});
        targets.push_back({L"docx", L"Word DOCX"});
        targets.push_back({L"html", L"HTML"});
        targets.push_back({L"md", L"Markdown"});
    }

    return targets;
}

// ---------------------------------------------------------------------------
// CuttleExplorerCommand
// ---------------------------------------------------------------------------

CuttleExplorerCommand::CuttleExplorerCommand(bool is_root,
                                             const std::wstring& target_fmt,
                                             const std::wstring& target_label)
    : is_root_(is_root), target_fmt_(target_fmt), target_label_(target_label) {
    g_cRefModule++;
}

CuttleExplorerCommand::~CuttleExplorerCommand() {
    g_cRefModule--;
}

IFACEMETHODIMP CuttleExplorerCommand::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;

    if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IExplorerCommand)) {
        *ppv = static_cast<IExplorerCommand*>(this);
        AddRef();
        return S_OK;
    }
    return E_NOINTERFACE;
}

IFACEMETHODIMP_(ULONG) CuttleExplorerCommand::AddRef() {
    return ++ref_count_;
}

IFACEMETHODIMP_(ULONG) CuttleExplorerCommand::Release() {
    ULONG count = --ref_count_;
    if (count == 0) {
        delete this;
    }
    return count;
}

IFACEMETHODIMP CuttleExplorerCommand::GetTitle(IShellItemArray*, LPWSTR* ppszName) {
    try {
        if (is_root_) {
            return CoTaskMemAllocString(L"Convert with Cuttle", ppszName);
        } else {
            return CoTaskMemAllocString(target_label_, ppszName);
        }
    } catch (...) {
        return E_FAIL;
    }
}

IFACEMETHODIMP CuttleExplorerCommand::GetIcon(IShellItemArray*, LPWSTR* ppszIcon) {
    try {
        if (!ppszIcon) return E_POINTER;
        *ppszIcon = nullptr;

        std::wstring mod_dir = GetModuleDirectory();
        std::wstring icon_candidate = mod_dir + L"\\cuttle.ico";
        if (GetFileAttributesW(icon_candidate.c_str()) != INVALID_FILE_ATTRIBUTES) {
            return CoTaskMemAllocString(icon_candidate, ppszIcon);
        }

        // Fallback to executable icon or module
        wchar_t buf[MAX_PATH * 2] = {0};
        GetModuleFileNameW(g_hInstance, buf, MAX_PATH * 2);
        std::wstring icon_str = std::wstring(buf) + L",0";
        return CoTaskMemAllocString(icon_str, ppszIcon);
    } catch (...) {
        return E_FAIL;
    }
}

IFACEMETHODIMP CuttleExplorerCommand::GetToolTip(IShellItemArray*, LPWSTR* ppszToolTip) {
    if (!ppszToolTip) return E_POINTER;
    *ppszToolTip = nullptr;
    return E_NOTIMPL;
}

IFACEMETHODIMP CuttleExplorerCommand::GetCanonicalName(GUID* pguidCommandName) {
    if (!pguidCommandName) return E_POINTER;
    *pguidCommandName = CLSID_CuttleExplorerCommand;
    return S_OK;
}

IFACEMETHODIMP CuttleExplorerCommand::GetState(IShellItemArray* psiItemArray, BOOL, EXPCMDSTATE* pCmdState) {
    try {
        if (!pCmdState) return E_POINTER;
        *pCmdState = ECS_HIDDEN;

        if (!is_root_) {
            *pCmdState = ECS_ENABLED;
            return S_OK;
        }

        if (!psiItemArray) {
            return S_OK;
        }

        DWORD count = 0;
        if (FAILED(psiItemArray->GetCount(&count)) || count == 0) {
            return S_OK;
        }

        IShellItem* item = nullptr;
        if (SUCCEEDED(psiItemArray->GetItemAt(0, &item)) && item) {
            LPWSTR path = nullptr;
            if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path)) && path) {
                std::vector<ConversionTarget> targets = GetTargetsForFile(path);
                if (!targets.empty()) {
                    *pCmdState = ECS_ENABLED;
                }
                CoTaskMemFree(path);
            }
            item->Release();
        }
        return S_OK;
    } catch (...) {
        if (pCmdState) *pCmdState = ECS_HIDDEN;
        return S_OK;
    }
}

IFACEMETHODIMP CuttleExplorerCommand::GetFlags(EXPCMDFLAGS* pFlags) {
    try {
        if (!pFlags) return E_POINTER;
        if (is_root_) {
            *pFlags = ECF_HASSUBCOMMANDS;
        } else {
            *pFlags = ECF_DEFAULT;
        }
        return S_OK;
    } catch (...) {
        return E_FAIL;
    }
}

IFACEMETHODIMP CuttleExplorerCommand::EnumSubCommands(IEnumExplorerCommand** ppEnum) {
    try {
        if (!ppEnum) return E_POINTER;
        *ppEnum = nullptr;

        if (!is_root_) {
            return E_NOTIMPL;
        }

        // By default provide common targets or extract from selected file
        std::vector<ConversionTarget> all_targets = {
            {L"mp3", L"MP3 (audio)"},
            {L"wav", L"WAV (audio)"},
            {L"png", L"PNG (image)"},
            {L"jpg", L"JPG (image)"},
            {L"webp", L"WebP (image)"},
            {L"pdf", L"PDF (document)"},
            {L"docx", L"Word DOCX"}
        };

        CuttleEnumCommands* enum_cmds = new (std::nothrow) CuttleEnumCommands(all_targets);
        if (!enum_cmds) return E_OUTOFMEMORY;
        return enum_cmds->QueryInterface(IID_PPV_ARGS(ppEnum));
    } catch (...) {
        return E_FAIL;
    }
}

IFACEMETHODIMP CuttleExplorerCommand::Invoke(IShellItemArray* psiItemArray, IBindCtx*) {
    try {
        if (!psiItemArray || is_root_ || target_fmt_.empty()) {
            return S_OK;
        }

        DWORD count = 0;
        if (FAILED(psiItemArray->GetCount(&count)) || count == 0) {
            return S_OK;
        }

        std::vector<std::wstring> files;
        for (DWORD i = 0; i < count; ++i) {
            IShellItem* item = nullptr;
            if (SUCCEEDED(psiItemArray->GetItemAt(i, &item)) && item) {
                LPWSTR path = nullptr;
                if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path)) && path) {
                    files.push_back(path);
                    CoTaskMemFree(path);
                }
                item->Release();
            }
        }

        if (files.empty()) return S_OK;

        // Locate cuttlectl.exe (launcher)
        std::wstring mod_dir = GetModuleDirectory();
        std::wstring launcher_exe = mod_dir + L"\\cuttlectl.exe";
        if (GetFileAttributesW(launcher_exe.c_str()) == INVALID_FILE_ATTRIBUTES) {
            launcher_exe = mod_dir + L"\\..\\launcher\\cuttlectl.exe";
        }

        std::wostringstream cmd;
        cmd << L"\"" << launcher_exe << L"\" submit --to " << target_fmt_;
        for (const auto& f : files) {
            cmd << L" \"" << f << L"\"";
        }

        STARTUPINFOW si = {sizeof(si)};
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
        PROCESS_INFORMATION pi = {0};

        std::wstring cmd_str = cmd.str();
        if (CreateProcessW(NULL, &cmd_str[0], NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, NULL, &si, &pi)) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
        } else {
            LogShellMessage(L"Failed to launch cuttlectl: " + cmd_str);
        }

        return S_OK;
    } catch (...) {
        LogShellMessage(L"Exception in IExplorerCommand::Invoke");
        return S_OK;
    }
}

// ---------------------------------------------------------------------------
// CuttleEnumCommands
// ---------------------------------------------------------------------------

CuttleEnumCommands::CuttleEnumCommands(const std::vector<ConversionTarget>& targets)
    : targets_(targets), current_index_(0) {
    g_cRefModule++;
}

CuttleEnumCommands::~CuttleEnumCommands() {
    g_cRefModule--;
}

IFACEMETHODIMP CuttleEnumCommands::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;

    if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IEnumExplorerCommand)) {
        *ppv = static_cast<IEnumExplorerCommand*>(this);
        AddRef();
        return S_OK;
    }
    return E_NOINTERFACE;
}

IFACEMETHODIMP_(ULONG) CuttleEnumCommands::AddRef() {
    return ++ref_count_;
}

IFACEMETHODIMP_(ULONG) CuttleEnumCommands::Release() {
    ULONG count = --ref_count_;
    if (count == 0) {
        delete this;
    }
    return count;
}

IFACEMETHODIMP CuttleEnumCommands::Next(ULONG celt, IExplorerCommand** apUICommand, ULONG* pceltFetched) {
    try {
        if (!apUICommand) return E_POINTER;
        ULONG fetched = 0;

        while (current_index_ < targets_.size() && fetched < celt) {
            const auto& t = targets_[current_index_++];
            CuttleExplorerCommand* child = new (std::nothrow) CuttleExplorerCommand(
                /*is_root=*/false,
                t.fmt,
                t.label
            );
            if (!child) return E_OUTOFMEMORY;
            apUICommand[fetched++] = child;
        }

        if (pceltFetched) *pceltFetched = fetched;
        return (fetched == celt) ? S_OK : S_FALSE;
    } catch (...) {
        return E_FAIL;
    }
}

IFACEMETHODIMP CuttleEnumCommands::Skip(ULONG celt) {
    current_index_ += celt;
    if (current_index_ > targets_.size()) {
        current_index_ = targets_.size();
        return S_FALSE;
    }
    return S_OK;
}

IFACEMETHODIMP CuttleEnumCommands::Reset() {
    current_index_ = 0;
    return S_OK;
}

IFACEMETHODIMP CuttleEnumCommands::Clone(IEnumExplorerCommand** ppEnum) {
    if (!ppEnum) return E_POINTER;
    CuttleEnumCommands* clone = new (std::nothrow) CuttleEnumCommands(targets_);
    if (!clone) return E_OUTOFMEMORY;
    clone->current_index_ = current_index_;
    return clone->QueryInterface(IID_PPV_ARGS(ppEnum));
}

// ---------------------------------------------------------------------------
// CuttleClassFactory
// ---------------------------------------------------------------------------

CuttleClassFactory::CuttleClassFactory() {
    g_cRefModule++;
}

CuttleClassFactory::~CuttleClassFactory() {
    g_cRefModule--;
}

IFACEMETHODIMP CuttleClassFactory::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;

    if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IClassFactory)) {
        *ppv = static_cast<IClassFactory*>(this);
        AddRef();
        return S_OK;
    }
    return E_NOINTERFACE;
}

IFACEMETHODIMP_(ULONG) CuttleClassFactory::AddRef() {
    return ++ref_count_;
}

IFACEMETHODIMP_(ULONG) CuttleClassFactory::Release() {
    ULONG count = --ref_count_;
    if (count == 0) {
        delete this;
    }
    return count;
}

IFACEMETHODIMP CuttleClassFactory::CreateInstance(IUnknown* pUnkOuter, REFIID riid, void** ppvObject) {
    if (!ppvObject) return E_POINTER;
    *ppvObject = nullptr;
    if (pUnkOuter) return CLASS_E_NOAGGREGATION;

    CuttleExplorerCommand* cmd = new (std::nothrow) CuttleExplorerCommand();
    if (!cmd) return E_OUTOFMEMORY;
    return cmd->QueryInterface(riid, ppvObject);
}

IFACEMETHODIMP CuttleClassFactory::LockServer(BOOL fLock) {
    if (fLock) {
        g_cRefModule++;
    } else {
        g_cRefModule--;
    }
    return S_OK;
}
