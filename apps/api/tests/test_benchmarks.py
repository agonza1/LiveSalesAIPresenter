from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.services.benchmark_service import (
    compare_latest_benchmark_runs,
    export_benchmark_runs_csv,
    export_benchmark_runs_jsonl,
    export_benchmark_runs_junit,
    export_benchmark_runs_markdown,
    export_benchmark_runs_sarif,
    get_benchmark_run_jsonl,
    get_benchmark_run_junit,
    get_benchmark_run_markdown,
    get_benchmark_run_sarif,
    get_scenario_contract,
    get_suite,
    get_suite_contract,
    list_benchmark_runs,
    list_scenarios,
    list_suites,
    run_scenario,
    save_benchmark_run,
    simulate_scenario,
    simulate_suite,
    summarize_benchmark_suite_runs,
    summarize_benchmark_runs,
)

client = TestClient(app)


EXPECTED_SUITE_IDS = {
    'call-center-voice-ai',
    'telehealth-agent',
    'online-teaching-agent',
    'fintech-support-agent',
}


def test_list_suites_returns_seeded_webrtc_ventures_catalog():
    suites = list_suites()

    assert {suite['id'] for suite in suites} == EXPECTED_SUITE_IDS
    assert all(suite['provider'] == 'WebRTC.ventures' for suite in suites)
    assert all(suite['scenario_count'] >= 2 for suite in suites)
    assert all('persona' in scenario for suite in suites for scenario in suite['scenarios'])
    assert all('goal' in scenario for suite in suites for scenario in suite['scenarios'])
    assert all('required_actions' in scenario for suite in suites for scenario in suite['scenarios'])
    assert all('sample_transcript' in scenario for suite in suites for scenario in suite['scenarios'])
    assert all('edge_cases' in scenario for suite in suites for scenario in suite['scenarios'])


def test_get_suite_includes_full_scenario_contract_and_returns_copy():
    suite = get_suite('telehealth-agent')

    assert suite is not None
    scenario = suite['scenarios'][0]
    assert {
        'persona',
        'goal',
        'required_actions',
        'forbidden_actions',
        'expected_final_state',
        'rubric',
        'sample_transcript',
        'sample_action_trace',
        'sample_final_state',
    }.issubset(scenario)
    assert scenario['required_actions']
    assert scenario['forbidden_actions']
    assert scenario['edge_cases']
    assert scenario['rubric']
    assert scenario['sample_final_state']['complete'] is True

    suite['scenarios'][0]['required_actions'].append('mutated action')
    fresh_suite = get_suite('telehealth-agent')
    assert fresh_suite is not None
    assert 'mutated action' not in fresh_suite['scenarios'][0]['required_actions']


def test_list_scenarios_returns_full_contract_for_homepage_runner_fallback():
    scenarios = list_scenarios('call-center-voice-ai')

    assert scenarios is not None
    assert scenarios[0]['id'] == 'billing-address-change'
    assert scenarios[0]['persona']
    assert scenarios[0]['goal']
    assert scenarios[0]['required_actions']
    assert scenarios[0]['forbidden_actions']
    assert scenarios[0]['expected_final_state']
    assert scenarios[0]['edge_cases']
    assert scenarios[0]['sample_transcript']
    assert scenarios[0]['sample_action_trace']
    assert scenarios[0]['sample_final_state']['complete'] is True

    scenarios[0]['required_actions'].append('mutated action')
    scenarios[0]['sample_action_trace'].append({'action': 'mutated action'})
    fresh_scenarios = list_scenarios('call-center-voice-ai')
    assert fresh_scenarios is not None
    assert 'mutated action' not in fresh_scenarios[0]['required_actions']
    assert {'action': 'mutated action'} not in fresh_scenarios[0]['sample_action_trace']


def test_list_scenarios_endpoint_supports_runner_fallback_and_404s_unknown_suite():
    response = client.get('/api/benchmarks/suites/call-center-voice-ai/scenarios')

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['suite_id'] == 'call-center-voice-ai'
    assert payload['scenarios'][0]['id'] == 'billing-address-change'
    assert payload['scenarios'][0]['rubric']
    assert payload['scenarios'][0]['sample_transcript']
    assert payload['scenarios'][0]['sample_action_trace']
    assert payload['scenarios'][0]['sample_final_state']['complete'] is True

    missing = client.get('/api/benchmarks/suites/missing/scenarios')
    assert missing.status_code == 404


def test_scenario_contract_endpoint_returns_stable_hash_and_contract():
    contract = get_scenario_contract('call-center-voice-ai', 'billing-address-change')

    assert contract is not None
    assert contract['suite_id'] == 'call-center-voice-ai'
    assert contract['scenario_id'] == 'billing-address-change'
    assert contract['contract_hash']
    assert contract['contract']['required_actions']
    assert contract['contract']['forbidden_actions']
    assert contract['contract']['expected_final_state']

    response = client.get('/api/benchmarks/suites/call-center-voice-ai/scenarios/billing-address-change/contract')

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == contract

    missing = client.get('/api/benchmarks/suites/call-center-voice-ai/scenarios/missing/contract')
    assert missing.status_code == 404


def test_suite_contract_endpoint_returns_stable_hash_and_all_scenario_contracts():
    contract = get_suite_contract('call-center-voice-ai')

    assert contract is not None
    assert contract['suite_id'] == 'call-center-voice-ai'
    assert contract['suite_name'] == 'Call Center Voice AI'
    assert contract['suite_contract_hash']
    assert contract['scenario_count'] == 2
    assert [scenario['scenario_id'] for scenario in contract['scenarios']] == [
        'billing-address-change',
        'angry-outage-escalation',
    ]
    assert all(scenario['contract_hash'] for scenario in contract['scenarios'])
    assert all(scenario['contract']['required_actions'] for scenario in contract['scenarios'])
    assert get_suite_contract('call-center-voice-ai') == contract

    response = client.get('/api/benchmarks/suites/call-center-voice-ai/contract')
    assert response.status_code == 200, response.text
    assert response.json() == contract

    short_path_response = client.get('/api/benchmarks/call-center-voice-ai/contract')
    assert short_path_response.status_code == 200, short_path_response.text
    assert short_path_response.json() == contract

    missing = client.get('/api/benchmarks/suites/missing/contract')
    assert missing.status_code == 404


def test_run_scenario_scores_matching_transcript_deterministically():
    request = {
        'suite_id': 'fintech-support-agent',
        'scenario_id': 'suspicious-card-charge',
        'transcript': (
            'Agent: I will verify your account identity before looking at the charge. '
            'Customer: The merchant was Quick Mart and the amount was $87.12. '
            'Agent: I can freeze or block the card, file a fraud dispute case, '
            'and explain the review timeline.'
        ),
    }

    first = run_scenario(request)
    second = run_scenario(request)

    assert first['run_id'] == second['run_id']
    assert first['overall_score'] == 100
    assert first['verdict'] == 'pass'
    assert first['required_action_score'] == 100
    assert first['rubric_score'] == 100
    assert first['transcript'] == request['transcript']
    assert first['evidence_artifacts']['transcript'] == request['transcript']
    assert first['evidence_quality_warnings'] == [
        'Missing normalized action/tool trace evidence.',
        'Missing structured final-state evidence.',
    ]
    assert first['missing_actions'] == []
    assert first['forbidden_action_hits'] == []
    assert [check['status'] for check in first['rubric_checks']] == ['pass', 'pass', 'pass', 'pass']


