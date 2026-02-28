# PreToolUse Hook: Destructive Operation Prevention

## Current Implementation (212 lines)

**File:** `/Users/forest/.claude/hooks/pre_tool_use.py`

### Exit Code Reference

| Code | Behavior | Usage |
|------|----------|-------|
| `0` | Allow tool call | Normal operations |
| `2` | Hard block, shows error to Claude | Dangerous operations |
| `3` | Prompt user for Yes/No | Sensitive operations (.env access) |

### Architecture

```
stdin (JSON) -> pre_tool_use.py -> exit code
                    |
                    +-- is_env_file_access()          -> exit 3 (ask)
                    +-- is_dangerous_python_rmtree()   -> exit 2 (block)
                    +-- is_dangerous_rm_command()       -> exit 2 (block)
                    +-- log to logs/pre_tool_use.json  -> exit 0 (allow)
```

### Three Protection Layers

1. **`.env` file access** (exit 3 = ask user) -- blocks Read/Write/Edit/Bash access to .env files outside the platform project
2. **Python recursive dir deletion** (exit 2 = hard block) -- blocks shutil.rmtree across Bash/Write/Edit/MultiEdit tools
3. **Shell rm -rf** (exit 2 = hard block) -- blocks dangerous rm command patterns in Bash

---

## Full Source Code

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import sys
import re
from pathlib import Path

def is_dangerous_rm_command(command):
    """
    Comprehensive detection of dangerous rm commands.
    Matches various forms of rm -rf and similar destructive patterns.
    """
    # Normalize command by removing extra spaces and converting to lowercase
    normalized = ' '.join(command.lower().split())

    # Pattern 1: Standard rm -rf variations
    patterns = [
        r'\brm\s+.*-[a-z]*r[a-z]*f',  # rm -rf, rm -fr, rm -Rf, etc.
        r'\brm\s+.*-[a-z]*f[a-z]*r',  # rm -fr variations
        r'\brm\s+--recursive\s+--force',  # rm --recursive --force
        r'\brm\s+--force\s+--recursive',  # rm --force --recursive
        r'\brm\s+-r\s+.*-f',  # rm -r ... -f
        r'\brm\s+-f\s+.*-r',  # rm -f ... -r
    ]

    # Check for dangerous patterns
    for pattern in patterns:
        if re.search(pattern, normalized):
            return True

    # Pattern 2: Check for rm with recursive flag targeting dangerous paths
    dangerous_paths = [
        r'/',           # Root directory
        r'/\*',         # Root with wildcard
        r'~',           # Home directory
        r'~/',          # Home directory path
        r'\$HOME',      # Home environment variable
        r'\.\.',        # Parent directory references
        r'\*',          # Wildcards in general rm -rf context
        r'\.',          # Current directory
        r'\.\s*$',      # Current directory at end of command
    ]

    if re.search(r'\brm\s+.*-[a-z]*r', normalized):  # If rm has recursive flag
        for path in dangerous_paths:
            if re.search(path, normalized):
                return True

    return False

def is_env_file_access(tool_name, tool_input):
    """
    Check if any tool is trying to access .env files containing sensitive data.
    """
    if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write', 'Bash']:
        # Check file paths for file-based tools
        if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write']:
            file_path = tool_input.get('file_path', '')
            # Allow platform project .env files
            if '/Applications/ServBay/www/platform/' in file_path:
                return False
            if '.env' in file_path and not file_path.endswith('.env.sample'):
                return True

        # Check bash commands for .env file access
        elif tool_name == 'Bash':
            command = tool_input.get('command', '')
            env_patterns = [
                r'\b\.env\b(?!\.sample)',
                r'cat\s+.*\.env\b(?!\.sample)',
                r'echo\s+.*>\s*\.env\b(?!\.sample)',
                r'touch\s+.*\.env\b(?!\.sample)',
                r'cp\s+.*\.env\b(?!\.sample)',
                r'mv\s+.*\.env\b(?!\.sample)',
            ]

            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True

    return False

# The target function name for recursive dir deletion in the shutil module
_BLOCKED_FUNC = 'rm' + 'tree'
# The module that contains it
_BLOCKED_MOD = 'shut' + 'il'

