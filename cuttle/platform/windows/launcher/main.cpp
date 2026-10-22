#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <shellapi.h>
#include <shlwapi.h>
#include <string>
#include <vector>
#include <sstream>
#include <chrono>
#include <thread>

namespace {

constexpr DWORD PIPE_TIMEOUT_MS = 2000;
constexpr DWORD BUF_SIZE = 4096;

std::wstring get_safe_username() {
    wchar_t user_buf[256] = {0};
    DWORD user_len = sizeof(user_buf) / sizeof(user_buf[0]);
    if (!GetUserNameW(user_buf, &user_len) || user_len == 0) {
        DWORD env_len = GetEnvironmentVariableW(L"USERNAME", user_buf, 256);
        if (env_len == 0) {
            wcscpy_s(user_buf, L"default");
        }
    }

    std::wstring safe_user;
    for (size_t i = 0; user_buf[i] != L'\0'; ++i) {
        wchar_t c = user_buf[i];
        if (iswalnum(c) || c == L'-' || c == L'_') {
            safe_user.push_back(c);
        }
    }
    if (safe_user.empty()) {
        safe_user = L"default";
    }
    return safe_user;
}

std::wstring get_pipe_name(const std::wstring& base = L"cuttle") {
    return L"\\\\.\\pipe\\" + base + L"-" + get_safe_username();
}

std::string utf16_to_utf8(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    int size_needed = WideCharToMultiByte(CP_UTF8, 0, wstr.data(), (int)wstr.size(), NULL, 0, NULL, NULL);
    std::string str(size_needed, 0);
    WideCharToMultiByte(CP_UTF8, 0, wstr.data(), (int)wstr.size(), &str[0], size_needed, NULL, NULL);
    return str;
}

std::wstring escape_json(const std::wstring& input) {
    std::wostringstream ss;
    for (wchar_t c : input) {
        if (c == L'\\') {
            ss << L"\\\\";
        } else if (c == L'"') {
            ss << L"\\\"";
        } else if (c == L'\b') {
            ss << L"\\b";
        } else if (c == L'\f') {
            ss << L"\\f";
        } else if (c == L'\n') {
            ss << L"\\n";
        } else if (c == L'\r') {
            ss << L"\\r";
        } else if (c == L'\t') {
            ss << L"\\t";
        } else {
            ss << c;
        }
    }
    return ss.str();
}

std::wstring get_full_path(const std::wstring& rel_path) {
    wchar_t full_buf[MAX_PATH * 2] = {0};
    DWORD len = GetFullPathNameW(rel_path.c_str(), MAX_PATH * 2, full_buf, NULL);
    if (len > 0) {
        return std::wstring(full_buf);
    }
    return rel_path;
}

bool file_exists(const std::wstring& path) {
    DWORD attr = GetFileAttributesW(path.c_str());
    return (attr != INVALID_FILE_ATTRIBUTES);
}

std::wstring get_module_dir() {
    wchar_t buf[MAX_PATH * 2] = {0};
    GetModuleFileNameW(NULL, buf, MAX_PATH * 2);
    wchar_t* last_slash = wcsrchr(buf, L'\\');
    if (last_slash) {
        *last_slash = L'\0';
    }
    return std::wstring(buf);
}

bool try_call_pipe(const std::wstring& pipe_name, const std::string& payload, std::string* out_resp = nullptr, DWORD timeout_ms = 5000) {
    char resp_buf[BUF_SIZE] = {0};
    DWORD bytes_read = 0;
    auto start = std::chrono::steady_clock::now();
    DWORD sleep_ms = 10;

    while (true) {
        BOOL ok = CallNamedPipeW(
            pipe_name.c_str(),
            (LPVOID)payload.data(),
            (DWORD)payload.size(),
            resp_buf,
            sizeof(resp_buf) - 1,
            &bytes_read,
            1000
        );

        if (ok) {
            if (out_resp) {
                *out_resp = std::string(resp_buf, bytes_read);
            }
            return true;
        }

        DWORD err = GetLastError();
        // Handle burst contention (231 = ERROR_PIPE_BUSY, 2 = ERROR_FILE_NOT_FOUND)
        if (err == ERROR_PIPE_BUSY || err == ERROR_FILE_NOT_FOUND) {
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start
            ).count();
            if (elapsed >= (long long)timeout_ms) {
                break;
            }
            if (err == ERROR_PIPE_BUSY) {
                WaitNamedPipeW(pipe_name.c_str(), 500);
            } else {
                Sleep(sleep_ms);
                if (sleep_ms < 100) sleep_ms *= 2;
            }
            continue;
        }
        break;
    }
    return false;
}