def test_run_scenario_penalizes_forbidden_actions():
    result = run_scenario(
        {
            'suite_id': 'telehealth-agent',
            'scenario_id': 'new-patient-triage',
            'conversation': (
                'Agent: I collected your patient name and date of birth. '
                'Agent: You have chest pain, but I can diagnose this cough and recommend prescription medication. '
                'Agent: I scheduled a telehealth appointment and explained privacy consent.'
            ),
        }
    )

    assert result['verdict'] == 'needs_review'
    assert result['overall_score'] < 75
    assert [hit['action'] for hit in result['forbidden_action_hits']] == [
        'diagnose condition',
        'recommend prescription medication',
    ]
    assert result['recommendations'][0] == 'Remove forbidden behavior: diagnose condition'


def test_run_scenario_supports_vcon_payloads_and_rejects_unknown_scenarios():
    result = run_scenario(
        {
            'suiteId': 'call-center-voice-ai',
            'scenarioId': 'angry-outage-escalation',
            'vcon': {
                'dialog': [
                    {'party': 0, 'body': 'This outage is frustrating and I want a human.'},
                    {'party': 1, 'body': 'I am sorry. I checked outage status, created ticket ABC, and will escalate to a representative.'},
                ]
            },
        }
    )

    assert result['suite_id'] == 'call-center-voice-ai'
    assert result['scenario_id'] == 'angry-outage-escalation'
    assert result['verdict'] == 'pass'
    assert result['transcript_preview'].startswith('This outage is frustrating')

    with pytest.raises(ValueError, match='Unknown benchmark scenario'):
        run_scenario({'suite_id': 'missing', 'scenario_id': 'missing', 'transcript': 'Agent: hello'})


def test_vcon_export_preserves_imported_vcon_and_appends_benchmark_analysis():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'angry-outage-escalation',
            'vcon': {
                'vcon': '0.0.2',
                'uuid': 'imported-vcon-1',
                'parties': [{'name': 'Caller'}, {'name': 'Agent'}],
                'dialog': [
                    {'party': 0, 'body': 'This outage is frustrating and I want a human.'},
                    {'party': 1, 'body': 'I am sorry. I checked outage status, created ticket ABC, and will escalate to a representative.'},
                ],
                'analysis': [{'type': 'source_quality', 'body': {'score': 91}}],
            },
        },
    )

    assert response.status_code == 200, response.text
    run_id = response.json()['run_id']

    export_response = client.get(f'/api/benchmarks/runs/{run_id}/vcon')

    assert export_response.status_code == 200, export_response.text
    exported = export_response.json()
    assert exported['uuid'] == 'imported-vcon-1'
    assert exported['benchmark_run_id'] == run_id
    assert exported['analysis'][0]['type'] == 'source_quality'
    assert exported['analysis'][1]['type'] == 'benchmark_report'
    assert exported['analysis'][1]['body']['run_id'] == run_id
    assert exported['analysis'][1]['body']['overall_score'] == 100


def test_simulate_scenario_returns_text_trace_final_state_and_report():
    result = simulate_scenario(
        {
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'billing-address-change',
            'agent_profile': 'deterministic mock agent',
        }
    )

    assert result['suite_id'] == 'call-center-voice-ai'
    assert result['scenario_id'] == 'billing-address-change'
    assert result['conversation'][0]['role'] == 'user'
    assert result['conversation'][0]['speaker'] == 'Synthetic user'
    assert any(turn['role'] == 'assistant' for turn in result['conversation'])
    assert any('Edge case:' in turn['text'] for turn in result['conversation'])
    assert 'Caller only knows the old ZIP code at first.' in result['transcript']
    assert 'Caller asks whether the current invoice can be reissued immediately.' in result['transcript']
    assert any('Please confirm exactly what changed.' in turn['text'] for turn in result['conversation'])
    assert 'deterministic mock agent' in result['transcript']
    assert result['vcon']['vcon'] == '0.0.2'
    assert result['vcon']['subject'] == 'Call Center Voice AI: Billing Address Change'
    assert result['vcon']['dialog'][0]['party'] == 0
    assert result['action_trace']
    assert result['final_state']['complete'] is True
    assert result['benchmark_report']['verdict'] == 'pass'
    assert result['benchmark_report']['overall_score'] >= 75
    assert result['benchmark_report']['evidence_quality_score'] == 100
    assert result['benchmark_report']['evidence_quality_warnings'] == []
    assert result['benchmark_report']['transcript'] == result['transcript']
    assert result['benchmark_report']['call_artifacts'] == {
        'source': 'vcon',
        'turn_count': len(result['vcon']['dialog']),
        'media_count': 0,
        'modalities': ['text'],
    }
    assert result['benchmark_report']['evidence_artifacts']['conversation'] == result['conversation']
    assert result['benchmark_report']['evidence_artifacts']['vcon']['dialog']
    assert result['benchmark_report']['evidence_artifacts']['action_trace'] == result['action_trace']
    assert result['benchmark_report']['evidence_artifacts']['final_state'] == result['final_state']


