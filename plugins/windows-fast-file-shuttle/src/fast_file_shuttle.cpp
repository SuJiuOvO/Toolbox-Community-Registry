#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif

#include <windows.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cwctype>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {

std::atomic_bool g_cancelled{false};
std::mutex g_logMutex;
std::atomic<int> g_detailedErrors{0};

struct Options {
  std::wstring source;
  std::wstring target;
  std::wstring mode = L"move";
  std::wstring conflict = L"skip";
  int threads = 8;
  bool dryRun = false;
};

struct FileEntry {
  std::wstring relative;
  std::uint64_t size = 0;
};

struct DirectoryEntry {
  std::wstring relative;
  FILETIME creation{};
  FILETIME access{};
  FILETIME write{};
  DWORD attributes = 0;
};

struct ScanResult {
  std::vector<FileEntry> files;
  std::vector<DirectoryEntry> directories;
  std::uint64_t totalBytes = 0;
  std::uint64_t skippedLinks = 0;
  std::uint64_t unreadableDirectories = 0;
};

struct SharedCounters {
  std::atomic<std::uint64_t> processedFiles{0};
  std::atomic<std::uint64_t> copiedBytes{0};
  std::atomic<std::uint64_t> completedBytes{0};
  std::atomic<std::uint64_t> movedFiles{0};
  std::atomic<std::uint64_t> copiedFiles{0};
  std::atomic<std::uint64_t> skippedFiles{0};
  std::atomic<std::uint64_t> failedFiles{0};
};

BOOL WINAPI ConsoleCtrlHandler(DWORD event) {
  if (event == CTRL_C_EVENT || event == CTRL_BREAK_EVENT ||
      event == CTRL_CLOSE_EVENT) {
    g_cancelled.store(true);
    return TRUE;
  }
  return FALSE;
}

std::string WideToUtf8(const std::wstring& value) {
  if (value.empty()) return {};
  const int required = WideCharToMultiByte(
      CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
  if (required <= 0) return "?";
  std::string result(static_cast<size_t>(required), '\0');
  WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
                      static_cast<int>(value.size()), result.data(), required,
                      nullptr, nullptr);
  return result;
}

void WriteLine(HANDLE handle, const std::wstring& message) {
  const std::string bytes = WideToUtf8(message) + "\r\n";
  DWORD written = 0;
  WriteFile(handle, bytes.data(), static_cast<DWORD>(bytes.size()), &written,
            nullptr);
}

void Log(const std::wstring& message) {
  std::lock_guard<std::mutex> lock(g_logMutex);
  WriteLine(GetStdHandle(STD_OUTPUT_HANDLE), message);
}

std::wstring WindowsErrorText(DWORD code) {
  wchar_t* buffer = nullptr;
  const DWORD length = FormatMessageW(
      FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
          FORMAT_MESSAGE_IGNORE_INSERTS,
      nullptr, code, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
      reinterpret_cast<wchar_t*>(&buffer), 0, nullptr);
  std::wstring text =
      (length > 0 && buffer != nullptr) ? std::wstring(buffer, length) : L"";
  if (buffer != nullptr) LocalFree(buffer);
  while (!text.empty() &&
         (text.back() == L'\r' || text.back() == L'\n' || text.back() == L' ')) {
    text.pop_back();
  }
  if (text.empty()) text = L"Windows error " + std::to_wstring(code);
  return text;
}

void Error(const std::wstring& message) {
  std::lock_guard<std::mutex> lock(g_logMutex);
  WriteLine(GetStdHandle(STD_ERROR_HANDLE), L"[error] " + message);
}

void DetailedError(const std::wstring& path, DWORD code = GetLastError()) {
  if (g_detailedErrors.fetch_add(1) < 80) {
    Error(path + L"：[" + std::to_wstring(code) + L"] " +
          WindowsErrorText(code));
  }
}

std::wstring TrimTrailingSeparators(std::wstring path) {
  while (path.size() > 3 &&
         (path.back() == L'\\' || path.back() == L'/')) {
    path.pop_back();
  }
  return path;
}

