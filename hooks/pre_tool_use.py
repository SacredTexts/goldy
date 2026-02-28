#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///
"""
PreToolUse Hook: Comprehensive Destructive Operation Prevention
Rename this file to pre_tool_use.py to activate.

Exit codes:
  0 = allow tool call
  2 = hard block (shows error to Claude)
  3 = ask user for permission (Yes/No prompt)

Protection layers (checked in order):
  1. .env file access                  -> exit 3 (ask)
  2. Python destructive code           -> exit 2 (block)
  3. Shell destructive commands        -> exit 2 (block)
  4. Credential / secret exfiltration  -> exit 2 (block)
  5. Dangerous write targets           -> exit 3 (ask)
"""

import json
import sys
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Self-protecting constants: split strings so this source file never contains
# the literal patterns it detects. Without this, the hook blocks edits to
# its own source code.
# ---------------------------------------------------------------------------
_MOD_SHUTIL = 'shut' + 'il'
_FUNC_RMTREE = 'rm' + 'tree'
_FUNC_REMOVEDIRS = 'remove' + 'dirs'

# Severity levels (match Claude Code hook exit codes)
BLOCK = 2
ASK = 3

# ---------------------------------------------------------------------------
# Self-exemption: paths that bypass content scanning for Write/Edit tools.
# Without this, the hook becomes permanently uneditable through Claude Code.
# ---------------------------------------------------------------------------
_HOOK_DIR = str(Path.home() / '.claude' / 'hooks') + '/'
_SELF_PATH = _HOOK_DIR + 'pre_tool_use.py'
_TEST_KIT_DIR = _HOOK_DIR + 'test-kit/'

# ---------------------------------------------------------------------------
# Configuration: optional config file for site-specific allowlists.
# If ~/.claude/hooks/prevention.config.json exists, it is loaded.
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(_HOOK_DIR) / 'prevention.config.json'
_CONFIG = {}
if _CONFIG_PATH.exists():
    try:
        _CONFIG = json.loads(_CONFIG_PATH.read_text())
    except Exception:
        pass

# Paths where .env access is allowed (e.g. your main project directory)
_ENV_ALLOWED_PATHS = _CONFIG.get('env_allowed_paths', [])


def _is_self_exempt(tool_name, tool_input):
    """Allow editing this hook file, docs, and test suite."""
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        return False
    fp = tool_input.get('file_path', '')
    if fp == _SELF_PATH:
        return True
    if fp.startswith(_HOOK_DIR) and fp.endswith('.md'):
        return True
    if fp.startswith(_TEST_KIT_DIR):
        return True
    return False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _get_scannable_texts(tool_name, tool_input):
    """Extract the text fields to scan from a tool invocation."""
    if tool_name == 'Bash':
        return [tool_input.get('command', '')]
    if tool_name == 'Write':
        return [tool_input.get('content', '')]
    if tool_name == 'Edit':
        return [tool_input.get('new_string', '')]
    if tool_name == 'MultiEdit':
        return [e.get('new_string', '') for e in tool_input.get('edits', [])]
    if tool_name == 'NotebookEdit':
        return [tool_input.get('new_source', '')]
    return []


def _matches_any(text, patterns, flags=re.IGNORECASE):
    """Return True if *text* matches any regex in *patterns*."""
    for p in patterns:
        if re.search(p, text, flags):
            return True
    return False


# ===================================================================
# CHECK 1: .env file access
# ===================================================================
def check_env_file_access(tool_name, tool_input):
    """Detect access to .env files containing secrets.

    Returns (severity, message) or None.
    """
    # File-based tools: inspect file_path
    if tool_name in ('Read', 'Edit', 'MultiEdit', 'Write'):
        fp = tool_input.get('file_path', '')
        # Allow platform project .env files
        if any(allowed in fp for allowed in _ENV_ALLOWED_PATHS):
            return None
        if '.env' in fp and not fp.endswith('.env.sample'):
            return (ASK, 'Attempting to access .env file with sensitive data')

    # Bash: inspect command string
    elif tool_name == 'Bash':
        cmd = tool_input.get('command', '')
        env_patterns = [
            r'\b\.env\b(?!\.sample)',           # any .env reference
            r'cat\s+.*\.env\b(?!\.sample)',
            r'echo\s+.*>\s*\.env\b(?!\.sample)',
            r'touch\s+.*\.env\b(?!\.sample)',
            r'cp\s+.*\.env\b(?!\.sample)',
            r'mv\s+.*\.env\b(?!\.sample)',
            # Sourcing .env (missed by original hook)
            r'source\s+.*\.env\b(?!\.sample)',
            r'\.\s+[^\|]*\.env\b(?!\.sample)',
            # Encoded exfiltration of .env
            r'base64\s+.*\.env\b(?!\.sample)',
            r'xxd\s+.*\.env\b(?!\.sample)',
        ]
        if _matches_any(cmd, env_patterns):
            return (ASK, 'Attempting to access .env file with sensitive data')

    return None


