# Phase 2 — System Resource Discovery

## Delivery status

This branch adds the first integrated, read-only system-resource inventory for Windows. It is built as an additive service and a typed automation action; it does not modify the permission architecture or invoke privileged execution.

The inventory is generated on demand. There is no background scanner, database index, or automatic full-drive crawl.

## Supported request categories

The deterministic voice/typed-command parser recognizes explicit requests such as:

| Request | Inventory scope |
| --- | --- |
| `Show system info` | OS, architecture, processor, logical CPU count, physical memory |
| `Show system resources` / `Show system inventory` | Combined system, installed-app, process, visible-window, and logical-drive inventory |
| `List installed applications` | Registered Start Menu entries and Windows App Paths names |
| `Show running processes` | Process image name, PID, and reported memory |
| `What apps are open?` | Visible titled windows, process identity, and foreground window |
| `List logical drives` | Drive letter, type, accessibility, and capacity |
| `Find a file named report across all drives` | Bounded file/folder name search on accessible volumes |

The same parser is used by the contextual-interpreter fast path, intent classifier, and deterministic automation router. These complete requests do not require the LLM. Pending confirmation or clarification state still takes precedence.

## Service API

The service is in `engine/system_resources.py`.

- `discover_system_resources(scopes=None)` returns a point-in-time in-memory inventory for the system, applications, processes, visible windows, and logical drives.
- `discover_system_resources(["files"], query="report")` runs an explicit filename/folder-name search across accessible drives.
- `parse_system_resource_request(text)` recognizes the supported natural-language request forms.
- The result includes a schema version, UTC generation timestamp, and the scopes that were requested.

## Safety and privacy boundaries

1. **Read-only.** Discovery does not launch, close, kill, modify, install, uninstall, or delete anything.
2. **Central policy.** The action type `discover_system_resources` is explicitly classified as ordinary. It still passes through `execute_action` and the existing audit writer. It is not a shell action and does not request administrator access.
3. **No arbitrary command execution.** Process listing uses the fixed argument list `tasklist.exe /FO CSV /NH` with `shell=False`. No user-provided text is interpolated into a command.
4. **Minimal process data.** The process inventory reports image name, PID, and memory only. It does not collect command lines, owner names, or full executable paths.
5. **Window inspection is bounded.** Only visible, titled top-level windows are listed. Window titles and process names are returned for the immediate response; the full inventory is not written to long-term conversation memory.
6. **Application discovery reports names.** Start Menu/App Paths sources are merged and aliases are normalized. Shortcut paths and packaged-app identifiers are not returned.
7. **No file-content access.** Cross-drive search matches names only. It does not open documents, inspect file contents, or build a persistent index.
8. **Explicit and bounded file search.** The user must request a specific name and explicitly ask to search across drives. The search is limited to 50 results by default (hard cap 200), 5,000 visited directories by default (hard cap 20,000), and 5 seconds by default (hard cap 20 seconds). Hidden entries, Windows/system folders, symlinks, and reparse-point directories are skipped by default.
9. **No silent action chaining.** A discovered process/window/file is reported, not automatically acted upon. Opening, closing, typing, moving, or deleting continues to use the existing typed action routes and permission policy.

The frontend displays the detailed inventory in the response panel. Speech and the conversation/episode summary receive only a concise count summary, rather than a long process or file listing.

## Coverage limitations

- Installed-app discovery is based on registered Start Menu and App Paths sources. It is useful for discovery and name resolution, but it is not a claim that every installed package or portable executable has been catalogued.
- Process, window, and logical-drive enumeration are Windows-specific. On other operating systems those Windows inventory sections return empty results.
- A drive search is best-effort and can stop at its result, directory, or time limit. A truncated result is explicitly marked.
- The inventory is a snapshot. It does not keep a live process/window feed or continually refresh itself.
- The service does not yet offer process termination, application lifecycle control based on arbitrary PIDs, automatic file indexing, or content search. Those are separate features and must retain their own safety review.

## Verification still required

CI tests cover CSV parsing, alias deduplication, bounded drive searches, scope validation, deterministic parsing, LLM bypass, typed action routing, ordinary policy classification, and audit recording. A real Windows machine check is still required for Win32 process/window/drive enumeration and voice/UI behavior.


## Runtime data accuracy improvements

The current resource-inventory implementation supplements the initial Phase 2 collectors with additional live Windows sources:

- **OS edition and revision:** `EditionID`, `DisplayVersion`, `CurrentBuildNumber`, and `UBR` from the 64-bit Windows CurrentVersion registry view. The display edition is mapped from the runtime edition identifier; the Windows 10/11 family is determined from the runtime build.
- **Processor identity:** `ProcessorNameString`, `Identifier`, `VendorIdentifier`, and `~MHz` from the Windows CentralProcessor registry key. Physical cores are counted from `GetLogicalProcessorInformationEx`; logical processors come from the running Python/OS view (`os.cpu_count`).
- **Memory:** installed RAM is queried through `GetPhysicallyInstalledSystemMemory`; usable and available physical RAM are read through `GlobalMemoryStatusEx`. Used bytes and the percentage are calculated from the returned runtime values. The report labels installed RAM separately from usable RAM.
- **Application evidence:** uninstall registry records are reported as conventional installed desktop applications; Start Menu AppUserModelID entries are reported as packaged applications; App Paths entries are reported as registered executables; shortcut-only entries are explicitly marked as installation-unverified; uninstall entries marked as system components/updates are reported separately.
- **Storage:** drive type, volume label and filesystem are queried at runtime; disk capacity, used and free bytes come from the mounted volume's disk-usage API. An empty optical drive can legitimately report unknown capacity/filesystem.

No machine-specific model, RAM size, processor count, application list, volume label, or capacity is embedded in the inventory code. Missing or inaccessible sources remain `unknown` rather than being filled with example values.

The CPU clock from the `~MHz` registry value is a registry-reported clock value, not a live per-core frequency measurement. The memory-use percentage is calculated from the current total and available physical-memory values, not a hardcoded threshold.