std::wstring AbsolutePath(const std::wstring& value) {
  if (value.empty()) return {};
  const DWORD required = GetFullPathNameW(value.c_str(), 0, nullptr, nullptr);
  if (required == 0) return {};
  std::wstring result(static_cast<size_t>(required), L'\0');
  const DWORD length =
      GetFullPathNameW(value.c_str(), required, result.data(), nullptr);
  if (length == 0 || length >= required) return {};
  result.resize(length);
  return TrimTrailingSeparators(result);
}

std::wstring ExtendedPath(const std::wstring& path) {
  if (path.rfind(L"\\\\?\\", 0) == 0) return path;
  if (path.rfind(L"\\\\", 0) == 0) return L"\\\\?\\UNC\\" + path.substr(2);
  return L"\\\\?\\" + path;
}

std::wstring JoinPath(const std::wstring& left, const std::wstring& right) {
  if (left.empty()) return right;
  if (right.empty()) return left;
  if (left.back() == L'\\' || left.back() == L'/') return left + right;
  return left + L"\\" + right;
}

std::wstring BaseName(const std::wstring& path) {
  const size_t position = path.find_last_of(L"\\/");
  return position == std::wstring::npos ? path : path.substr(position + 1);
}

std::wstring ParentPath(const std::wstring& path) {
  const std::wstring clean = TrimTrailingSeparators(path);
  const size_t position = clean.find_last_of(L"\\/");
  if (position == std::wstring::npos) return {};
  if (position == 2 && clean.size() >= 3 && clean[1] == L':') {
    return clean.substr(0, 3);
  }
  return clean.substr(0, position);
}

DWORD Attributes(const std::wstring& path) {
  return GetFileAttributesW(ExtendedPath(path).c_str());
}

