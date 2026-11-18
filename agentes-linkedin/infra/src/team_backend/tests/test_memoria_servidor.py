"""deploy/memoria.sh, the server's memory watch (organizaciones, phase 7; deploy/README.md «Memoria del servidor»), run as
cron runs it but without network: a fake `docker` first in PATH (it answers from files and honours --filter and the
--since/--until window), a fake /proc/meminfo, and Slack played by an HTTP server on 127.0.0.1 with an ephemeral port.
A `curl` wrapper records its arguments, to show the webhook never reaches a command line. No database."""
import http.server
import os
import shutil
import stat
import subprocess
import tempfile
import threading
from pathlib import Path

from django.test import SimpleTestCase

SCRIPT = Path(__file__).resolve().parents[5] / 'deploy' / 'memoria.sh'
NOW = 1_900_000_000
SECRET = 'T00000000/B00000000/secreto-del-webhook-de-prueba'

DOCKER = r'''#!/usr/bin/env bash
# A fake docker: answers from the files next to it and records each call.
here="$(dirname -- "$0")"
printf '%s\n' "$*" >> "$here/llamadas"
what=$1; shift
case $what in
  events)
    [ -e "$here/falla-events" ] && exit 1
    since=0 until=9999999999 types=() kinds=()
    while [ $# -gt 0 ]; do
      case $1 in
        --since) since=$2; shift ;;
        --until) until=$2; shift ;;
        --filter) case $2 in event=*) kinds+=("${2#event=}") ;; type=*) types+=("${2#type=}") ;; esac; shift ;;
        --format) shift ;;
      esac
      shift
    done
    [ -e "$here/eventos" ] || exit 0
    # one event per line: «seconds type event container-name»
    while read -r when type kind name; do
      [ -n "${when:-}" ] || continue
      [ "$when" -ge "$since" ] && [ "$when" -le "$until" ] || continue
      [ ${#types[@]} -eq 0 ] || printf '%s\n' "${types[@]}" | grep -qx -- "$type" || continue
      [ ${#kinds[@]} -eq 0 ] || printf '%s\n' "${kinds[@]}" | grep -qx -- "$kind" || continue
      echo "$name"
    done < "$here/eventos"
    ;;
  ps)
    [ -e "$here/falla-ps" ] && exit 1
    [ -e "$here/cuentas" ] || exit 0
    awk '{ print "id" NR }' "$here/cuentas"
    ;;
  inspect)
    cat "$here/cuentas"  # «/name RestartCount», one per running container
    ;;
  *) exit 64 ;;
esac
'''


