import { spawn } from 'node:child_process';
import net from 'node:net';

const configuredApiBase = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
const shouldUseRunningApi = Boolean(configuredApiBase) || process.env.BENCHMARK_SMOKE_USE_RUNNING_API === '1';
let apiProcess = null;
let apiBase = (configuredApiBase || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function getOpenPort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      server.close(() => {
        if (address && typeof address === 'object') {
          resolve(address.port);
        } else {
          reject(new Error('Could not allocate local API port'));
        }
      });
    });
  });
}

function startApi(port) {
  apiProcess = spawn(
    'apps/api/.venv/bin/python',
    ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'apps/api', '--host', '127.0.0.1', '--port', String(port)],
    {
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );

  let output = '';
  apiProcess.stdout.on('data', (chunk) => {
    output += chunk.toString();
  });
  apiProcess.stderr.on('data', (chunk) => {
    output += chunk.toString();
  });
  apiProcess.on('exit', (code, signal) => {
    if (code !== 0 && signal !== 'SIGTERM') {
      console.error(output.trim());
    }
  });

  return {
    stop() {
      if (apiProcess && !apiProcess.killed) {
        apiProcess.kill('SIGTERM');
      }
    },
    output() {
      return output.trim();
    },
  };
}

async function waitForHealth(api, timeoutMs = 12000) {
  const started = Date.now();
  let lastError = null;

  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(`${api}/health`);
      if (response.ok) return;
      lastError = new Error(`Health check returned ${response.status}`);
    } catch (err) {
      lastError = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw lastError instanceof Error ? lastError : new Error('Timed out waiting for API health check');
}

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) {
    throw new Error(`${options.method || 'GET'} ${path} returned ${response.status}: ${text}`);
  }
  return payload;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

let ownedApi = null;

try {
  if (!shouldUseRunningApi) {
    const port = await getOpenPort();
    apiBase = `http://127.0.0.1:${port}`;
    ownedApi = startApi(port);
    await waitForHealth(apiBase);
  }

  const suites = await request('/api/benchmarks/suites');
  assert(Array.isArray(suites), 'Expected benchmark suites array');
  assert(suites.some((suite) => suite.id === 'call-center-voice-ai'), 'Missing call-center benchmark suite');

  const simulation = await request('/api/benchmarks/simulate', {
    method: 'POST',
    body: JSON.stringify({
      suite_id: 'call-center-voice-ai',
      scenario_id: 'billing-address-change',
      agent_profile: 'http smoke text agent',
    }),
  });

  assert(simulation.transcript.includes('http smoke text agent'), 'Simulation transcript did not include agent profile');
  assert(simulation.vcon?.vcon === '0.0.2', 'Simulation did not return vCon 0.0.2 artifact');
  assert(Array.isArray(simulation.action_trace) && simulation.action_trace.length > 0, 'Simulation did not return action trace');
  assert(simulation.final_state?.complete === true, 'Simulation final state was not complete');
  assert(simulation.benchmark_report?.verdict === 'pass', 'Simulation benchmark report did not pass');
  assert(simulation.benchmark_report?.call_artifacts?.source === 'vcon', 'Simulation benchmark report did not include vCon call artifacts');
  assert(simulation.benchmark_report?.call_artifacts?.modalities?.includes('text'), 'Simulation benchmark report did not include text modality artifacts');

  const savedSimulation = await request(`/api/benchmarks/runs/${simulation.benchmark_report.run_id}`);
  assert(savedSimulation.report?.transcript === simulation.transcript, 'Saved simulation run did not include transcript report');
  assert(savedSimulation.evidence_artifacts?.action_trace?.length === simulation.action_trace.length, 'Saved simulation evidence did not include action trace');

  const exportedVcon = await request(`/api/benchmarks/runs/${simulation.benchmark_report.run_id}/vcon`);
  assert(exportedVcon.vcon === '0.0.2', 'Saved simulation vCon export used unexpected version');
  assert(exportedVcon.benchmark_run_id === simulation.benchmark_report.run_id, 'Saved simulation vCon export did not include run id');
  assert(exportedVcon.dialog?.length === simulation.vcon.dialog.length, 'Saved simulation vCon export did not preserve dialog');

  const exportedSarif = await request(`/api/benchmarks/runs/${simulation.benchmark_report.run_id}/sarif`);
  assert(exportedSarif.version === '2.1.0', 'Saved simulation SARIF export used unexpected version');
  assert(exportedSarif.runs?.[0]?.tool?.driver?.name === 'ConversationAgentEvals', 'Saved simulation SARIF export did not identify tool');
  assert(exportedSarif.runs?.[0]?.results?.[0]?.properties?.run_id === simulation.benchmark_report.run_id, 'Saved simulation SARIF export did not include run id');

  const failure = await request('/api/benchmarks/simulate', {
    method: 'POST',
    body: JSON.stringify({
      suite_id: 'telehealth-agent',
      scenario_id: 'medication-refill-routing',
      include_failure: true,
    }),
  });

  assert(failure.final_state?.complete === false, 'Failure baseline final state should be incomplete');
  assert(failure.benchmark_report?.verdict === 'needs_review', 'Failure baseline should need review');

  const rerun = await request('/api/benchmarks/run', {
    method: 'POST',
    body: JSON.stringify({
      suite_id: simulation.suite_id,
      scenario_id: simulation.scenario_id,
      transcript: simulation.transcript,
      action_trace: simulation.action_trace,
      final_state: simulation.final_state,
    }),
  });

  assert(rerun.verdict === 'pass', 'Rerun report did not pass');
  assert(rerun.overall_score >= 75, 'Rerun score was below pass threshold');

  const history = await request('/api/benchmarks/runs?suite_id=call-center-voice-ai&scenario_id=billing-address-change&limit=10');
  assert(Array.isArray(history.runs), 'Run history did not return runs array');
  assert(history.runs.some((run) => run.run_id === simulation.benchmark_report.run_id), 'Run history did not include saved simulation');
  assert(history.summary?.run_count === history.runs.length, 'Run history summary did not match run count');
  assert(['baseline', 'stable', 'improved', 'regressed'].includes(history.summary?.status), 'Run history summary returned unexpected status');
  assert(history.comparison?.status, 'Run history did not return comparison status');

  const historySarif = await request('/api/benchmarks/runs.sarif?suite_id=call-center-voice-ai&scenario_id=billing-address-change&limit=10');
  assert(historySarif.runs?.[0]?.results?.length >= 1, 'Run history SARIF did not include results');

  console.log(`Benchmark HTTP smoke passed against ${apiBase}`);
} catch (err) {
  if (ownedApi?.output()) {
    console.error(ownedApi.output());
  }
  throw err;
} finally {
  ownedApi?.stop();
}