# ===================================================================
# CHECK 2: Python destructive code (Bash + Write + Edit + NotebookEdit)
# ===================================================================
def check_python_destructive(tool_name, tool_input):
    """Detect dangerous Python operations across all content-bearing tools.

    Covers: recursive dir deletion, subprocess rm bypass, encoded exec,
    string-concatenation evasion, dangerous deserialization.

    Returns (severity, message) or None.
    """
    if _is_self_exempt(tool_name, tool_input):
        return None

    texts = _get_scannable_texts(tool_name, tool_input)
    if not texts:
        return None

    mod = _MOD_SHUTIL
    func = _FUNC_RMTREE
    rdirs = _FUNC_REMOVEDIRS

    # --- P0: recursive dir deletion via the shutil module ---
    rmtree_pats = [
        mod + r'\s*\.\s*' + func,
        r'from\s+' + mod + r'\s+import\s+[^;]*\b' + func + r'\b',
        r'from\s+' + mod + r'\s+import\s+\*',
        r"""__import__\s*\(\s*['"]""" + mod + r"""['"]\s*\)\s*\.\s*""" + func,
        r"""importlib\s*\.\s*import_module\s*\(\s*['"]""" + mod + r"""['"]\s*\)\s*\.\s*""" + func,
        r"""getattr\s*\(.*?['"]""" + func + r"""['"]""",
        r"""getattr\s*\(.*?""" + mod + r""".*?""" + func,
    ]

    # --- P0: os.removedirs ---
    removedirs_pats = [
        r'os\s*\.\s*' + rdirs,
        r'from\s+os\s+import\s+[^;]*\b' + rdirs + r'\b',
    ]

    # --- P0: subprocess / os.system rm bypass ---
    subprocess_pats = [
        r"""subprocess\s*\.\s*(run|call|Popen|check_call|check_output)\s*\(\s*\[.*?['"]rm['"]""",
        r"""os\s*\.\s*system\s*\(.*?\brm\s+""",
        r"""os\s*\.\s*popen\s*\(.*?\brm\s+""",
        r"""os\s*\.\s*exec[lv]p?\s*\(.*?['"]rm['"]""",
    ]

    # --- P0: encoded execution (base64, hex, compile) ---
    encoded_pats = [
        r'exec\s*\(\s*base64\s*\.\s*b64decode',
        r'eval\s*\(\s*base64\s*\.\s*b64decode',
        r'exec\s*\(\s*bytes\s*\.\s*fromhex',
        r'eval\s*\(\s*bytes\s*\.\s*fromhex',
        r'exec\s*\(\s*codecs\s*\.\s*decode',
        r'exec\s*\(\s*compile\s*\(',
    ]

    # --- P0: string-concatenation evasion (agent copies our own technique) ---
    # Only scan Bash commands for this -- Write/Edit may legitimately document it
    concat_pats = [
        r"""['"]shut['"]\s*\+\s*['"]il['"]""",
        r"""['"]rm['"]\s*\+\s*['"]tree['"]""",
    ]

    # --- P2: dangerous deserialization ---
    deser_pats = [
        r'pickle\s*\.\s*loads?\s*\(',
        r'marshal\s*\.\s*loads?\s*\(',
        r'yaml\s*\.\s*unsafe_load\s*\(',
    ]

    for text in texts:
        if _matches_any(text, rmtree_pats):
            return (BLOCK, 'Python recursive directory deletion detected')
        if _matches_any(text, removedirs_pats):
            return (BLOCK, 'os.removedirs recursive deletion detected')
        if _matches_any(text, subprocess_pats):
            return (BLOCK, 'subprocess/os.system rm bypass detected')
        if _matches_any(text, encoded_pats):
            return (BLOCK, 'Encoded exec/eval detected (possible evasion)')
        # Concat evasion: only in Bash commands
        if tool_name == 'Bash' and _matches_any(text, concat_pats):
            return (BLOCK, 'String-concatenation evasion of blocked module detected')
        if _matches_any(text, deser_pats):
            return (ASK, 'Dangerous deserialization detected')

    return None