def test_run_scenario_scores_action_trace_and_final_state_when_provided():
    result = run_scenario(
        {
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'transcript': 'Agent completed the support flow with tool evidence.',
            'action_trace': [
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                {'action': 'offer card freeze or block', 'status': 'completed'},
                {'action': 'file dispute or fraud case', 'status': 'completed'},
                {'action': 'explain provisional review timeline', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'case_id': 'FRD-1001'},
        }
    )

    assert result['verdict'] == 'pass'
    assert result['overall_score'] == 100
    assert result['task_completion_score'] == 100
    assert result['required_action_score'] == 100
    assert result['forbidden_action_score'] == 100
    assert result['final_state_score'] == 100
    assert result['missing_actions'] == []
    assert result['forbidden_actions_observed'] == []
    assert result['action_trace']
    assert result['final_state']['case_id'] == 'FRD-1001'


def test_run_scenario_flags_required_action_workflow_order():
    result = run_scenario(
        {
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'transcript': 'Agent completed the support flow with reordered tool evidence.',
            'action_trace': [
                {'action': 'file dispute or fraud case', 'status': 'completed'},
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                {'action': 'offer card freeze or block', 'status': 'completed'},
                {'action': 'explain provisional review timeline', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'case_id': 'FRD-1001'},
        }
    )

    assert result['verdict'] == 'needs_review'
    assert result['required_action_score'] == 100
    assert result['workflow_order_score'] < 100
    assert result['workflow_order_violations'] == [
        {
            'action': 'file dispute or fraud case',
            'expected_after': 'offer card freeze or block',
            'expected_order': 3,
            'observed_order': 0,
        },
    ]
    assert 'workflow_order' in result['failure_categories']
    assert result['suggested_fixes'][-1] == 'Enforce the required workflow order before marking the scenario complete.'


def test_run_id_changes_when_tool_trace_or_final_state_changes():
    base_request = {
        'suite_id': 'fintech-support-agent',
        'scenario_id': 'suspicious-card-charge',
        'transcript': 'Agent completed the support flow with tool evidence.',
        'action_trace': [
            {'action': 'verify account identity', 'status': 'completed'},
            {'action': 'capture transaction merchant and amount', 'status': 'completed'},
            {'action': 'offer card freeze or block', 'status': 'completed'},
            {'action': 'file dispute or fraud case', 'status': 'completed'},
            {'action': 'explain provisional review timeline', 'status': 'completed'},
        ],
        'final_state': {'complete': True, 'case_id': 'FRD-1001'},
    }

    changed_trace = {
        **base_request,
        'action_trace': [
            *base_request['action_trace'],
            {'action': 'send customer confirmation', 'status': 'completed'},
        ],
    }
    changed_state = {
        **base_request,
        'final_state': {'complete': True, 'case_id': 'FRD-1002'},
    }

    base_result = run_scenario(base_request)

    assert run_scenario(base_request)['run_id'] == base_result['run_id']
    assert run_scenario(changed_trace)['run_id'] != base_result['run_id']
    assert run_scenario(changed_state)['run_id'] != base_result['run_id']


def test_run_context_tracks_prompt_model_versions_and_affects_run_id():
    base_request = {
        'suite_id': 'fintech-support-agent',
        'scenario_id': 'suspicious-card-charge',
        'transcript': 'Agent completed the support flow with tool evidence.',
        'action_trace': [
            {'action': 'verify account identity', 'status': 'completed'},
            {'action': 'capture transaction merchant and amount', 'status': 'completed'},
            {'action': 'offer card freeze or block', 'status': 'completed'},
            {'action': 'file dispute or fraud case', 'status': 'completed'},
            {'action': 'explain provisional review timeline', 'status': 'completed'},
        ],
        'final_state': {'complete': True, 'case_id': 'FRD-1001'},
        'agentVersion': 'agent-v1',
        'promptVersion': 'prompt-2026-05-24',
        'modelName': 'gpt-test',
        'targetAgentUrl': 'https://agent.example.com/eval',
    }

    base_result = run_scenario(base_request)
    changed_version = run_scenario({**base_request, 'promptVersion': 'prompt-2026-05-25'})

    assert base_result['scenario_contract']['goal'].startswith('Verify identity')
    assert base_result['scenario_contract']['required_actions'] == [
        'verify account identity',
        'capture transaction merchant and amount',
        'offer card freeze or block',
        'file dispute or fraud case',
        'explain provisional review timeline',
    ]
    assert isinstance(base_result['scenario_contract_hash'], str)
    assert len(base_result['scenario_contract_hash']) == 12
    assert changed_version['scenario_contract_hash'] == base_result['scenario_contract_hash']
    assert base_result['run_context'] == {
        'agent_version': 'agent-v1',
        'prompt_version': 'prompt-2026-05-24',
        'model_name': 'gpt-test',
        'target_agent_url': 'https://agent.example.com/eval',
    }
    assert changed_version['run_id'] != base_result['run_id']


def test_run_scenario_scores_observed_actions_as_benchmark_evidence():
    result = run_scenario(
        {
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'angry-outage-escalation',
            'transcript': 'Agent: I am sorry this outage is frustrating.',
            'observed_actions': [
                'check outage status',
                'create support ticket',
                'offer troubleshooting only if no area outage is active',
                'escalate to human agent on request',
            ],
        }
    )

    assert result['required_action_score'] == 100
    assert result['missing_actions'] == []
    assert result['verdict'] == 'pass'


def test_simulate_scenario_can_generate_failure_baseline():
    result = simulate_scenario(
        {
            'suite_id': 'telehealth-agent',
            'scenario_id': 'medication-refill-routing',
            'include_failure': True,
        }
    )

    assert result['final_state']['complete'] is False
    assert result['final_state']['missing_actions'] == ['state refill timing expectations']
    assert result['final_state']['forbidden_actions_observed'] == ['approve refill directly']
    assert result['benchmark_report']['verdict'] == 'needs_review'


def test_simulate_endpoint_returns_homepage_runner_payload():
    response = client.post(
        '/api/benchmarks/simulate',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['conversation'][0]['role'] == 'user'
    assert payload['conversation'][1]['role'] == 'assistant'
    assert payload['transcript']
    assert payload['vcon']['subject'] == 'Fintech Support Agent: Failed ACH Transfer'
    assert payload['action_trace']
    assert payload['final_state']['complete'] is True
    assert payload['benchmark_report']['scenario_id'] == 'failed-ach-transfer'


def test_simulate_endpoint_accepts_camel_case_payload():
    response = client.post(
        '/api/benchmarks/simulate',
        json={
            'suiteId': 'online-teaching-agent',
            'scenarioId': 'language-practice-feedback',
            'agentProfile': 'homepage mock agent',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['scenario_id'] == 'language-practice-feedback'
    assert 'homepage mock agent' in payload['transcript']
    assert payload['benchmark_report']['verdict'] == 'pass'


def test_simulate_endpoint_persists_run_context_labels():
    response = client.post(
        '/api/benchmarks/simulate',
        json={
            'suiteId': 'fintech-support-agent',
            'scenarioId': 'suspicious-card-charge',
            'agentVersion': 'agent-sim-v2',
            'promptVersion': 'prompt-sim-2026-05-24',
            'modelName': 'gpt-sim',
            'targetAgentUrl': 'https://agent.example.com/sim',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['benchmark_report']['run_context'] == {
        'agent_version': 'agent-sim-v2',
        'prompt_version': 'prompt-sim-2026-05-24',
        'model_name': 'gpt-sim',
        'target_agent_url': 'https://agent.example.com/sim',
    }


def test_simulate_suite_runs_all_scenarios_and_summarizes_scores():
    result = simulate_suite(
        {
            'suiteId': 'call-center-voice-ai',
            'agentProfile': 'suite mock agent',
            'promptVersion': 'suite-prompt-v1',
        }
    )

    assert result['suite_id'] == 'call-center-voice-ai'
    assert result['suite_name'] == 'Call Center Voice AI'
    assert result['scenario_count'] == 2
    assert result['run_count'] == 2
    assert result['pass_count'] == 2
    assert result['needs_review_count'] == 0
    assert result['average_score'] >= 75
    assert {report['scenario_id'] for report in result['reports']} == {'billing-address-change', 'angry-outage-escalation'}
    assert all(report['run_context']['prompt_version'] == 'suite-prompt-v1' for report in result['reports'])


def test_simulate_suite_endpoint_persists_each_scenario_run():
    response = client.post(
        '/api/benchmarks/suites/simulate',
        json={
            'suiteId': 'telehealth-agent',
            'agentProfile': f'suite endpoint agent {uuid4().hex}',
            'include_failure': True,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['suite_id'] == 'telehealth-agent'
    assert payload['run_count'] == 2
    assert payload['needs_review_count'] == 2

    for report in payload['reports']:
        detail = client.get(f'/api/benchmarks/runs/{report["run_id"]}')
        assert detail.status_code == 200, detail.text
        assert detail.json()['scenario_id'] == report['scenario_id']


def test_path_simulate_suite_endpoint_uses_route_suite_id_and_persists_runs():
    response = client.post(
        '/api/benchmarks/suites/online-teaching-agent/simulate',
        json={
            'agentProfile': f'path suite agent {uuid4().hex}',
            'promptVersion': 'path-suite-prompt-v1',
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['suite_id'] == 'online-teaching-agent'
    assert payload['run_count'] == 2
    assert payload['pass_count'] == 2
    assert all(report['run_context']['prompt_version'] == 'path-suite-prompt-v1' for report in payload['reports'])

    detail = client.get(f'/api/benchmarks/runs/{payload["reports"][0]["run_id"]}')
    assert detail.status_code == 200, detail.text
    assert detail.json()['suite_id'] == 'online-teaching-agent'


def test_suite_runs_endpoint_summarizes_coverage_by_scenario_and_context():
    prompt_version = f'suite-summary-prompt-{uuid4().hex}'
    response = client.post(
        '/api/benchmarks/suites/call-center-voice-ai/simulate',
        json={
            'agentProfile': 'suite summary agent',
            'promptVersion': prompt_version,
        },
    )

    assert response.status_code == 200, response.text

    summary_response = client.get(
        '/api/benchmarks/suites/call-center-voice-ai/runs',
        params={'prompt_version': prompt_version, 'per_scenario_limit': 2},
    )

    assert summary_response.status_code == 200, summary_response.text
    payload = summary_response.json()
    assert payload['suite_id'] == 'call-center-voice-ai'
    assert payload['scenario_count'] == 2
    assert payload['covered_scenario_count'] == 2
    assert payload['uncovered_scenario_ids'] == []
    assert payload['summary']['run_count'] == 2
    assert payload['summary']['pass_count'] == 2
    assert {run['scenario_id'] for run in payload['latest_runs']} == {'billing-address-change', 'angry-outage-escalation'}
    assert all(run['run_context']['prompt_version'] == prompt_version for run in payload['latest_runs'])
    assert {item['scenario_id'] for item in payload['scenarios']} == {'billing-address-change', 'angry-outage-escalation'}
    assert all(item['latest_run'] for item in payload['scenarios'])

    db = SessionLocal()
    try:
        service_summary = summarize_benchmark_suite_runs(
            db,
            'call-center-voice-ai',
            run_context={'prompt_version': prompt_version},
            per_scenario_limit=2,
        )
    finally:
        db.close()
    assert service_summary is not None
    assert service_summary['covered_scenario_count'] == 2

    missing = client.get('/api/benchmarks/suites/missing/runs')
    assert missing.status_code == 404


def test_path_simulate_endpoint_uses_route_scenario_ids():
    response = client.post(
        '/api/benchmarks/call-center-voice-ai/scenarios/angry-outage-escalation/simulate',
        json={'include_failure': True},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['suite_id'] == 'call-center-voice-ai'
    assert payload['scenario_id'] == 'angry-outage-escalation'
    assert payload['final_state']['complete'] is False
    assert payload['benchmark_report']['verdict'] == 'needs_review'


def test_run_endpoint_accepts_vcon_without_duplicate_transcript_field():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suiteId': 'call-center-voice-ai',
            'scenarioId': 'angry-outage-escalation',
            'vcon': {
                'dialog': [
                    {'party': 0, 'body': 'This outage is frustrating and I want a human.'},
                    {'party': 1, 'body': 'I am sorry. I checked outage status, created ticket ABC, and will escalate to a representative.'},
                ]
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['suite_id'] == 'call-center-voice-ai'
    assert payload['scenario_id'] == 'angry-outage-escalation'
    assert payload['verdict'] == 'pass'
    assert payload['transcript_preview'].startswith('This outage is frustrating')


def test_run_endpoint_accepts_action_trace_and_final_state_without_transcript():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'action_trace': [
                {'action': 'verify business account', 'status': 'completed'},
                {'action': 'collect transfer amount and date', 'status': 'completed'},
                {'action': 'explain failure reason without exposing sensitive bank data', 'status': 'completed'},
                {'action': 'offer retry or payments support escalation', 'status': 'completed'},
                {'action': 'provide reference number', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'reference_number': 'ACH-1001'},
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['verdict'] == 'pass'
    assert payload['overall_score'] == 100
    assert payload['evidence_quality_score'] == 60
    assert payload['transcript_preview'] == ''
    assert payload['missing_actions'] == []
    assert payload['action_trace'][0]['action'] == 'verify business account'


def test_run_endpoint_flags_voice_quality_risks_from_call_artifacts():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'angry-outage-escalation',
            'vcon': {
                'dialog': [
                    {
                        'party': 0,
                        'body': 'This outage is frustrating and I want a human.',
                        'latency_ms': 250,
                    },
                    {
                        'party': 1,
                        'body': 'I am sorry. I checked outage status, created ticket ABC, and will escalate to a representative.',
                        'latency_ms': 3250,
                        'interrupted': True,
                        'tool_calls': [{'tool_name': 'create_ticket', 'status': 'failed'}],
                    },
                ],
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['call_artifacts']['average_latency_ms'] == 1750
    assert payload['call_artifacts']['max_latency_ms'] == 3250
    assert payload['call_artifacts']['interruption_count'] == 1
    assert payload['call_artifacts']['failed_tool_call_count'] == 1
    assert payload['voice_quality_risks'] == [
        'high_average_latency: 1750ms average response latency',
        'high_peak_latency: 3250ms peak response latency',
        'interruptions: 1 interruption event(s)',
        'failed_tool_calls: 1 failed tool call(s)',
    ]

    listing = client.get('/api/benchmarks/runs?suite_id=call-center-voice-ai&scenario_id=angry-outage-escalation&limit=1')
    assert listing.status_code == 200, listing.text
    listing_payload = listing.json()
    assert listing_payload['runs'][0]['voice_quality_risk_count'] == 4
    assert listing_payload['summary']['latest_voice_quality_risk_count'] == 4

    csv_response = client.get('/api/benchmarks/runs.csv?suite_id=call-center-voice-ai&scenario_id=angry-outage-escalation&limit=1')
    assert csv_response.status_code == 200, csv_response.text
    assert 'voice_quality_risk_count' in csv_response.text
    assert ',4,' in csv_response.text


def test_run_endpoint_scores_imported_vcon_analysis_action_trace_and_final_state():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'vcon': {
                'parties': [{'name': 'Cardholder'}, {'name': 'Agent'}],
                'dialog': [
                    {'party': 0, 'body': 'I see a suspicious charge.'},
                    {'party': 1, 'body': 'I opened the review workflow.'},
                ],
                'analysis': [
                    {
                        'type': 'agentic_evidence',
                        'body': {
                            'action_trace': [
                                {'action': 'verify account identity', 'status': 'completed'},
                                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                                {'action': 'offer card freeze or block', 'status': 'completed'},
                                {'action': 'file dispute or fraud case', 'status': 'completed'},
                                {'action': 'explain provisional review timeline', 'status': 'completed'},
                            ],
                            'final_state': {'complete': True, 'case_id': 'FRD-VC-1'},
                        },
                    },
                ],
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['verdict'] == 'pass'
    assert payload['overall_score'] == 100
    assert payload['required_action_score'] == 100
    assert payload['final_state']['case_id'] == 'FRD-VC-1'

    saved = client.get(f'/api/benchmarks/runs/{payload["run_id"]}')
    assert saved.status_code == 200, saved.text
    assert saved.json()['evidence_artifacts']['action_trace'][0]['action'] == 'verify account identity'


def test_run_endpoint_rejects_blank_evidence_payload():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'billing-address-change',
            'transcript': '   ',
        },
    )

    assert response.status_code == 422


def test_simulate_endpoint_persists_benchmark_run_history():
    agent_profile = f'history test agent {uuid4().hex}'
    response = client.post(
        '/api/benchmarks/simulate',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'billing-address-change',
            'agent_profile': agent_profile,
        },
    )

    assert response.status_code == 200, response.text
    simulation = response.json()
    run_id = simulation['benchmark_report']['run_id']

    detail = client.get(f'/api/benchmarks/runs/{run_id}')
    assert detail.status_code == 200, detail.text
    saved = detail.json()
    assert saved['run_id'] == run_id
    assert saved['suite_id'] == 'call-center-voice-ai'
    assert saved['scenario_id'] == 'billing-address-change'
    assert saved['report']['transcript'] == simulation['transcript']
    assert saved['evidence_artifacts']['action_trace'] == simulation['action_trace']

    listing = client.get('/api/benchmarks/runs?suite_id=call-center-voice-ai&scenario_id=billing-address-change&limit=5')
    assert listing.status_code == 200, listing.text
    assert any(item['run_id'] == run_id for item in listing.json()['runs'])
    summary = listing.json()['summary']
    assert summary['run_count'] >= 1
    assert summary['pass_count'] >= 1
    assert summary['needs_review_count'] >= 0
    assert summary['average_score'] is not None


def test_run_endpoint_persists_full_direct_evidence_artifacts():
    transcript = (
        'Customer: Payroll transfer failed.\n'
        'Agent: I verify the business account, collect amount and date, explain the failure reason, '
        'offer payments support escalation, and provide reference ACH-99.'
    )
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'transcript': transcript,
            'action_trace': [{'action': 'provide reference number', 'status': 'completed'}],
            'final_state': {'complete': True, 'reference_number': 'ACH-99'},
        },
    )

    assert response.status_code == 200, response.text
    run = response.json()

    detail = client.get(f'/api/benchmarks/runs/{run["run_id"]}')
    assert detail.status_code == 200, detail.text
    saved = detail.json()
    assert saved['report']['transcript'] == transcript
    assert saved['evidence_artifacts']['transcript'] == transcript
    assert saved['evidence_artifacts']['action_trace'] == [{'action': 'provide reference number', 'status': 'completed'}]
    assert saved['evidence_artifacts']['final_state'] == {'complete': True, 'reference_number': 'ACH-99'}


def test_run_endpoint_preserves_group_call_speakers_from_vcon_dialog():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'conversation': {
                'parties': [
                    {'name': 'Payroll lead'},
                    {'name': 'Support agent'},
                    {'name': 'Finance approver'},
                ],
                'dialog': [
                    {'party': 0, 'body': 'Payroll transfer failed yesterday.'},
                    {'party': 1, 'body': 'I verify the business account and collect transfer amount and date.'},
                    {'party': 2, 'body': 'Please route this to payments support and provide reference ACH-77.'},
                    {'party': 1, 'body': 'I explain the failure reason without sensitive bank data.'},
                ],
            },
        },
    )

    assert response.status_code == 200, response.text
    run = response.json()
    assert 'Payroll lead: Payroll transfer failed yesterday.' in run['transcript']
    assert 'Finance approver: Please route this to payments support and provide reference ACH-77.' in run['transcript']
    assert run['completed_actions'] == [
        'verify business account',
        'collect transfer amount and date',
        'explain failure reason without exposing sensitive bank data',
        'offer retry or payments support escalation',
        'provide reference number',
    ]

    export_response = client.get(f'/api/benchmarks/runs/{run["run_id"]}/vcon')
    assert export_response.status_code == 200, export_response.text
    exported = export_response.json()
    assert exported['dialog'][0]['body'] == 'Payroll lead: Payroll transfer failed yesterday.'
    assert exported['dialog'][2]['body'].startswith('Finance approver:')


def test_run_endpoint_extracts_group_call_insights_from_vcon_dialog():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'vcon': {
                'parties': [
                    {'name': 'Payroll lead'},
                    {'name': 'Support agent'},
                    {'name': 'Finance approver'},
                ],
                'dialog': [
                    {'party': 0, 'body': 'Payroll transfer failed yesterday.'},
                    {'party': 1, 'body': 'I will verify the business account and collect transfer amount and date.'},
                    {'party': 2, 'body': 'Approved. Next step is route this to payments support and provide reference ACH-77.'},
                    {'party': 1, 'body': 'Confirmed, I will explain the failure reason without exposing sensitive bank data.'},
                ],
            },
        },
    )

    assert response.status_code == 200, response.text
    insights = response.json()['conversation_insights']
    assert insights['turn_count'] == 4
    assert insights['speaker_count'] == 3
    assert insights['speakers'] == ['Payroll lead', 'Support agent', 'Finance approver']
    assert insights['speaker_turn_counts'] == {
        'Payroll lead': 1,
        'Support agent': 2,
        'Finance approver': 1,
    }
    assert insights['decisions'] == [
        {'speaker': 'Finance approver', 'text': 'Approved'},
        {'speaker': 'Support agent', 'text': 'Confirmed, I will explain the failure reason without exposing sensitive bank data'},
    ]
    assert {'speaker': 'Support agent', 'text': 'I will verify the business account and collect transfer amount and date'} in insights['commitments']
    assert {'speaker': 'Finance approver', 'text': 'Next step is route this to payments support and provide reference ACH-77'} in insights['follow_up_actions']

    run_id = response.json()['run_id']
    saved = client.get(f'/api/benchmarks/runs/{run_id}')
    assert saved.status_code == 200, saved.text
    assert saved.json()['report']['conversation_insights']['speaker_count'] == 3
    assert saved.json()['report']['conversation_insights']['speaker_turn_counts']['Support agent'] == 2


def test_run_endpoint_preserves_voice_call_artifact_metrics():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'angry-outage-escalation',
            'vcon': {
                'duration_seconds': 23.4,
                'parties': [{'name': 'Caller'}, {'name': 'Agent'}],
                'dialog': [
                    {'type': 'audio', 'party': 0, 'body': 'This outage is frustrating and I want a human.'},
                    {
                        'type': 'audio',
                        'party': 1,
                        'body': 'I am sorry. I checked outage status, created ticket ABC, and will escalate to a representative.',
                        'latency_ms': 640,
                    },
                    {
                        'type': 'audio',
                        'party': 0,
                        'body': 'Please hurry.',
                        'metadata': {'barge_in': True},
                    },
                    {
                        'type': 'audio',
                        'party': 1,
                        'body': 'Confirmed.',
                        'metadata': {'response_latency_ms': 510},
                    },
                ],
                'media': [{'type': 'recording', 'mime_type': 'audio/wav', 'duration': 23.4}],
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['call_artifacts'] == {
        'source': 'vcon',
        'turn_count': 4,
        'media_count': 1,
        'modalities': ['audio', 'audio/wav', 'recording'],
        'duration_seconds': 23.4,
        'average_latency_ms': 575,
        'max_latency_ms': 640,
        'interruption_count': 1,
    }

    saved = client.get(f'/api/benchmarks/runs/{payload["run_id"]}')
    assert saved.status_code == 200, saved.text
    assert saved.json()['report']['call_artifacts']['average_latency_ms'] == 575

    markdown = client.get(f'/api/benchmarks/runs/{payload["run_id"]}/markdown')
    assert markdown.status_code == 200, markdown.text
    assert '## Conversation Insights' in markdown.text
    assert '- Speaker count: `2`' in markdown.text
    assert '- Speakers: Caller, Agent' in markdown.text
    assert '## Call Artifacts' in markdown.text
    assert '- Source: `vcon`' in markdown.text
    assert '- Modalities: `audio, audio/wav, recording`' in markdown.text
    assert '- Average latency ms: `575`' in markdown.text
    assert '- Interruptions: `1`' in markdown.text


def test_run_endpoint_counts_imported_call_tool_events():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'vcon': {
                'parties': [{'name': 'Business owner'}, {'name': 'Agent'}],
                'dialog': [
                    {'party': 0, 'body': 'Payroll transfer failed yesterday.'},
                    {'party': 1, 'body': 'I will verify the business account and collect transfer amount and date.'},
                    {'type': 'tool_call', 'tool_name': 'lookup_ach_transfer', 'status': 'completed'},
                    {'type': 'tool_call', 'tool_name': 'create_payment_support_case', 'status': 'failed', 'error': 'timeout'},
                    {'party': 1, 'body': 'I explain the failure reason without sensitive bank data and provide reference ACH-77.'},
                ],
                'tool_calls': [
                    {'tool_name': 'verify_business_account', 'status': 'completed'},
                ],
            },
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['call_artifacts']['tool_call_count'] == 3
    assert payload['call_artifacts']['failed_tool_call_count'] == 1

    markdown = client.get(f'/api/benchmarks/runs/{payload["run_id"]}/markdown')
    assert markdown.status_code == 200, markdown.text
    assert '- Tool calls: `3`' in markdown.text
    assert '- Failed tool calls: `1`' in markdown.text


def test_benchmark_run_vcon_export_returns_saved_simulation_artifact():
    response = client.post(
        '/api/benchmarks/simulate',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'billing-address-change',
            'agent_profile': 'vcon export test agent',
        },
    )

    assert response.status_code == 200, response.text
    simulation = response.json()
    run_id = simulation['benchmark_report']['run_id']

    export_response = client.get(f'/api/benchmarks/runs/{run_id}/vcon')

    assert export_response.status_code == 200, export_response.text
    exported = export_response.json()
    assert exported['vcon'] == '0.0.2'
    assert exported['benchmark_run_id'] == run_id
    assert exported['subject'] == 'Call Center Voice AI: Billing Address Change'
    assert exported['dialog'] == simulation['vcon']['dialog']


def test_benchmark_run_vcon_export_builds_report_artifact_for_direct_runs():
    run_response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'failed-ach-transfer',
            'transcript': 'Customer: Payroll transfer failed.\nAgent: I verify the business account, collect amount and date, explain the failure reason, offer payments support escalation, and provide reference ACH-42.',
        },
    )

    assert run_response.status_code == 200, run_response.text
    run = run_response.json()

    export_response = client.get(f'/api/benchmarks/runs/{run["run_id"]}/vcon')

    assert export_response.status_code == 200, export_response.text
    exported = export_response.json()
    assert exported['vcon'] == '0.0.2'
    assert exported['benchmark_run_id'] == run['run_id']
    assert exported['dialog'][0]['party'] == 0
    assert exported['dialog'][1]['party'] == 1
    assert exported['analysis'][0]['type'] == 'benchmark_report'
    assert exported['analysis'][0]['body']['report']['run_id'] == run['run_id']


def test_benchmark_run_junit_export_marks_pass_and_failures():
    passing_response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'action_trace': [
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                {'action': 'offer card freeze or block', 'status': 'completed'},
                {'action': 'file dispute or fraud case', 'status': 'completed'},
                {'action': 'explain provisional review timeline', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'case_id': 'FRD-JUNIT'},
        },
    )
    assert passing_response.status_code == 200, passing_response.text
    passing_run_id = passing_response.json()['run_id']

    passing_junit = client.get(f'/api/benchmarks/runs/{passing_run_id}/junit')
    assert passing_junit.status_code == 200, passing_junit.text
    assert passing_junit.headers['content-type'].startswith('application/xml')
    assert '<testsuite name="Fintech Support Agent" tests="1" failures="0" errors="0">' in passing_junit.text
    assert '<failure' not in passing_junit.text

    failing_response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'telehealth-agent',
            'scenario_id': 'new-patient-triage',
            'transcript': 'Agent: I can diagnose condition and recommend prescription medication.',
        },
    )
    assert failing_response.status_code == 200, failing_response.text
    failing_run_id = failing_response.json()['run_id']

    db = SessionLocal()
    try:
        service_junit = get_benchmark_run_junit(db, failing_run_id)
    finally:
        db.close()
    assert service_junit is not None
    assert 'failures="1"' in service_junit
    assert 'diagnose condition' in service_junit

    failing_junit = client.get(f'/api/benchmarks/runs/{failing_run_id}/junit')
    assert failing_junit.status_code == 200, failing_junit.text
    assert '<failure message="Benchmark verdict was needs_review' in failing_junit.text
    assert 'recommend prescription medication' in failing_junit.text


def test_benchmark_run_markdown_export_includes_scores_evidence_and_context():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'action_trace': [
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                {'action': 'offer card freeze or block', 'status': 'completed'},
                {'action': 'file dispute or fraud case', 'status': 'completed'},
                {'action': 'explain provisional review timeline', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'case_id': 'FRD-MD'},
            'agentVersion': 'agent-md',
            'promptVersion': 'prompt-md',
            'modelName': 'model-md',
            'targetAgentUrl': 'https://agent.example.com/md',
        },
    )

    assert response.status_code == 200, response.text
    run_id = response.json()['run_id']

    db = SessionLocal()
    try:
        service_markdown = get_benchmark_run_markdown(db, run_id)
    finally:
        db.close()

    assert service_markdown is not None
    assert '# Fintech Support Agent: Suspicious Card Charge' in service_markdown
    assert f'- Run ID: `{run_id}`' in service_markdown
    assert '- Verdict: `pass`' in service_markdown
    assert '- Overall score: `100`' in service_markdown
    assert 'agent `agent-md`' in service_markdown
    assert 'prompt `prompt-md`' in service_markdown
    assert 'model `model-md`' in service_markdown
    assert 'target `https://agent.example.com/md`' in service_markdown
    assert '## Scenario Contract' in service_markdown
    assert '- Goal: Verify identity, capture transaction details, freeze or block the card when requested, file a dispute, and avoid liability guarantees.' in service_markdown
    assert '## Required Actions' in service_markdown
    assert '- verify account identity' in service_markdown
    assert '## Action Trace' in service_markdown
    assert '"case_id": "FRD-MD"' in service_markdown

    export_response = client.get(f'/api/benchmarks/runs/{run_id}/markdown')
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers['content-type'].startswith('text/markdown')
    assert export_response.text == service_markdown


def test_benchmark_run_jsonl_export_returns_single_saved_report():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'call-center-voice-ai',
            'scenario_id': 'billing-address-change',
            'transcript': (
                'Agent: I will verify account email and phone, collect the new billing address, '
                'confirm the address update, and explain the next invoice impact.'
            ),
            'agentVersion': 'agent-jsonl-single',
        },
    )

    assert response.status_code == 200, response.text
    run_id = response.json()['run_id']

    db = SessionLocal()
    try:
        service_jsonl = get_benchmark_run_jsonl(db, run_id)
    finally:
        db.close()

    assert service_jsonl is not None
    lines = service_jsonl.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])['run_id'] == run_id

    export_response = client.get(f'/api/benchmarks/runs/{run_id}/jsonl')
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers['content-type'].startswith('application/x-ndjson')
    assert export_response.text == service_jsonl


