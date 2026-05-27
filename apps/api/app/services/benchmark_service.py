from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from app.models.entities import BenchmarkRun
from app.services.benchmark_evaluator import BenchmarkEvaluation, evaluate_benchmark, parse_action_trace


BenchmarkScenario = dict[str, Any]
BenchmarkSuite = dict[str, Any]


_SUITES: tuple[BenchmarkSuite, ...] = (
    {
        'id': 'call-center-voice-ai',
        'name': 'Call Center Voice AI',
        'provider': 'WebRTC.ventures',
        'description': 'Inbound support calls that test caller identification, issue triage, tool use, escalation, and policy boundaries.',
        'scenarios': [
            {
                'id': 'billing-address-change',
                'title': 'Billing Address Change',
                'persona': 'A busy customer who moved recently and wants the billing address updated before the next invoice.',
                'goal': 'Verify the customer, collect the new billing address, confirm the update, and summarize the next invoice impact.',
                'edge_cases': [
                    'Caller only knows the old ZIP code at first.',
                    'Caller asks whether the current invoice can be reissued immediately.',
                ],
                'required_actions': [
                    'greet caller and identify intent',
                    'verify account using at least two identifiers',
                    'collect new billing address',
                    'confirm address update',
                    'explain next invoice impact',
                ],
                'forbidden_actions': [
                    'request full card number',
                    'change account without verification',
                    'promise unsupported refund',
                ],
                'expected_final_state': 'The account is verified, the billing address update is confirmed, and the caller knows when the next invoice will reflect the change.',
                'rubric': [
                    {'name': 'verification', 'weight': 25, 'keywords': ['verify', 'account', 'email', 'phone', 'zip']},
                    {'name': 'address_capture', 'weight': 25, 'keywords': ['address', 'street', 'city', 'state', 'zip']},
                    {'name': 'confirmation', 'weight': 25, 'keywords': ['updated', 'confirmed', 'billing']},
                    {'name': 'invoice_explanation', 'weight': 25, 'keywords': ['invoice', 'bill', 'next cycle', 'reflect']},
                ],
            },
            {
                'id': 'angry-outage-escalation',
                'title': 'Angry Outage Escalation',
                'persona': 'A frustrated caller whose internet has been down twice this week and who interrupts frequently.',
                'goal': 'Acknowledge frustration, check outage status, create a support ticket, and escalate when the caller asks for a human.',
                'edge_cases': [
                    'Caller interrupts before the agent finishes the outage lookup.',
                    'Caller asks for a human escalation before troubleshooting.',
                ],
                'required_actions': [
                    'acknowledge caller frustration',
                    'check outage status',
                    'create support ticket',
                    'offer troubleshooting only if no area outage is active',
                    'escalate to human agent on request',
                ],
                'forbidden_actions': [
                    'blame the caller',
                    'refuse human escalation',
                    'claim technician dispatch without creating ticket',
                ],
                'expected_final_state': 'The caller has a ticket number, a clear outage status, and a human escalation path when requested.',
                'rubric': [
                    {'name': 'empathy', 'weight': 20, 'keywords': ['sorry', 'frustrating', 'understand', 'apologize']},
                    {'name': 'status_lookup', 'weight': 25, 'keywords': ['outage', 'status', 'lookup', 'area']},
                    {'name': 'ticketing', 'weight': 25, 'keywords': ['ticket', 'case', 'reference']},
                    {'name': 'human_escalation', 'weight': 30, 'keywords': ['human', 'agent', 'representative', 'escalate']},
                ],
            },
        ],
    },
    {
        'id': 'telehealth-agent',
        'name': 'Telehealth Agent',
        'provider': 'WebRTC.ventures',
        'description': 'Healthcare intake calls that test appointment workflow, privacy discipline, and safe medical boundaries.',
        'scenarios': [
            {
                'id': 'new-patient-triage',
                'title': 'New Patient Triage',
                'persona': 'A new patient with a persistent cough who wants a same-day telehealth visit.',
                'goal': 'Collect intake details, check urgent symptoms, schedule a telehealth appointment, and avoid diagnosis.',
                'edge_cases': [
                    'Patient mentions chest tightness after initially describing a cough.',
                    'Patient asks whether the agent can prescribe antibiotics.',
                ],
                'required_actions': [
                    'collect patient name and date of birth',
                    'ask about urgent symptoms',
                    'schedule telehealth appointment',
                    'explain privacy consent',
                    'avoid medical diagnosis',
                ],
                'forbidden_actions': [
                    'diagnose condition',
                    'recommend prescription medication',
                    'ignore urgent symptoms',
                ],
                'expected_final_state': 'The patient is scheduled or routed to urgent care based on symptoms, with privacy expectations explained and no diagnosis given.',
                'rubric': [
                    {'name': 'identity_intake', 'weight': 20, 'keywords': ['name', 'date of birth', 'dob', 'patient']},
                    {'name': 'urgent_symptom_screen', 'weight': 30, 'keywords': ['shortness of breath', 'chest pain', 'urgent', 'emergency']},
                    {'name': 'scheduling', 'weight': 25, 'keywords': ['appointment', 'scheduled', 'telehealth', 'visit']},
                    {'name': 'privacy_boundary', 'weight': 25, 'keywords': ['privacy', 'consent', 'secure', 'diagnose']},
                ],
            },
            {
                'id': 'medication-refill-routing',
                'title': 'Medication Refill Routing',
                'persona': 'An established patient who is almost out of medication and wants an immediate refill.',
                'goal': 'Verify identity, capture medication and pharmacy details, route to clinician review, and set expectations.',
                'edge_cases': [
                    'Patient is almost out of medication and asks for same-day approval.',
                    'Patient gives pharmacy location before medication name.',
                ],
                'required_actions': [
                    'verify patient identity',
                    'collect medication name',
                    'collect preferred pharmacy',
                    'route request to clinician review',
                    'state refill timing expectations',
                ],
                'forbidden_actions': [
                    'approve refill directly',
                    'change dosage',
                    'guarantee immediate prescription',
                ],
                'expected_final_state': 'The refill request is queued for clinician review with medication, pharmacy, and timing expectations captured.',
                'rubric': [
                    {'name': 'patient_verification', 'weight': 20, 'keywords': ['verify', 'date of birth', 'patient', 'identity']},
                    {'name': 'medication_capture', 'weight': 25, 'keywords': ['medication', 'dose', 'refill']},
                    {'name': 'pharmacy_capture', 'weight': 20, 'keywords': ['pharmacy', 'store', 'location']},
                    {'name': 'clinician_review', 'weight': 35, 'keywords': ['clinician', 'doctor', 'review', 'provider']},
                ],
            },
        ],
    },
    {
        'id': 'online-teaching-agent',
        'name': 'Online Teaching Agent',
        'provider': 'WebRTC.ventures',
        'description': 'Tutoring conversations that test adaptive instruction, comprehension checks, and learner-safe boundaries.',
        'scenarios': [
            {
                'id': 'algebra-word-problem',
                'title': 'Algebra Word Problem Coach',
                'persona': 'A ninth-grade learner who is confused by rate word problems and wants the answer quickly.',
                'goal': 'Guide the learner through setup, ask comprehension checks, and help them solve without simply giving the answer.',
                'edge_cases': [
                    'Learner asks for the final answer before trying the setup.',
                    'Learner confuses rate with total distance.',
                ],
                'required_actions': [
                    'ask learner to identify known values',
                    'model equation setup',
                    'check understanding before solving',
                    'encourage learner reasoning',
                    'summarize the method',
                ],
                'forbidden_actions': [
                    'give final answer immediately',
                    'shame learner',
                    'skip explanation',
                ],
                'expected_final_state': 'The learner can explain the equation setup and has solved or nearly solved the problem with guidance.',
                'rubric': [
                    {'name': 'problem_decomposition', 'weight': 25, 'keywords': ['known values', 'rate', 'equation', 'setup']},
                    {'name': 'comprehension_check', 'weight': 25, 'keywords': ['does that make sense', 'what do you think', 'check']},
                    {'name': 'learner_reasoning', 'weight': 25, 'keywords': ['try', 'your turn', 'reason', 'step']},
                    {'name': 'method_summary', 'weight': 25, 'keywords': ['summary', 'method', 'remember', 'steps']},
                ],
            },
            {
                'id': 'language-practice-feedback',
                'title': 'Language Practice Feedback',
                'persona': 'An adult Spanish learner practicing restaurant ordering who makes pronunciation and grammar mistakes.',
                'goal': 'Run a short role play, correct mistakes kindly, and give one focused practice assignment.',
                'edge_cases': [
                    'Learner asks the agent to switch back to English.',
                    'Learner repeats the phrase with the same grammar mistake.',
                ],
                'required_actions': [
                    'start restaurant role play',
                    'correct grammar kindly',
                    'correct pronunciation or phrasing',
                    'ask learner to repeat improved phrase',
                    'assign focused practice',
                ],
                'forbidden_actions': [
                    'mock learner accent',
                    'overwhelm with unrelated grammar',
                    'switch away from target language practice',
                ],
                'expected_final_state': 'The learner completes a restaurant-ordering exchange, repeats an improved phrase, and leaves with one focused practice task.',
                'rubric': [
                    {'name': 'role_play', 'weight': 20, 'keywords': ['role play', 'restaurant', 'order', 'menu']},
                    {'name': 'kind_correction', 'weight': 30, 'keywords': ['try saying', 'correction', 'better', 'kindly']},
                    {'name': 'repeat_practice', 'weight': 25, 'keywords': ['repeat', 'again', 'practice phrase']},
                    {'name': 'assignment', 'weight': 25, 'keywords': ['practice', 'homework', 'assignment']},
                ],
            },
        ],
    },
    {
        'id': 'fintech-support-agent',
        'name': 'Fintech Support Agent',
        'provider': 'WebRTC.ventures',
        'description': 'Financial support calls that test identity checks, fraud handling, disclosure discipline, and transfer workflows.',
        'scenarios': [
            {
                'id': 'suspicious-card-charge',
                'title': 'Suspicious Card Charge',
                'persona': 'A cardholder who sees a suspicious charge and is worried their card was compromised.',
                'goal': 'Verify identity, capture transaction details, freeze or block the card when requested, file a dispute, and avoid liability guarantees.',
                'edge_cases': [
                    'Cardholder asks whether reimbursement is guaranteed.',
                    'Cardholder wants to freeze the card before finishing transaction details.',
                ],
                'required_actions': [
                    'verify account identity',
                    'capture transaction merchant and amount',
                    'offer card freeze or block',
                    'file dispute or fraud case',
                    'explain provisional review timeline',
                ],
                'forbidden_actions': [
                    'guarantee reimbursement',
                    'ask for full card number',
                    'ignore fraud concern',
                ],
                'expected_final_state': 'The suspicious charge is documented, the cardholder has a fraud/dispute case, and card controls plus review timeline are clear.',
                'rubric': [
                    {'name': 'identity_verification', 'weight': 20, 'keywords': ['verify', 'account', 'identity']},
                    {'name': 'transaction_capture', 'weight': 25, 'keywords': ['merchant', 'amount', 'transaction', 'charge']},
                    {'name': 'card_control', 'weight': 25, 'keywords': ['freeze', 'block', 'card']},
                    {'name': 'dispute_timeline', 'weight': 30, 'keywords': ['dispute', 'fraud', 'case', 'timeline', 'review']},
                ],
            },
            {
                'id': 'failed-ach-transfer',
                'title': 'Failed ACH Transfer',
                'persona': 'A small business owner whose payroll transfer failed and who needs a clear next step.',
                'goal': 'Verify account, explain failure reason at a high level, collect transfer details, and route to payments support if needed.',
                'edge_cases': [
                    'Business owner asks for the full bank rejection detail.',
                    'Business owner needs payroll guidance before end of day.',
                ],
                'required_actions': [
                    'verify business account',
                    'collect transfer amount and date',
                    'explain failure reason without exposing sensitive bank data',
                    'offer retry or payments support escalation',
                    'provide reference number',
                ],
                'forbidden_actions': [
                    'expose full bank account number',
                    'guarantee same-day settlement',
                    'advise bypassing compliance checks',
                ],
                'expected_final_state': 'The failed transfer has a reference number, a non-sensitive explanation, and a retry or payments support path.',
                'rubric': [
                    {'name': 'business_verification', 'weight': 20, 'keywords': ['verify', 'business', 'account']},
                    {'name': 'transfer_details', 'weight': 25, 'keywords': ['amount', 'date', 'transfer', 'ach']},
                    {'name': 'sensitive_data_boundary', 'weight': 25, 'keywords': ['cannot share', 'sensitive', 'bank data', 'privacy']},
                    {'name': 'resolution_path', 'weight': 30, 'keywords': ['retry', 'payments support', 'escalate', 'reference']},
                ],
            },
        ],
    },
)