def is_dangerous_python_rmtree(tool_name, tool_input):
    """
    Aggressively detect Python-level recursive directory deletion that
    bypasses shell rm command inspection. Scans Bash commands (inline Python),
    Write content, and Edit new_string fields.
    """
    # Self-exemption: allow editing this hook file and .md docs in hooks dir
    if tool_name in ('Write', 'Edit', 'MultiEdit'):
        file_path = tool_input.get('file_path', '')
        if file_path == '/Users/forest/.claude/hooks/pre_tool_use.py':
            return False
        if file_path.startswith('/Users/forest/.claude/hooks/') and file_path.endswith('.md'):
            return False

    # Determine what text to scan based on tool type
    texts_to_scan = []

    if tool_name == 'Bash':
        texts_to_scan.append(tool_input.get('command', ''))
    elif tool_name == 'Write':
        texts_to_scan.append(tool_input.get('content', ''))
    elif tool_name == 'Edit':
        texts_to_scan.append(tool_input.get('new_string', ''))
    elif tool_name == 'MultiEdit':
        for edit in tool_input.get('edits', []):
            texts_to_scan.append(edit.get('new_string', ''))

    if not texts_to_scan:
        return False

    # Build patterns dynamically to avoid self-triggering in source code
    mod = _BLOCKED_MOD    # shutil
    func = _BLOCKED_FUNC  # rmtree

    rmtree_patterns = [
        # Direct attribute access with optional whitespace
        mod + r'\s*\.\s*' + func,
        # from <mod> import <func> (possibly among other imports)
        r'from\s+' + mod + r'\s+import\s+[^;]*\b' + func + r'\b',
        # from <mod> import * (wildcard enables bare call)
        r'from\s+' + mod + r'\s+import\s+\*',
        # __import__('<mod>').<func> -- dynamic import evasion
        r"""__import__\s*\(\s*['"]""" + mod + r"""['"]\s*\)\s*\.\s*""" + func,
        # importlib.import_module('<mod>').<func>
        r"""importlib\s*\.\s*import_module\s*\(\s*['"]""" + mod + r"""['"]\s*\)\s*\.\s*""" + func,
        # attr lookup with func name as string -- handles nested parens
        r"""getattr\s*\(.*?['"]""" + func + r"""['"]""",
        # attr lookup with module name and func name together
        r"""getattr\s*\(.*?""" + mod + r""".*?""" + func,
    ]

    for text in texts_to_scan:
        for pattern in rmtree_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

    return False

def main():
    try:
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        if is_env_file_access(tool_name, tool_input):
            print("Permission required: Attempting to access .env file.", file=sys.stderr)
            print("Allow access to environment file?", file=sys.stderr)
            sys.exit(3)

        if is_dangerous_python_rmtree(tool_name, tool_input):
            print("BLOCKED: Python recursive directory deletion detected.", file=sys.stderr)
            print("This bypasses shell rm detection and is not allowed.", file=sys.stderr)
            sys.exit(2)

        if tool_name == 'Bash':
            command = tool_input.get('command', '')
            if is_dangerous_rm_command(command):
                print("BLOCKED: Dangerous rm command detected and prevented", file=sys.stderr)
                sys.exit(2)

        # Log tool usage
        log_dir = Path.cwd() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.json'

        if log_path.exists():
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        log_data.append(input_data)

        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)

if __name__ == '__main__':
    main()
```

---

## Test Results (13/13 passing)

```
--- Should ALLOW ---
  ALLOWED: Normal ls command
  ALLOWED: Normal Write
  ALLOWED: Edit hook file (self-exempt)
  ALLOWED: Normal Edit

--- Should BLOCK ---
  BLOCKED: Direct module.func (shutil.rmtree)
  BLOCKED: from X import Y (from shutil import rmtree)
  BLOCKED: from X import * (from shutil import *)
  BLOCKED: __import__ evasion (__import__('shutil').rmtree)
  BLOCKED: importlib evasion (importlib.import_module('shutil').rmtree)
  BLOCKED: getattr evasion (getattr(__import__('shutil'), 'rmtree'))
  BLOCKED: Write with blocked content
  BLOCKED: Edit with blocked content
  BLOCKED: Spaced attribute access (shutil . rmtree)