bool IsDirectory(const std::wstring& path) {
  const DWORD attributes = Attributes(path);
  return attributes != INVALID_FILE_ATTRIBUTES &&
         (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
}

bool IsDriveRoot(const std::wstring& path) {
  const std::wstring clean = TrimTrailingSeparators(path);
  return clean.size() == 3 && iswalpha(clean[0]) && clean[1] == L':' &&
         (clean[2] == L'\\' || clean[2] == L'/');
}

bool IsReparsePoint(const std::wstring& path) {
  const DWORD attributes = Attributes(path);
  return attributes != INVALID_FILE_ATTRIBUTES &&
         (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
}

bool EnsureDirectory(const std::wstring& path) {
  const DWORD existing = Attributes(path);
  if (existing != INVALID_FILE_ATTRIBUTES) {
    return (existing & FILE_ATTRIBUTE_DIRECTORY) != 0;
  }
  const std::wstring parent = ParentPath(path);
  if (!parent.empty() && !EnsureDirectory(parent)) return false;
  if (CreateDirectoryW(ExtendedPath(path).c_str(), nullptr)) return true;
  const DWORD code = GetLastError();
  return code == ERROR_ALREADY_EXISTS && IsDirectory(path);
}

bool CaseInsensitiveEqual(const std::wstring& left,
                          const std::wstring& right) {
  if (left.size() != right.size()) return false;
  return CompareStringOrdinal(left.c_str(), static_cast<int>(left.size()),
                              right.c_str(), static_cast<int>(right.size()),
                              TRUE) == CSTR_EQUAL;
}

bool IsSameOrChild(const std::wstring& child, const std::wstring& parent) {
  if (child.size() < parent.size()) return false;
  if (!CaseInsensitiveEqual(child.substr(0, parent.size()), parent)) return false;
  return child.size() == parent.size() || child[parent.size()] == L'\\' ||
         child[parent.size()] == L'/';
}

std::wstring VolumeRoot(const std::wstring& path) {
  std::wstring buffer(32768, L'\0');
  if (!GetVolumePathNameW(ExtendedPath(path).c_str(), buffer.data(),
                          static_cast<DWORD>(buffer.size()))) {
    return {};
  }
  buffer.resize(wcslen(buffer.c_str()));
  return buffer;
}

bool SameVolume(const std::wstring& left, const std::wstring& right) {
  const std::wstring leftRoot = VolumeRoot(left);
  const std::wstring rightRoot = VolumeRoot(right);
  return !leftRoot.empty() && !rightRoot.empty() &&
         CaseInsensitiveEqual(leftRoot, rightRoot);
}

std::wstring FormatBytes(std::uint64_t bytes) {
  static const wchar_t* units[] = {L"B", L"KiB", L"MiB", L"GiB", L"TiB"};
  double value = static_cast<double>(bytes);
  size_t unit = 0;
  while (value >= 1024.0 && unit + 1 < 5) {
    value /= 1024.0;
    ++unit;
  }
  std::wostringstream output;
  output << std::fixed << std::setprecision(unit == 0 ? 0 : 1) << value << L" "
         << units[unit];
  return output.str();
}

std::wstring Percent(std::uint64_t completed, std::uint64_t total) {
  const double value =
      total == 0 ? 100.0
                 : std::min(100.0, 100.0 * static_cast<double>(completed) /
                                        static_cast<double>(total));
  std::wostringstream output;
  output << std::fixed << std::setprecision(1) << value << L"%";
  return output.str();
}

bool IsSwitchOn(const std::wstring& value) {
  return CaseInsensitiveEqual(value, L"true") ||
         CaseInsensitiveEqual(value, L"1") ||
         CaseInsensitiveEqual(value, L"yes") ||
         CaseInsensitiveEqual(value, L"on");
}

void PrintUsage() {
  Log(L"小文件极速搬运 1.0.0");
  Log(L"用法：windows-fast-file-shuttle.exe --source <目录> --target <目录> "
      L"--mode move|copy --conflict skip|rename|overwrite --threads 0-32 "
      L"[--dry-run <true|false>]");
}

bool ParseOptions(int argc, wchar_t** argv, Options& options) {
  for (int index = 1; index < argc; ++index) {
    const std::wstring key = argv[index];
    auto next = [&](std::wstring& value) -> bool {
      if (index + 1 >= argc) return false;
      value = argv[++index];
      return true;
    };
    if (key == L"--help" || key == L"-h") {
      PrintUsage();
      return false;
    } else if (key == L"--source") {
      if (!next(options.source)) return false;
    } else if (key == L"--target") {
      if (!next(options.target)) return false;
    } else if (key == L"--mode") {
      if (!next(options.mode)) return false;
    } else if (key == L"--conflict") {
      if (!next(options.conflict)) return false;
    } else if (key == L"--threads") {
      std::wstring value;
      if (!next(value)) return false;
      options.threads = _wtoi(value.c_str());
    } else if (key == L"--dry-run" || key == L"--dryRun") {
      if (index + 1 < argc && argv[index + 1][0] != L'-') {
        options.dryRun = IsSwitchOn(argv[++index]);
      } else {
        options.dryRun = true;
      }
    } else if (key == L"true" || key == L"false" || key == L"1" ||
               key == L"0") {
      options.dryRun = IsSwitchOn(key);
    } else {
      Error(L"未知参数：" + key);
      return false;
    }
  }

  options.mode = options.mode.empty() ? L"move" : options.mode;
  options.conflict = options.conflict.empty() ? L"skip" : options.conflict;
  std::transform(options.mode.begin(), options.mode.end(), options.mode.begin(),
                 [](wchar_t value) { return static_cast<wchar_t>(towlower(value)); });
  std::transform(options.conflict.begin(), options.conflict.end(),
                 options.conflict.begin(),
                 [](wchar_t value) { return static_cast<wchar_t>(towlower(value)); });
  if (options.threads == 0) {
    const unsigned int hardware = std::thread::hardware_concurrency();
    options.threads =
        static_cast<int>(std::clamp(hardware == 0 ? 8U : hardware, 2U, 16U));
  }
  return true;
}

bool HasMultiplePickedDirectories(const std::wstring& value) {
  return value.find(L';') != std::wstring::npos ||
         value.find(L'\n') != std::wstring::npos ||
         value.find(L'\r') != std::wstring::npos;
}

void ScanDirectory(const std::wstring& root, ScanResult& result) {
  struct PendingDirectory {
    std::wstring absolute;
    std::wstring relative;
  };
  std::vector<PendingDirectory> pending{{root, L""}};

  while (!pending.empty() && !g_cancelled.load()) {
    const PendingDirectory current = std::move(pending.back());
    pending.pop_back();
    const std::wstring query = JoinPath(current.absolute, L"*");
    WIN32_FIND_DATAW data{};
    HANDLE find = FindFirstFileExW(
        ExtendedPath(query).c_str(), FindExInfoBasic, &data,
        FindExSearchNameMatch, nullptr,
        FIND_FIRST_EX_LARGE_FETCH);
    if (find == INVALID_HANDLE_VALUE) {
      ++result.unreadableDirectories;
      DetailedError(current.absolute);
      continue;
    }

    do {
      if (wcscmp(data.cFileName, L".") == 0 ||
          wcscmp(data.cFileName, L"..") == 0) {
        continue;
      }
      const std::wstring relative =
          current.relative.empty()
              ? std::wstring(data.cFileName)
              : JoinPath(current.relative, data.cFileName);
      const std::wstring absolute = JoinPath(current.absolute, data.cFileName);
      if ((data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        ++result.skippedLinks;
        Log(L"[scan] 跳过重解析点：" + relative);
        continue;
      }
      if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
        DirectoryEntry directory;
        directory.relative = relative;
        directory.creation = data.ftCreationTime;
        directory.access = data.ftLastAccessTime;
        directory.write = data.ftLastWriteTime;
        directory.attributes = data.dwFileAttributes;
        result.directories.push_back(std::move(directory));
        pending.push_back({absolute, relative});
      } else {
        FileEntry file;
        file.relative = relative;
        file.size =
            (static_cast<std::uint64_t>(data.nFileSizeHigh) << 32) |
            data.nFileSizeLow;
        result.totalBytes += file.size;
        result.files.push_back(std::move(file));
      }
    } while (FindNextFileW(find, &data));

    const DWORD findError = GetLastError();
    FindClose(find);
    if (findError != ERROR_NO_MORE_FILES) {
      ++result.unreadableDirectories;
      Error(current.absolute + L"：" + WindowsErrorText(findError));
    }
  }

  std::sort(result.directories.begin(), result.directories.end(),
            [](const DirectoryEntry& left, const DirectoryEntry& right) {
              return left.relative.size() < right.relative.size();
            });
}

bool CopyFileWithMetadata(const std::wstring& source,
                          const std::wstring& destination) {
  const std::wstring extendedDestination = ExtendedPath(destination);
  const DWORD destinationAttributes = Attributes(destination);
  if (destinationAttributes != INVALID_FILE_ATTRIBUTES) {
    SetFileAttributesW(extendedDestination.c_str(), FILE_ATTRIBUTE_NORMAL);
  }

  if (!CopyFileExW(ExtendedPath(source).c_str(), extendedDestination.c_str(),
                   nullptr, nullptr, nullptr, 0)) {
    return false;
  }

  WIN32_FILE_ATTRIBUTE_DATA metadata{};
  if (GetFileAttributesExW(ExtendedPath(source).c_str(), GetFileExInfoStandard,
                           &metadata)) {
    HANDLE output = CreateFileW(
        extendedDestination.c_str(), FILE_WRITE_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (output != INVALID_HANDLE_VALUE) {
      SetFileTime(output, &metadata.ftCreationTime, &metadata.ftLastAccessTime,
                  &metadata.ftLastWriteTime);
      CloseHandle(output);
    }
    const DWORD transferableAttributes =
        metadata.dwFileAttributes &
        (FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_HIDDEN |
         FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_ARCHIVE |
         FILE_ATTRIBUTE_NOT_CONTENT_INDEXED);
    SetFileAttributesW(extendedDestination.c_str(), transferableAttributes);
  }
  return true;
}

bool DeleteSourceFile(const std::wstring& path) {
  if (DeleteFileW(ExtendedPath(path).c_str())) return true;
  DWORD code = GetLastError();
  if (code == ERROR_ACCESS_DENIED) {
    SetFileAttributesW(ExtendedPath(path).c_str(), FILE_ATTRIBUTE_NORMAL);
    if (DeleteFileW(ExtendedPath(path).c_str())) return true;
    code = GetLastError();
  }
  SetLastError(code);
  return false;
}

std::uint64_t FileSize(const std::wstring& path) {
  WIN32_FILE_ATTRIBUTE_DATA data{};
  if (!GetFileAttributesExW(ExtendedPath(path).c_str(), GetFileExInfoStandard,
                            &data)) {
    return UINT64_MAX;
  }
  return (static_cast<std::uint64_t>(data.nFileSizeHigh) << 32) |
         data.nFileSizeLow;
}

std::wstring RenameCandidate(const std::wstring& destination, int index) {
  const size_t slash = destination.find_last_of(L"\\/");
  const size_t dot = destination.find_last_of(L'.');
  const bool hasExtension =
      dot != std::wstring::npos &&
      (slash == std::wstring::npos || dot > slash + 1);
  const std::wstring stem =
      hasExtension ? destination.substr(0, dot) : destination;
  const std::wstring extension =
      hasExtension ? destination.substr(dot) : L"";
  return stem + L" (" + std::to_wstring(index) + L")" + extension;
}

std::wstring ResolveConflict(const std::wstring& destination,
                             const std::wstring& policy, bool& shouldSkip,
                             bool& ok) {
  shouldSkip = false;
  ok = true;
  if (Attributes(destination) == INVALID_FILE_ATTRIBUTES) {
    return destination;
  }
  if (policy == L"skip") {
    shouldSkip = true;
    return destination;
  }
  if (policy == L"overwrite") return destination;
  for (int index = 1; index < 100000; ++index) {
    const std::wstring candidate = RenameCandidate(destination, index);
    if (Attributes(candidate) == INVALID_FILE_ATTRIBUTES) return candidate;
  }
  ok = false;
  SetLastError(ERROR_ALREADY_EXISTS);
  return destination;
}

void ApplyDirectoryMetadata(const std::wstring& source,
                            const DirectoryEntry& entry,
                            const std::wstring& destination) {
  if (!IsDirectory(source)) return;
  HANDLE handle = CreateFileW(
      ExtendedPath(destination).c_str(), FILE_WRITE_ATTRIBUTES,
      FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
      OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, nullptr);
  if (handle != INVALID_HANDLE_VALUE) {
    SetFileTime(handle, &entry.creation, &entry.access, &entry.write);
    CloseHandle(handle);
  }
  const DWORD transferableAttributes =
      entry.attributes & (FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_HIDDEN |
                          FILE_ATTRIBUTE_SYSTEM | FILE_ATTRIBUTE_ARCHIVE |
                          FILE_ATTRIBUTE_NOT_CONTENT_INDEXED);
  SetFileAttributesW(ExtendedPath(destination).c_str(),
                     transferableAttributes);
}

bool ProcessOneFile(const FileEntry& file, const Options& options,
                    const std::wstring& sourceRoot,
                    const std::wstring& destinationRoot, bool sameVolume,
                    SharedCounters& counters) {
  if (g_cancelled.load()) return false;
  const std::wstring source = JoinPath(sourceRoot, file.relative);
  const std::wstring requestedDestination =
      JoinPath(destinationRoot, file.relative);
  bool shouldSkip = false;
  bool conflictOk = true;
  const std::wstring destination =
      ResolveConflict(requestedDestination, options.conflict, shouldSkip,
                      conflictOk);
  if (!conflictOk) {
    DetailedError(requestedDestination, ERROR_ALREADY_EXISTS);
    counters.failedFiles.fetch_add(1);
    return false;
  }
  if (shouldSkip) {
    counters.skippedFiles.fetch_add(1);
    counters.processedFiles.fetch_add(1);
    counters.completedBytes.fetch_add(file.size);
    return true;
  }

  if (!EnsureDirectory(ParentPath(destination))) {
    DetailedError(ParentPath(destination));
    counters.failedFiles.fetch_add(1);
    counters.processedFiles.fetch_add(1);
    counters.completedBytes.fetch_add(file.size);
    return false;
  }

  if (options.dryRun) {
    if (options.mode == L"move") {
      counters.movedFiles.fetch_add(1);
    } else {
      counters.copiedFiles.fetch_add(1);
    }
    counters.processedFiles.fetch_add(1);
    counters.completedBytes.fetch_add(file.size);
    return true;
  }

  bool success = false;
  if (options.mode == L"move" && sameVolume) {
    DWORD moveFlags = 0;
    if (Attributes(destination) != INVALID_FILE_ATTRIBUTES) {
      SetFileAttributesW(ExtendedPath(destination).c_str(),
                         FILE_ATTRIBUTE_NORMAL);
      moveFlags |= MOVEFILE_REPLACE_EXISTING;
    }
    success = MoveFileExW(ExtendedPath(source).c_str(),
                          ExtendedPath(destination).c_str(),
                          moveFlags) != 0;
    if (!success) {
      DetailedError(file.relative + L"（同卷移动）");
    }
  } else {
    success = CopyFileWithMetadata(source, destination);
    if (!success) {
      DetailedError(file.relative + L"（复制）");
    } else if (FileSize(destination) != file.size) {
      SetLastError(ERROR_CRC);
      DetailedError(destination + L"（大小校验失败）", ERROR_CRC);
      success = false;
    } else if (options.mode == L"move" &&
               !DeleteSourceFile(source)) {
      DetailedError(file.relative + L"（目标已复制，但源文件删除失败）");
      success = false;
    }
  }

  if (success) {
    if (options.mode == L"move") {
      counters.movedFiles.fetch_add(1);
    } else {
      counters.copiedFiles.fetch_add(1);
    }
    counters.copiedBytes.fetch_add(file.size);
  } else {
    counters.failedFiles.fetch_add(1);
  }
  counters.processedFiles.fetch_add(1);
  counters.completedBytes.fetch_add(file.size);
  return success;
}

void RemoveMovedSourceDirectories(const std::wstring& sourceRoot,
                                  const ScanResult& scan) {
  std::vector<DirectoryEntry> directories = scan.directories;
  std::sort(directories.begin(), directories.end(),
            [](const DirectoryEntry& left, const DirectoryEntry& right) {
              return left.relative.size() > right.relative.size();
            });
  for (const DirectoryEntry& directory : directories) {
    RemoveDirectoryW(
        ExtendedPath(JoinPath(sourceRoot, directory.relative)).c_str());
  }
  RemoveDirectoryW(ExtendedPath(sourceRoot).c_str());
}

bool TryWholeDirectoryMove(const std::wstring& source,
                           const std::wstring& requestedDestination,
                           const Options& options, std::wstring& actualDestination) {
  if (options.mode != L"move" || options.dryRun || g_cancelled.load() ||
      !SameVolume(source, ParentPath(requestedDestination))) {
    return false;
  }

  actualDestination = requestedDestination;
  if (Attributes(actualDestination) != INVALID_FILE_ATTRIBUTES) {
    if (options.conflict == L"skip") return false;
    if (options.conflict == L"overwrite") return false;
    bool skip = false;
    bool ok = true;
    actualDestination =
        ResolveConflict(requestedDestination, L"rename", skip, ok);
    if (!ok) return false;
  }

  Log(L"[move] 同卷快速移动整个目录：" + source + L" -> " +
      actualDestination);
  if (!MoveFileExW(ExtendedPath(source).c_str(),
                   ExtendedPath(actualDestination).c_str(),
                   MOVEFILE_WRITE_THROUGH)) {
    Error(L"整目录快速移动失败，将回退到逐文件处理：" +
          WindowsErrorText(GetLastError()));
    return false;
  }
  return true;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
  SetConsoleCtrlHandler(ConsoleCtrlHandler, TRUE);
  SetConsoleOutputCP(CP_UTF8);

  Options options;
  if (!ParseOptions(argc, argv, options)) {
    if (!CaseInsensitiveEqual(options.mode, L"help")) PrintUsage();
    return 1;
  }
  if (options.mode != L"move" && options.mode != L"copy") {
    Error(L"--mode 只能是 move 或 copy");
    return 1;
  }
  if (options.conflict != L"skip" && options.conflict != L"rename" &&
      options.conflict != L"overwrite") {
    Error(L"--conflict 只能是 skip、rename 或 overwrite");
    return 1;
  }
  if (options.threads < 1 || options.threads > 32) {
    Error(L"--threads 必须在 1 到 32 之间");
    return 1;
  }
  if (HasMultiplePickedDirectories(options.source) ||
      HasMultiplePickedDirectories(options.target)) {
    Error(L"源文件夹和目标文件夹必须各选择 1 个目录，不能传入多项");
    return 1;
  }

  const std::wstring source = AbsolutePath(options.source);
  const std::wstring target = AbsolutePath(options.target);
  if (source.empty() || target.empty()) {
    Error(L"无法解析源文件夹或目标文件夹路径");
    return 1;
  }
  if (!IsDirectory(source)) {
    Error(L"源路径不存在或不是文件夹：" + source);
    return 1;
  }
  if (IsDriveRoot(source)) {
    Error(L"为安全起见，源文件夹不能直接选择盘符根目录，请选择具体文件夹");
    return 1;
  }
  if (IsReparsePoint(source)) {
    Error(L"源文件夹本身不能是符号链接或目录联接");
    return 1;
  }
  if (!IsDirectory(target)) {
    Error(L"目标路径不存在或不是文件夹：" + target);
    return 1;
  }
  if (IsReparsePoint(target)) {
    Error(L"目标文件夹本身不能是符号链接或目录联接");
    return 1;
  }
  if (IsSameOrChild(source, target) || IsSameOrChild(target, source)) {
    Error(L"源文件夹与目标文件夹不能相同或互相包含");
    return 1;
  }

  const std::wstring destination = JoinPath(target, BaseName(source));
  if (IsSameOrChild(source, destination) ||
      IsSameOrChild(destination, source)) {
    Error(L"计算出的目标子目录与源目录重叠，请换一个目标文件夹");
    return 1;
  }

  Log(L"小文件极速搬运 1.0.0");
  Log(L"[config] 源：" + source);
  Log(L"[config] 目标：" + target);
  Log(L"[config] 目标子目录：" + destination);
  Log(L"[config] 模式：" + options.mode + L"；冲突：" + options.conflict +
      L"；线程：" + std::to_wstring(options.threads) +
      (options.dryRun ? L"；仅预演" : L""));

  std::wstring directDestination;
  if (TryWholeDirectoryMove(source, destination, options, directDestination)) {
    Log(L"完成 100.0%；已通过同卷目录重命名一次移动整个源文件夹。");
    return 0;
  }
  if (g_cancelled.load()) return 3;

  const bool sameVolume = SameVolume(source, destination);
  if (!EnsureDirectory(target)) {
    Error(L"无法创建或访问目标文件夹：" + target);
    return 1;
  }

  Log(L"[scan] 正在枚举目录和文件...");
  ScanResult scan;
  const auto scanStart = std::chrono::steady_clock::now();
  ScanDirectory(source, scan);
  if (g_cancelled.load()) return 3;
  const auto scanEnd = std::chrono::steady_clock::now();
  const double scanSeconds =
      std::chrono::duration<double>(scanEnd - scanStart).count();
  Log(L"[scan] 文件 " + std::to_wstring(scan.files.size()) + L" 个；目录 " +
      std::to_wstring(scan.directories.size() + 1) + L" 个；体积 " +
      FormatBytes(scan.totalBytes) + L"；耗时 " +
      std::to_wstring(static_cast<int>(scanSeconds * 1000)) + L" ms。");
  if (scan.skippedLinks > 0) {
    Log(L"[scan] 已跳过 " + std::to_wstring(scan.skippedLinks) +
        L" 个符号链接/重解析点。");
  }
  if (scan.unreadableDirectories > 0) {
    Log(L"[scan] 有 " + std::to_wstring(scan.unreadableDirectories) +
        L" 个目录无法读取。");
  }

  if (options.dryRun) {
    Log(L"[dry-run] 将处理 " + std::to_wstring(scan.files.size()) +
        L" 个文件，共 " + FormatBytes(scan.totalBytes) + L"。未改动任何文件。");
    return 0;
  }

  if (!EnsureDirectory(destination)) {
    Error(L"无法创建目标子目录：" + destination);
    return 1;
  }
  for (const DirectoryEntry& directory : scan.directories) {
    const std::wstring destinationDirectory =
        JoinPath(destination, directory.relative);
    if (!EnsureDirectory(destinationDirectory)) {
      Error(L"无法创建目录：" + destinationDirectory);
      return 2;
    }
  }

  SharedCounters counters;
  std::atomic<size_t> nextIndex{0};
  const auto copyStart = std::chrono::steady_clock::now();
  std::vector<std::thread> workers;
  workers.reserve(static_cast<size_t>(options.threads));
  for (int index = 0; index < options.threads; ++index) {
    workers.emplace_back([&]() {
      while (!g_cancelled.load()) {
        const size_t workIndex = nextIndex.fetch_add(1);
        if (workIndex >= scan.files.size()) break;
        ProcessOneFile(scan.files[workIndex], options, source, destination,
                       sameVolume, counters);
      }
    });
  }

  auto lastReport = std::chrono::steady_clock::now();
  while (counters.processedFiles.load() < scan.files.size()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(250));
    const auto now = std::chrono::steady_clock::now();
    if (now - lastReport >= std::chrono::milliseconds(500)) {
      const double elapsed =
          std::chrono::duration<double>(now - copyStart).count();
      const std::uint64_t bytes = counters.copiedBytes.load();
      const double rate = elapsed > 0 ? bytes / elapsed : 0;
      Log(L"[progress] " +
          Percent(counters.processedFiles.load(), scan.files.size()) + L"；" +
          std::to_wstring(counters.processedFiles.load()) + L"/" +
          std::to_wstring(scan.files.size()) + L" 文件；已传输 " +
          FormatBytes(bytes) + L"；" +
          std::to_wstring(static_cast<std::uint64_t>(rate / 1024.0 / 1024.0)) +
          L" MiB/s；失败 " +
          std::to_wstring(counters.failedFiles.load()));
      lastReport = now;
    }
    if (g_cancelled.load()) break;
  }
  for (std::thread& worker : workers) worker.join();
  const bool interrupted = g_cancelled.load();
  const auto copyEnd = std::chrono::steady_clock::now();

  if (!options.dryRun) {
    for (const DirectoryEntry& directory : scan.directories) {
      if (!IsDirectory(JoinPath(source, directory.relative))) continue;
      ApplyDirectoryMetadata(source, directory,
                             JoinPath(destination, directory.relative));
    }
    if (options.mode == L"move") {
      RemoveMovedSourceDirectories(source, scan);
    }
  }

  const double seconds =
      std::chrono::duration<double>(copyEnd - copyStart).count();
  const double rate = seconds > 0
                          ? counters.copiedBytes.load() / seconds / 1024.0 / 1024.0
                          : 0;
  Log(L"[summary] 处理 " + std::to_wstring(counters.processedFiles.load()) +
      L"/" + std::to_wstring(scan.files.size()) + L" 个文件；移动 " +
      std::to_wstring(counters.movedFiles.load()) + L"；复制 " +
      std::to_wstring(counters.copiedFiles.load()) + L"；跳过 " +
      std::to_wstring(counters.skippedFiles.load()) + L"；失败 " +
      std::to_wstring(counters.failedFiles.load()) + L"；传输 " +
      FormatBytes(counters.copiedBytes.load()) + L"；平均 " +
      std::to_wstring(static_cast<std::uint64_t>(rate)) + L" MiB/s；耗时 " +
      std::to_wstring(static_cast<std::uint64_t>(seconds * 1000)) + L" ms。");

  if (interrupted && counters.processedFiles.load() < scan.files.size()) {
    Error(L"操作已取消；未处理的源文件保持原样。");
    return 3;
  }
  if (counters.failedFiles.load() > 0 || scan.unreadableDirectories > 0) {
    Error(L"操作结束，但有文件或目录失败。失败项的源文件未被删除。");
    return 2;
  }
  Log(L"完成 100.0%；全部文件处理成功。");
  return 0;
}