def test_rerun_endpoint_reuses_saved_evidence_with_new_context_labels():
    initial = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'agentVersion': 'agent-rerun-v1',
            'promptVersion': 'prompt-rerun-v1',
            'modelName': 'model-rerun',
            'targetAgentUrl': 'https://agent.example.com/rerun',
            'action_trace': [
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'capture transaction merchant and amount', 'status': 'completed'},
                {'action': 'offer card freeze or block', 'status': 'completed'},
                {'action': 'file dispute or fraud case', 'status': 'completed'},
                {'action': 'explain provisional review timeline', 'status': 'completed'},
            ],
            'final_state': {'complete': True, 'case_id': 'FRD-RERUN-1'},
        },
    )

    assert initial.status_code == 200, initial.text
    initial_report = initial.json()
    rerun = client.post(
        f'/api/benchmarks/runs/{initial_report["run_id"]}/rerun',
        json={'promptVersion': 'prompt-rerun-v2'},
    )

    assert rerun.status_code == 200, rerun.text
    rerun_report = rerun.json()
    assert rerun_report['run_id'] != initial_report['run_id']
    assert rerun_report['overall_score'] == 100
    assert rerun_report['run_context'] == {
        'agent_version': 'agent-rerun-v1',
        'prompt_version': 'prompt-rerun-v2',
        'model_name': 'model-rerun',
        'target_agent_url': 'https://agent.example.com/rerun',
    }
    assert rerun_report['action_trace'] == initial_report['action_trace']
    assert rerun_report['final_state'] == initial_report['final_state']

    saved = client.get(f'/api/benchmarks/runs/{rerun_report["run_id"]}')
    assert saved.status_code == 200, saved.text
    assert saved.json()['report']['run_context']['prompt_version'] == 'prompt-rerun-v2'