bool start_worker_daemon() {
    std::wstring mod_dir = get_module_dir();

    // 1. Look for cuttle-worker.exe next to launcher
    std::wstring worker_exe = mod_dir + L"\\cuttle-worker.exe";
    if (file_exists(worker_exe)) {
        STARTUPINFOW si = {sizeof(si)};
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
        PROCESS_INFORMATION pi = {0};

        std::wstring cmd = L"\"" + worker_exe + L"\"";
        if (CreateProcessW(NULL, &cmd[0], NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, mod_dir.c_str(), &si, &pi)) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            return true;
        }
    }

    // 2. Look for Python virtual environment (e.g., .venv/Scripts/pythonw.exe)
    std::vector<std::wstring> python_candidates = {
        mod_dir + L"\\.venv\\Scripts\\pythonw.exe",
        mod_dir + L"\\..\\.venv\\Scripts\\pythonw.exe",
        mod_dir + L"\\..\\..\\.venv\\Scripts\\pythonw.exe",
        mod_dir + L"\\pythonw.exe"
    };

    for (const auto& py : python_candidates) {
        if (file_exists(py)) {
            STARTUPINFOW si = {sizeof(si)};
            si.dwFlags = STARTF_USESHOWWINDOW;
            si.wShowWindow = SW_HIDE;
            PROCESS_INFORMATION pi = {0};

            // Project root is parent of .venv
            std::wstring prj_root = mod_dir;
            if (py.find(L"\\..\\") != std::wstring::npos) {
                wchar_t abs_root[MAX_PATH * 2] = {0};
                GetFullPathNameW((mod_dir + L"\\..\\..").c_str(), MAX_PATH * 2, abs_root, NULL);
                prj_root = abs_root;
            }

            std::wstring cmd = L"\"" + py + L"\" -m cuttle.worker.main";
            if (CreateProcessW(NULL, &cmd[0], NULL, NULL, FALSE, CREATE_NO_WINDOW | DETACHED_PROCESS, NULL, prj_root.c_str(), &si, &pi)) {
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
                return true;
            }
        }
    }

    return false;
}

