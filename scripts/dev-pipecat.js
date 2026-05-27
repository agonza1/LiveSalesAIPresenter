const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const appDir = path.join(root, 'apps', 'pipecat');
const requirementsPath = path.join(appDir, 'requirements.txt');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    ...options,
  });

  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function getPythonVersion(command) {
  const result = spawnSync(command, ['-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'], {
    encoding: 'utf8',
  });

  if (result.status !== 0) return null;
  const [major, minor] = result.stdout.trim().split('.').map(Number);
  if (!Number.isFinite(major) || !Number.isFinite(minor)) return null;
  return { command, major, minor };
}

function findPython() {
  for (const command of ['python3.13', 'python3.12', 'python3.11', 'python3.10', 'python3']) {
    const version = getPythonVersion(command);
    if (version && (version.major > 3 || (version.major === 3 && version.minor >= 10))) {
      return version;
    }
  }

  throw new Error('Pipecat dev server requires Python 3.10+. Install python3.10 or newer and rerun.');
}

const python = findPython();
const venvDir = path.join(appDir, `.venv-py${python.major}${python.minor}`);
const venvPython = path.join(venvDir, 'bin', 'python');
const uvicorn = path.join(venvDir, 'bin', 'uvicorn');

if (!fs.existsSync(venvPython)) {
  run(python.command, ['-m', 'venv', venvDir], { cwd: appDir });
}

run(venvPython, ['-m', 'pip', 'install', '-q', '-r', requirementsPath], { cwd: appDir });
run(uvicorn, ['server:app', '--app-dir', appDir, '--host', '0.0.0.0', '--port', process.env.PIPECAT_PORT ?? '8110'], {
  cwd: appDir,
  env: process.env,
});