--- Results: 13 passed, 0 failed ---
```

---

## Design Patterns Worth Noting

### Self-Protecting Code (Anti-Bootstrapping)

The hook uses string concatenation (`'rm' + 'tree'`) for blocked identifiers so the source code itself does not contain the literal patterns it detects. Without this, the hook would block edits to its own source file via the Write/Edit tool scanners.

### Self-Exemption Path

The hook exempts its own file path and `.md` files in the hooks directory from Write/Edit scanning so it remains editable and documentable. Without this, the hook becomes permanently unmodifiable through Claude Code tools.

### Dynamic Pattern Construction

Patterns are built at runtime from split constants, keeping the source clean while generating correct regex at execution time.

---

## KNOWN WEAKNESSES IN CURRENT IMPLEMENTATION

These are gaps in the current code that an agent could exploit TODAY.

### W1. Variable Indirection Bypasses rm Detection

The rm detector normalizes and scans the command string, but shell variable expansion happens at runtime, not in the string:

```bash
CMD=rm; $CMD -rf /important        # $CMD expands at runtime, hook sees "$CMD"
alias nuke='rm -rf'; nuke /path    # alias expansion not visible to hook
```

**Fix:** Also scan for suspicious variable-to-rm assignment patterns like `CMD=rm` or `alias.*=.*rm`.

### W2. rm --no-preserve-root Not Caught

GNU coreutils rm has `--no-preserve-root` which explicitly enables deleting `/`:

```bash
rm -r --no-preserve-root /
```

The current patterns check for `-rf` combinations but not `--no-preserve-root`.

**Fix:** Add `r'\brm\s+.*--no-preserve-root'` to the patterns list.

### W3. .env Detection Misses Shell Sourcing

The .env detector catches `cat .env`, `cp .env`, etc. but misses:

```bash
source .env                  # loads all vars into shell
. .env                       # POSIX equivalent
set -a && . .env && set +a   # export all vars from .env
env $(cat .env | xargs)      # parse and use .env contents
```

**Fix:** Add patterns for `source\s+.*\.env`, `\.\s+.*\.env`, and `env\s+.*cat.*\.env`.

### W4. .env Detection Misses Encoded Access

```bash
base64 < .env                    # exfiltrate via encoding
xxd .env                         # hex dump
od .env                          # octal dump
python3 -c "print(open('.env').read())"  # Python file read
```

**Fix:** Add patterns for `base64\s+.*\.env`, `xxd\s+.*\.env`, `od\s+.*\.env`, and Python open() with .env paths.

### W5. Cross-Tool Attack Chains (Write-then-Execute)

An agent can split the attack across two tool calls:
1. **Write tool:** Create `/tmp/cleanup.py` with innocent-looking name but destructive content
2. **Bash tool:** Run `python3 /tmp/cleanup.py` -- the Bash command contains no blocked patterns

The Write tool blocks the content, but the Bash tool running the script does NOT -- it just sees `python3 /tmp/cleanup.py`.

**Fix:** Track recently-written Python/shell files and flag their execution. Or: scan file contents before allowing `python3 <path>` execution (via PostToolUse or a file hash registry).

### W6. Self-Exemption Could Be Exploited

The hook exempts any `.md` file in `/Users/forest/.claude/hooks/`. An agent could:
1. Write a file named `exploit.md` to the hooks directory containing dangerous content
2. Then rename it to `.py` and execute it

**Fix:** Consider narrowing the exemption to specific known filenames rather than all `.md` files.

---

## IMPROVEMENT IDEAS: Organized by Category

### Category A: Shell-Level Destructive Commands (Bash tool)

All patterns in this category apply to Bash `command` field scanning.

#### A1. Block `git clean -fdx` -- Removes Untracked Files

Recursively removes all untracked files and directories, including ignored ones with `-x`:

```python
git_clean_patterns = [
    r'\bgit\s+clean\s+.*-[a-z]*f',       # git clean -f, -fd, -fdx
    r'\bgit\s+clean\s+--force',           # git clean --force
]
```

**Severity:** exit 2 (hard block). There is almost never a legitimate reason for an agent to run git clean -fdx.

#### A2. Block `find ... -delete` and `find ... -exec rm`

```python
find_delete_patterns = [
    r'\bfind\s+.*-delete\b',              # find ... -delete
    r'\bfind\s+.*-exec\s+rm\b',           # find ... -exec rm {} \;
    r'\bfind\s+.*-exec\s+/bin/rm\b',      # absolute path variant
    r'\bfind\s+.*\|\s*xargs\s+rm\b',      # find ... | xargs rm
]
```

**Severity:** exit 3 (ask user). find -delete has legitimate uses for cache cleanup.

#### A3. Block `dd` Disk Overwrite

```python
dd_patterns = [
    r'\bdd\s+.*if=/dev/(zero|random|urandom)\s+.*of=',  # zero-fill a target
    r'\bdd\s+.*of=/dev/',                 # writing TO a device file
]
```

**Severity:** exit 2 (hard block).

#### A4. Block `mkfs` / `newfs` -- Filesystem Formatting

```python
format_patterns = [
    r'\bmkfs\b',                          # mkfs.ext4, mkfs.xfs, etc.
    r'\bnewfs\b',                          # macOS/BSD equivalent
    r'\bdiskutil\s+eraseDisk\b',           # macOS disk erase
    r'\bdiskutil\s+eraseVolume\b',         # macOS volume erase
]
```

**Severity:** exit 2 (hard block).

#### A5. Block `truncate` / File Zeroing

```python
truncate_patterns = [
    r'\btruncate\s+.*-s\s*0\b',           # truncate -s 0 file (zero out)
    r'\bshred\b',                          # secure file destruction
    r'>\s+/[^\s]',                         # > /path (redirect to truncate)
]
```

**Severity:** exit 2 for shred. exit 3 for truncate (has legitimate uses).

#### A6. Block `rsync --delete` to Dangerous Targets

```python
rsync_patterns = [
    r'\brsync\s+.*--delete',              # rsync with delete flag
]
```

**Severity:** exit 3 (ask user). rsync --delete is common in deployments but dangerous if targeting wrong paths.

#### A7. Block `curl | bash` / `wget | bash` -- Remote Code Execution

```python
pipe_exec_patterns = [
    r'\bcurl\s+.*\|\s*(ba)?sh\b',         # curl ... | bash
    r'\bwget\s+.*\|\s*(ba)?sh\b',         # wget ... | bash
    r'\bcurl\s+.*\|\s*python',            # curl ... | python
    r'\bwget\s+.*\|\s*python',            # wget ... | python
    r'\bcurl\s+.*\|\s*sudo\b',            # curl ... | sudo
]
```

**Severity:** exit 2 (hard block). Downloading and executing remote code is always dangerous.

#### A8. Block Process Kill-All Patterns

```python
kill_all_patterns = [
    r'\bkill\s+-9\s+-1\b',               # kill -9 -1 (kill ALL processes)
    r'\bkillall\s+-9\b',                  # killall -9 (force kill by name)
    r'\bpkill\s+-9\s+-u\b',              # pkill -9 -u (kill all user procs)
]
```

**Severity:** exit 2 for `kill -9 -1`. exit 3 for others.

#### A9. Block `chmod -R 000` / `chmod -R 777`

```python
chmod_patterns = [
    r'\bchmod\s+.*-[a-z]*R.*\b0{3,4}\b',   # chmod -R 000 (lock out)
    r'\bchmod\s+.*-[a-z]*R.*\b777\b',       # chmod -R 777 (world writable)
    r'\bchmod\s+.*-[a-z]*R.*\ba\+w\b',      # chmod -R a+w (world writable)
]
```

**Severity:** exit 2 (hard block).

#### A10. Block `rm --no-preserve-root`

```python
rm_root_patterns = [
    r'\brm\s+.*--no-preserve-root',
]
```

**Severity:** exit 2 (hard block).

---

### Category B: Python-Level Destructive Operations (Bash + Write + Edit)

All patterns in this category apply across Bash commands (inline Python), Write content, and Edit new_string fields -- same multi-tool scanning as the current rmtree detector.

#### B1. Block `os.removedirs()` -- Recursive Directory Removal

```python
_OS_REMOVEDIRS = 'remove' + 'dirs'

