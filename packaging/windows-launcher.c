#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
#include <stdio.h>

static HANDLE job, process;
static HWND status_label;
static wchar_t ready_path[32768], log_dir[32768], url[512];
static BOOL opened = FALSE, failed = FALSE;

static void error_box(HWND owner, const wchar_t *message) {
    wchar_t text[2048];
    swprintf(text, 2048, L"%ls\n\n로그 폴더에서 오류 내용을 확인해 주세요:\n%ls", message, log_dir);
    MessageBoxW(owner, text, L"Transitioner", MB_OK | MB_ICONERROR);
}
static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wp, LPARAM lp) {
    switch (message) {
    case WM_CREATE:
        status_label = CreateWindowW(L"STATIC", L"프로그램을 준비하고 있습니다…", WS_VISIBLE|WS_CHILD,
            24,24,450,48,window,NULL,NULL,NULL);
        CreateWindowW(L"BUTTON", L"프로그램 열기", WS_VISIBLE|WS_CHILD,24,90,140,36,window,(HMENU)1,NULL,NULL);
        CreateWindowW(L"BUTTON", L"로그 폴더", WS_VISIBLE|WS_CHILD,178,90,120,36,window,(HMENU)2,NULL,NULL);
        CreateWindowW(L"BUTTON", L"종료", WS_VISIBLE|WS_CHILD,312,90,120,36,window,(HMENU)3,NULL,NULL);
        SetTimer(window,1,500,NULL);
        return 0;
    case WM_TIMER: {
        DWORD code;
        if (process && GetExitCodeProcess(process,&code) && code != STILL_ACTIVE && !failed) {
            failed=TRUE;
            SetWindowTextW(status_label,L"실행이 종료되었습니다. 로그 폴더를 확인하세요.");
            error_box(window,L"프로그램이 실행 도중 종료되었습니다.");
        }
        if (!opened && !failed) {
            HANDLE file=CreateFileW(ready_path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,0,NULL);
            if (file != INVALID_HANDLE_VALUE) {
                char bytes[512]={0}; DWORD length=0;
                if (ReadFile(file,bytes,511,&length,NULL) && length>0) {
                    MultiByteToWideChar(CP_UTF8,0,bytes,(int)length,url,511);
                    url[511]=0;
                    if (wcsncmp(url,L"http://127.0.0.1:",17)==0) {
                        opened=TRUE;
                        SetWindowTextW(status_label,L"실행 중입니다. 브라우저에서 파일을 변환하세요.\n이 창을 닫으면 프로그램도 종료됩니다.");
                        ShellExecuteW(window,L"open",url,NULL,NULL,SW_SHOWNORMAL);
                    }
                }
                CloseHandle(file);
            }
        }
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(wp)==1 && opened) ShellExecuteW(window,L"open",url,NULL,NULL,SW_SHOWNORMAL);
        if (LOWORD(wp)==2) ShellExecuteW(window,L"open",log_dir,NULL,NULL,SW_SHOWNORMAL);
        if (LOWORD(wp)==3) SendMessageW(window,WM_CLOSE,0,0);
        return 0;
    case WM_CLOSE:
        DestroyWindow(window); return 0;
    case WM_DESTROY:
        if (job) { CloseHandle(job); job=NULL; }
        if (process) CloseHandle(process);
        DeleteFileW(ready_path);
        PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(window,message,wp,lp);
}

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,LPWSTR arguments,int show) {
    wchar_t root[32768], python[32768], command[65536], local[32768];
    if (!GetModuleFileNameW(NULL,root,32768)) return 1;
    wchar_t *slash=wcsrchr(root,L'\\'); if (!slash) return 1; *slash=0;
    DWORD n=GetEnvironmentVariableW(L"LOCALAPPDATA",local,32768);
    if (!n || n>=32768) { if (!GetTempPathW(32768,local)) return 1; }
    swprintf(log_dir,32768,L"%ls\\Transitioner\\logs",local);
    swprintf(ready_path,32768,L"%ls\\ready-%lu.txt",log_dir,GetCurrentProcessId());
    DeleteFileW(ready_path);
    SetEnvironmentVariableW(L"TRANSITIONER_READY_FILE",ready_path);
    SetEnvironmentVariableW(L"TRANSITIONER_MANAGED",L"1");
    SetEnvironmentVariableW(L"PYTHONHOME",NULL);
    SetEnvironmentVariableW(L"PYTHONPATH",NULL);
    BOOL test=wcscmp(arguments,L"--self-test")==0;
    swprintf(python,32768,L"%ls\\runtime\\pythonw.exe",root);
    swprintf(command,65536,L"\"%ls\" -I \"%ls\\portable_bootstrap.py\"%ls",python,root,test?L" --self-test":L"");
    if (GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES) {
        error_box(NULL,L"runtime 폴더를 찾을 수 없습니다. ZIP 전체를 압축 해제한 후 다시 실행하세요."); return 2;
    }
    job=CreateJobObjectW(NULL,NULL);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limit={0};
    limit.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job || !SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limit,sizeof(limit))) {
        error_box(NULL,L"프로그램 종료 관리자를 초기화하지 못했습니다."); return 3;
    }
    STARTUPINFOW startup={0}; PROCESS_INFORMATION child={0}; startup.cb=sizeof(startup);
    if (!CreateProcessW(python,command,NULL,NULL,FALSE,CREATE_SUSPENDED|CREATE_NO_WINDOW,NULL,root,&startup,&child)) {
        error_box(NULL,L"내장 Python을 실행하지 못했습니다."); CloseHandle(job); return 4;
    }
    if (!AssignProcessToJobObject(job,child.hProcess)) {
        TerminateProcess(child.hProcess,5); CloseHandle(child.hThread);CloseHandle(child.hProcess);CloseHandle(job);
        error_box(NULL,L"실행 프로세스를 관리할 수 없습니다."); return 5;
    }
    process=child.hProcess; ResumeThread(child.hThread); CloseHandle(child.hThread);
    if (test) {
        WaitForSingleObject(process,180000); DWORD code=1;GetExitCodeProcess(process,&code);
        CloseHandle(job);CloseHandle(process);return code==STILL_ACTIVE?6:(int)code;
    }
    WNDCLASSW wc={0};wc.lpfnWndProc=window_proc;wc.hInstance=instance;
    wc.lpszClassName=L"TransitionerLauncher";wc.hCursor=LoadCursorW(NULL,IDC_ARROW);
    wc.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);
    RegisterClassW(&wc);
    HWND window=CreateWindowW(wc.lpszClassName,L"Transitioner — 이미지·PDF → 엑셀",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        CW_USEDEFAULT,CW_USEDEFAULT,480,190,NULL,NULL,instance,NULL);
    if (!window) {CloseHandle(job);CloseHandle(process);return 7;}
    ShowWindow(window,show);UpdateWindow(window);
    MSG msg;while(GetMessageW(&msg,NULL,0,0)>0){TranslateMessage(&msg);DispatchMessageW(&msg);}
    return 0;
}
