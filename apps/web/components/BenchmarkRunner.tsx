'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

type JsonRecord = Record<string, unknown>;

interface BenchmarkSuite {
  id: string;
  title: string;
  description?: string | null;
  scenarios: BenchmarkScenario[];
}

interface BenchmarkScenario {
  id: string;
  suite_id?: string;
  title: string;
  domain?: string | null;
  user_persona?: string | null;
  user_goal?: string | null;
  edge_cases?: string[] | string | null;
  constraints?: string[] | string | null;
  required_actions?: string[] | string | null;
  forbidden_actions?: string[] | string | null;
  expected_final_state?: JsonRecord | string | null;
  rubric?: string[] | string | null;
  sample_transcript?: string | null;
  sample_action_trace?: unknown;
  sample_final_state?: unknown;
}

interface BenchmarkReport {
  run_id?: string;
  suite_id?: string;
  scenario_id?: string;
  scenario_title?: string;
  verdict?: string;
  overall?: string;
  score?: number;
  overall_score?: number;
  task_completion_score?: number;
  required_action_score?: number;
  forbidden_action_score?: number;
  final_state_score?: number;
  evidence_spans?: Array<string | JsonRecord>;
  evidence?: Array<string | JsonRecord>;
  missing_actions?: string[];
  forbidden_actions_observed?: string[];
  failure_categories?: string[];
  voice_quality_risks?: string[];
  suggested_fixes?: string[];
  transcript?: string;
  action_trace?: unknown;
  final_state?: unknown;
  conversation_insights?: {
    turn_count?: number;
    speaker_count?: number;
    speakers?: string[];
    speaker_turn_counts?: Record<string, number>;
    decisions?: Array<string | JsonRecord>;
    commitments?: Array<string | JsonRecord>;
    follow_up_actions?: Array<string | JsonRecord>;
  };
  call_artifacts?: {
    source?: string;
    turn_count?: number;
    media_count?: number;
    modalities?: string[];
    duration_seconds?: number;
    average_latency_ms?: number;
    max_latency_ms?: number;
    interruption_count?: number;
    tool_call_count?: number;
    failed_tool_call_count?: number;
  };
  run_context?: {
    agent_version?: string;
    prompt_version?: string;
    model_name?: string;
    target_agent_url?: string;
  };
}

interface BenchmarkRunSummary {
  run_id: string;
  suite_id: string;
  scenario_id: string;
  scenario_title?: string;
  verdict: string;
  overall_score: number;
  previous_overall_score?: number | null;
  score_delta?: number | null;
  trend?: 'improved' | 'regressed' | 'unchanged' | 'baseline' | string;
  voice_quality_risk_count?: number;
  run_context?: {
    agent_version?: string;
    prompt_version?: string;
    model_name?: string;
    target_agent_url?: string;
  };
  created_at?: string | null;
}

interface BenchmarkRegressionSummary {
  status: 'empty' | 'baseline' | 'stable' | 'improved' | 'regressed' | string;
  run_count: number;
  pass_count?: number;
  pass_rate?: number | null;
  needs_review_count?: number;
  average_score?: number | null;
  latest_score?: number | null;
  previous_score?: number | null;
  score_delta?: number | null;
  latest_verdict?: string | null;
  latest_run_id?: string | null;
  regression_count?: number;
  improvement_count?: number;
  failure_category_counts?: Record<string, number>;
  most_common_failure_category?: string | null;
  voice_quality_risk_count?: number;
  latest_voice_quality_risk_count?: number;
}

interface BenchmarkComparison {
  status: 'insufficient_history' | 'compared' | string;
  latest_run_id?: string | null;
  previous_run_id?: string | null;
  new_missing_actions?: string[];
  resolved_missing_actions?: string[];
  new_forbidden_actions?: string[];
  resolved_forbidden_actions?: string[];
  new_failure_categories?: string[];
  resolved_failure_categories?: string[];
}

interface BenchmarkSimulationResponse {
  conversation?: Array<Record<string, string>>;
  transcript: string;
  vcon?: JsonRecord;
  action_trace: unknown;
  final_state: unknown;
  benchmark_report: BenchmarkReport;
}

interface BenchmarkSuiteSimulationResponse {
  suite_id: string;
  suite_name?: string;
  scenario_count: number;
  run_count: number;
  pass_count: number;
  needs_review_count: number;
  average_score: number;
  run_context?: BenchmarkReport['run_context'];
  reports: BenchmarkReport[];
}

interface SimulationArtifacts {
  conversation: Array<Record<string, string>>;
  vcon: JsonRecord | null;
}

function normalizeApiBase(value: string) {
  return value.replace(/\/$/, '').replace(/\/api$/, '');
}

function getApiBase() {
  if (typeof window === 'undefined') {
    return normalizeApiBase(process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8025');
  }

  const fromQuery = new URLSearchParams(window.location.search).get('api_base');
  if (fromQuery) {
    try {
      return normalizeApiBase(new URL(fromQuery, window.location.origin).toString());
    } catch {
      // Fall through to the same-origin API proxy.
    }
  }

  return '';
}

async function handleJson<T>(response: Response): Promise<T> {
  const text = await response.text();

  if (!response.ok) {
    let message = text || `Request failed with ${response.status}`;
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      message = parsed.detail || message;
    } catch {
      // Keep plain-text fallback.
    }
    throw new Error(message);
  }

  return (text ? JSON.parse(text) : {}) as T;
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {};
}

function toStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(/\n|;/).map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function stringifyEditable(value: unknown, fallback = '') {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function parseMaybeJson(value: string): string | JsonRecord | unknown[] {
  if (!value.trim()) return '';

  try {
    return JSON.parse(value) as JsonRecord | unknown[];
  } catch {
    return value;
  }
}

function hasEditableEvidence(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return false;

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) return parsed.length > 0;
    if (parsed && typeof parsed === 'object') return Object.keys(parsed).length > 0;
    return Boolean(parsed);
  } catch {
    return true;
  }
}

function parseImportedCallEvidence(value: string): { call?: string | JsonRecord | unknown[]; vcon?: JsonRecord } {
  if (!hasEditableEvidence(value)) return {};
  const parsed = parseMaybeJson(value);

  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const record = parsed as JsonRecord;
    if (record.vcon || record.dialog || record.parties) return { vcon: record };
  }

  return { call: parsed };
}