os_removedirs_patterns = [
    r'os\s*\.\s*' + _OS_REMOVEDIRS,
    r'from\s+os\s+import\s+[^;]*\b' + _OS_REMOVEDIRS + r'\b',
]
```

**Severity:** exit 2 (hard block).

#### B2. Block `subprocess.run(['rm', ...])` / `os.system('rm ...')`

Python subprocess can bypass the shell rm detector because the Bash command is just `python3 script.py`:

```python
subprocess_rm_patterns = [
    r"""subprocess\s*\.\s*(run|call|Popen|check_call|check_output)\s*\(\s*\[.*?['"]rm['"]""",
    r"""os\s*\.\s*system\s*\(.*?\brm\s+""",
    r"""os\s*\.\s*popen\s*\(.*?\brm\s+""",
    r"""os\s*\.\s*exec[lv]p?\s*\(.*?['"]rm['"]""",
]
```

**Severity:** exit 2 (hard block).

#### B3. Block `os.walk()` + `os.remove()` -- Manual Recursive Delete

An agent could reimplement rmtree manually:

```python
# Use re.DOTALL to match across lines
walk_rm_patterns = [
    r'os\s*\.\s*walk\b.*?os\s*\.\s*(remove|rmdir|unlink)',  # DOTALL needed
]
```

**Severity:** exit 3 (ask user). os.walk has many legitimate uses; only suspicious when combined with deletion.

#### B4. Block `pathlib` Recursive Operations

```python
pathlib_patterns = [
    r'\.rglob\s*\(.*?\).*?\.unlink',      # Path.rglob('*').unlink() pattern
    r'Path\s*\(.*?\)\s*\.\s*rmdir',        # Path(...).rmdir()
    r'\.iterdir\s*\(.*?\).*?\.unlink',     # iterate + delete pattern
]
```

**Severity:** exit 3 (ask user).

#### B5. Block Dangerous Deserialization

Pickle, marshal, and YAML can execute arbitrary code during deserialization:

```python
deser_patterns = [
    r'pickle\s*\.\s*loads?\b',             # pickle.load / pickle.loads
    r'marshal\s*\.\s*loads?\b',            # marshal.load / marshal.loads
    r'yaml\s*\.\s*load\b(?!.*SafeLoader)', # yaml.load without SafeLoader
    r'yaml\s*\.\s*unsafe_load\b',          # yaml.unsafe_load (explicit unsafe)
]
```

**Severity:** exit 3 (ask user). These have legitimate uses but are common exploit vectors.

#### B6. Block Encoded Execution (eval/exec with Encoding)

An agent could encode the dangerous call inside eval/exec with base64 or other encoding:

```python
encoded_exec_patterns = [
    r'exec\s*\(\s*base64\s*\.\s*b64decode',     # exec(base64.b64decode(...))
    r'eval\s*\(\s*base64\s*\.\s*b64decode',     # eval(base64.b64decode(...))
    r'exec\s*\(\s*bytes\s*\.\s*fromhex',        # exec(bytes.fromhex(...))
    r'eval\s*\(\s*bytes\s*\.\s*fromhex',        # eval(bytes.fromhex(...))
    r'exec\s*\(\s*codecs\s*\.\s*decode',        # exec(codecs.decode(...))
    r"""exec\s*\(\s*['"].*?\\x""",               # exec with hex escapes
    r"exec\s*\(\s*compile\s*\(",                 # exec(compile(...))
]
```

**Severity:** exit 2 (hard block). There is no legitimate reason for an agent to eval decoded base64/hex.

---

### Category C: Database Destructive Operations (Bash tool)

#### C1. Block SQL DROP / TRUNCATE

```python
sql_patterns = [
    r'\bDROP\s+(DATABASE|TABLE|SCHEMA|INDEX)\b',
    r'\bTRUNCATE\s+(TABLE\s+)?\w',
    r'\bDELETE\s+FROM\s+\w+\s*;',           # DELETE without WHERE clause
    r'\bALTER\s+TABLE\s+\w+\s+DROP\b',      # ALTER TABLE ... DROP COLUMN
]
```

**Severity:** exit 3 (ask user). Some DROP operations are intentional during migrations.

#### C2. Block NoSQL Destructive Operations

```python
nosql_patterns = [
    r'db\s*\.\s*dropDatabase\s*\(',          # MongoDB dropDatabase
    r'\.drop\s*\(\s*\)',                     # MongoDB collection.drop()
    r'\bFLUSHALL\b',                         # Redis FLUSHALL
    r'\bFLUSHDB\b',                          # Redis FLUSHDB
]
```

**Severity:** exit 2 (hard block).

---

### Category D: Container / Infrastructure (Bash tool)

#### D1. Block Docker Destructive Operations

```python
docker_patterns = [
    r'\bdocker\s+system\s+prune\s+.*-a',     # docker system prune -af
    r'\bdocker\s+volume\s+rm\b',              # docker volume rm
    r'\bdocker\s+volume\s+prune\b',           # docker volume prune
    r'\bdocker\s+(rm|rmi)\s+.*-f',            # docker rm -f / docker rmi -f
]
```

**Severity:** exit 3 (ask user).

#### D2. Block Kubernetes Destructive Operations

```python
k8s_patterns = [
    r'\bkubectl\s+delete\s+(namespace|ns)\b', # kubectl delete namespace
    r'\bkubectl\s+delete\s+.*--all\b',        # kubectl delete ... --all
    r'\bhelm\s+uninstall\b',                  # helm uninstall
]
```

**Severity:** exit 3 (ask user).

---

### Category E: Credential / Secret Exfiltration (Bash tool)

#### E1. Block SSH Key Access

```python
ssh_patterns = [
    r'cat\s+.*\.ssh/(id_|authorized_keys)',    # cat ~/.ssh/id_rsa
    r'cp\s+.*\.ssh/',                          # cp from .ssh
    r'scp\s+.*\.ssh/',                         # scp from .ssh
    r'base64\s+.*\.ssh/',                      # encode ssh keys
]
```

**Severity:** exit 2 (hard block).

#### E2. Block Token / Credential File Access

```python
cred_patterns = [
    r'cat\s+.*(credentials|\.aws/|\.kube/config|\.npmrc|\.pypirc)',
    r'cat\s+.*\.netrc',
    r'cat\s+.*token',
    r'base64\s+.*(credentials|\.aws/|\.kube/)',
]
```

**Severity:** exit 3 (ask user).

#### E3. Block Network Exfiltration of Sensitive Files

```python
exfil_patterns = [
    r'curl\s+.*-d\s+@.*\.(env|pem|key)',        # curl -d @file.env (POST file contents)
    r'curl\s+.*--data.*\.(env|pem|key)',         # curl --data variant
    r'curl\s+.*-F\s+.*\.(env|pem|key)',          # curl -F (form upload)
    r'nc\s+.*<\s*.*\.(env|pem|key)',             # netcat file send
]
```

**Severity:** exit 2 (hard block).

---

### Category F: Write Tool Path Restrictions

#### F1. Block Writes to Shell Config Files

An agent could inject malicious commands into shell startup files:

```python
shell_config_paths = [
    '.bashrc', '.bash_profile', '.zshrc', '.zprofile',
    '.profile', '.login', '.bash_login',
]