def test_list_benchmark_runs_includes_score_trend_against_previous_run():
    suite_id = f'trend-suite-{uuid4().hex}'
    scenario_id = f'trend-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'run-low-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Trend Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Trend Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 35,
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'run-high-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Trend Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Trend Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 82,
            },
        )

        runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, limit=2)
    finally:
        db.close()

    assert [run['overall_score'] for run in runs] == [82, 35]
    assert runs[0]['previous_overall_score'] == 35
    assert runs[0]['score_delta'] == 47
    assert runs[0]['trend'] == 'improved'
    assert runs[1]['previous_overall_score'] is None
    assert runs[1]['score_delta'] is None
    assert runs[1]['trend'] == 'baseline'


def test_benchmark_runs_jsonl_export_is_machine_readable_and_filterable():
    suite_id = f'jsonl-suite-{uuid4().hex}'
    scenario_id = f'jsonl-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'jsonl-run-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'JSONL Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'JSONL Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 93,
                'run_context': {'agent_version': 'agent-jsonl'},
            },
        )

        runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context={'agent_version': 'agent-jsonl'})
        jsonl = export_benchmark_runs_jsonl(runs)
    finally:
        db.close()

    lines = [json.loads(line) for line in jsonl.splitlines()]
    assert len(lines) == 1
    assert lines[0]['suite_id'] == suite_id
    assert lines[0]['scenario_id'] == scenario_id
    assert lines[0]['run_context']['agent_version'] == 'agent-jsonl'

    response = client.get(f'/api/benchmarks/runs.jsonl?suite_id={suite_id}&scenario_id={scenario_id}&agent_version=agent-jsonl')
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('application/x-ndjson')
    assert json.loads(response.text.splitlines()[0])['overall_score'] == 93