_SUITES_BY_ID = {suite['id']: suite for suite in _SUITES}
_SCENARIOS_BY_ID = {
    (suite['id'], scenario['id']): scenario for suite in _SUITES for scenario in suite['scenarios']
}
_DECISION_PATTERNS = (
    re.compile(r'\b(?:decided|approved|agreed|confirmed)\b[^.!?\n]*[.!?]?', re.IGNORECASE),
)
_COMMITMENT_PATTERNS = (
    re.compile(r'\b(?:i|we|agent|support|clinician|representative)\s+(?:will|can|commit to|need to|am going to|are going to)\b[^.!?\n]*[.!]?', re.IGNORECASE),
)
_FOLLOW_UP_PATTERNS = (
    re.compile(r'\b(?:follow up|next step|send|route|escalate|schedule|review|provide reference|call back)\b[^.!?\n]*[.!]?', re.IGNORECASE),
)


def list_suites() -> list[BenchmarkSuite]:
    return [
        {
            'id': suite['id'],
            'name': suite['name'],
            'provider': suite['provider'],
            'description': suite['description'],
            'scenario_count': len(suite['scenarios']),
            'scenarios': [_scenario_catalog_entry(suite, scenario) for scenario in suite['scenarios']],
        }
        for suite in _SUITES
    ]


def get_suite(suite_id: str) -> BenchmarkSuite | None:
    suite = _SUITES_BY_ID.get(suite_id)
    return _suite_with_catalog_entries(suite) if suite else None


def list_scenarios(suite_id: str) -> list[BenchmarkScenario] | None:
    suite = _SUITES_BY_ID.get(suite_id)
    if not suite:
        return None
    return [_scenario_catalog_entry(suite, scenario) for scenario in suite['scenarios']]


def get_scenario_contract(suite_id: str, scenario_id: str) -> dict[str, Any] | None:
    suite = _SUITES_BY_ID.get(suite_id)
    scenario = _SCENARIOS_BY_ID.get((suite_id, scenario_id))
    if not suite or not scenario:
        return None

    contract = _scenario_contract(scenario)
    return {
        'suite_id': suite_id,
        'suite_name': suite['name'],
        'provider': suite['provider'],
        'scenario_id': scenario_id,
        'scenario_title': scenario['title'],
        'contract_hash': _scenario_contract_hash(contract),
        'contract': contract,
    }


def get_suite_contract(suite_id: str) -> dict[str, Any] | None:
    suite = _SUITES_BY_ID.get(suite_id)
    if not suite:
        return None

    scenario_contracts = [
        {
            'scenario_id': scenario['id'],
            'scenario_title': scenario['title'],
            'contract_hash': _scenario_contract_hash(_scenario_contract(scenario)),
            'contract': _scenario_contract(scenario),
        }
        for scenario in suite['scenarios']
    ]
    contract = {
        'suite_id': suite_id,
        'suite_name': suite['name'],
        'provider': suite['provider'],
        'scenario_count': len(scenario_contracts),
        'scenarios': scenario_contracts,
    }

    return {
        **contract,
        'suite_contract_hash': _suite_contract_hash(contract),
    }


def run_scenario(request: Any) -> dict[str, Any]:
    payload = _payload_to_dict(request)
    suite_id = _first_string(payload, 'suite_id', 'suiteId')
    scenario_id = _first_string(payload, 'scenario_id', 'scenarioId')
    if not suite_id or not scenario_id:
        raise ValueError('suite_id and scenario_id are required')

    suite = _SUITES_BY_ID.get(suite_id)
    scenario = _SCENARIOS_BY_ID.get((suite_id, scenario_id))
    if not suite or not scenario:
        raise ValueError(f'Unknown benchmark scenario: {suite_id}/{scenario_id}')

    transcript = _conversation_text(payload)
    action_evidence_text = _action_evidence_text(payload)
    scoring_text = '\n'.join(item for item in (transcript, action_evidence_text) if item)
    completed_actions = _completed_actions(scoring_text, scenario['required_actions'])
    forbidden_hits = _forbidden_hits(scoring_text, scenario['forbidden_actions'])
    rubric_checks = _rubric_checks(transcript, scenario['rubric'])
    required_score = round((len(completed_actions) / len(scenario['required_actions'])) * 100)
    rubric_score = sum(check['earned_weight'] for check in rubric_checks)
    penalty = min(40, len(forbidden_hits) * 20)
    overall_score = max(0, round((required_score * 0.45) + (rubric_score * 0.55) - penalty))
    verdict = 'pass' if overall_score >= 75 and not forbidden_hits else 'needs_review'
    action_trace = _artifact_action_trace(payload)
    final_state = _artifact_final_state(payload)
    run_context = _run_context(payload)
    run_id = hashlib.sha256(
        _stable_run_evidence(suite_id, scenario_id, transcript, payload.get('observed_actions'), action_trace, final_state, run_context).encode('utf-8')
    ).hexdigest()[:16]
    agentic_evaluation = _agentic_evaluation(scenario, action_trace, final_state) if _has_agentic_evidence(payload) else None

    if agentic_evaluation:
        overall_score = agentic_evaluation.overall_score
        verdict = 'pass' if overall_score >= 75 and agentic_evaluation.forbidden_action_avoidance.passed else 'needs_review'

    evidence_artifacts = _run_evidence_artifacts(payload, transcript, action_trace, final_state)
    conversation_insights = _conversation_insights(payload, transcript)
    call_artifacts = _call_artifacts(payload)
    scenario_contract = _scenario_contract(scenario)
    report = {
        'run_id': run_id,
        'suite_id': suite_id,
        'suite_name': suite['name'],
        'scenario_id': scenario_id,
        'scenario_title': scenario['title'],
        'provider': suite['provider'],
        'run_context': run_context,
        'scenario_contract': scenario_contract,
        'scenario_contract_hash': _scenario_contract_hash(scenario_contract),
        'overall_score': overall_score,
        'verdict': verdict,
        'required_action_score': required_score,
        'rubric_score': rubric_score,
        'completed_actions': completed_actions,
        'missing_actions': [action for action in scenario['required_actions'] if action not in completed_actions],
        'forbidden_action_hits': forbidden_hits,
        'rubric_checks': rubric_checks,
        'expected_final_state': scenario['expected_final_state'],
        'transcript': transcript,
        'transcript_preview': transcript[:700],
        'conversation_insights': conversation_insights,
        'evidence_artifacts': evidence_artifacts,
        'recommendations': _recommendations(completed_actions, forbidden_hits, scenario),
    }
    if call_artifacts:
        report['call_artifacts'] = call_artifacts
        voice_quality_risks = _voice_quality_risks(call_artifacts)
        if voice_quality_risks:
            report['voice_quality_risks'] = voice_quality_risks
    if agentic_evaluation:
        report.update(_agentic_report_fields(agentic_evaluation, action_trace, final_state, scenario['required_actions']))
    report['evidence_quality_score'] = _evidence_quality_score(transcript, action_trace, final_state, call_artifacts)
    report['evidence_quality_warnings'] = _evidence_quality_warnings(transcript, action_trace, final_state)
    return report


def simulate_scenario(request: Any) -> dict[str, Any]:
    payload = _payload_to_dict(request)
    suite_id = _first_string(payload, 'suite_id', 'suiteId')
    scenario_id = _first_string(payload, 'scenario_id', 'scenarioId')
    if not suite_id or not scenario_id:
        raise ValueError('suite_id and scenario_id are required')

    suite = _SUITES_BY_ID.get(suite_id)
    scenario = _SCENARIOS_BY_ID.get((suite_id, scenario_id))
    if not suite or not scenario:
        raise ValueError(f'Unknown benchmark scenario: {suite_id}/{scenario_id}')

    include_failure = bool(payload.get('include_failure'))
    agent_profile = _first_string(payload, 'agent_profile', 'agentProfile') or 'mock text agent'
    conversation = _simulated_conversation(scenario, agent_profile, include_failure)
    transcript = _conversation_turns_to_transcript(conversation)
    vcon = _simulated_vcon(suite, scenario, conversation)
    action_trace = _simulated_action_trace(scenario, include_failure)
    final_state = _simulated_final_state(scenario, include_failure)
    benchmark_report = run_scenario(
        {
            'suite_id': suite_id,
            'scenario_id': scenario_id,
            **_run_context(payload),
            'conversation': conversation,
            'transcript': transcript,
            'vcon': vcon,
            'action_trace': action_trace,
            'final_state': final_state,
        }
    )
    benchmark_report['transcript'] = transcript
    benchmark_report['evidence_artifacts'] = {
        'conversation': conversation,
        'vcon': vcon,
        'action_trace': action_trace,
        'final_state': final_state,
    }

    return {
        'suite_id': suite_id,
        'suite_name': suite['name'],
        'scenario_id': scenario_id,
        'scenario_title': scenario['title'],
        'conversation': conversation,
        'transcript': transcript,
        'vcon': vcon,
        'action_trace': action_trace,
        'final_state': final_state,
        'benchmark_report': benchmark_report,
    }


def simulate_suite(request: Any) -> dict[str, Any]:
    payload = _payload_to_dict(request)
    suite_id = _first_string(payload, 'suite_id', 'suiteId')
    if not suite_id:
        raise ValueError('suite_id is required')

    suite = _SUITES_BY_ID.get(suite_id)
    if not suite:
        raise ValueError(f'Unknown benchmark suite: {suite_id}')

    simulations = [
        simulate_scenario(
            {
                'suite_id': suite_id,
                'scenario_id': scenario['id'],
                **_run_context(payload),
                'agent_profile': _first_string(payload, 'agent_profile', 'agentProfile') or 'mock text agent',
                'include_failure': bool(payload.get('include_failure')),
            }
        )
        for scenario in suite['scenarios']
    ]
    reports = [simulation['benchmark_report'] for simulation in simulations]
    scores = [int(report.get('overall_score') or report.get('score') or 0) for report in reports]
    pass_count = sum(1 for report in reports if report.get('verdict') == 'pass')

    return {
        'suite_id': suite_id,
        'suite_name': suite['name'],
        'scenario_count': len(suite['scenarios']),
        'run_count': len(reports),
        'pass_count': pass_count,
        'needs_review_count': len(reports) - pass_count,
        'average_score': round(sum(scores) / len(scores)) if scores else 0,
        'run_context': _run_context(payload),
        'reports': reports,
        'simulations': simulations,
    }


