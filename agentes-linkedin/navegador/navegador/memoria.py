"""How much memory there is to open one more account's browser (README «Memoria»; organizaciones, phase 7).

One account's browser took its container to about 1 GiB on the server (13/11/2026), and the server has 4 GB: two
accounts fit, just (docs/plan-linkedin-directo.md). Before a Chromium opens, the service asks here how many MiB are
free, the smaller of:
- the host's MemAvailable (/proc/meminfo: inside a Docker container it is the host's, not the container's), what the
  kernel can hand out without swapping or killing anyone;
- what is left under this container's own cap (cgroup v2 memory.max, set by mem_limit in deploy/compose.prod.yaml):
  memory.max minus memory.current, with the reclaimable file cache (inactive_file) counted as free, as `docker stats`
  counts it. Without a cap (memory.max = max) or without cgroup v2, only the host counts.
None when neither can be read (not Linux, an unusual container): the guard never blocks on a guess."""
from pathlib import Path

MEMINFO = Path('/proc/meminfo')
CGROUP = Path('/sys/fs/cgroup')
MIB = 1024 * 1024


def host_mb(meminfo=MEMINFO):
    """MemAvailable in MiB, or None."""
    try:
        for line in Path(meminfo).read_text(encoding='ascii').splitlines():
            name, _, rest = line.partition(':')
            if name == 'MemAvailable':
                parts = rest.split()
                return int(parts[0]) // 1024 if parts and parts[-1] == 'kB' else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return None


def _number(path):
    raw = Path(path).read_text(encoding='ascii').strip()
    return None if raw == 'max' else int(raw)


def cgroup_mb(cgroup=CGROUP):
    """MiB left under this container's cap (cgroup v2), or None without a cap or without cgroup v2."""
    root = Path(cgroup)
    try:
        cap = _number(root / 'memory.max')
        if cap is None:
            return None
        used = _number(root / 'memory.current')
        inactive = 0
        for line in (root / 'memory.stat').read_text(encoding='ascii').splitlines():
            name, _, value = line.partition(' ')
            if name == 'inactive_file':
                inactive = int(value)
                break
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return None
    return max(0, cap - max(0, used - inactive)) // MIB


def available_mb(meminfo=MEMINFO, cgroup=CGROUP):
    """The smaller of the host's and the container's free MiB; None when neither can be read."""
    found = [value for value in (host_mb(meminfo), cgroup_mb(cgroup)) if value is not None]
    return min(found) if found else None
