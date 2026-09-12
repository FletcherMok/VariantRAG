"""Exercise built Compose images with isolated volumes and no published ports."""

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.check_output(args, cwd=ROOT, text=True, **kwargs).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", action="store_true", help="Also test the built Mutalyzer image")
    args = parser.parse_args()
    project = "variantrag-smoke-" + uuid.uuid4().hex[:10]
    compose = ["docker", "compose", "-p", project]
    containers = []

    def start(service):
        container = run(*compose, "run", "-d", "--no-deps", "--use-aliases", service)
        containers.append(container)
        for _ in range(90):
            status = run("docker", "inspect", "--format", "{{.State.Health.Status}}", container)
            if status == "healthy":
                return container
            if status == "unhealthy":
                break
            time.sleep(1)
        raise RuntimeError(run("docker", "logs", container))

    def python(container, code):
        return run("docker", "exec", "-i", container, "python", "-", input=code, stderr=subprocess.PIPE)

    try:
        app = start("workbench")
        identity = python(
            app,
            """
import json,time,urllib.request,os,socket
socket.setdefaulttimeout(30)
assert os.getuid() != 0
base='http://127.0.0.1:8000'
assert b'<html' in urllib.request.urlopen(base).read().lower()
def get(path): return json.load(urllib.request.urlopen(base+path))
job=json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/demo',method='POST')))
for _ in range(120):
    result=get('/api/results/'+job['run_id'])
    if result['status'] in ('completed','failed'): break
    time.sleep(.25)
assert result['status']=='completed',result
assert len(result['result']['ranked_variants'])==3
print(job['run_id'])
""",
        )
        run("docker", "restart", app)
        for _ in range(60):
            try:
                python(
                    app,
                    f"""
import json,urllib.request,socket
socket.setdefaulttimeout(30)
r=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/results/{identity}'))
assert r['status']=='completed'
""",
                )
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise RuntimeError("Run did not survive container restart")
        if args.research:
            normalizer = start("mutalyzer")
            python(
                app,
                """
import json,urllib.request,socket
socket.setdefaulttimeout(30)
r=json.load(urllib.request.urlopen('http://mutalyzer:5000/api/normalize/2del?only_variants=true&sequence=AAAA'))
assert r['normalized_description']=='4del',r
""",
            )
            assert normalizer
        print(
            json.dumps(
                {
                    "static_ui": "passed",
                    "demo_candidates": 3,
                    "restart_persistence": "passed",
                    "normalizer": "passed" if args.research else "not requested",
                }
            )
        )
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr)
        raise
    finally:
        for container in containers:
            subprocess.run(
                ["docker", "rm", "-f", container], cwd=ROOT, check=False, stdout=subprocess.DEVNULL
            )
        subprocess.run([*compose, "down", "--volumes", "--remove-orphans"], cwd=ROOT, check=False)


if __name__ == "__main__":
    main()