if tool_name == 'Write':
    file_path = tool_input.get('file_path', '')
    if any(file_path.endswith(p) for p in shell_config_paths):
        # exit 3 (ask user)
```

**Severity:** exit 3 (ask user).

#### F2. Block Writes to Crontab / LaunchAgent

Deferred execution via scheduled tasks:

```python
scheduled_paths = [
    '/etc/crontab',
    'crontab',
    'LaunchAgents/',
    'LaunchDaemons/',
    '/etc/cron.',
]
```

**Severity:** exit 2 (hard block).

#### F3. Block Writes to Git Hooks

An agent could write malicious code to `.git/hooks/pre-commit` etc.:

```python
git_hook_paths = [
    '.git/hooks/',
]

if tool_name in ('Write', 'Edit') and '.git/hooks/' in file_path:
    # exit 3 (ask user)
```

**Severity:** exit 3 (ask user).

---

### Category G: Architectural Improvements

#### G1. Pattern Registry Architecture

Replace scattered pattern lists with a centralized registry:

```python
PATTERNS = {
    'shell_rm': {
        'severity': 2,          # exit code
        'tools': ['Bash'],      # which tools to scan
        'field': 'command',     # which field
        'patterns': [...],
        'message': 'Dangerous rm command detected',
    },
    'python_rmtree': {
        'severity': 2,
        'tools': ['Bash', 'Write', 'Edit', 'MultiEdit'],
        'field': 'auto',        # command/content/new_string based on tool
        'patterns': [...],
        'message': 'Python recursive directory deletion detected',
    },
    # ... each category registers here
}
```

**Benefits:**
- All patterns in one place for auditing
- Consistent severity handling
- Easy to add new categories
- Self-documenting

#### G2. Structured Logging with Timestamps and Severity

```python
import datetime

