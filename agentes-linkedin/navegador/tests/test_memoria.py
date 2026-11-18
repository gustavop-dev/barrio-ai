"""How much memory there is to open a browser (navegador/memoria.py), from fake /proc/meminfo and cgroup v2 files."""
import tempfile
import unittest
from pathlib import Path

from navegador import memoria

MEMINFO = 'MemTotal:        3920000 kB\nMemFree:          200000 kB\nMemAvailable:    1536000 kB\nBuffers: 1 kB\n'
MIB = 1024 * 1024


class MemoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.meminfo = self.root / 'meminfo'
        self.cgroup = self.root / 'cgroup'
        self.cgroup.mkdir()

    def write(self, meminfo=MEMINFO, cap=None, current=None, inactive=None):
        if meminfo is not None:
            self.meminfo.write_text(meminfo)
        for name, value in (('memory.max', cap), ('memory.current', current)):
            if value is not None:
                (self.cgroup / name).write_text(f'{value}\n')
        if inactive is not None:
            (self.cgroup / 'memory.stat').write_text(f'anon 1\nfile 2\ninactive_file {inactive}\nactive_file 3\n')

    def available(self):
        return memoria.available_mb(self.meminfo, self.cgroup)

    def test_the_host_without_a_cap(self):
        self.write(cap='max', current=900 * MIB, inactive=0)
        self.assertEqual(memoria.host_mb(self.meminfo), 1500)
        self.assertIsNone(memoria.cgroup_mb(self.cgroup))
        self.assertEqual(self.available(), 1500)

    def test_the_smaller_of_the_host_and_what_is_left_under_the_cap(self):
        # 2304 MiB cap, 1300 MiB charged of which 100 is cache the kernel can drop: 1104 MiB left under the cap
        self.write(cap=2304 * MIB, current=1300 * MIB, inactive=100 * MIB)
        self.assertEqual(memoria.cgroup_mb(self.cgroup), 1104)
        self.assertEqual(self.available(), 1104)
        self.write(meminfo=MEMINFO.replace('1536000', '512000'))  # the host is tighter than the cap
        self.assertEqual(self.available(), 500)

    def test_over_the_cap_is_zero(self):
        self.write(cap=1024 * MIB, current=1100 * MIB, inactive=0)
        self.assertEqual(memoria.cgroup_mb(self.cgroup), 0)

    def test_none_when_nothing_can_be_read(self):
        self.assertIsNone(self.available())  # no files at all: not Linux, or no cgroup v2
        self.write(meminfo='MemTotal: 1 kB\n')  # an old kernel without MemAvailable
        self.assertIsNone(self.available())
        self.write(meminfo='MemAvailable: mucho kB\n', cap='raro', current=1, inactive=0)
        self.assertIsNone(memoria.host_mb(self.meminfo))
        self.assertIsNone(memoria.cgroup_mb(self.cgroup))
        self.assertIsNone(self.available())

    def test_a_cap_without_memory_stat_is_not_trusted(self):
        self.write(cap=2048 * MIB, current=1024 * MIB)
        self.assertIsNone(memoria.cgroup_mb(self.cgroup))  # half a cgroup is not trusted: only the host counts
        self.assertEqual(self.available(), 1500)


if __name__ == '__main__':
    unittest.main()