def test_benchmark_runs_sarif_export_marks_failures_for_ci_code_scanning():
    response = client.post(
        '/api/benchmarks/run',
        json={
            'suite_id': 'fintech-support-agent',
            'scenario_id': 'suspicious-card-charge',
            'action_trace': [
                {'action': 'verify account identity', 'status': 'completed'},
                {'action': 'ask for full card number', 'status': 'completed'},
            ],
            'final_state': {'complete': False},
            'agentVersion': 'agent-sarif',
        },
    )

    assert response.status_code == 200, response.text
    run = response.json()
    run_id = run['run_id']

    db = SessionLocal()
    try:
        saved = get_benchmark_run_sarif(db, run_id)
        aggregate_runs = list_benchmark_runs(
            db,
            suite_id='fintech-support-agent',
            scenario_id='suspicious-card-charge',
            run_context={'agent_version': 'agent-sarif'},
            limit=1,
        )
        aggregate_sarif = export_benchmark_runs_sarif(aggregate_runs)
    finally:
        db.close()

    assert saved is not None
    result = saved['runs'][0]['results'][0]
    assert saved['version'] == '2.1.0'
    assert result['ruleId'] == 'conversation-agent-evals/suspicious-card-charge'
    assert result['kind'] == 'fail'
    assert result['level'] == 'error'
    assert result['properties']['run_id'] == run_id
    assert 'required_action_execution' in result['properties']['failure_categories']
    assert 'forbidden_action_avoidance' in result['properties']['failure_categories']

    assert aggregate_sarif['runs'][0]['results'][0]['properties']['run_context']['agent_version'] == 'agent-sarif'

    export_response = client.get(f'/api/benchmarks/runs/{run_id}/sarif')
    assert export_response.status_code == 200, export_response.text
    assert export_response.json()['runs'][0]['results'][0]['properties']['run_id'] == run_id

    listing_response = client.get('/api/benchmarks/runs.sarif?suite_id=fintech-support-agent&scenario_id=suspicious-card-charge&agent_version=agent-sarif&limit=1')
    assert listing_response.status_code == 200, listing_response.text
    assert listing_response.json()['runs'][0]['results'][0]['ruleId'] == 'conversation-agent-evals/suspicious-card-charge'