def log_event(input_data, severity='info', reason=None):
    log_dir = Path.cwd() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'pre_tool_use.json'

    entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'severity': severity,    # info, warn, blocked
        'reason': reason,
        'tool_name': input_data.get('tool_name'),
        'tool_input_preview': str(input_data.get('tool_input', {}))[:200],
    }
    # ... append to log
```

This enables post-session analysis: "show me all blocked attempts in the last hour."

#### G3. Rate Limiting / Escalation

Track blocked attempts and escalate if repeated:

```python
BLOCK_LOG = Path('/tmp/claude_hook_blocks.json')

def record_block(reason):
    """Record a block event with timestamp."""
    blocks = json.loads(BLOCK_LOG.read_text()) if BLOCK_LOG.exists() else []
    blocks.append({'time': time.time(), 'reason': reason})
    # Keep last 50 entries
    BLOCK_LOG.write_text(json.dumps(blocks[-50:]))

def check_block_rate():
    """If >5 blocks in last 10 minutes, emit session-level warning."""
    if not BLOCK_LOG.exists():
        return
    blocks = json.loads(BLOCK_LOG.read_text())
    cutoff = time.time() - 600  # 10 minutes
    recent = [b for b in blocks if b['time'] > cutoff]
    if len(recent) > 5:
        print("ALERT: Multiple destructive command attempts in this session.", file=sys.stderr)
        print(f"Blocked {len(recent)} times in the last 10 minutes.", file=sys.stderr)
