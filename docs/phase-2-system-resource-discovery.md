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
| `Show application process relationships` | Evidence-based application ↔ process ↔ visible-window mapping |
| `Which processes belong to Chrome?` | Relationship rows filtered to the requested application/process |
| `List logical drives` | Drive letter, type, accessibility, and capacity |
| `Find a file named report across all drives` | Bounded file/folder name search on accessible volumes |

The same parser is used by the contextual-interpreter fast path, intent classifier, and deterministic automation router. These complete requests do not require the LLM. Pending confirmation or clarification state still takes precedence.

## Service API

The service is in `engine/system_resources.py`.

- `discover_system_resources(scopes=None)` returns a point-in-time in-memory inventory for the system, applications, processes, visible windows, and logical drives.
- `discover_system_resources(["files"], query="report")` runs an explicit filename/folder-name search across accessible drives.
- `discover_system_resources(["relationships"])` builds a point-in-time application/process/window relationship map without including dependency inventories in the response.
- `build_application_process_relationships(applications, processes, windows)` is the deterministic in-memory join. It prefers exact executable paths, then registered install-location containment, then unique executable basenames.
- `parse_system_resource_request(text)` recognizes the supported natural-language request forms.
- The result includes a schema version, UTC generation timestamp, and the scopes that were requested.

## Safety and privacy boundaries

1. **Read-only.** Discovery does not launch, close, kill, modify, install, uninstall, or delete anything.
2. **Central policy.** The action type `discover_system_resources` is explicitly classified as ordinary. It still passes through `execute_action` and the existing audit writer. It is not a shell action and does not request administrator access.
3. **No arbitrary command execution.** Process listing uses the fixed argument list `tasklist.exe /FO CSV /NH` with `shell=False`. No user-provided text is interpolated into a command.
4. **Minimal process data.** The ordinary process inventory reports image name, PID, and memory only. It does not collect command lines or owner names. Full executable image paths are queried with process-query-limited access only during an explicit relationship request; they stay in memory for matching and are removed before a response is returned.
5. **Window inspection is bounded.** Only visible, titled top-level windows are listed. Window titles and process names are returned for the immediate response; the full inventory is not written to long-term conversation memory.
6. **Application discovery reports names.** Uninstall registry, Start Menu, packaged-app and App Paths sources are merged and aliases are normalized. Executable targets and installation folders are held only as short-lived internal relationship evidence; they are not returned as raw paths.
7. **No file-content access.** Cross-drive search matches names only. It does not open documents, inspect file contents, or build a persistent index.
8. **Explicit and bounded file search.** The user must request a specific name and explicitly ask to search across drives. The search is limited to 50 results by default (hard cap 200), 5,000 visited directories by default (hard cap 20,000), and 5 seconds by default (hard cap 20 seconds). Hidden entries, Windows/system folders, symlinks, and reparse-point directories are skipped by default.
9. **No silent action chaining.** A discovered process/window/file is reported, not automatically acted upon. Opening, closing, typing, moving, or deleting continues to use the existing typed action routes and permission policy.

The frontend displays the detailed inventory in the response panel. Speech and the conversation/episode summary receive only a concise count summary, rather than a long process or file listing.

## Coverage limitations

- Installed-app discovery is based on registered Start Menu and App Paths sources. It is useful for discovery and name resolution, but it is not a claim that every installed package or portable executable has been catalogued.
- Process, window, and logical-drive enumeration are Windows-specific. On other operating systems those Windows inventory sections return empty results.
- A drive search is best-effort and can stop at its result, directory, or time limit. A truncated result is explicitly marked.
- The inventory is a snapshot. It does not keep a live process/window feed or continually refresh itself.
- The service does not terminate processes or launch/close applications based on arbitrary PIDs. The relationship map is read-only and does not imply authorization to act on a process.
- A process is mapped only when an exact executable path, verified install-location prefix, or unique executable basename links it to application evidence. If multiple applications claim the same executable name, the row is explicitly ambiguous. Access-denied process paths and unsupported packaged-app hosts can remain unmapped.
- Visible windows are joined to process rows by the exact PID returned by Windows. Window titles are not used to infer the owning application.
- The relationship map is requested explicitly and is not added to every normal system overview. Process image paths are queried only for this scope and are never persisted.
- The service does not offer process termination, application lifecycle control based on arbitrary PIDs, automatic file indexing, or content search. Those are separate features and must retain their own safety review.

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