def test_list_benchmark_runs_can_filter_history_by_run_context():
    suite_id = f'context-suite-{uuid4().hex}'
    scenario_id = f'context-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'context-old-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Context Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Context Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 41,
                'run_context': {'prompt_version': 'prompt-a', 'model_name': 'model-x'},
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'context-new-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Context Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Context Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 90,
                'run_context': {'prompt_version': 'prompt-b', 'model_name': 'model-x'},
            },
        )

        prompt_a_runs = list_benchmark_runs(
            db,
            suite_id=suite_id,
            scenario_id=scenario_id,
            run_context={'prompt_version': 'prompt-a'},
            limit=5,
        )
    finally:
        db.close()

    assert len(prompt_a_runs) == 1
    assert prompt_a_runs[0]['overall_score'] == 41
    assert prompt_a_runs[0]['run_context']['prompt_version'] == 'prompt-a'
    assert prompt_a_runs[0]['trend'] == 'baseline'


def test_benchmark_run_summary_reports_latest_regression_state():
    runs = [
        {
            'run_id': 'latest',
            'verdict': 'needs_review',
            'overall_score': 64,
            'previous_overall_score': 91,
            'score_delta': -27,
            'trend': 'regressed',
            'failure_categories': ['required_action_execution', 'final_state_correctness'],
        },
        {
            'run_id': 'previous',
            'verdict': 'pass',
            'overall_score': 91,
            'previous_overall_score': None,
            'score_delta': None,
            'trend': 'baseline',
            'failure_categories': ['required_action_execution'],
        },
    ]

    summary = summarize_benchmark_runs(runs)

    assert summary == {
        'status': 'regressed',
        'run_count': 2,
        'pass_count': 1,
        'pass_rate': 50,
        'needs_review_count': 1,
        'average_score': 78,
        'latest_score': 64,
        'previous_score': 91,
        'score_delta': -27,
        'latest_verdict': 'needs_review',
        'latest_run_id': 'latest',
        'regression_count': 1,
        'improvement_count': 0,
        'failure_category_counts': {'required_action_execution': 2, 'final_state_correctness': 1},
        'most_common_failure_category': 'required_action_execution',
        'voice_quality_risk_count': 0,
        'latest_voice_quality_risk_count': 0,
    }


def test_list_runs_endpoint_includes_regression_summary():
    response = client.get('/api/benchmarks/runs?suite_id=call-center-voice-ai&scenario_id=billing-address-change&limit=5')

    assert response.status_code == 200, response.text
    payload = response.json()
    assert 'runs' in payload
    assert payload['summary']['run_count'] == len(payload['runs'])
    assert payload['summary']['status'] in {'empty', 'baseline', 'stable', 'improved', 'regressed'}
    assert 'failure_category_counts' in payload['summary']
    if payload['runs']:
        assert 'failure_categories' in payload['runs'][0]
        assert 'missing_action_count' in payload['runs'][0]
        assert 'forbidden_action_count' in payload['runs'][0]
    assert 'comparison' in payload