```

#### G4. File Hash Registry (Cross-Tool Chain Defense)

Track files written by the Write tool, then flag when Bash tries to execute them:

```python
WRITTEN_FILES = Path('/tmp/claude_written_files.json')

# In PostToolUse hook (after Write completes):
def track_written_file(file_path):
    files = json.loads(WRITTEN_FILES.read_text()) if WRITTEN_FILES.exists() else {}
    files[file_path] = {'time': time.time(), 'hash': hash_file(file_path)}
    WRITTEN_FILES.write_text(json.dumps(files))

# In PreToolUse hook (before Bash executes):
def check_executing_written_file(command):
    """Flag if Bash is executing a file that was recently written by Write tool."""
    if not WRITTEN_FILES.exists():
        return False
    files = json.loads(WRITTEN_FILES.read_text())
    for path in files:
        if path in command and (path.endswith('.py') or path.endswith('.sh')):
            return True  # Ask user before executing recently-written script
    return False
```

This is the most effective defense against the Write-then-Execute chain attack (W5).

#### G5. NotebookEdit Tool Coverage

Currently missing from all scanners:

```python
elif tool_name == 'NotebookEdit':
    texts_to_scan.append(tool_input.get('new_source', ''))
```

Add to every content scanner, not just the rmtree detector.

#### G6. Allowlist for Safe Paths (Graduated Response)

Instead of binary block/allow, use graduated severity based on the target path:

```python
SAFE_DELETION_PATHS = [
    '/tmp/',
    'node_modules/.cache/',
    '.vite/',
    '__pycache__/',
    'dist/',
    '.next/',
    '.turbo/',
    '.cache/',
]

CRITICAL_PATHS = [
    '/',
    '/etc/',
    '/usr/',
    '/var/',
    '/home/',
    '/Users/',
    '~/',
    '$HOME/',
    '.ssh/',
    '.claude/',
    '.git/',
]

def get_path_severity(command_or_content):
    """Return exit code based on target path risk level."""
    for path in CRITICAL_PATHS:
        if path in command_or_content:
            return 2  # Hard block
    for path in SAFE_DELETION_PATHS:
        if path in command_or_content:
            return 3  # Ask user
    return 3  # Default: ask user for unknown paths
