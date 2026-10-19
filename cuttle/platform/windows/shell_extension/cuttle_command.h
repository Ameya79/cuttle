#pragma once

#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#if defined(__has_include) && __has_include(<shobjidl_core.h>)
#include <shobjidl_core.h>
#else
#include <shobjidl.h>
#endif
#include <string>
#include <vector>
#include <atomic>
#include <fstream>

// CLSID for CuttleExplorerCommand: {F4312356-5D3C-486B-8C92-72188A47559B}
// {F4312356-5D3C-486B-8C92-72188A47559B}
static const GUID CLSID_CuttleExplorerCommand = {
    0xf4312356, 0x5d3c, 0x486b, {0x8c, 0x92, 0x72, 0x18, 0x8a, 0x47, 0x55, 0x9b}
};

extern std::atomic<long> g_cRefModule;
extern HINSTANCE g_hInstance;

void LogShellMessage(const std::wstring& msg);
std::wstring GetModuleDirectory();

struct ConversionTarget {
    std::wstring fmt;
    std::wstring label;
};

std::vector<ConversionTarget> GetTargetsForFile(const std::wstring& file_path);

class CuttleExplorerCommand : public IExplorerCommand {
public:
    CuttleExplorerCommand(bool is_root = true,
                          const std::wstring& target_fmt = L"",
                          const std::wstring& target_label = L"");
    virtual ~CuttleExplorerCommand();

    // IUnknown
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override;
    IFACEMETHODIMP_(ULONG) AddRef() override;
    IFACEMETHODIMP_(ULONG) Release() override;

    // IExplorerCommand
    IFACEMETHODIMP GetTitle(IShellItemArray* psiItemArray, LPWSTR* ppszName) override;
    IFACEMETHODIMP GetIcon(IShellItemArray* psiItemArray, LPWSTR* ppszIcon) override;
    IFACEMETHODIMP GetToolTip(IShellItemArray* psiItemArray, LPWSTR* ppszToolTip) override;
    IFACEMETHODIMP GetCanonicalName(GUID* pguidCommandName) override;
    IFACEMETHODIMP GetState(IShellItemArray* psiItemArray, BOOL fOkToBeSlow, EXPCMDSTATE* pCmdState) override;
    IFACEMETHODIMP Invoke(IShellItemArray* psiItemArray, IBindCtx* pbc) override;
    IFACEMETHODIMP GetFlags(EXPCMDFLAGS* pFlags) override;
    IFACEMETHODIMP EnumSubCommands(IEnumExplorerCommand** ppEnum) override;

private:
    std::atomic<long> ref_count_{1};
    bool is_root_{true};
    std::wstring target_fmt_;
    std::wstring target_label_;
};

class CuttleEnumCommands : public IEnumExplorerCommand {
public:
    CuttleEnumCommands(const std::vector<ConversionTarget>& targets);
    virtual ~CuttleEnumCommands();

    // IUnknown
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override;
    IFACEMETHODIMP_(ULONG) AddRef() override;
    IFACEMETHODIMP_(ULONG) Release() override;

    // IEnumExplorerCommand
    IFACEMETHODIMP Next(ULONG celt, IExplorerCommand** apUICommand, ULONG* pceltFetched) override;
    IFACEMETHODIMP Skip(ULONG celt) override;
    IFACEMETHODIMP Reset() override;
    IFACEMETHODIMP Clone(IEnumExplorerCommand** ppEnum) override;

private:
    std::atomic<long> ref_count_{1};
    std::vector<ConversionTarget> targets_;
    size_t current_index_{0};
};

class CuttleClassFactory : public IClassFactory {
public:
    CuttleClassFactory();
    virtual ~CuttleClassFactory();

    // IUnknown
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override;
    IFACEMETHODIMP_(ULONG) AddRef() override;
    IFACEMETHODIMP_(ULONG) Release() override;

    // IClassFactory
    IFACEMETHODIMP CreateInstance(IUnknown* pUnkOuter, REFIID riid, void** ppvObject) override;
    IFACEMETHODIMP LockServer(BOOL fLock) override;

private:
    std::atomic<long> ref_count_{1};
};