### Evidence and classification limits

A Start Menu shortcut can point to an installed program, a portable executable, a web link, or a broken target. An App Paths entry is registration evidence, not conclusive proof of a conventional installation. These are therefore not silently classified as installed or portable. The inventory reports them as unverified launch entries. A portable-app label will only be added when the target executable and installation context can be positively established at runtime.

## Phase 2.2 — Application / process / window relationship mapping

The explicit relationship scope creates a read-only point-in-time map:

`Application evidence → executable → running process (PID) → visible window(s) (same PID)`

### Evidence order

1. **Exact executable path:** a live process image path equals a path registered by the application's App Paths entry, uninstall DisplayIcon metadata, or a resolved Start Menu shortcut target.
2. **Registered install-location containment:** the live process image path is under an install directory obtained from uninstall-registry metadata.
3. **Unique executable basename:** the process executable name is claimed by exactly one discovered application record.
4. **Ambiguous / unmapped:** multiple app records claim the basename, or no reliable evidence is available. The service does not select a likely match.

Visible windows are attached to the process by the exact PID returned by Windows. An application can have several processes and a process can own multiple visible windows.

### Data minimization

- Process full image paths are queried only for an explicit relationship request using `PROCESS_QUERY_LIMITED_INFORMATION`.
- Full paths are held only in the current Python call and are stripped before returning the inventory.
- The report includes application label, executable basename, PID, match evidence, visible-window count, and bounded window titles.
- No command line, process owner, environment variables, or executable file contents are collected.
- No process is started, stopped, terminated, or modified.

### Manual Windows verification

After merging, test:

- `Show application process relationships`
- `Which processes belong to Chrome`
- `Show running processes` (must remain the original minimal report)
- `What apps are open?` (window ownership must agree with Task Manager process IDs)

Compare PID values in JARVIS with Task Manager → Details. Expect some processes to remain unmapped or ambiguous; that is the correct result when Windows access or application evidence is insufficient.

## Phase 2.3 — Intelligent application state awareness

The explicit \`application_states\` scope produces a bounded, read-only snapshot of
known applications, running processes, and their top-level windows.

Supported examples:

- \`Show application states\`
- \`Check application state for Chrome\`
- \`What is the state of Brave?\`
- \`Is Visual Studio Code responding?\`
- \`Which applications are running right now?\`

The report separates these states:

- **Foreground:** a related window is the current foreground window.
- **Visible:** at least one related visible window exists.
- **Minimized:** at least one related window is minimized.
- **Running in background:** a verified process exists but no visible window is associated with it.
- **Not running:** no related process was found and the bounded process sample was not saturated.
- **Not verified (process sample limit):** no related process was found, but the process sample reached its configured limit; absence is not treated as proof that the application is closed.
- **Ambiguous:** multiple application records still compete for the same process evidence.

Window responsiveness is derived from the Windows \`IsHungAppWindow\` result when available.
A result is reported as \`unknown\` or \`not_checked_no_window\` when Windows cannot provide a
meaningful check. This is a point-in-time check, not a continuous monitor.

### Safety and evidence boundaries

- Process discovery uses the existing bounded \`tasklist.exe\` inventory and query-limited process image paths.
- Window state uses Win32 visibility/minimized/foreground metadata and the Windows hung-window status check.
- No process command lines, owners, environment variables, file contents, or credentials are collected.
- No process is started, stopped, terminated, or modified.
- No administrator elevation is requested.
- The state inventory is not added to normal system-resource defaults; it runs only after an explicit state query.
- Process sampling and window enumeration are bounded. Absence from a truncated sample is reported as unverified, not closed.