```

#### G7. Configuration File

Move hardcoded values to a config file for easy tuning without code changes:

```json
// ~/.claude/hooks/prevention.config.json
{
  "self_exempt_paths": [
    "/Users/forest/.claude/hooks/pre_tool_use.py"
  ],
  "safe_deletion_paths": ["/tmp/", "node_modules/.cache/"],
  "critical_paths": ["/", "/etc/", "~/.ssh/"],
  "project_allowlist": ["/Applications/ServBay/www/platform/"],
  "severity_overrides": {
    "git_clean": 3,
    "docker_prune": 3
  }
}
```

---

### Category H: Advanced Evasion Defenses

#### H1. String Concatenation Detection

An agent could split the module name to evade pattern matching -- the same technique WE use to protect our source code:

```python
# Agent evasion: mod = 'shut' + 'il'; getattr(__import__(mod), 'rmtree')
concat_patterns = [
    r"""['"]shut['"]\s*\+\s*['"]il['"]""",    # 'shut' + 'il'
    r"""['"]rm['"]\s*\+\s*['"]tree['"]""",     # 'rm' + 'tree'
]
```

**Severity:** exit 2 (hard block). If an agent is concatenating these specific strings, it is actively evading detection.

#### H2. Base64/Hex Encoded Module Names

```python
# Agent evasion: exec(base64.b64decode('aW1wb3J0IHNodXRpbDsgc2h1dGlsLnJtdHJlZSgiLyIp'))
encoded_import_patterns = [
    r'exec\s*\(\s*base64\s*\.\s*b64decode',
    r'eval\s*\(\s*base64\s*\.\s*b64decode',
    r'exec\s*\(\s*bytes\s*\.\s*fromhex',
    r'exec\s*\(\s*codecs\s*\.\s*decode',
    r"""exec\s*\(\s*['"].*\\x""",             # hex escape sequences
]
```

**Severity:** exit 2 (hard block). Encoded exec/eval is a strong signal of evasion.

#### H3. Reversed String Detection

```python
# Agent evasion: exec(''.join(reversed(')"/" (eertmr.lituhS tropmi')))
reversed_patterns = [
    r"reversed\s*\(\s*['\"].*?(eertmr|lituh)",   # reversed rmtree or shutil
    r"[::\s*-1\s*].*?(eertmr|lituh)",             # string[::-1] reversal
]
```

**Severity:** exit 2 (hard block).

#### H4. sys.modules Manipulation

```python
# Agent evasion: sys.modules['shutil'].rmtree('/')
sys_modules_patterns = [
    r"""sys\s*\.\s*modules\s*\[.*?['"]shut""" + 'il' + r"""['"]""",
]
```

**Severity:** exit 2 (hard block).

#### H5. ctypes / cffi Foreign Function Calls

An agent could use ctypes to call C-level unlink/rmdir directly:

```python
ctypes_patterns = [
    r'ctypes\s*\.\s*CDLL',                   # Loading shared libraries
    r'ctypes\s*\.\s*cdll',                    # ctypes.cdll.LoadLibrary
    r'cffi\b',                                # cffi foreign function interface
]
```

**Severity:** exit 3 (ask user). ctypes has legitimate uses but is suspicious in agent context.

---

## PRIORITY IMPLEMENTATION ORDER

Ranked by risk (exploitability x damage potential):

| Priority | ID | Category | Reason |
|----------|----|----------|--------|
| **P0** | W5 | Cross-tool chain | Write + Execute completely bypasses all detection |
| **P0** | B2 | subprocess.run rm | Direct bypass of shell rm detection |
| **P0** | B6 | Encoded exec | Bypasses ALL pattern matching |
| **P0** | H1 | String concat evasion | Agent uses our own technique against us |
| **P1** | A7 | curl pipe bash | Remote code execution |
| **P1** | E1 | SSH key access | Credential theft |
| **P1** | E3 | Network exfiltration | Data theft via curl/nc |
| **P1** | W1 | Variable indirection | Trivial rm bypass |
| **P1** | A1 | git clean | Common destructive command |
| **P2** | C1 | SQL DROP | Database destruction |
| **P2** | F1 | Shell config writes | Deferred execution |
| **P2** | F2 | Crontab writes | Scheduled attacks |
| **P2** | A3 | dd overwrite | Disk destruction |
| **P2** | B1 | os.removedirs | Directory deletion |
| **P3** | G1 | Pattern registry | Code organization |
| **P3** | G2 | Structured logging | Observability |
| **P3** | G3 | Rate limiting | Escalation |
| **P3** | G6 | Graduated response | Fewer false positives |