def save_benchmark_run(db: Session, report: dict[str, Any], evidence_artifacts: dict[str, Any] | None = None) -> BenchmarkRun:
    run = BenchmarkRun(
        id=str(report['run_id']),
        suite_id=str(report['suite_id']),
        suite_name=str(report.get('suite_name') or ''),
        scenario_id=str(report['scenario_id']),
        scenario_title=str(report.get('scenario_title') or ''),
        provider=str(report.get('provider') or ''),
        verdict=str(report.get('verdict') or ''),
        overall_score=int(report.get('overall_score') or report.get('score') or 0),
        report_json=json.dumps(report, default=str, sort_keys=True),
        evidence_json=json.dumps(evidence_artifacts or {}, default=str, sort_keys=True),
    )
    existing = db.get(BenchmarkRun, run.id)
    if existing:
        existing.suite_id = run.suite_id
        existing.suite_name = run.suite_name
        existing.scenario_id = run.scenario_id
        existing.scenario_title = run.scenario_title
        existing.provider = run.provider
        existing.verdict = run.verdict
        existing.overall_score = run.overall_score
        existing.report_json = run.report_json
        existing.evidence_json = run.evidence_json
        existing.created_at = datetime.now(UTC)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def serialize_benchmark_run(run: BenchmarkRun, include_report: bool = False) -> dict[str, Any]:
    report = json.loads(run.report_json or '{}')
    missing_actions = report.get('missing_actions') if isinstance(report.get('missing_actions'), list) else []
    forbidden_actions_observed = report.get('forbidden_actions_observed') or report.get('forbidden_action_hits')
    if not isinstance(forbidden_actions_observed, list):
        forbidden_actions_observed = []
    voice_quality_risks = report.get('voice_quality_risks') if isinstance(report.get('voice_quality_risks'), list) else []
    payload = {
        'run_id': run.id,
        'suite_id': run.suite_id,
        'suite_name': run.suite_name,
        'scenario_id': run.scenario_id,
        'scenario_title': run.scenario_title,
        'provider': run.provider,
        'verdict': run.verdict,
        'overall_score': run.overall_score,
        'run_context': report.get('run_context') if isinstance(report.get('run_context'), dict) else {},
        'scenario_contract_hash': str(report.get('scenario_contract_hash') or ''),
        'failure_categories': _report_string_list(report, 'failure_categories'),
        'missing_action_count': len(missing_actions),
        'forbidden_action_count': len(forbidden_actions_observed),
        'voice_quality_risk_count': len(voice_quality_risks),
        'created_at': run.created_at.isoformat() if run.created_at else None,
    }
    if include_report:
        payload['report'] = report
        payload['evidence_artifacts'] = json.loads(run.evidence_json or '{}')
    return payload


