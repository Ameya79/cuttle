"""Unit tests for the Cuttle IExplorerCommand Windows 11 shell extension.

Per task cards P4-02 and P4-03:
- Tests that cuttle_shell.dll compiles, loads via ctypes, and exposes COM entry points.
- Verifies IClassFactory and IExplorerCommand instantiation.
- Verifies GetTitle, GetFlags (ECF_HASSUBCOMMANDS), and EnumSubCommands.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import HRESULT, POINTER, byref, c_ulong, c_void_p, c_wchar_p
from pathlib import Path

import pytest

DLL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "cuttle"
    / "platform"
    / "windows"
    / "shell_extension"
    / "cuttle_shell.dll"
)


@pytest.fixture(scope="module", autouse=True)
def ensure_dll_compiled() -> None:
    """Ensure the COM DLL is compiled before tests run."""
    if not DLL_PATH.is_file():
        build_script = (
            Path(__file__).resolve().parent.parent.parent / "scripts" / "build_shell_extension.py"
        )
        res = subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True)
        assert res.returncode == 0, f"Failed to build shell extension: {res.stderr}"
    assert DLL_PATH.is_file(), "cuttle_shell.dll must exist"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


# CLSID_CuttleExplorerCommand: {F4312356-5D3C-486B-8C92-72188A47559B}
CLSID_Cuttle = GUID(
    0xF4312356,
    0x5D3C,
    0x486B,
    (ctypes.c_ubyte * 8)(0x8C, 0x92, 0x72, 0x18, 0x8A, 0x47, 0x55, 0x9B),
)

# IID_IClassFactory: {00000001-0000-0000-C000-000000000046}
IID_IClassFactory = GUID(
    0x00000001,
    0x0000,
    0x0000,
    (ctypes.c_ubyte * 8)(0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46),
)

# IID_IExplorerCommand: {a08ce4d0-fa25-44ab-b57c-c7b1c323e0b9}
IID_IExplorerCommand = GUID(
    0xA08CE4D0,
    0xFA25,
    0x44AB,
    (ctypes.c_ubyte * 8)(0xB5, 0x7C, 0xC7, 0xB1, 0xC3, 0x23, 0xE0, 0xB9),
)


class TestShellExtensionCOM:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_dll_exports_exist(self) -> None:
        """Verify the compiled DLL exports standard COM entry points."""
        dll = ctypes.windll.LoadLibrary(str(DLL_PATH))
        assert hasattr(dll, "DllGetClassObject")
        assert hasattr(dll, "DllCanUnloadNow")
        assert hasattr(dll, "DllRegisterServer")
        assert hasattr(dll, "DllUnregisterServer")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_com_instantiation_and_title(self) -> None:
        """Instantiate the COM class factory and query IExplorerCommand interface."""
        dll = ctypes.windll.LoadLibrary(str(DLL_PATH))
        dll_get_class_object = dll.DllGetClassObject
        dll_get_class_object.argtypes = [
            POINTER(GUID),
            POINTER(GUID),
            POINTER(c_void_p),
        ]
        dll_get_class_object.restype = HRESULT

        factory_ptr = c_void_p()
        hr = dll_get_class_object(
            byref(CLSID_Cuttle),
            byref(IID_IClassFactory),
            byref(factory_ptr),
        )
        assert hr == 0, f"DllGetClassObject failed with HRESULT 0x{hr & 0xFFFFFFFF:08X}"
        assert factory_ptr.value is not None

        # Call IClassFactory::CreateInstance
        # Vtable for IClassFactory:
        # [0]: QueryInterface, [1]: AddRef, [2]: Release, [3]: CreateInstance, [4]: LockServer
        vtable = ctypes.cast(factory_ptr, POINTER(POINTER(c_void_p))).contents
        create_instance_func = ctypes.WINFUNCTYPE(
            HRESULT, c_void_p, c_void_p, POINTER(GUID), POINTER(c_void_p)
        )(vtable[3])

        cmd_ptr = c_void_p()
        hr = create_instance_func(
            factory_ptr,
            None,
            byref(IID_IExplorerCommand),
            byref(cmd_ptr),
        )
        assert hr == 0, f"CreateInstance failed with HRESULT 0x{hr & 0xFFFFFFFF:08X}"
        assert cmd_ptr.value is not None

        # Call IExplorerCommand::GetTitle
        # Vtable for IExplorerCommand:
        # [0]: QI, [1]: AddRef, [2]: Release, [3]: GetTitle
        cmd_vtable = ctypes.cast(cmd_ptr, POINTER(POINTER(c_void_p))).contents
        get_title_func = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_void_p, POINTER(c_wchar_p))(
            cmd_vtable[3]
        )

        title_ptr = c_wchar_p()
        hr = get_title_func(cmd_ptr, None, byref(title_ptr))
        assert hr == 0
        assert title_ptr.value == "Convert with Cuttle"

        # Call IExplorerCommand::GetFlags: vtable[9]
        # [0]: QI, [1]: AddRef, [2]: Release, [3]: GetTitle, [4]: GetIcon,
        # [5]: GetToolTip, [6]: GetCanonicalName, [7]: GetState, [8]: Invoke
        # [9]: GetFlags, [10]: EnumSubCommands
        get_flags_func = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_ulong))(cmd_vtable[9])

        flags = c_ulong()
        hr = get_flags_func(cmd_ptr, byref(flags))
        assert hr == 0
        # ECF_HASSUBCOMMANDS = 0x1
        assert flags.value & 0x1 != 0

        # Call IExplorerCommand::EnumSubCommands: vtable[10]
        enum_sub_func = ctypes.WINFUNCTYPE(HRESULT, c_void_p, POINTER(c_void_p))(cmd_vtable[10])

        enum_ptr = c_void_p()
        hr = enum_sub_func(cmd_ptr, byref(enum_ptr))
        assert hr == 0
        assert enum_ptr.value is not None

        # EnumSubCommands::Next: vtable[3]
        enum_vtable = ctypes.cast(enum_ptr, POINTER(POINTER(c_void_p))).contents
        next_func = ctypes.WINFUNCTYPE(
            HRESULT, c_void_p, c_ulong, POINTER(c_void_p), POINTER(c_ulong)
        )(enum_vtable[3])

        child_cmd_ptr = c_void_p()
        fetched = c_ulong()
        hr = next_func(enum_ptr, 1, byref(child_cmd_ptr), byref(fetched))
        assert hr == 0
        assert fetched.value == 1
        assert child_cmd_ptr.value is not None

        # Check child title
        child_vtable = ctypes.cast(child_cmd_ptr, POINTER(POINTER(c_void_p))).contents
        child_title_func = ctypes.WINFUNCTYPE(HRESULT, c_void_p, c_void_p, POINTER(c_wchar_p))(
            child_vtable[3]
        )

        child_title = c_wchar_p()
        hr = child_title_func(child_cmd_ptr, None, byref(child_title))
        assert hr == 0
        assert child_title.value is not None
        assert len(child_title.value) > 0

        # Release child command
        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(child_vtable[2])(child_cmd_ptr)

        # Release enum
        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(enum_vtable[2])(enum_ptr)

        # Release COM objects
        release_cmd = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(cmd_vtable[2])
        release_cmd(cmd_ptr)

        release_factory = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(vtable[2])
        release_factory(factory_ptr)