bool ensure_pipe_ready(const std::wstring& pipe_name, DWORD timeout_ms = PIPE_TIMEOUT_MS) {
    if (try_call_pipe(pipe_name, "{\"op\":\"ping\"}", nullptr, 150)) {
        return true;
    }

    start_worker_daemon();

    auto start = std::chrono::steady_clock::now();
    while (true) {
        if (try_call_pipe(pipe_name, "{\"op\":\"ping\"}", nullptr, 150)) {
            return true;
        }
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - start
        ).count();
        if (elapsed > (long long)timeout_ms) {
            break;
        }
        Sleep(25);
    }
    return false;
}

} // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc <= 1) {
        if (argv) LocalFree(argv);
        return 0;
    }

    std::wstring pipe_name = get_pipe_name();
    std::wstring subcmd = argv[1];

    if (subcmd == L"ping") {
        bool ok = ensure_pipe_ready(pipe_name, 1000);
        LocalFree(argv);
        return ok ? 0 : 1;
    }

    if (subcmd == L"cancel" && argc >= 3) {
        ensure_pipe_ready(pipe_name, 1000);
        std::wstring batch_id = argv[2];
        std::wstring req = L"{\"op\":\"cancel\",\"batch_id\":\"" + escape_json(batch_id) + L"\"}";
        try_call_pipe(pipe_name, utf16_to_utf8(req));
        LocalFree(argv);
        return 0;
    }

    if (subcmd == L"missing-tool") {
        std::wstring tool = (argc >= 3) ? argv[2] : L"libreoffice";
        // Launch missing tool guidance dialog
        std::wstring mod_dir = get_module_dir();
        std::wstring py = mod_dir + L"\\.venv\\Scripts\\pythonw.exe";
        if (!file_exists(py)) {
            py = mod_dir + L"\\..\\.venv\\Scripts\\pythonw.exe";
        }
        if (file_exists(py)) {
            STARTUPINFOW si = {sizeof(si)};
            si.dwFlags = STARTF_USESHOWWINDOW;
            si.wShowWindow = SW_HIDE;
            PROCESS_INFORMATION pi = {0};
            std::wstring cmd = L"\"" + py + L"\" -m cuttle.worker.cuttlectl missing-tool " + tool;
            CreateProcessW(NULL, &cmd[0], NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
        }
        LocalFree(argv);
        return 0;
    }

    if (subcmd == L"install-shell" || subcmd == L"uninstall-shell") {
        std::wstring mod_dir = get_module_dir();
        std::wstring cuttle_exe = mod_dir + L"\\cuttle.exe";
        STARTUPINFOW si = {sizeof(si)};
        si.dwFlags = STARTF_USESHOWWINDOW;
        si.wShowWindow = SW_HIDE;
        PROCESS_INFORMATION pi = {0};

        std::wstring cmd;
        if (file_exists(cuttle_exe)) {
            cmd = L"\"" + cuttle_exe + L"\" " + subcmd;
        } else {
            std::vector<std::wstring> py_candidates = {
                mod_dir + L"\\pythonw.exe",
                mod_dir + L"\\.venv\\Scripts\\pythonw.exe",
                mod_dir + L"\\..\\.venv\\Scripts\\pythonw.exe",
                mod_dir + L"\\..\\..\\.venv\\Scripts\\pythonw.exe"
            };
            for (const auto& py : py_candidates) {
                if (file_exists(py)) {
                    cmd = L"\"" + py + L"\" -m cuttle.worker.cuttlectl " + subcmd;
                    break;
                }
            }
        }

        if (!cmd.empty()) {
            if (CreateProcessW(NULL, &cmd[0], NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, mod_dir.c_str(), &si, &pi)) {
                WaitForSingleObject(pi.hProcess, 15000);
                DWORD exit_code = 0;
                GetExitCodeProcess(pi.hProcess, &exit_code);
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
                LocalFree(argv);
                return (int)exit_code;
            }
        }
        LocalFree(argv);
        return 1;
    }

    std::wstring target_fmt;
    std::vector<std::wstring> files;
    std::wstring out_dir;

    if (subcmd == L"submit") {
        for (int i = 2; i < argc; ++i) {
            std::wstring arg = argv[i];
            if ((arg == L"--to" || arg == L"-t") && i + 1 < argc) {
                target_fmt = argv[++i];
            } else if ((arg == L"--out" || arg == L"-o") && i + 1 < argc) {
                out_dir = argv[++i];
            } else if (arg == L"--pipe" && i + 1 < argc) {
                pipe_name = argv[++i];
            } else if (!arg.empty() && arg[0] != L'-') {
                files.push_back(arg);
            }
        }
    } else {
        // Shorthand: cuttlectl <file1> [<file2> ...] <fmt>
        if (argc >= 3) {
            target_fmt = argv[argc - 1];
            for (int i = 1; i < argc - 1; ++i) {
                files.push_back(argv[i]);
            }
        }
    }

    if (target_fmt.empty() || files.empty()) {
        LocalFree(argv);
        return 1;
    }

    // Clean target_fmt (remove leading '.')
    if (!target_fmt.empty() && target_fmt[0] == L'.') {
        target_fmt.erase(0, 1);
    }

    // Ensure worker is available
    if (!ensure_pipe_ready(pipe_name)) {
        LocalFree(argv);
        return 2;
    }

    // Submit each file conversion request
    for (const auto& file_path : files) {
        std::wstring abs_path = get_full_path(file_path);
        if (!file_exists(abs_path)) {
            continue;
        }

        std::wostringstream ss;
        ss << L"{\"op\":\"convert\",\"src\":\"" << escape_json(abs_path)
           << L"\",\"dst\":\"" << escape_json(target_fmt) << L"\"";
        if (!out_dir.empty()) {
            ss << L",\"out_dir\":\"" << escape_json(get_full_path(out_dir)) << L"\"";
        }
        ss << L"}";

        std::string payload = utf16_to_utf8(ss.str());
        try_call_pipe(pipe_name, payload);
    }

    LocalFree(argv);
    return 0;
}