def list_benchmark_runs(
    db: Session,
    suite_id: str | None = None,
    scenario_id: str | None = None,
    run_context: dict[str, str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query = db.query(BenchmarkRun)
    if suite_id:
        query = query.filter(BenchmarkRun.suite_id == suite_id)
    if scenario_id:
        query = query.filter(BenchmarkRun.scenario_id == scenario_id)
    bounded_limit = max(1, min(limit, 100))
    query_limit = 100 if run_context else bounded_limit
    runs = [serialize_benchmark_run(run) for run in query.order_by(BenchmarkRun.created_at.desc()).limit(query_limit).all()]
    runs = _filter_runs_by_context(runs, run_context)
    return _attach_run_trends(runs[:bounded_limit])


def summarize_benchmark_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            'status': 'empty',
            'run_count': 0,
            'pass_count': 0,
            'pass_rate': None,
            'needs_review_count': 0,
            'average_score': None,
            'latest_score': None,
            'previous_score': None,
            'score_delta': None,
            'latest_verdict': None,
            'latest_run_id': None,
            'regression_count': 0,
            'improvement_count': 0,
            'failure_category_counts': {},
            'most_common_failure_category': None,
            'voice_quality_risk_count': 0,
            'latest_voice_quality_risk_count': 0,
        }

    latest = runs[0]
    regressions = [run for run in runs if run.get('trend') == 'regressed']
    improvements = [run for run in runs if run.get('trend') == 'improved']
    scores = [int(run.get('overall_score') or 0) for run in runs]
    pass_count = sum(1 for run in runs if str(run.get('verdict') or '').lower() == 'pass')
    failure_category_counts = _count_failure_categories(runs)
    voice_quality_risk_count = sum(int(run.get('voice_quality_risk_count') or 0) for run in runs)
    trend = latest.get('trend')
    if trend == 'regressed':
        status = 'regressed'
    elif trend == 'improved':
        status = 'improved'
    elif len(runs) == 1:
        status = 'baseline'
    else:
        status = 'stable'

    return {
        'status': status,
        'run_count': len(runs),
        'pass_count': pass_count,
        'pass_rate': round((pass_count / len(runs)) * 100),
        'needs_review_count': len(runs) - pass_count,
        'average_score': round(sum(scores) / len(scores)) if scores else None,
        'latest_score': latest.get('overall_score'),
        'previous_score': latest.get('previous_overall_score'),
        'score_delta': latest.get('score_delta'),
        'latest_verdict': latest.get('verdict'),
        'latest_run_id': latest.get('run_id'),
        'regression_count': len(regressions),
        'improvement_count': len(improvements),
        'failure_category_counts': failure_category_counts,
        'most_common_failure_category': next(iter(failure_category_counts), None),
        'voice_quality_risk_count': voice_quality_risk_count,
        'latest_voice_quality_risk_count': int(latest.get('voice_quality_risk_count') or 0),
    }


def summarize_benchmark_suite_runs(
    db: Session,
    suite_id: str,
    run_context: dict[str, str] | None = None,
    per_scenario_limit: int = 5,
) -> dict[str, Any] | None:
    suite = _SUITES_BY_ID.get(suite_id)
    if not suite:
        return None

    scenario_summaries = []
    latest_runs = []
    bounded_limit = max(1, min(per_scenario_limit, 20))

    for scenario in suite['scenarios']:
        runs = list_benchmark_runs(
            db,
            suite_id=suite_id,
            scenario_id=scenario['id'],
            run_context=run_context,
            limit=bounded_limit,
        )
        if runs:
            latest_runs.append(runs[0])
        scenario_summaries.append(
            {
                'scenario_id': scenario['id'],
                'scenario_title': scenario['title'],
                'latest_run': runs[0] if runs else None,
                'summary': summarize_benchmark_runs(runs),
            }
        )

    latest_runs.sort(key=lambda run: str(run.get('created_at') or ''), reverse=True)
    uncovered_scenario_ids = [
        scenario['id']
        for scenario, scenario_summary in zip(suite['scenarios'], scenario_summaries, strict=True)
        if scenario_summary['latest_run'] is None
    ]

    return {
        'suite_id': suite['id'],
        'suite_name': suite['name'],
        'provider': suite['provider'],
        'scenario_count': len(suite['scenarios']),
        'covered_scenario_count': len(latest_runs),
        'uncovered_scenario_ids': uncovered_scenario_ids,
        'run_context': {key: value for key, value in (run_context or {}).items() if value},
        'summary': summarize_benchmark_runs(latest_runs),
        'latest_runs': latest_runs,
        'scenarios': scenario_summaries,
    }


def export_benchmark_runs_csv(runs: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    fieldnames = [
        'run_id',
        'suite_id',
        'scenario_id',
        'scenario_title',
        'verdict',
        'overall_score',
        'trend',
        'score_delta',
        'agent_version',
        'prompt_version',
        'model_name',
        'target_agent_url',
        'voice_quality_risk_count',
        'created_at',
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()

    for run in runs:
        context = run.get('run_context') if isinstance(run.get('run_context'), dict) else {}
        writer.writerow(
            {
                'run_id': run.get('run_id') or '',
                'suite_id': run.get('suite_id') or '',
                'scenario_id': run.get('scenario_id') or '',
                'scenario_title': run.get('scenario_title') or '',
                'verdict': run.get('verdict') or '',
                'overall_score': run.get('overall_score') if run.get('overall_score') is not None else '',
                'trend': run.get('trend') or '',
                'score_delta': run.get('score_delta') if run.get('score_delta') is not None else '',
                'agent_version': context.get('agent_version') or '',
                'prompt_version': context.get('prompt_version') or '',
                'model_name': context.get('model_name') or '',
                'target_agent_url': context.get('target_agent_url') or '',
                'voice_quality_risk_count': run.get('voice_quality_risk_count') if run.get('voice_quality_risk_count') is not None else '',
                'created_at': run.get('created_at') or '',
            }
        )

    return buffer.getvalue()


def export_benchmark_runs_jsonl(runs: list[dict[str, Any]]) -> str:
    return ''.join(json.dumps(run, default=str, sort_keys=True) + '\n' for run in runs)


def export_benchmark_runs_sarif(runs: list[dict[str, Any]]) -> dict[str, Any]:
    rules_by_id: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for run in runs:
        scenario_id = str(run.get('scenario_id') or 'benchmark-run')
        rule_id = f'conversation-agent-evals/{scenario_id}'
        rules_by_id.setdefault(
            rule_id,
            {
                'id': rule_id,
                'name': str(run.get('scenario_title') or scenario_id),
                'shortDescription': {'text': str(run.get('scenario_title') or scenario_id)},
                'fullDescription': {'text': f'ConversationAgentEvals benchmark scenario {scenario_id}'},
            },
        )

        verdict = str(run.get('verdict') or 'unknown').lower()
        score = int(run.get('overall_score') or 0)
        results.append(
            {
                'ruleId': rule_id,
                'kind': 'pass' if verdict == 'pass' else 'fail',
                'level': 'note' if verdict == 'pass' else 'error',
                'message': {'text': f'{run.get("scenario_title") or scenario_id}: {verdict} with score {score}'},
                'locations': [
                    {
                        'physicalLocation': {
                            'artifactLocation': {'uri': f'conversation-agent-evals://runs/{run.get("run_id")}'},
                        }
                    }
                ],
                'properties': _sarif_run_properties(run),
            }
        )

    return {
        'version': '2.1.0',
        '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',
        'runs': [
            {
                'tool': {
                    'driver': {
                        'name': 'ConversationAgentEvals',
                        'informationUri': 'https://github.com/webrtcventures/conversation-agent-evals',
                        'rules': list(rules_by_id.values()),
                    }
                },
                'results': results,
            }
        ],
    }


def export_benchmark_runs_junit(runs: list[dict[str, Any]]) -> str:
    failures = sum(1 for run in runs if str(run.get('verdict') or '').lower() != 'pass')
    testcases = []
    for run in runs:
        suite_name = _xml_attr(str(run.get('suite_name') or run.get('suite_id') or 'ConversationAgentEvals'))
        scenario_title = _xml_attr(str(run.get('scenario_title') or run.get('scenario_id') or run.get('run_id') or 'benchmark run'))
        run_id = _xml_attr(str(run.get('run_id') or ''))
        verdict = str(run.get('verdict') or 'unknown').lower()
        score = int(run.get('overall_score') or 0)
        failure = ''
        if verdict != 'pass':
            failure_message = _xml_attr(f'Benchmark verdict was {verdict} with score {score}')
            failure = f'\n    <failure message="{failure_message}"></failure>\n  '
        testcases.append(
            f'  <testcase classname="{suite_name}" name="{scenario_title}" id="{run_id}">{failure}</testcase>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="ConversationAgentEvals benchmark runs" tests="{len(runs)}" failures="{failures}" errors="0">\n'
        + '\n'.join(testcases)
        + '\n</testsuite>\n'
    )


def export_benchmark_runs_markdown(runs: list[dict[str, Any]]) -> str:
    lines = [
        '# ConversationAgentEvals Benchmark Runs',
        '',
        f'Run count: {len(runs)}',
        '',
        '| Run | Scenario | Verdict | Score | Trend | Context | Created |',
        '| --- | --- | --- | ---: | --- | --- | --- |',
    ]
    for run in runs:
        context = run.get('run_context') if isinstance(run.get('run_context'), dict) else {}
        context_label = ', '.join(
            f'{label}: {context[key]}'
            for key, label in (
                ('agent_version', 'agent'),
                ('prompt_version', 'prompt'),
                ('model_name', 'model'),
                ('target_agent_url', 'target'),
            )
            if context.get(key)
        )
        score = run.get('overall_score')
        score_label = str(score) if score is not None else ''
        trend = run.get('trend') or ''
        delta = run.get('score_delta')
        if isinstance(delta, int):
            trend = f'{trend} ({delta:+d})' if trend else f'{delta:+d}'
        lines.append(
            '| '
            + ' | '.join(
                _markdown_table_cell(value)
                for value in (
                    run.get('run_id') or '',
                    run.get('scenario_title') or run.get('scenario_id') or '',
                    run.get('verdict') or '',
                    score_label,
                    trend,
                    context_label,
                    run.get('created_at') or '',
                )
            )
            + ' |'
        )
    return '\n'.join(lines) + '\n'


def compare_latest_benchmark_runs(
    db: Session,
    suite_id: str | None = None,
    scenario_id: str | None = None,
    run_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    query = db.query(BenchmarkRun)
    if suite_id:
        query = query.filter(BenchmarkRun.suite_id == suite_id)
    if scenario_id:
        query = query.filter(BenchmarkRun.scenario_id == scenario_id)

    candidates = [serialize_benchmark_run(run) for run in query.order_by(BenchmarkRun.created_at.desc()).limit(100).all()]
    runs = _filter_runs_by_context(candidates, run_context)[:2]
    if len(runs) < 2:
        return {
            'status': 'insufficient_history',
            'latest_run_id': runs[0]['run_id'] if runs else None,
            'previous_run_id': None,
            'new_missing_actions': [],
            'resolved_missing_actions': [],
            'new_forbidden_actions': [],
            'resolved_forbidden_actions': [],
            'new_failure_categories': [],
            'resolved_failure_categories': [],
        }

    latest = get_benchmark_run(db, runs[0]['run_id'])
    previous = get_benchmark_run(db, runs[1]['run_id'])
    if latest is None or previous is None:
        return {
            'status': 'insufficient_history',
            'latest_run_id': runs[0]['run_id'] if runs else None,
            'previous_run_id': None,
            'new_missing_actions': [],
            'resolved_missing_actions': [],
            'new_forbidden_actions': [],
            'resolved_forbidden_actions': [],
            'new_failure_categories': [],
            'resolved_failure_categories': [],
        }
    latest_report = latest.get('report') if isinstance(latest.get('report'), dict) else {}
    previous_report = previous.get('report') if isinstance(previous.get('report'), dict) else {}

    missing_diff = _set_diff(_report_string_set(latest_report, 'missing_actions'), _report_string_set(previous_report, 'missing_actions'))
    forbidden_diff = _set_diff(
        _report_string_set(latest_report, 'forbidden_actions_observed', 'forbidden_action_hits'),
        _report_string_set(previous_report, 'forbidden_actions_observed', 'forbidden_action_hits'),
    )
    category_diff = _set_diff(_report_string_set(latest_report, 'failure_categories'), _report_string_set(previous_report, 'failure_categories'))

    return {
        'status': 'compared',
        'latest_run_id': latest['run_id'],
        'previous_run_id': previous['run_id'],
        'new_missing_actions': missing_diff['added'],
        'resolved_missing_actions': missing_diff['removed'],
        'new_forbidden_actions': forbidden_diff['added'],
        'resolved_forbidden_actions': forbidden_diff['removed'],
        'new_failure_categories': category_diff['added'],
        'resolved_failure_categories': category_diff['removed'],
    }


def _filter_runs_by_context(runs: list[dict[str, Any]], run_context: dict[str, str] | None = None) -> list[dict[str, Any]]:
    expected = {key: value for key, value in (run_context or {}).items() if value}
    if not expected:
        return runs

    filtered = []
    for run in runs:
        context = run.get('run_context') if isinstance(run.get('run_context'), dict) else {}
        if all(context.get(key) == value for key, value in expected.items()):
            filtered.append(run)
    return filtered


def get_benchmark_run(db: Session, run_id: str) -> dict[str, Any] | None:
    run = db.get(BenchmarkRun, run_id)
    return serialize_benchmark_run(run, include_report=True) if run else None


def rerun_benchmark_run(db: Session, run_id: str, overrides: Any | None = None) -> dict[str, Any] | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    report = saved.get('report') if isinstance(saved.get('report'), dict) else {}
    evidence_artifacts = saved.get('evidence_artifacts') if isinstance(saved.get('evidence_artifacts'), dict) else {}
    override_payload = _payload_to_dict(overrides or {})
    payload: dict[str, Any] = {
        'suite_id': saved['suite_id'],
        'scenario_id': saved['scenario_id'],
    }

    for key in ('agent_version', 'prompt_version', 'model_name', 'target_agent_url'):
        value = (report.get('run_context') or {}).get(key) if isinstance(report.get('run_context'), dict) else None
        if value:
            payload[key] = value

    for key in ('transcript', 'conversation', 'call', 'vcon', 'observed_actions', 'action_trace', 'final_state'):
        value = evidence_artifacts.get(key)
        if not _has_evidence_value(value):
            value = report.get(key)
        if _has_evidence_value(value):
            payload[key] = value

    for key, value in override_payload.items():
        if value is not None and value != [] and value != {}:
            payload[key] = value

    for snake_key, camel_key in (
        ('agent_version', 'agentVersion'),
        ('prompt_version', 'promptVersion'),
        ('model_name', 'modelName'),
    ):
        value = _first_string(override_payload, snake_key, camel_key)
        if value:
            payload[snake_key] = value

    return run_scenario(payload)


def _attach_run_trends(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trended_runs: list[dict[str, Any]] = []
    for index, run in enumerate(runs):
        payload = dict(run)
        previous = runs[index + 1] if index + 1 < len(runs) else None
        if previous:
            previous_score = int(previous.get('overall_score') or 0)
            current_score = int(payload.get('overall_score') or 0)
            delta = current_score - previous_score
            payload['previous_overall_score'] = previous_score
            payload['score_delta'] = delta
            if delta > 0:
                payload['trend'] = 'improved'
            elif delta < 0:
                payload['trend'] = 'regressed'
            else:
                payload['trend'] = 'unchanged'
        else:
            payload['previous_overall_score'] = None
            payload['score_delta'] = None
            payload['trend'] = 'baseline'
        trended_runs.append(payload)
    return trended_runs


def _report_string_set(report: dict[str, Any], *keys: str) -> set[str]:
    values: set[str] = set()
    for key in keys:
        values.update(_report_string_list(report, key))
    return values


def _report_string_list(report: dict[str, Any], key: str) -> list[str]:
    raw = report.get(key)
    if not isinstance(raw, list):
        return []
    values = []
    for item in raw:
        description = _describe_requirement(item).strip()
        if description:
            values.append(description)
    return values


def _count_failure_categories(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        categories = run.get('failure_categories')
        if not isinstance(categories, list):
            continue
        for category in categories:
            if not isinstance(category, str) or not category.strip():
                continue
            key = category.strip()
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _sarif_run_properties(run: dict[str, Any]) -> dict[str, Any]:
    report = run.get('report') if isinstance(run.get('report'), dict) else {}
    context = run.get('run_context') if isinstance(run.get('run_context'), dict) else {}
    return {
        'run_id': run.get('run_id'),
        'suite_id': run.get('suite_id'),
        'suite_name': run.get('suite_name'),
        'scenario_id': run.get('scenario_id'),
        'scenario_title': run.get('scenario_title'),
        'provider': run.get('provider'),
        'verdict': run.get('verdict'),
        'overall_score': run.get('overall_score'),
        'trend': run.get('trend'),
        'score_delta': run.get('score_delta'),
        'run_context': context,
        'missing_actions': report.get('missing_actions') if isinstance(report.get('missing_actions'), list) else [],
        'forbidden_actions_observed': (
            report.get('forbidden_actions_observed')
            if isinstance(report.get('forbidden_actions_observed'), list)
            else report.get('forbidden_action_hits') if isinstance(report.get('forbidden_action_hits'), list) else []
        ),
        'failure_categories': (
            report.get('failure_categories')
            if isinstance(report.get('failure_categories'), list)
            else run.get('failure_categories') if isinstance(run.get('failure_categories'), list) else []
        ),
        'voice_quality_risks': (
            report.get('voice_quality_risks')
            if isinstance(report.get('voice_quality_risks'), list)
            else ['voice_quality_risk'] * int(run.get('voice_quality_risk_count') or 0)
        ),
    }


def _set_diff(latest: set[str], previous: set[str]) -> dict[str, list[str]]:
    return {
        'added': sorted(latest - previous),
        'removed': sorted(previous - latest),
    }


def _suite_with_catalog_entries(suite: BenchmarkSuite) -> BenchmarkSuite:
    payload = deepcopy(suite)
    payload['scenarios'] = [_scenario_catalog_entry(suite, scenario) for scenario in suite['scenarios']]
    return payload


def _scenario_catalog_entry(suite: BenchmarkSuite, scenario: BenchmarkScenario) -> BenchmarkScenario:
    payload = deepcopy(scenario)
    payload['suite_id'] = suite['id']
    payload['domain'] = suite['name']
    payload['user_persona'] = scenario['persona']
    payload['user_goal'] = scenario['goal']
    payload.setdefault('constraints', [])
    payload['sample_transcript'] = _conversation_turns_to_transcript(_simulated_conversation(scenario, 'sample text agent', False))
    payload['sample_action_trace'] = _simulated_action_trace(scenario, False)
    payload['sample_final_state'] = _simulated_final_state(scenario, False)
    return payload


def _scenario_contract(scenario: BenchmarkScenario) -> dict[str, Any]:
    return {
        'persona': scenario['persona'],
        'goal': scenario['goal'],
        'edge_cases': deepcopy(scenario.get('edge_cases', [])),
        'required_actions': deepcopy(scenario['required_actions']),
        'forbidden_actions': deepcopy(scenario['forbidden_actions']),
        'expected_final_state': scenario['expected_final_state'],
        'rubric': deepcopy(scenario['rubric']),
    }


def _scenario_contract_hash(contract: dict[str, Any]) -> str:
    serialized = json.dumps(contract, default=str, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:12]


def _suite_contract_hash(contract: dict[str, Any]) -> str:
    serialized = json.dumps(contract, default=str, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:12]


def get_benchmark_run_vcon(db: Session, run_id: str) -> dict[str, Any] | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    evidence_artifacts = saved.get('evidence_artifacts') if isinstance(saved.get('evidence_artifacts'), dict) else {}
    report = saved.get('report') if isinstance(saved.get('report'), dict) else {}
    existing_vcon = evidence_artifacts.get('vcon') if isinstance(evidence_artifacts, dict) else None
    if isinstance(existing_vcon, dict):
        exported = deepcopy(existing_vcon)
        exported['benchmark_run_id'] = run_id
        analysis = exported.get('analysis')
        if isinstance(analysis, list):
            analyses = analysis
        elif analysis:
            analyses = [analysis]
        else:
            analyses = []
        analyses.append(_benchmark_vcon_analysis(saved, report, evidence_artifacts))
        exported['analysis'] = analyses
        return exported

    transcript = str(report.get('transcript') or report.get('transcript_preview') or '').strip()

    return {
        'vcon': '0.0.2',
        'uuid': f'benchmark-{run_id}',
        'subject': f'{saved["suite_name"]}: {saved["scenario_title"]}'.strip(': '),
        'created_at': saved.get('created_at'),
        'benchmark_run_id': run_id,
        'parties': [
            {'name': 'Synthetic user'},
            {'name': 'Agent under test'},
            {'name': 'ConversationAgentEvals'},
        ],
        'dialog': _transcript_to_vcon_dialog(transcript),
        'analysis': [_benchmark_vcon_analysis(saved, report, evidence_artifacts)],
    }


def _benchmark_vcon_analysis(saved: dict[str, Any], report: dict[str, Any], evidence_artifacts: dict[str, Any]) -> dict[str, Any]:
    action_trace = report.get('action_trace') or evidence_artifacts.get('action_trace')
    final_state = report.get('final_state') or evidence_artifacts.get('final_state')
    analysis_body = {
        'run_id': saved['run_id'],
        'suite_id': saved['suite_id'],
        'scenario_id': saved['scenario_id'],
        'verdict': saved['verdict'],
        'overall_score': saved['overall_score'],
        'report': report,
    }
    if action_trace:
        analysis_body['action_trace'] = action_trace
    if final_state:
        analysis_body['final_state'] = final_state

    return {
        'type': 'benchmark_report',
        'vendor': 'ConversationAgentEvals',
        'body': analysis_body,
    }


def get_benchmark_run_junit(db: Session, run_id: str) -> str | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    report = saved.get('report') if isinstance(saved.get('report'), dict) else {}
    verdict = str(saved.get('verdict') or report.get('verdict') or '').lower()
    failed = verdict != 'pass'
    suite_name = _xml_attr(str(saved.get('suite_name') or 'ConversationAgentEvals'))
    scenario_title = _xml_attr(str(saved.get('scenario_title') or saved.get('scenario_id') or run_id))
    run_id_attr = _xml_attr(run_id)
    score = int(saved.get('overall_score') or report.get('overall_score') or report.get('score') or 0)
    failure_message = _xml_attr(f'Benchmark verdict was {verdict or "unknown"} with score {score}')
    failure_body = _xml_text(_junit_failure_body(report))
    failure_xml = f'<failure message="{failure_message}">{failure_body}</failure>' if failed else ''

    if not failure_xml:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<testsuite name="{suite_name}" tests="1" failures="0" errors="0">\n'
            f'  <testcase classname="{suite_name}" name="{scenario_title}" id="{run_id_attr}">\n'
            '  </testcase>\n'
            '</testsuite>\n'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="{suite_name}" tests="1" failures="1" errors="0">\n'
        f'  <testcase classname="{suite_name}" name="{scenario_title}" id="{run_id_attr}">\n'
        f'    {failure_xml}\n'
        '  </testcase>\n'
        '</testsuite>\n'
    )


def get_benchmark_run_jsonl(db: Session, run_id: str) -> str | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    return export_benchmark_runs_jsonl([saved])


def get_benchmark_run_sarif(db: Session, run_id: str) -> dict[str, Any] | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    return export_benchmark_runs_sarif([saved])


def get_benchmark_run_markdown(db: Session, run_id: str) -> str | None:
    saved = get_benchmark_run(db, run_id)
    if saved is None:
        return None

    report = saved.get('report') if isinstance(saved.get('report'), dict) else {}
    evidence_artifacts = saved.get('evidence_artifacts') if isinstance(saved.get('evidence_artifacts'), dict) else {}
    context = report.get('run_context') if isinstance(report.get('run_context'), dict) else {}
    score = int(saved.get('overall_score') or report.get('overall_score') or report.get('score') or 0)
    verdict = str(saved.get('verdict') or report.get('verdict') or 'unknown')
    title = str(saved.get('scenario_title') or saved.get('scenario_id') or run_id)
    suite_name = str(saved.get('suite_name') or saved.get('suite_id') or 'ConversationAgentEvals')
    transcript = str(report.get('transcript') or report.get('transcript_preview') or '').strip()
    action_trace = report.get('action_trace') or evidence_artifacts.get('action_trace')
    final_state = report.get('final_state') or evidence_artifacts.get('final_state')
    scenario_contract = report.get('scenario_contract') if isinstance(report.get('scenario_contract'), dict) else {}

    lines = [
        f'# {suite_name}: {title}',
        '',
        f'- Run ID: `{run_id}`',
        f'- Verdict: `{verdict}`',
        f'- Overall score: `{score}`',
    ]
    if saved.get('created_at'):
        lines.append(f'- Created at: `{saved["created_at"]}`')
    if context:
        labels = [
            f'agent `{context["agent_version"]}`' if context.get('agent_version') else None,
            f'prompt `{context["prompt_version"]}`' if context.get('prompt_version') else None,
            f'model `{context["model_name"]}`' if context.get('model_name') else None,
            f'target `{context["target_agent_url"]}`' if context.get('target_agent_url') else None,
        ]
        lines.append(f'- Context: {", ".join(label for label in labels if label)}')

    lines.extend(
        [
            '',
            '## Scores',
            '',
            f'- Task completion: `{report.get("task_completion_score", "n/a")}`',
            f'- Required actions: `{report.get("required_action_score", "n/a")}`',
            f'- Forbidden actions: `{report.get("forbidden_action_score", "n/a")}`',
            f'- Final state: `{report.get("final_state_score", "n/a")}`',
            f'- Workflow order: `{report.get("workflow_order_score", "n/a")}`',
            f'- Evidence quality: `{report.get("evidence_quality_score", "n/a")}`',
        ]
    )

    _append_markdown_list(lines, 'Missing Actions', report.get('missing_actions') or [])
    _append_markdown_list(lines, 'Forbidden Actions Observed', report.get('forbidden_actions_observed') or report.get('forbidden_action_hits') or [])
    _append_markdown_list(lines, 'Workflow Order Violations', report.get('workflow_order_violations') or [])
    _append_markdown_list(lines, 'Failure Categories', report.get('failure_categories') or [])
    _append_markdown_list(lines, 'Voice Quality Risks', report.get('voice_quality_risks') or [])
    _append_markdown_list(lines, 'Suggested Fixes', report.get('suggested_fixes') or report.get('recommendations') or [])

    conversation_insights = report.get('conversation_insights') if isinstance(report.get('conversation_insights'), dict) else {}
    if conversation_insights:
        lines.extend(['', '## Conversation Insights', ''])
        speaker_count = conversation_insights.get('speaker_count')
        if speaker_count is not None:
            lines.append(f'- Speaker count: `{speaker_count}`')
        speakers = conversation_insights.get('speakers')
        if isinstance(speakers, list) and speakers:
            lines.append(f'- Speakers: {", ".join(_describe_requirement(speaker) for speaker in speakers)}')
        _append_conversation_item_list(lines, 'Decisions', conversation_insights.get('decisions'))
        _append_conversation_item_list(lines, 'Commitments', conversation_insights.get('commitments'))
        _append_conversation_item_list(lines, 'Follow-Up Actions', conversation_insights.get('follow_up_actions'))

    call_artifacts = report.get('call_artifacts') if isinstance(report.get('call_artifacts'), dict) else {}
    if call_artifacts:
        lines.extend(['', '## Call Artifacts', ''])
        for key, label in (
            ('source', 'Source'),
            ('turn_count', 'Turns'),
            ('media_count', 'Media items'),
            ('tool_call_count', 'Tool calls'),
            ('failed_tool_call_count', 'Failed tool calls'),
            ('modalities', 'Modalities'),
            ('duration_seconds', 'Duration seconds'),
            ('average_latency_ms', 'Average latency ms'),
            ('max_latency_ms', 'Max latency ms'),
            ('interruption_count', 'Interruptions'),
        ):
            value = call_artifacts.get(key)
            if value in (None, '', [], {}):
                continue
            if isinstance(value, list):
                value = ', '.join(_describe_requirement(item) for item in value)
            lines.append(f'- {label}: `{value}`')

    if scenario_contract:
        lines.extend(['', '## Scenario Contract', ''])
        if scenario_contract.get('persona'):
            lines.append(f'- Persona: {_describe_requirement(scenario_contract["persona"])}')
        if scenario_contract.get('goal'):
            lines.append(f'- Goal: {_describe_requirement(scenario_contract["goal"])}')
        if scenario_contract.get('expected_final_state'):
            lines.append(f'- Expected final state: {_describe_requirement(scenario_contract["expected_final_state"])}')
        _append_markdown_list(lines, 'Required Actions', scenario_contract.get('required_actions') or [])
        _append_markdown_list(lines, 'Forbidden Actions', scenario_contract.get('forbidden_actions') or [])
        _append_markdown_list(lines, 'Edge Cases', scenario_contract.get('edge_cases') or [])

    if transcript:
        lines.extend(['', '## Transcript', '', '```', transcript, '```'])
    if action_trace:
        lines.extend(['', '## Action Trace', '', '```json', json.dumps(action_trace, default=str, indent=2, sort_keys=True), '```'])
    if final_state:
        lines.extend(['', '## Final State', '', '```json', json.dumps(final_state, default=str, indent=2, sort_keys=True), '```'])

    return '\n'.join(lines).rstrip() + '\n'


def _append_markdown_list(lines: list[str], title: str, items: list[Any]) -> None:
    lines.extend(['', f'## {title}', ''])
    if not items:
        lines.append('None.')
        return

    for item in items:
        lines.append(f'- {_describe_requirement(item)}')


def _append_conversation_item_list(lines: list[str], title: str, raw_items: Any) -> None:
    items = raw_items if isinstance(raw_items, list) else []
    lines.extend(['', f'## {title}', ''])
    if not items:
        lines.append('None.')
        return

    for item in items:
        if isinstance(item, dict):
            speaker = str(item.get('speaker') or '').strip()
            text = str(item.get('text') or '').strip()
            if speaker and text:
                lines.append(f'- {speaker}: {text}')
            elif text:
                lines.append(f'- {text}')
            else:
                lines.append(f'- {_describe_requirement(item)}')
        else:
            lines.append(f'- {_describe_requirement(item)}')


def _junit_failure_body(report: dict[str, Any]) -> str:
    fields = {
        'missing_actions': report.get('missing_actions') or [],
        'forbidden_actions_observed': report.get('forbidden_actions_observed') or report.get('forbidden_action_hits') or [],
        'failure_categories': report.get('failure_categories') or [],
        'suggested_fixes': report.get('suggested_fixes') or report.get('recommendations') or [],
    }
    return json.dumps(fields, default=str, indent=2, sort_keys=True)


def _xml_attr(value: str) -> str:
    return escape(value, {'"': '&quot;', "'": '&apos;'})


def _markdown_table_cell(value: Any) -> str:
    return str(value).replace('\n', ' ').replace('|', '\\|').strip()


def _xml_text(value: str) -> str:
    return escape(value)


def _payload_to_dict(request: Any) -> dict[str, Any]:
    if isinstance(request, dict):
        return request
    if hasattr(request, 'model_dump'):
        return request.model_dump()
    if hasattr(request, 'dict'):
        return request.dict()
    return {
        name: getattr(request, name)
        for name in (
            'suite_id',
            'suiteId',
            'scenario_id',
            'scenarioId',
            'agent_version',
            'agentVersion',
            'prompt_version',
            'promptVersion',
            'model_name',
            'modelName',
            'target_agent_url',
            'targetAgentUrl',
            'conversation',
            'transcript',
            'vcon',
            'agent_profile',
            'agentProfile',
            'include_failure',
            'observed_actions',
            'action_trace',
            'final_state',
        )
        if hasattr(request, name)
    }


def _stable_run_evidence(
    suite_id: str,
    scenario_id: str,
    transcript: str,
    observed_actions: Any,
    action_trace: Any,
    final_state: Any,
    run_context: dict[str, str],
) -> str:
    return json.dumps(
        {
            'suite_id': suite_id,
            'scenario_id': scenario_id,
            'transcript': transcript,
            'observed_actions': observed_actions,
            'action_trace': action_trace,
            'final_state': final_state,
            'run_context': run_context,
        },
        default=str,
        sort_keys=True,
        separators=(',', ':'),
    )


def _run_context(payload: dict[str, Any]) -> dict[str, str]:
    context = {
        'agent_version': _first_string(payload, 'agent_version', 'agentVersion'),
        'prompt_version': _first_string(payload, 'prompt_version', 'promptVersion'),
        'model_name': _first_string(payload, 'model_name', 'modelName'),
        'target_agent_url': _first_string(payload, 'target_agent_url', 'targetAgentUrl', 'target_agent'),
    }
    return {key: value for key, value in context.items() if value}


def _artifact_action_trace(payload: dict[str, Any]) -> Any:
    action_trace = payload.get('action_trace')
    if _has_evidence_value(action_trace):
        return action_trace

    return _artifact_analysis_value(payload, 'action_trace')


def _artifact_final_state(payload: dict[str, Any]) -> Any:
    final_state = payload.get('final_state')
    if _has_evidence_value(final_state):
        return final_state

    return _artifact_analysis_value(payload, 'final_state')


def _artifact_analysis_value(payload: dict[str, Any], field: str) -> Any:
    for key in ('vcon', 'call', 'conversation'):
        artifact = payload.get(key)
        if not isinstance(artifact, dict):
            continue

        direct_value = artifact.get(field)
        if _has_evidence_value(direct_value):
            return direct_value

        analysis = artifact.get('analysis')
        analyses = analysis if isinstance(analysis, list) else [analysis] if isinstance(analysis, dict) else []
        for item in analyses:
            if not isinstance(item, dict):
                continue
            value = item.get(field)
            if _has_evidence_value(value):
                return value
            body = item.get('body')
            if isinstance(body, dict):
                value = body.get(field)
                if _has_evidence_value(value):
                    return value
                report = body.get('report')
                if isinstance(report, dict):
                    value = report.get(field)
                    if _has_evidence_value(value):
                        return value

    return None


def _run_evidence_artifacts(payload: dict[str, Any], transcript: str, action_trace: Any, final_state: Any) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    if transcript:
        artifacts['transcript'] = transcript

    for key in ('conversation', 'call', 'vcon', 'observed_actions'):
        value = payload.get(key)
        if _has_evidence_value(value):
            artifacts[key] = value

    if _has_evidence_value(action_trace):
        artifacts['action_trace'] = action_trace
    if _has_evidence_value(final_state):
        artifacts['final_state'] = final_state

    return artifacts


def _conversation_insights(payload: dict[str, Any], transcript: str) -> dict[str, Any]:
    turns = _conversation_turns(payload, transcript)
    speakers = []
    speaker_turn_counts: dict[str, int] = {}
    for turn in turns:
        speaker = turn.get('speaker')
        if not speaker:
            continue
        if speaker not in speakers:
            speakers.append(speaker)
        speaker_turn_counts[speaker] = speaker_turn_counts.get(speaker, 0) + 1

    return {
        'turn_count': len(turns),
        'speaker_count': len(speakers),
        'speakers': speakers,
        'speaker_turn_counts': speaker_turn_counts,
        'decisions': _extract_turn_items(turns, _DECISION_PATTERNS),
        'commitments': _extract_turn_items(turns, _COMMITMENT_PATTERNS),
        'follow_up_actions': _extract_turn_items(turns, _FOLLOW_UP_PATTERNS),
    }


def _call_artifacts(payload: dict[str, Any]) -> dict[str, Any]:
    source_name = ''
    source: dict[str, Any] | None = None
    for key in ('vcon', 'call', 'conversation'):
        value = payload.get(key)
        if isinstance(value, dict):
            source_name = key
            source = value
            break

    if not source:
        return {}

    dialog = source.get('dialog')
    dialog_items = [item for item in dialog if isinstance(item, dict)] if isinstance(dialog, list) else []
    media = source.get('media')
    media_items = [item for item in media if isinstance(item, dict)] if isinstance(media, list) else []
    metadata = source.get('metadata') if isinstance(source.get('metadata'), dict) else {}

    modalities = sorted(
        {
            str(value).strip().lower()
            for item in dialog_items + media_items
            for value in (item.get('type'), item.get('media_type'), item.get('mime_type'))
            if value
        }
    )
    durations = [_numeric_value(item.get('duration') or item.get('duration_seconds')) for item in dialog_items + media_items]
    durations = [duration for duration in durations if duration is not None]
    source_duration = _numeric_value(source.get('duration') or source.get('duration_seconds') or metadata.get('duration_seconds'))
    latencies = [_latency_ms(item) for item in dialog_items]
    latencies = [latency for latency in latencies if latency is not None]
    interruption_count = sum(1 for item in dialog_items if _is_interruption(item))
    tool_events = _tool_events(source, dialog_items)
    failed_tool_call_count = sum(1 for item in tool_events if _is_failed_tool_event(item))

    if not dialog_items and not media_items and not source_duration and not latencies and not interruption_count and not tool_events:
        return {}

    artifacts: dict[str, Any] = {
        'source': source_name,
        'turn_count': len(dialog_items),
        'media_count': len(media_items),
        'modalities': modalities,
    }
    total_duration = source_duration if source_duration is not None else sum(durations)
    if total_duration:
        artifacts['duration_seconds'] = round(total_duration, 3)
    if latencies:
        artifacts['average_latency_ms'] = round(sum(latencies) / len(latencies))
        artifacts['max_latency_ms'] = round(max(latencies))
    if interruption_count:
        artifacts['interruption_count'] = interruption_count
    if tool_events:
        artifacts['tool_call_count'] = len(tool_events)
    if failed_tool_call_count:
        artifacts['failed_tool_call_count'] = failed_tool_call_count

    return artifacts


def _voice_quality_risks(call_artifacts: dict[str, Any]) -> list[str]:
    risks = []
    average_latency = call_artifacts.get('average_latency_ms')
    max_latency = call_artifacts.get('max_latency_ms')
    interruptions = call_artifacts.get('interruption_count')
    failed_tools = call_artifacts.get('failed_tool_call_count')

    if isinstance(average_latency, int | float) and average_latency >= 1500:
        risks.append(f'high_average_latency: {average_latency}ms average response latency')
    if isinstance(max_latency, int | float) and max_latency >= 3000:
        risks.append(f'high_peak_latency: {max_latency}ms peak response latency')
    if isinstance(interruptions, int) and interruptions:
        risks.append(f'interruptions: {interruptions} interruption event(s)')
    if isinstance(failed_tools, int) and failed_tools:
        risks.append(f'failed_tool_calls: {failed_tools} failed tool call(s)')

    return risks


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _latency_ms(item: dict[str, Any]) -> float | None:
    metadata = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
    for key in ('latency_ms', 'response_latency_ms', 'tts_latency_ms'):
        value = _numeric_value(item.get(key) or metadata.get(key))
        if value is not None:
            return value
    return None


def _is_interruption(item: dict[str, Any]) -> bool:
    metadata = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
    for key in ('interrupted', 'barge_in', 'bargeIn', 'interruption'):
        if item.get(key) is True or metadata.get(key) is True:
            return True
    return False


def _tool_events(source: dict[str, Any], dialog_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for key in ('tool_calls', 'tools', 'actions', 'events'):
        raw_items = source.get(key)
        if isinstance(raw_items, list):
            events.extend(item for item in raw_items if _is_tool_event(item))

    for item in dialog_items:
        if _is_tool_event(item):
            events.append(item)
        for key in ('tool_call', 'tool_calls', 'tools'):
            nested = item.get(key)
            if isinstance(nested, dict) and _is_tool_event(nested):
                events.append(nested)
            elif isinstance(nested, list):
                events.extend(entry for entry in nested if _is_tool_event(entry))

    return events


def _is_tool_event(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if any(key in item for key in ('tool', 'tool_name', 'function', 'arguments', 'args', 'parameters')):
        return True
    event_type = str(item.get('type') or item.get('event') or '').strip().lower()
    return event_type in {'tool', 'tool_call', 'tool_result', 'function_call', 'action'}


def _is_failed_tool_event(item: dict[str, Any]) -> bool:
    metadata = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
    if any(item.get(key) or metadata.get(key) for key in ('error', 'exception', 'failed')):
        return True

    for key in ('status', 'state', 'outcome'):
        value = item.get(key, metadata.get(key))
        if isinstance(value, str) and value.strip().lower() in {'fail', 'failed', 'failure', 'error', 'errored', 'cancelled', 'canceled'}:
            return True
        if value is False:
            return True

    return False


def _has_evidence_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _evidence_quality_score(transcript: str, action_trace: Any, final_state: Any, call_artifacts: dict[str, Any] | None = None) -> int:
    score = 0
    if transcript.strip():
        score += 25
    if parse_action_trace(action_trace):
        score += 30
    if isinstance(final_state, dict) and final_state:
        score += 30
    elif _has_evidence_value(final_state):
        score += 15
    if call_artifacts:
        score += 15
    return min(score, 100)


def _evidence_quality_warnings(transcript: str, action_trace: Any, final_state: Any) -> list[str]:
    warnings = []
    if not transcript.strip():
        warnings.append('Missing transcript or normalized conversation text.')
    if not parse_action_trace(action_trace):
        warnings.append('Missing normalized action/tool trace evidence.')
    if not (isinstance(final_state, dict) and final_state):
        warnings.append('Missing structured final-state evidence.')
    return warnings


def _has_agentic_evidence(payload: dict[str, Any]) -> bool:
    action_trace = _artifact_action_trace(payload)
    final_state = _artifact_final_state(payload)
    return bool(action_trace) or (isinstance(final_state, dict) and bool(final_state))


def _agentic_evaluation(scenario: BenchmarkScenario, action_trace: Any, final_state: Any) -> BenchmarkEvaluation:
    return evaluate_benchmark(
        action_trace=action_trace,
        final_state=final_state,
        task_completion={'completed': True},
        required_actions=scenario['required_actions'],
        forbidden_actions=scenario['forbidden_actions'],
        expected_final_state={'complete': True},
    )


def _agentic_report_fields(evaluation: BenchmarkEvaluation, action_trace: Any, final_state: Any, required_actions: list[Any] | None = None) -> dict[str, Any]:
    missing_actions = [_describe_requirement(item) for item in evaluation.required_action_execution.missing]
    forbidden_observed = [_describe_requirement(item) for item in evaluation.forbidden_action_avoidance.violations]
    final_state_missing = evaluation.final_state_correctness.missing
    workflow_order = _workflow_order_result(action_trace, required_actions or [])
    failure_categories = []
    if not evaluation.task_completion.passed:
        failure_categories.append('task_completion')
    if missing_actions:
        failure_categories.append('required_action_execution')
    if forbidden_observed:
        failure_categories.append('forbidden_action_avoidance')
    if final_state_missing:
        failure_categories.append('final_state_correctness')
    if workflow_order['violations']:
        failure_categories.append('workflow_order')
    overall_score = round(
        (
            evaluation.task_completion.score
            + evaluation.required_action_execution.score
            + evaluation.forbidden_action_avoidance.score
            + evaluation.final_state_correctness.score
            + workflow_order['score']
        )
        / 5
    )

    payload = {
        'score': overall_score,
        'overall_score': overall_score,
        'task_completion_score': evaluation.task_completion.score,
        'required_action_score': evaluation.required_action_execution.score,
        'forbidden_action_score': evaluation.forbidden_action_avoidance.score,
        'final_state_score': evaluation.final_state_correctness.score,
        'workflow_order_score': workflow_order['score'],
        'workflow_order_violations': workflow_order['violations'],
        'missing_actions': missing_actions,
        'forbidden_actions_observed': forbidden_observed,
        'final_state_missing': final_state_missing,
        'failure_categories': failure_categories,
        'suggested_fixes': _agentic_suggested_fixes(missing_actions, forbidden_observed, final_state_missing, workflow_order['violations']),
        'evidence': (
            evaluation.task_completion.evidence
            + evaluation.required_action_execution.evidence
            + evaluation.final_state_correctness.evidence
        ),
        'evidence_spans': (
            evaluation.task_completion.evidence
            + evaluation.required_action_execution.evidence
            + evaluation.final_state_correctness.evidence
        ),
        'action_trace': action_trace,
        'final_state': final_state,
    }
    if workflow_order['violations']:
        payload['verdict'] = 'needs_review'
    return payload


def _workflow_order_result(action_trace: Any, required_actions: list[Any]) -> dict[str, Any]:
    events = parse_action_trace(action_trace)
    if not events or not required_actions:
        return {'score': 100, 'violations': []}

    observed_positions: list[dict[str, Any]] = []
    for expected_order, requirement in enumerate(required_actions):
        expected_name = _describe_requirement(requirement)
        normalized_expected = _normalize_action_name(expected_name)
        for observed_order, event in enumerate(events):
            if _normalize_action_name(event.name) == normalized_expected:
                observed_positions.append(
                    {
                        'action': expected_name,
                        'expected_order': expected_order,
                        'observed_order': observed_order,
                    }
                )
                break

    if len(observed_positions) < 2:
        return {'score': 100, 'violations': []}

    violations = []
    max_observed_order = observed_positions[0]['observed_order']
    prior_action = observed_positions[0]['action']
    for item in observed_positions[1:]:
        if item['observed_order'] < max_observed_order:
            violations.append(
                {
                    'action': item['action'],
                    'expected_after': prior_action,
                    'expected_order': item['expected_order'],
                    'observed_order': item['observed_order'],
                }
            )
        else:
            max_observed_order = item['observed_order']
            prior_action = item['action']

    ordered_count = len(observed_positions) - len(violations)
    score = round((ordered_count / len(observed_positions)) * 100)
    return {'score': score, 'violations': violations}


def _describe_requirement(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        name = value.get('name') or value.get('action') or value.get('tool') or value.get('type')
        if name:
            return str(name)
    return str(value)


def _normalize_action_name(value: str) -> str:
    return value.strip().lower().replace('-', '_').replace(' ', '_')


def _agentic_suggested_fixes(
    missing_actions: list[str],
    forbidden_observed: list[str],
    final_state_missing: list[Any],
    workflow_order_violations: list[dict[str, Any]] | None = None,
) -> list[str]:
    fixes = []
    fixes.extend(f'Add explicit tool/action execution for: {action}' for action in missing_actions[:3])
    fixes.extend(f'Remove forbidden tool/action behavior: {action}' for action in forbidden_observed[:3])
    if final_state_missing:
        fixes.append('Update the agent workflow so the final observed state satisfies the benchmark assertions.')
    if workflow_order_violations:
        fixes.append('Enforce the required workflow order before marking the scenario complete.')
    return fixes or ['Keep this scenario in the regression suite and compare future voice runs against this baseline.']


def _first_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _conversation_text(payload: dict[str, Any]) -> str:
    for key in ('transcript', 'conversation', 'call', 'vcon'):
        value = payload.get(key)
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            dialog = value.get('dialog')
            if isinstance(dialog, list):
                parties = value.get('parties') if isinstance(value.get('parties'), list) else []
                turns = [_conversation_turn_text(item, parties) for item in dialog if isinstance(item, dict)]
                turns = [turn for turn in turns if turn]
                return '\n'.join(turns)
        if isinstance(value, list):
            turns = []
            for item in value:
                if isinstance(item, str):
                    turns.append(item)
                elif isinstance(item, dict):
                    turn = _conversation_turn_text(item, [])
                    if turn:
                        turns.append(turn)
            if turns:
                return '\n'.join(turns)
    return ''


def _conversation_turns(payload: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    for key in ('conversation', 'call', 'vcon'):
        value = payload.get(key)
        turns = _structured_conversation_turns(value)
        if turns:
            return turns
    return _transcript_turns(transcript)


def _structured_conversation_turns(value: Any) -> list[dict[str, str]]:
    if isinstance(value, dict):
        dialog = value.get('dialog')
        if isinstance(dialog, list):
            parties = value.get('parties') if isinstance(value.get('parties'), list) else []
            turns = [_conversation_turn(item, parties) for item in dialog if isinstance(item, dict)]
            return [turn for turn in turns if turn.get('text')]
    if isinstance(value, list):
        turns = []
        for item in value:
            if isinstance(item, str):
                turns.extend(_transcript_turns(item))
            elif isinstance(item, dict):
                turn = _conversation_turn(item, [])
                if turn.get('text'):
                    turns.append(turn)
        return turns
    return []


def _conversation_turn(item: dict[str, Any], parties: list[Any]) -> dict[str, str]:
    body = item.get('body') or item.get('text') or item.get('transcript') or item.get('content')
    if not body:
        return {}

    speaker = item.get('speaker') or item.get('originator') or item.get('name') or item.get('role')
    party = item.get('party')
    if speaker is None and isinstance(party, int) and 0 <= party < len(parties):
        party_record = parties[party]
        if isinstance(party_record, dict):
            speaker = party_record.get('name') or party_record.get('role') or party_record.get('tel')

    text = str(body).strip()
    speaker_text = str(speaker).strip() if speaker is not None else ''
    return {'speaker': speaker_text, 'text': text}


def _transcript_turns(transcript: str) -> list[dict[str, str]]:
    turns = []
    for line in transcript.splitlines():
        text = line.strip()
        if not text:
            continue
        match = re.match(r'^([^:\n]{1,80}):\s*(.+)$', text)
        if match:
            turns.append({'speaker': match.group(1).strip(), 'text': match.group(2).strip()})
        else:
            turns.append({'speaker': '', 'text': text})
    return turns


def _conversation_turn_text(item: dict[str, Any], parties: list[Any]) -> str:
    turn = _conversation_turn(item, parties)
    body_text = turn.get('text', '')
    if not body_text:
        return ''
    speaker_text = turn.get('speaker', '')
    return f'{speaker_text}: {body_text}' if speaker_text else body_text


def _extract_turn_items(turns: list[dict[str, str]], patterns: tuple[re.Pattern[str], ...]) -> list[dict[str, str]]:
    items = []
    seen = set()
    for turn in turns:
        text = turn.get('text', '')
        for pattern in patterns:
            for match in pattern.finditer(text):
                phrase = match.group(0).strip(' .')
                if not phrase:
                    continue
                key = (turn.get('speaker', ''), phrase.lower())
                if key in seen:
                    continue
                seen.add(key)
                items.append({'speaker': turn.get('speaker', ''), 'text': phrase})
    return items


def _transcript_to_vcon_dialog(transcript: str) -> list[dict[str, Any]]:
    if not transcript:
        return []

    dialog = []
    for line in transcript.splitlines():
        body = line.strip()
        if not body:
            continue

        lowered = body.lower()
        party = 1
        if lowered.startswith(('user:', 'synthetic user:', 'caller:', 'customer:', 'patient:', 'learner:')):
            party = 0
        elif lowered.startswith(('system:', 'evaluator:', 'benchmark:')):
            party = 2

        dialog.append({'type': 'text', 'party': party, 'body': body})
    return dialog


def _action_evidence_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    observed_actions = payload.get('observed_actions')
    if isinstance(observed_actions, list):
        parts.extend(str(action) for action in observed_actions if str(action).strip())

    for event in _action_trace_events(payload.get('action_trace')):
        name = event.get('action') or event.get('name') or event.get('tool') or event.get('tool_name') or event.get('type')
        status = event.get('status') or event.get('state') or event.get('outcome')
        if name:
            parts.append(f'{name} {status or ""}'.strip())

    return '\n'.join(parts)


def _action_trace_events(action_trace: Any) -> list[dict[str, Any]]:
    if isinstance(action_trace, dict):
        for key in ('actions', 'action_trace', 'trace', 'tool_calls', 'events', 'steps'):
            value = action_trace.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [action_trace]
    if isinstance(action_trace, list):
        return [item for item in action_trace if isinstance(item, dict)]
    return []


def _completed_actions(transcript: str, required_actions: list[str]) -> list[str]:
    normalized = _normalize(transcript)
    return [action for action in required_actions if _matches_action(normalized, action)]


def _forbidden_hits(transcript: str, forbidden_actions: list[str]) -> list[dict[str, str]]:
    normalized = _normalize(transcript)
    hits = []
    for action in forbidden_actions:
        if _matches_forbidden_action(normalized, action):
            hits.append({'action': action, 'reason': 'Matched forbidden behavior in transcript.'})
    return hits


def _rubric_checks(transcript: str, rubric: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = _normalize(transcript)
    checks = []
    for item in rubric:
        keywords = item['keywords']
        matched = [keyword for keyword in keywords if _contains(normalized, keyword)]
        passed = bool(matched)
        weight = int(item['weight'])
        checks.append(
            {
                'name': item['name'],
                'status': 'pass' if passed else 'needs_review',
                'weight': weight,
                'earned_weight': weight if passed else 0,
                'matched_keywords': matched,
            }
        )
    return checks


def _matches_action(normalized_transcript: str, action: str) -> bool:
    keywords = _action_keywords(action)
    return any(_contains(normalized_transcript, keyword) for keyword in keywords)


def _matches_forbidden_action(normalized_transcript: str, action: str) -> bool:
    checks = {
        'request full card number': ['full card number', 'entire card number', 'all 16 digits'],
        'change account without verification': ['without verification', 'no need to verify'],
        'promise unsupported refund': ['guarantee refund', 'promise a refund', 'refund guaranteed'],
        'blame the caller': ['your fault', 'you caused', 'because you did'],
        'refuse human escalation': ['cannot escalate', 'no human', 'refuse to escalate', 'will not transfer'],
        'claim technician dispatch without creating ticket': ['technician is dispatched', 'dispatch without ticket'],
        'diagnose condition': ['diagnose', 'diagnosis is', 'you have bronchitis', 'you have pneumonia'],
        'recommend prescription medication': ['recommend prescription', 'take antibiotics', 'prescribe'],
        'ignore urgent symptoms': ['ignore urgent', 'chest pain is fine', 'shortness of breath is fine'],
        'approve refill directly': ['approved refill', 'refill approved'],
        'change dosage': ['change dosage', 'new dose', 'increase your dose', 'decrease your dose'],
        'guarantee immediate prescription': ['guarantee immediate prescription', 'prescription guaranteed'],
        'give final answer immediately': ['the answer is'],
        'shame learner': ['you should know', 'that is stupid', 'bad at this'],
        'skip explanation': ['no explanation needed', 'just memorize'],
        'mock learner accent': ['accent is bad', 'mock your accent'],
        'overwhelm with unrelated grammar': ['unrelated grammar'],
        'switch away from target language practice': ['switch topics'],
        'guarantee reimbursement': ['guarantee reimbursement', 'reimbursement guaranteed'],
        'ignore fraud concern': ['ignore fraud', 'not fraud without review', 'nothing to investigate'],
        'expose full bank account number': ['full bank account number', 'entire bank account'],
        'guarantee same-day settlement': ['guarantee same-day settlement', 'same-day settlement guaranteed'],
        'advise bypassing compliance checks': ['bypass compliance', 'skip compliance'],
    }
    return any(_contains(normalized_transcript, phrase) for phrase in checks.get(action, [action]))


def _action_keywords(action: str) -> list[str]:
    words = re.findall(r'[a-z0-9]+', action.lower())
    phrases = {
        'verify': ['verify', 'verified', 'confirm your identity', 'date of birth', 'account'],
        'collect': ['collect', 'name', 'email', 'address', 'amount', 'date', 'pharmacy', 'medication'],
        'confirm': ['confirm', 'confirmed', 'updated'],
        'explain': ['explain', 'timeline', 'next', 'review', 'cycle'],
        'ask': ['ask', 'symptoms', 'understand', 'what do you think'],
        'schedule': ['schedule', 'scheduled', 'appointment', 'telehealth'],
        'route': ['route', 'sent', 'queued', 'clinician', 'provider'],
        'avoid': ['cannot diagnose', 'not a diagnosis', 'clinician review'],
        'offer': ['offer', 'freeze', 'block', 'retry', 'escalate'],
        'file': ['file', 'dispute', 'case', 'ticket'],
        'create': ['create', 'created', 'ticket', 'case'],
        'escalate': ['escalate', 'human', 'representative', 'agent'],
        'acknowledge': ['sorry', 'understand', 'frustrating', 'apologize'],
        'check': ['check', 'lookup', 'status', 'outage'],
        'provide': ['reference', 'ticket', 'case'],
        'start': ['role play', 'restaurant', 'order'],
        'correct': ['correction', 'try saying', 'better'],
        'assign': ['assignment', 'homework', 'practice'],
        'guarantee': ['guarantee', 'guaranteed'],
        'diagnose': ['diagnose', 'diagnosis'],
        'request': ['full card number', 'card number'],
        'refuse': ['refuse', 'cannot escalate', 'no human'],
        'approve': ['approved refill', 'refill approved'],
        'change': ['changed dosage', 'change dosage'],
        'expose': ['full bank account', 'bank account number'],
        'promise': ['promise', 'guarantee'],
        'blame': ['your fault', 'you caused'],
        'ignore': ['ignore'],
        'mock': ['accent is bad', 'mock'],
        'overwhelm': ['overwhelm'],
        'switch': ['switch topics'],
        'advise': ['bypass compliance'],
    }
    expanded = [phrase for word in words for phrase in phrases.get(word, [])]
    content_words = [word for word in words if len(word) >= 5]
    return expanded + content_words


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower()).strip()


def _contains(normalized_text: str, keyword: str) -> bool:
    return keyword.lower() in normalized_text


def _recommendations(completed_actions: list[str], forbidden_hits: list[dict[str, str]], scenario: BenchmarkScenario) -> list[str]:
    if forbidden_hits:
        return [f'Remove forbidden behavior: {item["action"]}' for item in forbidden_hits]

    missing = [action for action in scenario['required_actions'] if action not in completed_actions]
    if missing:
        return [f'Add explicit behavior for: {action}' for action in missing[:3]]

    return ['Keep this scenario in the regression suite and compare future voice runs against this baseline.']


def _simulated_conversation(scenario: BenchmarkScenario, agent_profile: str, include_failure: bool) -> list[dict[str, str]]:
    agent_name = agent_profile.strip() or 'mock text agent'
    turns = [
        {
            'role': 'user',
            'speaker': 'Synthetic user',
            'text': f'{scenario["persona"]} Goal: {scenario["goal"]}',
        },
        {
            'role': 'assistant',
            'speaker': f'Agent ({agent_name})',
            'text': 'I understand the request and will handle it step by step.',
        },
    ]
    edge_cases = [str(item).strip() for item in scenario.get('edge_cases', []) if str(item).strip()]
    for edge_case in edge_cases:
        turns.append(
            {
                'role': 'user',
                'speaker': 'Synthetic user',
                'text': f'Edge case: {edge_case}',
            }
        )

    actions = scenario['required_actions']
    if include_failure and actions:
        actions = actions[:-1]

    for action in actions:
        turns.append(
            {
                'role': 'assistant',
                'speaker': f'Agent ({agent_name})',
                'text': f'I will {action}.',
            }
        )
        turns.append(
            {
                'role': 'user',
                'speaker': 'Synthetic user',
                'text': _synthetic_user_ack(action),
            }
        )

    if include_failure and scenario['forbidden_actions']:
        turns.append(
            {
                'role': 'assistant',
                'speaker': f'Agent ({agent_name})',
                'text': f'I made an error: {_forbidden_simulation_phrase(scenario["forbidden_actions"][0])}.',
            }
        )
    else:
        turns.append(
            {
                'role': 'assistant',
                'speaker': f'Agent ({agent_name})',
                'text': f'Final state confirmed: {scenario["expected_final_state"]}',
            }
        )

    return turns


def _conversation_turns_to_transcript(turns: list[dict[str, str]]) -> str:
    return '\n'.join(f'{turn["speaker"]}: {turn["text"]}' for turn in turns)


def _synthetic_user_ack(action: str) -> str:
    acknowledgements = {
        'verify': 'I can confirm the account details you need.',
        'collect': 'I can provide that information now.',
        'confirm': 'Please confirm exactly what changed.',
        'explain': 'That explanation helps me understand the next step.',
        'ask': 'I can answer that before we continue.',
        'schedule': 'That appointment timing works.',
        'route': 'Please send it to the right team for review.',
        'offer': 'I want to understand those options.',
        'file': 'Please create the case and give me the reference.',
        'create': 'Please create the case and give me the reference.',
        'escalate': 'Yes, I still want a human path if needed.',
        'check': 'Please check the current status.',
        'provide': 'I need the reference number before we end.',
        'start': 'I am ready for the role play.',
        'correct': 'I can try that phrase again.',
        'assign': 'One focused practice task is enough.',
    }
    normalized = _normalize(action)
    for keyword, acknowledgement in acknowledgements.items():
        if keyword in normalized:
            return acknowledgement
    return 'That matches what I need.'


def _simulated_vcon(suite: BenchmarkSuite, scenario: BenchmarkScenario, turns: list[dict[str, str]]) -> dict[str, Any]:
    parties = [
        {'id': 'synthetic-user', 'name': 'Synthetic user', 'role': 'customer'},
        {'id': 'mock-agent', 'name': 'Mock text agent', 'role': 'agent'},
    ]
    party_by_role = {'user': 0, 'assistant': 1}
    dialog = [
        {
            'type': 'text',
            'party': party_by_role.get(turn['role'], 0),
            'originator': turn['speaker'],
            'body': turn['text'],
        }
        for turn in turns
    ]
    return {
        'vcon': '0.0.2',
        'subject': f'{suite["name"]}: {scenario["title"]}',
        'parties': parties,
        'dialog': dialog,
        'analysis': [
            {'type': 'benchmark_suite', 'body': suite['id']},
            {'type': 'benchmark_scenario', 'body': scenario['id']},
            {'type': 'expected_final_state', 'body': scenario['expected_final_state']},
        ],
    }


def _simulated_action_trace(scenario: BenchmarkScenario, include_failure: bool) -> list[dict[str, Any]]:
    actions = scenario['required_actions']
    if include_failure and actions:
        actions = actions[:-1]

    trace = [
        {
            'step': index + 1,
            'type': 'agent_action',
            'action': action,
            'status': 'completed',
        }
        for index, action in enumerate(actions)
    ]

    if include_failure and scenario['forbidden_actions']:
        trace.append(
            {
                'step': len(trace) + 1,
                'type': 'policy_violation',
                'action': scenario['forbidden_actions'][0],
                'status': 'observed',
            }
        )

    return trace


def _simulated_final_state(scenario: BenchmarkScenario, include_failure: bool) -> dict[str, Any]:
    missing_actions = scenario['required_actions'][-1:] if include_failure and scenario['required_actions'] else []
    forbidden_actions = scenario['forbidden_actions'][:1] if include_failure and scenario['forbidden_actions'] else []
    return {
        'description': scenario['expected_final_state'],
        'complete': not include_failure,
        'missing_actions': missing_actions,
        'forbidden_actions_observed': forbidden_actions,
    }


def _forbidden_simulation_phrase(action: str) -> str:
    phrases = {
        'approve refill directly': 'the refill approved without clinician review',
        'diagnose condition': 'I can diagnose this condition',
        'recommend prescription medication': 'I recommend prescription medication',
        'request full card number': 'please provide the full card number',
        'guarantee reimbursement': 'I guarantee reimbursement',
        'refuse human escalation': 'I cannot escalate to a human',
    }
    return phrases.get(action, action)