function normalizeScenario(value: unknown, suiteId?: string): BenchmarkScenario {
  const record = asRecord(value);
  return {
    id: String(record.id ?? record.scenario_id ?? crypto.randomUUID()),
    suite_id: String(record.suite_id ?? suiteId ?? ''),
    title: String(record.title ?? record.name ?? 'Untitled scenario'),
    domain: typeof record.domain === 'string' ? record.domain : null,
    user_persona: typeof record.user_persona === 'string' ? record.user_persona : typeof record.persona === 'string' ? record.persona : null,
    user_goal: typeof record.user_goal === 'string' ? record.user_goal : typeof record.goal === 'string' ? record.goal : null,
    edge_cases: record.edge_cases as BenchmarkScenario['edge_cases'],
    constraints: record.constraints as BenchmarkScenario['constraints'],
    required_actions: record.required_actions as BenchmarkScenario['required_actions'],
    forbidden_actions: record.forbidden_actions as BenchmarkScenario['forbidden_actions'],
    expected_final_state: record.expected_final_state as BenchmarkScenario['expected_final_state'],
    rubric: record.rubric as BenchmarkScenario['rubric'],
    sample_transcript: typeof record.sample_transcript === 'string' ? record.sample_transcript : null,
    sample_action_trace: record.sample_action_trace,
    sample_final_state: record.sample_final_state,
  };
}

function normalizeSuites(payload: unknown): BenchmarkSuite[] {
  const record = asRecord(payload);
  const rawSuites = Array.isArray(payload) ? payload : Array.isArray(record.suites) ? record.suites : [];

  return rawSuites.map((item) => {
    const suite = asRecord(item);
    const id = String(suite.id ?? suite.suite_id ?? crypto.randomUUID());
    const scenarios = Array.isArray(suite.scenarios) ? suite.scenarios.map((scenario) => normalizeScenario(scenario, id)) : [];

    return {
      id,
      title: String(suite.title ?? suite.name ?? 'Untitled suite'),
      description: typeof suite.description === 'string' ? suite.description : null,
      scenarios,
    };
  });
}

async function fetchBenchmarkSuites(): Promise<BenchmarkSuite[]> {
  const suites = await handleJson<unknown>(await fetch(`${getApiBase()}/api/benchmarks/suites`, { cache: 'no-store' }));
  const normalizedSuites = normalizeSuites(suites);

  return Promise.all(
    normalizedSuites.map(async (suite) => {
      if (suite.scenarios.length) return suite;

      try {
        const payload = await handleJson<unknown>(
          await fetch(`${getApiBase()}/api/benchmarks/suites/${encodeURIComponent(suite.id)}/scenarios`, { cache: 'no-store' }),
        );
        const record = asRecord(payload);
        const rawScenarios = Array.isArray(payload) ? payload : Array.isArray(record.scenarios) ? record.scenarios : [];
        return { ...suite, scenarios: rawScenarios.map((scenario) => normalizeScenario(scenario, suite.id)) };
      } catch {
        return suite;
      }
    }),
  );
}