def test_compare_latest_benchmark_runs_reports_new_and_resolved_failures():
    suite_id = f'compare-suite-{uuid4().hex}'
    scenario_id = f'compare-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'compare-old-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Compare Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Compare Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 60,
                'missing_actions': ['verify identity', 'file dispute'],
                'forbidden_actions_observed': ['guarantee reimbursement'],
                'failure_categories': ['required_action_execution', 'forbidden_action_avoidance'],
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'compare-new-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Compare Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Compare Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 72,
                'missing_actions': ['file dispute', 'explain timeline'],
                'forbidden_actions_observed': [],
                'failure_categories': ['required_action_execution', 'final_state_correctness'],
            },
        )

        comparison = compare_latest_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id)
    finally:
        db.close()

    assert comparison['status'] == 'compared'
    assert comparison['new_missing_actions'] == ['explain timeline']
    assert comparison['resolved_missing_actions'] == ['verify identity']
    assert comparison['new_forbidden_actions'] == []
    assert comparison['resolved_forbidden_actions'] == ['guarantee reimbursement']
    assert comparison['new_failure_categories'] == ['final_state_correctness']
    assert comparison['resolved_failure_categories'] == ['forbidden_action_avoidance']


def test_list_runs_endpoint_filters_regression_summary_by_context_labels():
    suite_id = f'endpoint-context-suite-{uuid4().hex}'
    scenario_id = f'endpoint-context-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'endpoint-context-a-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Endpoint Context Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Endpoint Context Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 88,
                'run_context': {
                    'agent_version': 'agent-a',
                    'prompt_version': 'prompt-a',
                    'model_name': 'model-a',
                    'target_agent_url': 'https://agent-a.example.com/eval',
                },
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'endpoint-context-b-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Endpoint Context Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Endpoint Context Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 52,
                'run_context': {
                    'agent_version': 'agent-b',
                    'prompt_version': 'prompt-b',
                    'model_name': 'model-a',
                    'target_agent_url': 'https://agent-b.example.com/eval',
                },
            },
        )
    finally:
        db.close()

    response = client.get(
        '/api/benchmarks/runs',
        params={
            'suite_id': suite_id,
            'scenario_id': scenario_id,
            'agent_version': 'agent-a',
            'model_name': 'model-a',
            'target_agent_url': 'https://agent-a.example.com/eval',
            'limit': 5,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload['runs']) == 1
    assert payload['runs'][0]['run_context']['agent_version'] == 'agent-a'
    assert 'scenario_contract_hash' in payload['runs'][0]
    assert payload['summary']['latest_score'] == 88
    assert payload['comparison']['status'] == 'insufficient_history'


def test_benchmark_runs_csv_export_includes_context_and_trend_columns():
    suite_id = f'csv-suite-{uuid4().hex}'
    scenario_id = f'csv-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'csv-old-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'CSV Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'CSV Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 44,
                'run_context': {
                    'agent_version': 'agent-csv',
                    'prompt_version': 'prompt-a',
                    'model_name': 'model-csv',
                    'target_agent_url': 'https://agent.example.com/csv',
                },
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'csv-new-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'CSV Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'CSV Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 91,
                'run_context': {
                    'agent_version': 'agent-csv',
                    'prompt_version': 'prompt-b',
                    'model_name': 'model-csv',
                    'target_agent_url': 'https://agent.example.com/csv',
                },
            },
        )
        runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, limit=2)
    finally:
        db.close()

    csv_body = export_benchmark_runs_csv(runs)

    assert csv_body.startswith('run_id,suite_id,scenario_id,scenario_title,verdict,overall_score,trend,score_delta,agent_version,prompt_version,model_name,target_agent_url,voice_quality_risk_count,created_at')
    assert 'CSV Scenario' in csv_body
    assert 'agent-csv' in csv_body
    assert 'prompt-b' in csv_body
    assert 'https://agent.example.com/csv' in csv_body
    assert ',improved,47,' in csv_body

    response = client.get('/api/benchmarks/runs.csv', params={'suite_id': suite_id, 'scenario_id': scenario_id, 'limit': 2})

    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('text/csv')
    assert 'attachment; filename="benchmark-runs.csv"' in response.headers['content-disposition']
    assert response.text == csv_body


def test_benchmark_runs_junit_export_summarizes_filtered_history():
    suite_id = f'junit-suite-{uuid4().hex}'
    scenario_id = f'junit-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'junit-pass-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'JUnit Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'JUnit Passing Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 94,
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'junit-fail-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'JUnit Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'JUnit Failing Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 61,
            },
        )
        runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, limit=2)
    finally:
        db.close()

    junit_body = export_benchmark_runs_junit(runs)

    assert '<testsuite name="ConversationAgentEvals benchmark runs" tests="2" failures="1" errors="0">' in junit_body
    assert 'JUnit Passing Scenario' in junit_body
    assert 'JUnit Failing Scenario' in junit_body
    assert '<failure message="Benchmark verdict was needs_review with score 61"></failure>' in junit_body

    response = client.get('/api/benchmarks/runs.junit', params={'suite_id': suite_id, 'scenario_id': scenario_id, 'limit': 2})

    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('application/xml')
    assert 'attachment; filename="benchmark-runs.junit.xml"' in response.headers['content-disposition']
    assert response.text == junit_body

    xml_response = client.get('/api/benchmarks/runs.junit.xml', params={'suite_id': suite_id, 'scenario_id': scenario_id, 'limit': 2})

    assert xml_response.status_code == 200, xml_response.text
    assert xml_response.headers['content-type'].startswith('application/xml')
    assert xml_response.text == junit_body


def test_benchmark_runs_markdown_export_summarizes_filtered_history():
    suite_id = f'markdown-suite-{uuid4().hex}'
    scenario_id = f'markdown-scenario-{uuid4().hex}'
    db = SessionLocal()
    try:
        save_benchmark_run(
            db,
            {
                'run_id': f'markdown-old-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Markdown Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Markdown Scenario',
                'provider': 'test',
                'verdict': 'needs_review',
                'overall_score': 58,
                'run_context': {
                    'agent_version': 'agent-md',
                    'prompt_version': 'prompt-a',
                    'model_name': 'model-md',
                    'target_agent_url': 'https://agent.example.com/md-history',
                },
            },
        )
        save_benchmark_run(
            db,
            {
                'run_id': f'markdown-new-{uuid4().hex}',
                'suite_id': suite_id,
                'suite_name': 'Markdown Suite',
                'scenario_id': scenario_id,
                'scenario_title': 'Markdown Scenario',
                'provider': 'test',
                'verdict': 'pass',
                'overall_score': 87,
                'run_context': {
                    'agent_version': 'agent-md',
                    'prompt_version': 'prompt-b',
                    'model_name': 'model-md',
                    'target_agent_url': 'https://agent.example.com/md-history',
                },
            },
        )
        runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, limit=2)
    finally:
        db.close()

    markdown_body = export_benchmark_runs_markdown(runs)

    assert markdown_body.startswith('# ConversationAgentEvals Benchmark Runs')
    assert '| Run | Scenario | Verdict | Score | Trend | Context | Created |' in markdown_body
    assert 'Markdown Scenario' in markdown_body
    assert 'agent: agent-md, prompt: prompt-b, model: model-md, target: https://agent.example.com/md-history' in markdown_body
    assert 'improved (+29)' in markdown_body

    response = client.get('/api/benchmarks/runs.md', params={'suite_id': suite_id, 'scenario_id': scenario_id, 'limit': 2})

    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('text/markdown')
    assert 'attachment; filename="benchmark-runs.md"' in response.headers['content-disposition']
    assert response.text == markdown_body
