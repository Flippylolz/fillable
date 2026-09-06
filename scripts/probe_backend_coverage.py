"""Negative verification runs only in a disposable backend test container."""
import subprocess
from pathlib import Path

from check_coverage import check

assert Path.cwd() == Path('/app')
probe = Path('app/coverage_probe.py')
assert not probe.exists()
try:
    probe.write_text('def untested(value):\n' + ''.join(
        f'    if value == {i}:\n        return {i}\n' for i in range(30)
    ) + '    return -1\n')
    subprocess.run(['pytest', '--cov=app', '--cov-branch',
                    '--cov-report=json:coverage/coverage.json'], check=True)
    try:
        check('backend', '/app')
    except ValueError as error:
        assert 'below 90%' in str(error), error
        print(f'PASS: real unimported backend source blocked: {error}')
    else:
        raise AssertionError('Uncovered backend source did not block the gate')
finally:
    probe.unlink()
