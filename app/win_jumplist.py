"""Windows 작업 표시줄 점프리스트의 '작업' 카테고리.

Qt 6에서 QtWinExtras가 제거돼서 :mod:`comtypes` 로 Windows Shell COM
API를 직접 호출한다. 점프리스트는 UX 부가 기능일 뿐이므로 모든 호출을
best-effort try/except로 감싸, 어떤 COM 실패(Wine, 권한 거부, 특이한
Windows 빌드)에도 등록만 건너뛰고 앱은 정상 동작한다."""
from __future__ import annotations

from . import i18n

import ctypes
import sys
from ctypes import (
    POINTER,
    Structure,
    Union,
    byref,
    c_byte,
    c_int,
    c_uint,
    c_ulong,
    c_ushort,
    c_void_p,
    c_wchar_p,
)

try:
    from ctypes import HRESULT
except ImportError:
    HRESULT = c_int

try:
    from comtypes import COMMETHOD, CoCreateInstance, GUID, IUnknown
    _COMTYPES_OK = True
except Exception:
    _COMTYPES_OK = False


# 작업 표시줄 그룹화 키로도 쓰인다.
APP_USER_MODEL_ID = "SyncNotes.LeeSeungGyu.Desktop.1"


def set_app_user_model_id() -> None:
    """어떤 창이든 표시되기 전에 호출해야 작업 표시줄 버튼이 이 ID를
    인식하고 점프리스트가 앱 아이콘과 연결된다."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID)
    except Exception:
        pass


# 일부 메서드만 호출하지만, vtable 인덱스를 맞추려면 _methods_ 의
# 순서와 항목 전체를 정확히 적어 두어야 한다.

if _COMTYPES_OK:

    class IObjectArray(IUnknown):
        _iid_ = GUID('{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetCount',
                      (['out'], POINTER(c_uint), 'pcObjects')),
            COMMETHOD([], HRESULT, 'GetAt',
                      (['in'], c_uint, 'uiIndex'),
                      (['in'], POINTER(GUID), 'riid'),
                      (['out'], POINTER(POINTER(IUnknown)), 'ppv')),
        ]

    class IObjectCollection(IObjectArray):
        _iid_ = GUID('{5632B1A4-E38A-400A-928A-D4CD63230295}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'AddObject',
                      (['in'], POINTER(IUnknown), 'punk')),
            COMMETHOD([], HRESULT, 'AddFromArray',
                      (['in'], POINTER(IObjectArray), 'poaSource')),
            COMMETHOD([], HRESULT, 'RemoveObjectAt',
                      (['in'], c_uint, 'uiIndex')),
            COMMETHOD([], HRESULT, 'Clear'),
        ]

    class ICustomDestinationList(IUnknown):
        _iid_ = GUID('{6332DEBF-87B5-4670-90C0-5E57B408A49E}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'SetAppID',
                      (['in'], c_wchar_p, 'pszAppID')),
            COMMETHOD([], HRESULT, 'BeginList',
                      (['out'], POINTER(c_uint), 'pcMinSlots'),
                      (['in'], POINTER(GUID), 'riid'),
                      (['out'], POINTER(POINTER(IUnknown)), 'ppv')),
            COMMETHOD([], HRESULT, 'AppendCategory',
                      (['in'], c_wchar_p, 'pszCategory'),
                      (['in'], POINTER(IObjectArray), 'poa')),
            COMMETHOD([], HRESULT, 'AppendKnownCategory',
                      (['in'], c_int, 'category')),
            COMMETHOD([], HRESULT, 'AddUserTasks',
                      (['in'], POINTER(IObjectArray), 'poa')),
            COMMETHOD([], HRESULT, 'CommitList'),
            COMMETHOD([], HRESULT, 'GetRemovedDestinations',
                      (['in'], POINTER(GUID), 'riid'),
                      (['out'], POINTER(POINTER(IUnknown)), 'ppv')),
            COMMETHOD([], HRESULT, 'DeleteList',
                      (['in'], c_wchar_p, 'pszAppID')),
            COMMETHOD([], HRESULT, 'AbortList'),
        ]

    class IShellLinkW(IUnknown):
        _iid_ = GUID('{000214F9-0000-0000-C000-000000000046}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetPath',
                      (['in'], c_wchar_p, 'pszFile'),
                      (['in'], c_int, 'cch'),
                      (['in'], c_void_p, 'pfd'),
                      (['in'], c_uint, 'fFlags')),
            COMMETHOD([], HRESULT, 'GetIDList',
                      (['out'], POINTER(c_void_p), 'ppidl')),
            COMMETHOD([], HRESULT, 'SetIDList',
                      (['in'], c_void_p, 'pidl')),
            COMMETHOD([], HRESULT, 'GetDescription',
                      (['in'], c_wchar_p, 'pszName'),
                      (['in'], c_int, 'cch')),
            COMMETHOD([], HRESULT, 'SetDescription',
                      (['in'], c_wchar_p, 'pszName')),
            COMMETHOD([], HRESULT, 'GetWorkingDirectory',
                      (['in'], c_wchar_p, 'pszDir'),
                      (['in'], c_int, 'cch')),
            COMMETHOD([], HRESULT, 'SetWorkingDirectory',
                      (['in'], c_wchar_p, 'pszDir')),
            COMMETHOD([], HRESULT, 'GetArguments',
                      (['in'], c_wchar_p, 'pszArgs'),
                      (['in'], c_int, 'cch')),
            COMMETHOD([], HRESULT, 'SetArguments',
                      (['in'], c_wchar_p, 'pszArgs')),
            COMMETHOD([], HRESULT, 'GetHotkey',
                      (['out'], POINTER(c_ushort), 'pwHotkey')),
            COMMETHOD([], HRESULT, 'SetHotkey',
                      (['in'], c_ushort, 'wHotkey')),
            COMMETHOD([], HRESULT, 'GetShowCmd',
                      (['out'], POINTER(c_int), 'piShowCmd')),
            COMMETHOD([], HRESULT, 'SetShowCmd',
                      (['in'], c_int, 'iShowCmd')),
            COMMETHOD([], HRESULT, 'GetIconLocation',
                      (['in'], c_wchar_p, 'pszIconPath'),
                      (['in'], c_int, 'cch'),
                      (['out'], POINTER(c_int), 'piIcon')),
            COMMETHOD([], HRESULT, 'SetIconLocation',
                      (['in'], c_wchar_p, 'pszIconPath'),
                      (['in'], c_int, 'iIcon')),
            COMMETHOD([], HRESULT, 'SetRelativePath',
                      (['in'], c_wchar_p, 'pszPathRel'),
                      (['in'], c_uint, 'dwReserved')),
            COMMETHOD([], HRESULT, 'Resolve',
                      (['in'], c_void_p, 'hwnd'),
                      (['in'], c_uint, 'fFlags')),
            COMMETHOD([], HRESULT, 'SetPath',
                      (['in'], c_wchar_p, 'pszFile')),
        ]

    # IPropertyStore::SetValue(title) 용 PROPVARIANT + PROPERTYKEY.
    class _PROPERTYKEY(Structure):
        _fields_ = [('fmtid', GUID), ('pid', c_ulong)]

    class _PVUnion(Union):
        _fields_ = [
            ('pwszVal', c_wchar_p),
            ('_padding', c_byte * 16),  # 64비트 환경 최대 variant 폭
        ]

    class _PROPVARIANT(Structure):
        _fields_ = [
            ('vt', c_ushort),
            ('wReserved1', c_ushort),
            ('wReserved2', c_ushort),
            ('wReserved3', c_ushort),
            ('u', _PVUnion),
        ]

    _VT_LPWSTR = 31

    class IPropertyStore(IUnknown):
        _iid_ = GUID('{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetCount',
                      (['out'], POINTER(c_uint), 'cProps')),
            COMMETHOD([], HRESULT, 'GetAt',
                      (['in'], c_uint, 'iProp'),
                      (['out'], POINTER(_PROPERTYKEY), 'pkey')),
            COMMETHOD([], HRESULT, 'GetValue',
                      (['in'], POINTER(_PROPERTYKEY), 'key'),
                      (['out'], POINTER(_PROPVARIANT), 'pv')),
            COMMETHOD([], HRESULT, 'SetValue',
                      (['in'], POINTER(_PROPERTYKEY), 'key'),
                      (['in'], POINTER(_PROPVARIANT), 'propvar')),
            COMMETHOD([], HRESULT, 'Commit'),
        ]

    _CLSID_DestinationList = GUID('{77F10CF0-3DB5-4966-B520-B7C54FD35ED6}')
    _CLSID_ShellLink = GUID('{00021401-0000-0000-C000-000000000046}')
    _CLSID_EnumerableObjectCollection = GUID(
        '{2D3468C1-36A7-43B6-AC24-D3F02FD9607A}')

    # PKEY_Title: Shell이 점프리스트 작업의 표시 라벨로 사용하는 속성.
    _PKEY_TITLE = _PROPERTYKEY()
    _PKEY_TITLE.fmtid = GUID('{F29F85E0-4FF9-1068-AB91-08002B27B3D9}')
    _PKEY_TITLE.pid = 2


def _make_task(exe_path: str, arguments: str, title: str,
               description: str, icon_path: str, icon_index: int = 0):
    link = CoCreateInstance(_CLSID_ShellLink, interface=IShellLinkW)
    link.SetPath(exe_path)
    if arguments:
        link.SetArguments(arguments)
    if description:
        link.SetDescription(description)
    if icon_path:
        link.SetIconLocation(icon_path, icon_index)
    # 표시 라벨은 IPropertyStore의 PKEY_Title로 설정해야 한다.
    prop_store = link.QueryInterface(IPropertyStore)
    pv = _PROPVARIANT()
    pv.vt = _VT_LPWSTR
    pv.u.pwszVal = title
    prop_store.SetValue(byref(_PKEY_TITLE), byref(pv))
    prop_store.Commit()
    return link


def register(*, exe_path: str = "", icon_path: str = "") -> None:
    """앱 시작 시 1회 호출하면 되며, 멱등하다."""
    if sys.platform != "win32" or not _COMTYPES_OK:
        return
    try:
        ctypes.windll.ole32.CoInitialize(None)
    except Exception:
        pass
    try:
        exe = exe_path or sys.executable
        icon = icon_path or exe

        dest_list = CoCreateInstance(
            _CLSID_DestinationList, interface=ICustomDestinationList)
        dest_list.SetAppID(APP_USER_MODEL_ID)

        # AddUserTasks 전에 반드시 BeginList를 먼저 호출해야 한다.
        _slots, _removed = dest_list.BeginList(byref(IObjectArray._iid_))

        tasks = CoCreateInstance(
            _CLSID_EnumerableObjectCollection, interface=IObjectCollection)

        new_note = _make_task(
            exe_path=exe,
            arguments="--new-note",
            title=i18n.t("jumplist.new_note_title"),
            description=i18n.t("jumplist.new_note_desc"),
            icon_path=icon,
            icon_index=0,
        )
        tasks.AddObject(new_note)

        tasks_array = tasks.QueryInterface(IObjectArray)
        dest_list.AddUserTasks(tasks_array)
        dest_list.CommitList()
    except Exception as exc:
        try:
            sys.stderr.write(f"[JumpList] registration failed: {exc!r}\n")
        except Exception:
            pass