# ===================================================================
# CHECK 3: Shell destructive commands (Bash only)
# ===================================================================
def check_shell_destructive(tool_name, tool_input):
    """Detect dangerous shell commands.

    Returns (severity, message) or None.
    """
    if tool_name != 'Bash':
        return None
    cmd = tool_input.get('command', '')
    normalized = ' '.join(cmd.lower().split())

    # --- rm -rf and variants ---
    rm_pats = [
        r'\brm\s+.*-[a-z]*r[a-z]*f',
        r'\brm\s+.*-[a-z]*f[a-z]*r',
        r'\brm\s+--recursive\s+--force',
        r'\brm\s+--force\s+--recursive',
        r'\brm\s+-r\s+.*-f',
        r'\brm\s+-f\s+.*-r',
        r'\brm\s+.*--no-preserve-root',
    ]
    if _matches_any(normalized, rm_pats):
        # Hard-block only truly catastrophic targets (/, ~, $HOME, ..)
        catastrophic = [r'^rm\s.*\s/$', r'^rm\s.*\s/\*', r'\$HOME\s*$', r'\brm\s.*\s~/?$', r'\.\.']
        for p in catastrophic:
            if re.search(p, normalized):
                return (BLOCK, 'Recursive rm targeting critical path')
        return (ASK, 'Dangerous rm command detected')

    # --- rm -r targeting critical paths ---
    if re.search(r'\brm\s+.*-[a-z]*r', normalized):
        critical = [r'^\s*/$', r'/\*\s*$', r'~\s*$', r'~/\s*$', r'\$HOME', r'\.\.', r'^\*$']
        for p in critical:
            if re.search(p, normalized):
                return (BLOCK, 'Recursive rm targeting critical path')

    # --- Variable / alias indirection to rm ---
    var_pats = [
        r'\b\w+=\s*["\']?rm\b',
        r'alias\s+\w+=.*\brm\b',
    ]
    if _matches_any(cmd, var_pats):
        return (ASK, 'Variable/alias assignment to rm detected')

    # --- git clean ---
    git_clean_pats = [
        r'\bgit\s+clean\s+.*-[a-z]*f',
        r'\bgit\s+clean\s+--force',
    ]
    if _matches_any(cmd, git_clean_pats):
        return (BLOCK, 'git clean with force flag detected')

    # --- find -delete / find -exec rm ---
    find_pats = [
        r'\bfind\s+.*-delete\b',
        r'\bfind\s+.*-exec\s+rm\b',
        r'\bfind\s+.*-exec\s+/bin/rm\b',
        r'\bfind\s+.*\|\s*xargs\s+rm\b',
    ]
    if _matches_any(cmd, find_pats):
        return (ASK, 'Bulk file deletion via find detected')

    # --- dd disk overwrite ---
    dd_pats = [
        r'\bdd\s+.*if=/dev/(zero|random|urandom).*of=',
        r'\bdd\s+.*of=/dev/',
    ]
    if _matches_any(cmd, dd_pats):
        return (BLOCK, 'dd disk overwrite detected')

    # --- mkfs / newfs / diskutil erase ---
    fmt_pats = [
        r'\bmkfs\b',
        r'\bnewfs\b',
        r'\bdiskutil\s+erase(Disk|Volume)\b',
    ]
    if _matches_any(cmd, fmt_pats):
        return (BLOCK, 'Filesystem format command detected')

    # --- truncate / shred ---
    trunc_pats = [
        r'\btruncate\s+.*-s\s*0\b',
        r'\bshred\b',
    ]
    if _matches_any(cmd, trunc_pats):
        return (BLOCK, 'File destruction command detected')

    # --- curl/wget piped to shell (remote code execution) ---
    pipe_pats = [
        r'\bcurl\s+.*\|\s*(ba)?sh\b',
        r'\bwget\s+.*\|\s*(ba)?sh\b',
        r'\bcurl\s+.*\|\s*python',
        r'\bwget\s+.*\|\s*python',
        r'\bcurl\s+.*\|\s*sudo\b',
    ]
    if _matches_any(cmd, pipe_pats):
        return (BLOCK, 'Remote code execution via pipe detected')

    # --- kill all processes ---
    kill_pats = [r'\bkill\s+-9\s+-1\b']
    if _matches_any(cmd, kill_pats):
        return (BLOCK, 'Kill-all-processes command detected')

    # --- chmod -R 000/777 ---
    chmod_pats = [
        r'\bchmod\s+.*-[a-z]*R.*\b0{3,4}\b',
        r'\bchmod\s+.*-[a-z]*R.*\b777\b',
        r'\bchmod\s+.*-[a-z]*R.*\ba\+w\b',
    ]
    if _matches_any(cmd, chmod_pats):
        return (BLOCK, 'Dangerous recursive chmod detected')

    # --- rsync --delete ---
    if _matches_any(cmd, [r'\brsync\s+.*--delete']):
        return (ASK, 'rsync with --delete flag detected')

    # --- SQL DROP / TRUNCATE ---
    sql_pats = [
        r'\bDROP\s+(DATABASE|TABLE|SCHEMA)\b',
        r'\bTRUNCATE\s+(TABLE\s+)?\w',
    ]
    if _matches_any(cmd, sql_pats):
        return (ASK, 'SQL destructive operation detected')

    # --- NoSQL flush ---
    nosql_pats = [r'\bFLUSHALL\b', r'\bFLUSHDB\b']
    if _matches_any(cmd, nosql_pats):
        return (BLOCK, 'NoSQL flush command detected')

    # --- Docker destructive ---
    docker_pats = [
        r'\bdocker\s+system\s+prune\s+.*-a',
        r'\bdocker\s+volume\s+(rm|prune)\b',
    ]
    if _matches_any(cmd, docker_pats):
        return (ASK, 'Docker destructive operation detected')

    return None