class Slack(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        server = self.server
        server.received.append((self.path, self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode()))
        self.send_response(server.status)
        self.end_headers()

    def log_message(self, *args):
        pass


class MemoryWatchTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.deploy = self.root / 'deploy'
        self.deploy.mkdir()
        shutil.copy2(SCRIPT, self.deploy / 'memoria.sh')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'docker').write_text(DOCKER)
        (self.bin / 'curl').write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$(dirname -- "$0")/curl-args"\n'
                                       f'exec {shutil.which("curl")} "$@"\n')
        for name in ('docker', 'curl'):
            (self.bin / name).chmod(0o755)
        self.meminfo = self.root / 'meminfo'
        self.free(2400)
        self.slack = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Slack)
        self.slack.received, self.slack.status = [], 200
        thread = threading.Thread(target=self.slack.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.slack.server_close)
        self.addCleanup(self.slack.shutdown)
        self.url = f'http://127.0.0.1:{self.slack.server_address[1]}/services/{SECRET}'
        self.env(SLACK_WEBHOOK_URL=f'"{self.url}"')
        self.outputs = []

    # --- the world around the script ------------------------------------------------------------------------------
    def env(self, **values):
        lines = ['DJANGO_SECRET_KEY=no-se-lee', *(f'{k}={v}' for k, v in values.items()), 'OTRA=1']
        (self.deploy / '.env').write_text('\n'.join(lines) + '\n')

    def free(self, mib):
        self.meminfo.write_text(f'MemTotal:        3920000 kB\nMemFree:          100000 kB\nMemAvailable:   {mib * 1024} kB\n')

    def events(self, *lines):
        (self.bin / 'eventos').write_text(''.join(f'{when} container {kind} {name}\n' for when, kind, name in lines))

    def running(self, **counts):
        (self.bin / 'cuentas').write_text(''.join(f'/barrio-ai-{name}-1 {n}\n' for name, n in counts.items()))

    def run_at(self, when):
        done = subprocess.run([str(self.deploy / 'memoria.sh')], capture_output=True, text=True, timeout=60,
                              env={'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.root), 'LANG': 'C.UTF-8',
                                   'TZ': 'UTC', 'MEMORIA_MEMINFO': str(self.meminfo), 'MEMORIA_AHORA': str(when)})
        self.outputs.append(done.stdout + done.stderr)
        return done

    def posts(self):
        return [body for _, body in self.slack.received]

    def tearDown(self):
        # The webhook never shows: not in what the script printed, nor on curl's command line.
        curl_args = (self.bin / 'curl-args').read_text() if (self.bin / 'curl-args').exists() else ''
        for text in (*self.outputs, curl_args):
            self.assertNotIn(SECRET, text)
            self.assertNotIn('127.0.0.1:', text)
        for path, _ in self.slack.received:
            self.assertEqual(path, f'/services/{SECRET}')

    # --- low memory --------------------------------------------------------------------------------------------------
    def test_low_memory_is_told_once_per_episode_and_its_recovery_too(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), 'cron runs it as it is: it must be executable')
        self.free(200)
        first = self.run_at(NOW)
        self.assertEqual((first.returncode, first.stdout, self.posts()), (0, '', []))  # one dip is not an episode
        second = self.run_at(NOW + 300)
        self.assertEqual(second.returncode, 0)
        [post] = self.posts()
        self.assertIn('Memoria baja en el servidor: 200 MiB disponibles (aviso por debajo de 300) desde las 17:46', post)
        self.assertIn('Memoria baja en el servidor', second.stdout)  # also in cron's log
        for mib in (150, 400, 250):  # still low, then between the thresholds, low again: the same episode
            self.free(mib)
            self.assertEqual(self.run_at(NOW + 600).returncode, 0)
        self.assertEqual(len(self.posts()), 1)
        self.free(600)
        self.run_at(NOW + 900)
        self.assertEqual(len(self.posts()), 2)
        self.assertIn('La memoria del servidor se recuperó: 600 MiB disponibles', self.posts()[1])
        self.run_at(NOW + 1200)
        self.assertEqual(len(self.posts()), 2)
        self.free(100)  # a new episode, told again after two readings
        self.run_at(NOW + 1500)
        self.run_at(NOW + 1800)
        self.assertEqual(len(self.posts()), 3)
        state = self.deploy / 'estado' / 'memoria'
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o600)

    def test_the_thresholds_come_from_the_env_file(self):
        self.env(SLACK_WEBHOOK_URL=self.url, MEMORIA_ALERTA_MB='1000', MEMORIA_RECUPERADA_MB="'1500'")
        self.free(1000)  # at the threshold is not below it
        self.run_at(NOW)
        self.run_at(NOW + 300)
        self.assertEqual(self.posts(), [])
        self.free(999)
        self.run_at(NOW + 600)
        self.run_at(NOW + 900)
        self.assertEqual(len(self.posts()), 1)
        self.assertIn('999 MiB disponibles (aviso por debajo de 1000)', self.posts()[0])
        self.free(1499)
        self.run_at(NOW + 1200)
        self.assertEqual(len(self.posts()), 1)
        self.free(1500)
        self.run_at(NOW + 1500)
        self.assertEqual(len(self.posts()), 2)

    # --- containers ------------------------------------------------------------------------------------------------
    def test_a_container_the_kernel_killed_once_per_hour_and_only_oom_counts(self):
        self.running(db=0, api=0)
        self.events((NOW - 60, 'oom', 'barrio-ai-api-1'), (NOW - 50, 'oom', 'barrio-ai-api-1'),
                    (NOW - 40, 'die', 'barrio-ai-web-1'), (NOW - 40, 'kill', 'barrio-ai-worker-1'))
        done = self.run_at(NOW)
        self.assertEqual(done.returncode, 0)
        [post] = self.posts()
        self.assertIn('barrio-ai-api-1 (el kernel lo mató por falta de memoria, 2 veces)', post)
        self.assertNotIn('web', post)  # a stop or a deploy is not a memory problem
        self.assertNotIn('worker', post)
        self.assertIn('Memoria disponible: 2400 MiB', post)
        calls = (self.bin / 'llamadas').read_text()
        self.assertIn(f'events --since {NOW - 600} --until {NOW} --filter type=container --filter event=oom', calls)
        self.run_at(NOW + 300)  # the same events are not read twice
        self.assertEqual(len(self.posts()), 1)
        self.events((NOW + 1000, 'oom', 'barrio-ai-api-1'), (NOW + 1000, 'oom', 'barrio-ai-navegador-1'))
        self.run_at(NOW + 1200)  # api within the hour of its notice: only the browser is news
        self.assertEqual(len(self.posts()), 2)
        self.assertIn('barrio-ai-navegador-1 (el kernel lo mató', self.posts()[1])
        self.assertNotIn('api', self.posts()[1])
        self.events((NOW + 3700, 'oom', 'barrio-ai-api-1'))
        self.run_at(NOW + 3900)
        self.assertEqual(len(self.posts()), 3)
        self.assertIn('barrio-ai-api-1', self.posts()[2])

    def test_a_container_docker_restarted_by_itself_but_not_a_deploy(self):
        self.running(db=0, api=2)
        self.run_at(NOW)  # the first pass only learns the counts
        self.assertEqual(self.posts(), [])
        self.running(db=0, api=3)
        self.run_at(NOW + 300)
        [post] = self.posts()
        self.assertIn('barrio-ai-api-1 (Docker lo reinició solo 1 vez)', post)
        self.assertNotIn('db', post)
        self.run_at(NOW + 600)
        self.running(db=0, api=0)  # recreated by a deploy: its count starts again
        self.run_at(NOW + 900)
        self.assertEqual(len(self.posts()), 1)
        self.running(db=2, api=0)
        self.run_at(NOW + 1200)
        self.assertIn('barrio-ai-db-1 (Docker lo reinició solo 2 veces)', self.posts()[1])

    # --- without Slack or with Slack failing ------------------------------------------------------------------------
    def test_without_a_webhook_nothing_is_posted_and_the_text_goes_to_the_output(self):
        for webhook in ('', "''"):
            with self.subTest(webhook=webhook):
                self.env(SLACK_WEBHOOK_URL=webhook)
                shutil.rmtree(self.deploy / 'estado', ignore_errors=True)
                self.free(100)
                self.run_at(NOW)
                done = self.run_at(NOW + 300)
                self.assertEqual(done.returncode, 0)
                self.assertIn('Memoria baja en el servidor: 100 MiB', done.stdout)
                self.assertEqual(self.run_at(NOW + 600).stdout, '')  # told: not printed again
        (self.deploy / '.env').unlink()  # no .env at all
        self.running(api=0)
        self.run_at(NOW + 900)
        self.running(api=1)
        self.assertIn('Docker lo reinició solo 1 vez', self.run_at(NOW + 1200).stdout)
        self.assertEqual(self.slack.received, [])
        self.assertFalse((self.bin / 'curl-args').exists())

    def test_a_notice_that_does_not_go_out_is_tried_again_and_never_hides_the_exit_code(self):
        self.slack.status = 500
        self.free(100)
        self.run_at(NOW)
        failed = self.run_at(NOW + 300)
        self.assertEqual(failed.returncode, 3)
        self.assertIn('el aviso a Slack no salió', failed.stderr)
        self.slack.status = 200
        self.assertEqual(self.run_at(NOW + 600).returncode, 0)  # the same episode, now told
        self.assertEqual(len(self.posts()), 2)
        self.run_at(NOW + 900)
        self.assertEqual(len(self.posts()), 2)
        # Docker failing first: its code stays, whatever the notice does after it.
        self.free(2400)
        self.running(api=0)
        self.run_at(NOW + 1000)
        self.events((NOW + 1100, 'oom', 'barrio-ai-api-1'))
        (self.bin / 'falla-ps').touch()
        self.slack.status = 500
        done = self.run_at(NOW + 1200)
        self.assertEqual(done.returncode, 2)
        self.assertIn('docker no respondió al listar los contenedores', done.stderr)
        self.assertIn('el aviso a Slack no salió', done.stderr)
        # The memory unreadable first: 1, though the notice of the same OOM fails again.
        self.meminfo.unlink()
        done = self.run_at(NOW + 1500)
        self.assertEqual(done.returncode, 1)
        self.assertIn('Memoria disponible: ? MiB', self.posts()[-1])
        # Back to normal: the OOM that was never told is still found (the window did not move) and told once.
        self.free(2400)
        (self.bin / 'falla-ps').unlink()
        self.slack.status = 200
        before = len(self.posts())
        self.assertEqual(self.run_at(NOW + 1800).returncode, 0)
        self.assertEqual(len(self.posts()), before + 1)
        self.assertIn('barrio-ai-api-1 (el kernel lo mató', self.posts()[-1])
        self.run_at(NOW + 2100)
        self.assertEqual(len(self.posts()), before + 1)

    def test_docker_down_does_not_lose_the_events_it_could_not_read(self):
        self.running(api=0)
        self.run_at(NOW - 1000)  # the window starts here
        self.events((NOW - 60, 'oom', 'barrio-ai-api-1'))
        (self.bin / 'falla-events').touch()
        done = self.run_at(NOW)
        self.assertEqual(done.returncode, 2)
        self.assertIn('docker no respondió al pedir los eventos oom', done.stderr)
        self.assertEqual(self.posts(), [])
        (self.bin / 'falla-events').unlink()
        self.run_at(NOW + 2000)  # more than ten minutes after the event: found only because the window held
        [post] = self.posts()
        self.assertIn('barrio-ai-api-1 (el kernel lo mató', post)