async function runBenchmark(payload: {
  suite_id: string;
  scenario_id: string;
  agent_version?: string;
  prompt_version?: string;
  model_name?: string;
  target_agent_url?: string;
  transcript?: string;
  call?: string | JsonRecord | unknown[];
  vcon?: JsonRecord;
  action_trace?: string | JsonRecord | unknown[];
  final_state?: string | JsonRecord | unknown[];
}) {
  return handleJson<BenchmarkReport>(
    await fetch(`${getApiBase()}/api/benchmarks/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

async function simulateBenchmark(payload: {
  suite_id: string;
  scenario_id: string;
  agent_profile?: string;
  agent_version?: string;
  prompt_version?: string;
  model_name?: string;
  target_agent_url?: string;
  include_failure?: boolean;
}) {
  return handleJson<BenchmarkSimulationResponse>(
    await fetch(`${getApiBase()}/api/benchmarks/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

async function simulateBenchmarkSuite(payload: {
  suite_id: string;
  agent_profile?: string;
  agent_version?: string;
  prompt_version?: string;
  model_name?: string;
  target_agent_url?: string;
  include_failure?: boolean;
}) {
  return handleJson<BenchmarkSuiteSimulationResponse>(
    await fetch(`${getApiBase()}/api/benchmarks/suites/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

async function fetchBenchmarkRuns(payload: {
  suite_id: string;
  scenario_id: string;
  agent_version?: string;
  prompt_version?: string;
  model_name?: string;
  target_agent_url?: string;
  limit?: number;
}) {
  const params = new URLSearchParams({
    suite_id: payload.suite_id,
    scenario_id: payload.scenario_id,
    limit: String(payload.limit ?? 5),
  });
  if (payload.agent_version) params.set('agent_version', payload.agent_version);
  if (payload.prompt_version) params.set('prompt_version', payload.prompt_version);
  if (payload.model_name) params.set('model_name', payload.model_name);
  if (payload.target_agent_url) params.set('target_agent_url', payload.target_agent_url);
  const response = await handleJson<{ runs?: BenchmarkRunSummary[]; summary?: BenchmarkRegressionSummary; comparison?: BenchmarkComparison }>(
    await fetch(`${getApiBase()}/api/benchmarks/runs?${params.toString()}`, { cache: 'no-store' }),
  );
  return {
    runs: Array.isArray(response.runs) ? response.runs : [],
    summary: response.summary ?? null,
    comparison: response.comparison ?? null,
  };
}

async function rerunBenchmarkRun(runId: string, payload: {
  agent_version?: string;
  prompt_version?: string;
  model_name?: string;
  target_agent_url?: string;
}) {
  return handleJson<BenchmarkReport>(
    await fetch(`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(runId)}/rerun`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

function scoreColor(score: number | undefined) {
  if (score === undefined) return 'var(--muted)';
  if (score >= 80) return 'var(--success-text)';
  if (score >= 60) return '#b45309';
  return 'var(--danger)';
}

function trendLabel(run: BenchmarkRunSummary) {
  if (typeof run.score_delta !== 'number') return 'Baseline';
  if (run.score_delta > 0) return `+${run.score_delta} vs prior`;
  if (run.score_delta < 0) return `${run.score_delta} vs prior`;
  return 'No change';
}

function trendColor(run: BenchmarkRunSummary) {
  if (run.trend === 'improved') return 'var(--success-text)';
  if (run.trend === 'regressed') return 'var(--danger)';
  return 'var(--muted)';
}

function summaryColor(summary: BenchmarkRegressionSummary | null) {
  if (summary?.status === 'improved') return 'var(--success-text)';
  if (summary?.status === 'regressed') return 'var(--danger)';
  return 'var(--text)';
}

function summaryDeltaLabel(summary: BenchmarkRegressionSummary | null) {
  if (!summary || typeof summary.score_delta !== 'number') return 'No prior run';
  if (summary.score_delta > 0) return `+${summary.score_delta}`;
  return String(summary.score_delta);
}

function failureCategoryItems(summary: BenchmarkRegressionSummary | null) {
  const counts = summary?.failure_category_counts;
  if (!counts) return [];

  return Object.entries(counts)
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([category, count]) => `${category}: ${count}`);
}

function benchmarkRunsCsvHref(payload: {
  suiteId?: string;
  scenarioId?: string;
  agentVersion?: string;
  promptVersion?: string;
  modelName?: string;
  targetAgentUrl?: string;
}) {
  const params = new URLSearchParams();
  if (payload.suiteId) params.set('suite_id', payload.suiteId);
  if (payload.scenarioId) params.set('scenario_id', payload.scenarioId);
  if (payload.agentVersion?.trim()) params.set('agent_version', payload.agentVersion.trim());
  if (payload.promptVersion?.trim()) params.set('prompt_version', payload.promptVersion.trim());
  if (payload.modelName?.trim()) params.set('model_name', payload.modelName.trim());
  if (payload.targetAgentUrl?.trim()) params.set('target_agent_url', payload.targetAgentUrl.trim());
  params.set('limit', '100');

  return `${getApiBase()}/api/benchmarks/runs.csv?${params.toString()}`;
}

function benchmarkRunsMarkdownHref(payload: {
  suiteId?: string;
  scenarioId?: string;
  agentVersion?: string;
  promptVersion?: string;
  modelName?: string;
  targetAgentUrl?: string;
}) {
  const params = new URLSearchParams();
  if (payload.suiteId) params.set('suite_id', payload.suiteId);
  if (payload.scenarioId) params.set('scenario_id', payload.scenarioId);
  if (payload.agentVersion?.trim()) params.set('agent_version', payload.agentVersion.trim());
  if (payload.promptVersion?.trim()) params.set('prompt_version', payload.promptVersion.trim());
  if (payload.modelName?.trim()) params.set('model_name', payload.modelName.trim());
  if (payload.targetAgentUrl?.trim()) params.set('target_agent_url', payload.targetAgentUrl.trim());
  params.set('limit', '100');

  return `${getApiBase()}/api/benchmarks/runs.md?${params.toString()}`;
}

function benchmarkRunsJsonlHref(payload: {
  suiteId?: string;
  scenarioId?: string;
  agentVersion?: string;
  promptVersion?: string;
  modelName?: string;
  targetAgentUrl?: string;
}) {
  const params = new URLSearchParams();
  if (payload.suiteId) params.set('suite_id', payload.suiteId);
  if (payload.scenarioId) params.set('scenario_id', payload.scenarioId);
  if (payload.agentVersion?.trim()) params.set('agent_version', payload.agentVersion.trim());
  if (payload.promptVersion?.trim()) params.set('prompt_version', payload.promptVersion.trim());
  if (payload.modelName?.trim()) params.set('model_name', payload.modelName.trim());
  if (payload.targetAgentUrl?.trim()) params.set('target_agent_url', payload.targetAgentUrl.trim());
  params.set('limit', '100');

  return `${getApiBase()}/api/benchmarks/runs.jsonl?${params.toString()}`;
}

function benchmarkRunsJunitHref(payload: {
  suiteId?: string;
  scenarioId?: string;
  agentVersion?: string;
  promptVersion?: string;
  modelName?: string;
  targetAgentUrl?: string;
}) {
  const params = new URLSearchParams();
  if (payload.suiteId) params.set('suite_id', payload.suiteId);
  if (payload.scenarioId) params.set('scenario_id', payload.scenarioId);
  if (payload.agentVersion?.trim()) params.set('agent_version', payload.agentVersion.trim());
  if (payload.promptVersion?.trim()) params.set('prompt_version', payload.promptVersion.trim());
  if (payload.modelName?.trim()) params.set('model_name', payload.modelName.trim());
  if (payload.targetAgentUrl?.trim()) params.set('target_agent_url', payload.targetAgentUrl.trim());
  params.set('limit', '100');

  return `${getApiBase()}/api/benchmarks/runs.junit.xml?${params.toString()}`;
}

function EvidenceItem({ item }: { item: string | JsonRecord }) {
  if (typeof item === 'string') {
    return <li>{item}</li>;
  }

  return <li><code>{JSON.stringify(item)}</code></li>;
}

export function BenchmarkRunner() {
  const [suites, setSuites] = useState<BenchmarkSuite[]>([]);
  const [selectedSuiteId, setSelectedSuiteId] = useState('');
  const [selectedScenarioId, setSelectedScenarioId] = useState('');
  const [transcript, setTranscript] = useState('');
  const [importedCallEvidence, setImportedCallEvidence] = useState('');
  const [actionTrace, setActionTrace] = useState('');
  const [finalState, setFinalState] = useState('');
  const [agentProfile, setAgentProfile] = useState('mock text agent');
  const [agentVersion, setAgentVersion] = useState('agent-v1');
  const [promptVersion, setPromptVersion] = useState('prompt-baseline');
  const [modelName, setModelName] = useState('mock-model');
  const [targetAgentUrl, setTargetAgentUrl] = useState('');
  const [includeFailure, setIncludeFailure] = useState(false);
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [suiteRun, setSuiteRun] = useState<BenchmarkSuiteSimulationResponse | null>(null);
  const [recentRuns, setRecentRuns] = useState<BenchmarkRunSummary[]>([]);
  const [regressionSummary, setRegressionSummary] = useState<BenchmarkRegressionSummary | null>(null);
  const [runComparison, setRunComparison] = useState<BenchmarkComparison | null>(null);
  const [simulationArtifacts, setSimulationArtifacts] = useState<SimulationArtifacts | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isSimulatingSuite, setIsSimulatingSuite] = useState(false);
  const [rerunningRunId, setRerunningRunId] = useState<string | null>(null);

  const selectedSuite = useMemo(
    () => suites.find((suite) => suite.id === selectedSuiteId) ?? suites[0] ?? null,
    [selectedSuiteId, suites],
  );
  const selectedScenario = useMemo(
    () => selectedSuite?.scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? selectedSuite?.scenarios[0] ?? null,
    [selectedScenarioId, selectedSuite],
  );

  const refreshRecentRuns = useCallback(async (suiteId = selectedSuite?.id, scenarioId = selectedScenario?.id) => {
    if (!suiteId || !scenarioId) {
      setRecentRuns([]);
      setRegressionSummary(null);
      setRunComparison(null);
      return;
    }

    try {
      const history = await fetchBenchmarkRuns({
        suite_id: suiteId,
        scenario_id: scenarioId,
        ...(agentVersion.trim() ? { agent_version: agentVersion.trim() } : {}),
        ...(promptVersion.trim() ? { prompt_version: promptVersion.trim() } : {}),
        ...(modelName.trim() ? { model_name: modelName.trim() } : {}),
        ...(targetAgentUrl.trim() ? { target_agent_url: targetAgentUrl.trim() } : {}),
      });
      setRecentRuns(history.runs);
      setRegressionSummary(history.summary);
      setRunComparison(history.comparison);
    } catch {
      setRecentRuns([]);
      setRegressionSummary(null);
      setRunComparison(null);
    }
  }, [agentVersion, modelName, promptVersion, selectedScenario?.id, selectedSuite?.id, targetAgentUrl]);

  useEffect(() => {
    let isMounted = true;

    async function loadSuites() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const nextSuites = await fetchBenchmarkSuites();
        if (!isMounted) return;
        setSuites(nextSuites);
        setSelectedSuiteId(nextSuites[0]?.id ?? '');
        setSelectedScenarioId(nextSuites[0]?.scenarios[0]?.id ?? '');
      } catch (err) {
        if (!isMounted) return;
        setLoadError(err instanceof Error ? err.message : 'Could not load benchmark suites');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadSuites();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedSuite) return;
    setSelectedScenarioId((current) => (
      selectedSuite.scenarios.some((scenario) => scenario.id === current) ? current : selectedSuite.scenarios[0]?.id ?? ''
    ));
  }, [selectedSuite]);

  useEffect(() => {
    if (!selectedScenario) return;

    setTranscript(selectedScenario.sample_transcript ?? '');
    setImportedCallEvidence('');
    setActionTrace(stringifyEditable(selectedScenario.sample_action_trace, '[]'));
    setFinalState(stringifyEditable(selectedScenario.sample_final_state ?? selectedScenario.expected_final_state, '{}'));
    setReport(null);
    setSuiteRun(null);
    setSimulationArtifacts(null);
    setRunError(null);
  }, [selectedScenario]);

  useEffect(() => {
    if (selectedSuite?.id && selectedScenario.id) {
      void refreshRecentRuns(selectedSuite.id, selectedScenario.id);
    }
  }, [refreshRecentRuns, selectedScenario?.id, selectedSuite?.id]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSuite || !selectedScenario) return;

    setIsRunning(true);
    setRunError(null);
    setReport(null);
    setSuiteRun(null);
    setSimulationArtifacts(null);

    try {
      const nextReport = await runBenchmark({
        suite_id: selectedSuite.id,
        scenario_id: selectedScenario.id,
        ...(agentVersion.trim() ? { agent_version: agentVersion.trim() } : {}),
        ...(promptVersion.trim() ? { prompt_version: promptVersion.trim() } : {}),
        ...(modelName.trim() ? { model_name: modelName.trim() } : {}),
        ...(targetAgentUrl.trim() ? { target_agent_url: targetAgentUrl.trim() } : {}),
        ...(hasEditableEvidence(transcript) ? { transcript } : {}),
        ...parseImportedCallEvidence(importedCallEvidence),
        ...(hasEditableEvidence(actionTrace) ? { action_trace: parseMaybeJson(actionTrace) } : {}),
        ...(hasEditableEvidence(finalState) ? { final_state: parseMaybeJson(finalState) } : {}),
      });
      setReport(nextReport);
      void refreshRecentRuns(selectedSuite.id, selectedScenario.id);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Benchmark run failed');
    } finally {
      setIsRunning(false);
    }
  }

  async function onSimulate() {
    if (!selectedSuite || !selectedScenario) return;

    setIsSimulating(true);
    setRunError(null);
    setReport(null);
    setSuiteRun(null);

    try {
      const simulation = await simulateBenchmark({
        suite_id: selectedSuite.id,
        scenario_id: selectedScenario.id,
        agent_profile: agentProfile,
        ...(agentVersion.trim() ? { agent_version: agentVersion.trim() } : {}),
        ...(promptVersion.trim() ? { prompt_version: promptVersion.trim() } : {}),
        ...(modelName.trim() ? { model_name: modelName.trim() } : {}),
        ...(targetAgentUrl.trim() ? { target_agent_url: targetAgentUrl.trim() } : {}),
        include_failure: includeFailure,
      });
      setTranscript(simulation.transcript);
      setImportedCallEvidence(stringifyEditable(simulation.vcon, ''));
      setActionTrace(stringifyEditable(simulation.action_trace, '[]'));
      setFinalState(stringifyEditable(simulation.final_state, '{}'));
      setReport(simulation.benchmark_report);
      void refreshRecentRuns(selectedSuite.id, selectedScenario.id);
      setSimulationArtifacts({
        conversation: Array.isArray(simulation.conversation) ? simulation.conversation : [],
        vcon: simulation.vcon ?? null,
      });
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Scenario simulation failed');
    } finally {
      setIsSimulating(false);
    }
  }

  async function onSimulateSuite() {
    if (!selectedSuite) return;

    setIsSimulatingSuite(true);
    setRunError(null);
    setReport(null);
    setSuiteRun(null);
    setSimulationArtifacts(null);

    try {
      const nextSuiteRun = await simulateBenchmarkSuite({
        suite_id: selectedSuite.id,
        agent_profile: agentProfile,
        ...(agentVersion.trim() ? { agent_version: agentVersion.trim() } : {}),
        ...(promptVersion.trim() ? { prompt_version: promptVersion.trim() } : {}),
        ...(modelName.trim() ? { model_name: modelName.trim() } : {}),
        ...(targetAgentUrl.trim() ? { target_agent_url: targetAgentUrl.trim() } : {}),
        include_failure: includeFailure,
      });
      setSuiteRun(nextSuiteRun);
      void refreshRecentRuns(selectedSuite.id, selectedScenario?.id);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Suite simulation failed');
    } finally {
      setIsSimulatingSuite(false);
    }
  }

  async function onRerun(runId: string) {
    if (!selectedSuite || !selectedScenario) return;

    setRerunningRunId(runId);
    setRunError(null);
    setReport(null);
    setSuiteRun(null);
    setSimulationArtifacts(null);

    try {
      const nextReport = await rerunBenchmarkRun(runId, {
        ...(agentVersion.trim() ? { agent_version: agentVersion.trim() } : {}),
        ...(promptVersion.trim() ? { prompt_version: promptVersion.trim() } : {}),
        ...(modelName.trim() ? { model_name: modelName.trim() } : {}),
        ...(targetAgentUrl.trim() ? { target_agent_url: targetAgentUrl.trim() } : {}),
      });
      setReport(nextReport);
      if (typeof nextReport.transcript === 'string') setTranscript(nextReport.transcript);
      setImportedCallEvidence('');
      setActionTrace(stringifyEditable(nextReport.action_trace, actionTrace));
      setFinalState(stringifyEditable(nextReport.final_state, finalState));
      void refreshRecentRuns(selectedSuite.id, selectedScenario.id);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Benchmark rerun failed');
    } finally {
      setRerunningRunId(null);
    }
  }

  const evidence = report?.evidence_spans ?? report?.evidence ?? [];
  const score = report?.score ?? report?.overall_score;
  const verdict = report?.verdict ?? report?.overall;
  const hasEvidence = hasEditableEvidence(transcript) || hasEditableEvidence(importedCallEvidence) || hasEditableEvidence(actionTrace) || hasEditableEvidence(finalState);

  return (
    <section style={{ display: 'grid', gap: 20 }}>
      <form onSubmit={onSubmit} className="card" style={{ padding: 24, display: 'grid', gap: 18 }}>
        {loadError ? (
          <div style={{ border: '1px solid var(--error-border)', background: 'var(--error-bg)', color: 'var(--error-text)', borderRadius: 8, padding: 12 }}>
            {loadError}
          </div>
        ) : null}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          <label style={{ display: 'grid', gap: 8 }}>
            <span style={{ fontWeight: 700 }}>Benchmark suite</span>
            <select
              value={selectedSuite?.id ?? ''}
              disabled={isLoading || !suites.length}
              onChange={(event) => setSelectedSuiteId(event.target.value)}
              style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
            >
              {suites.map((suite) => (
                <option key={suite.id} value={suite.id}>{suite.title}</option>
              ))}
            </select>
          </label>

          <label style={{ display: 'grid', gap: 8 }}>
            <span style={{ fontWeight: 700 }}>Scenario</span>
            <select
              value={selectedScenario?.id ?? ''}
              disabled={isLoading || !selectedSuite?.scenarios.length}
              onChange={(event) => setSelectedScenarioId(event.target.value)}
              style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
            >
              {(selectedSuite?.scenarios ?? []).map((scenario) => (
                <option key={scenario.id} value={scenario.id}>{scenario.title}</option>
              ))}
            </select>
          </label>
        </div>

        {isLoading ? <p style={{ margin: 0, color: 'var(--muted)' }}>Loading benchmark suites...</p> : null}

        {selectedScenario ? (
          <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, background: 'var(--panel-alt)', display: 'grid', gap: 10 }}>
            <div>
              <p style={{ margin: '0 0 6px', color: 'var(--muted)', fontSize: 13 }}>{selectedScenario.domain ?? selectedSuite?.title}</p>
              <h3 style={{ margin: 0 }}>{selectedScenario.title}</h3>
            </div>
            <p style={{ margin: 0, color: 'var(--muted)', lineHeight: 1.5 }}>{selectedScenario.user_goal || selectedScenario.user_persona || 'No goal provided.'}</p>
            <details>
              <summary style={{ cursor: 'pointer', fontWeight: 800 }}>Scenario rubric</summary>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginTop: 12 }}>
                <ScenarioList title="Required actions" items={toStringList(selectedScenario.required_actions)} />
                <ScenarioList title="Forbidden actions" items={toStringList(selectedScenario.forbidden_actions)} />
                <ScenarioList title="Edge cases" items={toStringList(selectedScenario.edge_cases)} />
                <ScenarioList title="Constraints" items={toStringList(selectedScenario.constraints)} />
              </div>
            </details>
          </div>
        ) : !isLoading ? (
          <p style={{ margin: 0, color: 'var(--muted)' }}>No benchmark scenarios are available yet.</p>
        ) : null}

        <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, display: 'grid', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) auto', gap: 16, alignItems: 'end' }}>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Agent profile</span>
              <input
                value={agentProfile}
                onChange={(event) => setAgentProfile(event.target.value)}
                placeholder="mock text agent"
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
              />
            </label>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Agent version</span>
              <input
                value={agentVersion}
                onChange={(event) => setAgentVersion(event.target.value)}
                placeholder="agent-v1"
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
              />
            </label>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Prompt version</span>
              <input
                value={promptVersion}
                onChange={(event) => setPromptVersion(event.target.value)}
                placeholder="prompt-baseline"
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
              />
            </label>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Model</span>
              <input
                value={modelName}
                onChange={(event) => setModelName(event.target.value)}
                placeholder="mock-model"
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
              />
            </label>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Target agent URL</span>
              <input
                value={targetAgentUrl}
                onChange={(event) => setTargetAgentUrl(event.target.value)}
                placeholder="https://agent.example.com/eval"
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'white' }}
              />
            </label>
            <label
              style={{
                minHeight: 46,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '10px 12px',
                fontWeight: 760,
              }}
            >
              <input
                type="checkbox"
                checked={includeFailure}
                onChange={(event) => setIncludeFailure(event.target.checked)}
              />
              Failure baseline
            </label>
          </div>
        </div>

        <details>
          <summary style={{ cursor: 'pointer', fontWeight: 800 }}>Evidence payload</summary>
          <div style={{ display: 'grid', gap: 16, marginTop: 14 }}>
            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Transcript</span>
              <textarea
                value={transcript}
                onChange={(event) => setTranscript(event.target.value)}
                rows={7}
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, resize: 'vertical', lineHeight: 1.45 }}
              />
            </label>

            <label style={{ display: 'grid', gap: 8 }}>
              <span style={{ fontWeight: 700 }}>Call or vCon JSON</span>
              <textarea
                value={importedCallEvidence}
                onChange={(event) => setImportedCallEvidence(event.target.value)}
                rows={7}
                placeholder='{"vcon":"0.0.2","dialog":[...]}'
                style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, resize: 'vertical', lineHeight: 1.45 }}
              />
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
              <label style={{ display: 'grid', gap: 8 }}>
                <span style={{ fontWeight: 700 }}>Action/tool trace</span>
                <textarea
                  value={actionTrace}
                  onChange={(event) => setActionTrace(event.target.value)}
                  rows={7}
                  style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, resize: 'vertical', lineHeight: 1.45 }}
                />
              </label>

              <label style={{ display: 'grid', gap: 8 }}>
                <span style={{ fontWeight: 700 }}>Final observed state</span>
                <textarea
                  value={finalState}
                  onChange={(event) => setFinalState(event.target.value)}
                  rows={7}
                  style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, resize: 'vertical', lineHeight: 1.45 }}
                />
              </label>
            </div>
          </div>
        </details>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          <button
            type="button"
            disabled={isSimulating || isSimulatingSuite || isRunning || !selectedScenario}
            onClick={onSimulate}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: 'white',
              color: 'var(--text)',
              padding: '12px 18px',
              fontWeight: 800,
              opacity: isSimulating || isSimulatingSuite || isRunning || !selectedScenario ? 0.65 : 1,
            }}
          >
            {isSimulating ? 'Simulating scenario...' : 'Simulate scenario'}
          </button>
          <button
            type="button"
            disabled={isSimulatingSuite || isSimulating || isRunning || !selectedSuite}
            onClick={onSimulateSuite}
            style={{
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: 'white',
              color: 'var(--text)',
              padding: '12px 18px',
              fontWeight: 800,
              opacity: isSimulatingSuite || isSimulating || isRunning || !selectedSuite ? 0.65 : 1,
            }}
          >
            {isSimulatingSuite ? 'Simulating suite...' : 'Simulate suite'}
          </button>
          <button
            type="submit"
            disabled={isRunning || isSimulating || isSimulatingSuite || !selectedScenario || !hasEvidence}
            style={{
              border: 0,
              borderRadius: 8,
              background: 'var(--accent)',
              color: 'white',
              padding: '12px 18px',
              fontWeight: 800,
              opacity: isRunning || isSimulating || isSimulatingSuite || !selectedScenario || !hasEvidence ? 0.65 : 1,
            }}
          >
            {isRunning ? 'Running benchmark...' : 'Run benchmark'}
          </button>
        </div>

        {runError ? <p style={{ color: 'var(--error-text)', margin: 0 }}>{runError}</p> : null}
      </form>

      {suiteRun ? (
        <section className="card" style={{ padding: 24, display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <p style={{ margin: '0 0 6px', color: 'var(--muted)' }}>Suite run</p>
              <h2 style={{ margin: 0, fontSize: 26 }}>{suiteRun.suite_name ?? suiteRun.suite_id}</h2>
            </div>
            <strong style={{ fontSize: 34, color: scoreColor(suiteRun.average_score) }}>{suiteRun.average_score}</strong>
          </div>
          <RunContext context={suiteRun.run_context} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
            <SummaryTile label="Scenarios" value={suiteRun.scenario_count} color="var(--text)" />
            <SummaryTile label="Passed" value={suiteRun.pass_count} color="var(--success-text)" />
            <SummaryTile label="Needs review" value={suiteRun.needs_review_count} color={suiteRun.needs_review_count ? 'var(--danger)' : 'var(--muted)'} />
            <SummaryTile label="Runs saved" value={suiteRun.run_count} color="var(--text)" />
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {suiteRun.reports.map((item) => (
              <div
                key={item.run_id ?? `${item.suite_id}-${item.scenario_id}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) auto',
                  gap: 12,
                  alignItems: 'start',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: '0 0 4px', fontWeight: 850 }}>{item.scenario_title ?? item.scenario_id}</p>
                  <p style={{ margin: 0, color: 'var(--muted)', textTransform: 'capitalize' }}>{item.verdict ?? 'complete'}</p>
                  <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 13 }}>
                    {suiteReportIssueLabel(item)}
                  </p>
                  <div style={{ marginTop: 8 }}>
                    <ReportExports runId={item.run_id} compact />
                  </div>
                </div>
                <strong style={{ fontSize: 24, color: scoreColor(item.overall_score ?? item.score) }}>{item.overall_score ?? item.score ?? 'n/a'}</strong>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {report ? (
        <section className="card" style={{ padding: 24, display: 'grid', gap: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <p style={{ margin: '0 0 6px', color: 'var(--muted)' }}>Benchmark report</p>
              <h2 style={{ margin: 0, fontSize: 28, textTransform: 'capitalize' }}>{verdict ?? 'Complete'}</h2>
            </div>
            {score !== undefined ? (
              <div style={{ fontSize: 40, fontWeight: 900, color: scoreColor(score) }}>{score}</div>
            ) : null}
          </div>

          <RunContext context={report.run_context} />

          <ReportExports runId={report.run_id} />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
            <ScoreTile label="Task completion" score={report.task_completion_score} />
            <ScoreTile label="Required actions" score={report.required_action_score} />
            <ScoreTile label="Forbidden actions" score={report.forbidden_action_score} />
            <ScoreTile label="Final state" score={report.final_state_score} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            <ReportList title="Failure categories" items={report.failure_categories} empty="No failure categories reported." />
            <ReportList title="Missing actions" items={report.missing_actions} empty="No missing required actions reported." />
            <ReportList title="Forbidden actions observed" items={report.forbidden_actions_observed} empty="No forbidden actions observed." />
            <ReportList title="Voice quality risks" items={report.voice_quality_risks} empty="No voice quality risks reported." />
            <ReportList title="Suggested fixes" items={report.suggested_fixes} empty="No suggested fixes reported." />
          </div>

          {simulationArtifacts ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
              <section style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <h3 style={{ marginTop: 0 }}>Synthetic conversation</h3>
                {simulationArtifacts.conversation.length ? (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {simulationArtifacts.conversation.map((turn, index) => (
                      <div key={`${index}-${turn.speaker ?? turn.role ?? 'turn'}`} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
                        <p style={{ margin: '0 0 4px', color: 'var(--muted)', fontSize: 13, fontWeight: 800 }}>
                          {turn.speaker ?? turn.role ?? `Turn ${index + 1}`}
                        </p>
                        <p style={{ margin: 0, lineHeight: 1.5 }}>{turn.text ?? turn.content ?? turn.body ?? ''}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ margin: 0, color: 'var(--muted)' }}>No synthetic turns returned.</p>
                )}
              </section>

              <section style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
                <h3 style={{ marginTop: 0 }}>vCon artifact</h3>
                {simulationArtifacts.vcon ? (
                  <pre style={{ maxHeight: 320, overflow: 'auto', background: '#0f172a', color: '#e2e8f0', borderRadius: 8, padding: 14, margin: 0 }}>
                    {JSON.stringify(simulationArtifacts.vcon, null, 2)}
                  </pre>
                ) : (
                  <p style={{ margin: 0, color: 'var(--muted)' }}>No vCon artifact returned.</p>
                )}
              </section>
            </div>
          ) : null}

          <ConversationEvidenceSummary report={report} />

          <div>
            <h3 style={{ marginTop: 0 }}>Evidence</h3>
            {evidence.length ? (
              <ul style={{ marginBottom: 0 }}>
                {evidence.map((item, index) => (
                  <EvidenceItem key={`${index}-${typeof item === 'string' ? item : JSON.stringify(item)}`} item={item} />
                ))}
              </ul>
            ) : (
              <p style={{ margin: 0, color: 'var(--muted)' }}>No evidence spans returned.</p>
            )}
          </div>

          <details>
            <summary style={{ cursor: 'pointer', fontWeight: 800 }}>Raw benchmark report</summary>
            <pre style={{ overflowX: 'auto', background: '#0f172a', color: '#e2e8f0', borderRadius: 8, padding: 16 }}>
              {JSON.stringify(report, null, 2)}
            </pre>
          </details>
        </section>
      ) : null}

      {recentRuns.length ? (
        <section className="card" style={{ padding: 24, display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <p style={{ margin: '0 0 6px', color: 'var(--muted)' }}>Run history</p>
              <h2 style={{ margin: 0, fontSize: 24 }}>Recent scenario runs</h2>
            </div>
            <div style={{ display: 'inline-flex', gap: 8, flexWrap: 'wrap' }}>
              <a
                href={benchmarkRunsCsvHref({
                  suiteId: selectedSuite?.id,
                  scenarioId: selectedScenario?.id,
                  agentVersion,
                  promptVersion,
                  modelName,
                  targetAgentUrl,
                })}
                target="_blank"
                rel="noreferrer"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--accent)',
                  fontSize: 13,
                  fontWeight: 850,
                  padding: '7px 10px',
                  textDecoration: 'none',
                }}
              >
                Export CSV
              </a>
              <a
                href={benchmarkRunsMarkdownHref({
                  suiteId: selectedSuite?.id,
                  scenarioId: selectedScenario?.id,
                  agentVersion,
                  promptVersion,
                  modelName,
                  targetAgentUrl,
                })}
                target="_blank"
                rel="noreferrer"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--accent)',
                  fontSize: 13,
                  fontWeight: 850,
                  padding: '7px 10px',
                  textDecoration: 'none',
                }}
              >
                Export Markdown
              </a>
              <a
                href={benchmarkRunsJsonlHref({
                  suiteId: selectedSuite?.id,
                  scenarioId: selectedScenario?.id,
                  agentVersion,
                  promptVersion,
                  modelName,
                  targetAgentUrl,
                })}
                target="_blank"
                rel="noreferrer"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--accent)',
                  fontSize: 13,
                  fontWeight: 850,
                  padding: '7px 10px',
                  textDecoration: 'none',
                }}
              >
                Export JSONL
              </a>
              <a
                href={benchmarkRunsJunitHref({
                  suiteId: selectedSuite?.id,
                  scenarioId: selectedScenario?.id,
                  agentVersion,
                  promptVersion,
                  modelName,
                  targetAgentUrl,
                })}
                target="_blank"
                rel="noreferrer"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  color: 'var(--accent)',
                  fontSize: 13,
                  fontWeight: 850,
                  padding: '7px 10px',
                  textDecoration: 'none',
                }}
              >
                Export JUnit
              </a>
            </div>
          </div>
          {regressionSummary ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
              <SummaryTile label="Status" value={regressionSummary.status} color={summaryColor(regressionSummary)} />
              <SummaryTile label="Average" value={regressionSummary.average_score ?? 'n/a'} color={scoreColor(regressionSummary.average_score ?? undefined)} />
              <SummaryTile label="Passed" value={regressionSummary.pass_count ?? 0} color="var(--success-text)" />
              <SummaryTile label="Pass rate" value={regressionSummary.pass_rate === null || regressionSummary.pass_rate === undefined ? 'n/a' : `${regressionSummary.pass_rate}%`} color={scoreColor(regressionSummary.pass_rate ?? undefined)} />
              <SummaryTile label="Needs review" value={regressionSummary.needs_review_count ?? 0} color={regressionSummary.needs_review_count ? 'var(--danger)' : 'var(--muted)'} />
              <SummaryTile label="Latest" value={regressionSummary.latest_score ?? 'n/a'} color={scoreColor(regressionSummary.latest_score ?? undefined)} />
              <SummaryTile label="Prior" value={regressionSummary.previous_score ?? 'n/a'} color={scoreColor(regressionSummary.previous_score ?? undefined)} />
              <SummaryTile label="Delta" value={summaryDeltaLabel(regressionSummary)} color={summaryColor(regressionSummary)} />
              <SummaryTile label="Top failure" value={regressionSummary.most_common_failure_category ?? 'none'} color={regressionSummary.most_common_failure_category ? 'var(--danger)' : 'var(--muted)'} />
              <SummaryTile label="Voice risks" value={regressionSummary.latest_voice_quality_risk_count ?? 0} color={regressionSummary.latest_voice_quality_risk_count ? 'var(--danger)' : 'var(--muted)'} />
            </div>
          ) : null}
          {failureCategoryItems(regressionSummary).length ? (
            <ComparisonList
              title="Failure category counts"
              items={failureCategoryItems(regressionSummary)}
              empty="No failure categories in this history."
              tone="bad"
            />
          ) : null}
          {runComparison?.status === 'compared' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
              <ComparisonList title="New misses" items={runComparison.new_missing_actions} empty="No new missing actions." tone="bad" />
              <ComparisonList title="Resolved misses" items={runComparison.resolved_missing_actions} empty="No resolved missing actions." tone="good" />
              <ComparisonList title="New failures" items={[...(runComparison.new_failure_categories ?? []), ...(runComparison.new_forbidden_actions ?? [])]} empty="No new failure categories." tone="bad" />
              <ComparisonList title="Resolved failures" items={[...(runComparison.resolved_failure_categories ?? []), ...(runComparison.resolved_forbidden_actions ?? [])]} empty="No resolved failure categories." tone="good" />
            </div>
          ) : null}
          <div style={{ display: 'grid', gap: 10 }}>
            {recentRuns.map((run) => (
              <div
                key={run.run_id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) auto',
                  gap: 12,
                  alignItems: 'center',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: '0 0 4px', fontWeight: 850, textTransform: 'capitalize' }}>{run.verdict}</p>
                  <p style={{ margin: 0, color: 'var(--muted)', fontSize: 13 }}>
                    {run.created_at ? new Date(run.created_at).toLocaleString() : run.run_id}
                  </p>
                  <p style={{ margin: '4px 0 0', color: trendColor(run), fontSize: 13, fontWeight: 800 }}>
                    {trendLabel(run)}
                  </p>
                  {run.voice_quality_risk_count ? (
                    <p style={{ margin: '4px 0 0', color: 'var(--danger)', fontSize: 13, fontWeight: 800 }}>
                      Voice risks: {run.voice_quality_risk_count}
                    </p>
                  ) : null}
                  <RunContext context={run.run_context} compact />
                </div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
                  <button
                    type="button"
                    disabled={Boolean(rerunningRunId)}
                    onClick={() => void onRerun(run.run_id)}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      background: 'white',
                      color: 'var(--accent)',
                      cursor: rerunningRunId ? 'default' : 'pointer',
                      fontWeight: 800,
                      padding: '7px 10px',
                      opacity: rerunningRunId ? 0.65 : 1,
                    }}
                  >
                    {rerunningRunId === run.run_id ? 'Rerunning...' : 'Rerun'}
                  </button>
                  <a
                    href={`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(run.run_id)}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}
                  >
                    Report JSON
                  </a>
                  <a
                    href={`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(run.run_id)}/vcon`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}
                  >
                    vCon
                  </a>
                  <a
                    href={`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(run.run_id)}/junit`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}
                  >
                    JUnit
                  </a>
                  <a
                    href={`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(run.run_id)}/jsonl`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}
                  >
                    JSONL
                  </a>
                  <a
                    href={`${getApiBase()}/api/benchmarks/runs/${encodeURIComponent(run.run_id)}/markdown`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: 'var(--accent)', fontWeight: 800, textDecoration: 'none' }}
                  >
                    Markdown
                  </a>
                  <strong style={{ fontSize: 24, color: scoreColor(run.overall_score) }}>{run.overall_score}</strong>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}

function ScenarioList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p style={{ margin: '0 0 6px', fontWeight: 800 }}>{title}</p>
      {items.length ? (
        <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--muted)', lineHeight: 1.5 }}>
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p style={{ margin: 0, color: 'var(--muted)' }}>Not specified.</p>
      )}
    </div>
  );
}

function ScoreTile({ label, score }: { label: string; score?: number }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
      <p style={{ margin: '0 0 6px', color: 'var(--muted)', fontSize: 13 }}>{label}</p>
      <p style={{ margin: 0, fontSize: 24, fontWeight: 900, color: scoreColor(score) }}>{score ?? 'n/a'}</p>
    </div>
  );
}

function SummaryTile({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
      <p style={{ margin: '0 0 6px', color: 'var(--muted)', fontSize: 13 }}>{label}</p>
      <p style={{ margin: 0, fontSize: 20, fontWeight: 900, color, textTransform: typeof value === 'string' ? 'capitalize' : undefined }}>
        {value}
      </p>
    </div>
  );
}

function RunContext({ context, compact = false }: { context?: BenchmarkReport['run_context']; compact?: boolean }) {
  const items = [
    context?.agent_version ? `Agent ${context.agent_version}` : null,
    context?.prompt_version ? `Prompt ${context.prompt_version}` : null,
    context?.model_name ? `Model ${context.model_name}` : null,
    context?.target_agent_url ? `Target ${context.target_agent_url}` : null,
  ].filter(Boolean);

  if (!items.length) return null;

  return (
    <p
      style={{
        margin: compact ? '4px 0 0' : 0,
        color: 'var(--muted)',
        fontSize: compact ? 13 : 14,
        lineHeight: 1.45,
      }}
    >
      {items.join(' · ')}
    </p>
  );
}

function ConversationEvidenceSummary({ report }: { report: BenchmarkReport }) {
  const insights = report.conversation_insights;
  const callArtifacts = report.call_artifacts;
  const decisions = insights?.decisions ?? [];
  const commitments = insights?.commitments ?? [];
  const followUps = insights?.follow_up_actions ?? [];
  const hasInsights = Boolean(
    (insights?.speaker_count ?? 0) > 0
    || decisions.length
    || commitments.length
    || followUps.length,
  );
  const hasCallArtifacts = Boolean(
    callArtifacts
    && (
      callArtifacts.turn_count
      || callArtifacts.media_count
      || callArtifacts.duration_seconds
      || callArtifacts.average_latency_ms
      || callArtifacts.max_latency_ms
      || callArtifacts.interruption_count
      || callArtifacts.tool_call_count
      || callArtifacts.failed_tool_call_count
      || callArtifacts.modalities?.length
    ),
  );

  if (!hasInsights && !hasCallArtifacts) return null;

  return (
    <section style={{ display: 'grid', gap: 14 }}>
      <h3 style={{ margin: 0 }}>Conversation evidence</h3>
      {hasInsights ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          <SummaryTile label="Speakers" value={insights?.speaker_count ?? 0} color="var(--text)" />
          <ReportList title="Speaker names" items={insights?.speakers} empty="No named speakers found." />
          <ReportList title="Decisions" items={decisions.map(formatConversationItem)} empty="No decisions detected." />
          <ReportList title="Commitments" items={commitments.map(formatConversationItem)} empty="No commitments detected." />
          <ReportList title="Follow-up actions" items={followUps.map(formatConversationItem)} empty="No follow-up actions detected." />
        </div>
      ) : null}
      {hasCallArtifacts && callArtifacts ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          <SummaryTile label="Source" value={callArtifacts.source ?? 'call'} color="var(--text)" />
          <SummaryTile label="Turns" value={callArtifacts.turn_count ?? 0} color="var(--text)" />
          <SummaryTile label="Media" value={callArtifacts.media_count ?? 0} color="var(--text)" />
          {callArtifacts.duration_seconds !== undefined ? (
            <SummaryTile label="Duration" value={`${callArtifacts.duration_seconds}s`} color="var(--text)" />
          ) : null}
          {callArtifacts.average_latency_ms !== undefined ? (
            <SummaryTile label="Avg latency" value={`${callArtifacts.average_latency_ms}ms`} color="var(--text)" />
          ) : null}
          {callArtifacts.interruption_count !== undefined ? (
            <SummaryTile label="Interruptions" value={callArtifacts.interruption_count} color={callArtifacts.interruption_count ? 'var(--danger)' : 'var(--muted)'} />
          ) : null}
          {callArtifacts.tool_call_count !== undefined ? (
            <SummaryTile label="Tool calls" value={callArtifacts.tool_call_count} color="var(--text)" />
          ) : null}
          {callArtifacts.failed_tool_call_count !== undefined ? (
            <SummaryTile label="Tool failures" value={callArtifacts.failed_tool_call_count} color={callArtifacts.failed_tool_call_count ? 'var(--danger)' : 'var(--muted)'} />
          ) : null}
          <ReportList title="Modalities" items={callArtifacts.modalities} empty="No media modalities reported." />
        </div>
      ) : null}
    </section>
  );
}

function formatConversationItem(item: string | JsonRecord) {
  if (typeof item === 'string') return item;
  const speaker = typeof item.speaker === 'string' && item.speaker.trim() ? `${item.speaker}: ` : '';
  const text = typeof item.text === 'string' && item.text.trim() ? item.text : JSON.stringify(item);
  return `${speaker}${text}`;
}

function suiteReportIssueLabel(report: BenchmarkReport) {
  const missingCount = report.missing_actions?.length ?? 0;
  const forbiddenCount = report.forbidden_actions_observed?.length ?? 0;
  const failureCount = report.failure_categories?.length ?? 0;
  const issueCount = missingCount + forbiddenCount + failureCount;

  if (!issueCount) return 'No missing actions or policy hits.';

  const parts = [
    missingCount ? `${missingCount} missing` : null,
    forbiddenCount ? `${forbiddenCount} forbidden` : null,
    failureCount ? `${failureCount} failure ${failureCount === 1 ? 'category' : 'categories'}` : null,
  ].filter(Boolean);

  return parts.join(' · ');
}

function ReportExports({ runId, compact = false }: { runId?: string; compact?: boolean }) {
  if (!runId) return null;

  const encodedRunId = encodeURIComponent(runId);
  const exports = [
    { label: 'Report JSON', href: `${getApiBase()}/api/benchmarks/runs/${encodedRunId}` },
    { label: 'vCon', href: `${getApiBase()}/api/benchmarks/runs/${encodedRunId}/vcon` },
    { label: 'JUnit', href: `${getApiBase()}/api/benchmarks/runs/${encodedRunId}/junit` },
    { label: 'JSONL', href: `${getApiBase()}/api/benchmarks/runs/${encodedRunId}/jsonl` },
    { label: 'Markdown', href: `${getApiBase()}/api/benchmarks/runs/${encodedRunId}/markdown` },
  ];

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
      <span style={{ color: 'var(--muted)', fontSize: 13, fontWeight: 800 }}>Exports</span>
      {exports.map((item) => (
        <a
          key={item.label}
          href={item.href}
          target="_blank"
          rel="noreferrer"
          style={{
            border: '1px solid var(--border)',
            borderRadius: 8,
            color: 'var(--accent)',
            fontSize: 13,
            fontWeight: 850,
            padding: compact ? '5px 8px' : '7px 10px',
            textDecoration: 'none',
          }}
        >
          {item.label}
        </a>
      ))}
    </div>
  );
}

function ComparisonList({ title, items, empty, tone }: { title: string; items?: string[]; empty: string; tone: 'good' | 'bad' }) {
  const color = tone === 'good' ? 'var(--success-text)' : 'var(--danger)';

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
      <p style={{ margin: '0 0 8px', fontWeight: 850, color }}>{title}</p>
      {items?.length ? (
        <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--muted)', lineHeight: 1.5 }}>
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p style={{ margin: 0, color: 'var(--muted)' }}>{empty}</p>
      )}
    </div>
  );
}

function ReportList({ title, items, empty }: { title: string; items?: string[]; empty: string }) {
  return (
    <div>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {items?.length ? (
        <ul style={{ marginBottom: 0 }}>
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p style={{ margin: 0, color: 'var(--muted)' }}>{empty}</p>
      )}
    </div>
  );
}