# ===================================================================
# CHECK 4: Credential / secret exfiltration (Bash only)
# ===================================================================
def check_credential_exfil(tool_name, tool_input):
    """Detect attempts to read or exfiltrate secrets.

    Returns (severity, message) or None.
    """
    if tool_name != 'Bash':
        return None
    cmd = tool_input.get('command', '')

    # --- SSH key access ---
    ssh_pats = [
        r'cat\s+.*\.ssh/(id_|authorized_keys)',
        r'cp\s+.*\.ssh/',
        r'scp\s+.*\.ssh/',
        r'base64\s+.*\.ssh/',
    ]
    if _matches_any(cmd, ssh_pats):
        return (BLOCK, 'SSH key access detected')

    # --- Credential file access ---
    cred_pats = [
        r'cat\s+.*(\.aws/credentials|\.kube/config|\.npmrc|\.pypirc|\.netrc)',
        r'base64\s+.*(\.aws/|\.kube/)',
    ]
    if _matches_any(cmd, cred_pats):
        return (ASK, 'Credential file access detected')

    # --- Network exfiltration of sensitive files ---
    exfil_pats = [
        r'curl\s+.*(-d|--data)\s+@.*\.(env|pem|key)',
        r'curl\s+.*-F\s+.*\.(env|pem|key)',
        r'nc\s+.*<\s*.*\.(env|pem|key)',
    ]
    if _matches_any(cmd, exfil_pats):
        return (BLOCK, 'Network exfiltration of sensitive file detected')

    return None


# ===================================================================
# CHECK 5: Dangerous write targets (Write/Edit only)
# ===================================================================
def check_dangerous_write_target(tool_name, tool_input):
    """Detect writes to sensitive system files.

    Returns (severity, message) or None.
    """
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        return None
    fp = tool_input.get('file_path', '')

    # Shell config files
    shell_configs = [
        '.bashrc', '.bash_profile', '.zshrc', '.zprofile',
        '.profile', '.login', '.bash_login',
    ]
    if any(fp.endswith(c) for c in shell_configs):
        return (ASK, 'Write to shell startup config detected')

    # Crontab / LaunchAgent / LaunchDaemon
    sched_markers = ['crontab', 'LaunchAgents/', 'LaunchDaemons/', '/etc/cron.']
    if any(m in fp for m in sched_markers):
        return (BLOCK, 'Write to scheduled task config detected')

    # Git hooks
    if '.git/hooks/' in fp:
        return (ASK, 'Write to git hook detected')

    return None


# ===================================================================
# Structured logging
# ===================================================================
def _log_event(input_data, severity='info', reason=None):
    """Append a log entry. Never raises -- logging must not break the hook."""
    try:
        import datetime
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

        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'severity': severity,
            'tool_name': input_data.get('tool_name'),
        }
        if reason:
            entry['reason'] = reason
        if severity != 'info':
            # Include a preview of what was blocked/asked for audit trail
            entry['tool_input_preview'] = str(
                input_data.get('tool_input', {})
            )[:300]

        log_data.append(entry)

        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
    except Exception:
        pass


# ===================================================================
# Main entry point
# ===================================================================
def main():
    try:
        input_data = json.load(sys.stdin)
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Run every check in priority order. First match wins.
        checks = [
            check_env_file_access,
            check_python_destructive,
            check_shell_destructive,
            check_credential_exfil,
            check_dangerous_write_target,
        ]

        for check_fn in checks:
            result = check_fn(tool_name, tool_input)
            if result is not None:
                severity, message = result
                sev_label = 'blocked' if severity == BLOCK else 'ask'
                _log_event(input_data, severity=sev_label, reason=message)

                if severity == BLOCK:
                    print(f"BLOCKED: {message}", file=sys.stderr)
                else:
                    print(f"Permission required: {message}", file=sys.stderr)
                sys.exit(severity)

        # All checks passed
        _log_event(input_data)
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == '__main__':
    main()
