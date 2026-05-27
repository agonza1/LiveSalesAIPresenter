from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.benchmarks import BenchmarkRerunRequest, BenchmarkRunRequest, BenchmarkSimulationRequest, BenchmarkSuiteSimulationRequest
from app.services.benchmark_service import (
    compare_latest_benchmark_runs,
    export_benchmark_runs_csv,
    export_benchmark_runs_jsonl,
    export_benchmark_runs_junit,
    export_benchmark_runs_markdown,
    export_benchmark_runs_sarif,
    get_benchmark_run,
    get_benchmark_run_jsonl,
    get_benchmark_run_junit,
    get_benchmark_run_markdown,
    get_benchmark_run_sarif,
    get_benchmark_run_vcon,
    get_scenario_contract,
    get_suite,
    get_suite_contract,
    list_benchmark_runs,
    list_scenarios,
    list_suites,
    rerun_benchmark_run,
    run_scenario,
    save_benchmark_run,
    simulate_suite,
    simulate_scenario,
    summarize_benchmark_suite_runs,
    summarize_benchmark_runs,
)

router = APIRouter(prefix='/api/benchmarks', tags=['benchmarks'])


@router.get('')
@router.get('/suites')
def list_benchmark_suites():
    return [get_suite(suite['id']) for suite in list_suites()]


@router.get('/runs')
def list_runs(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    return {
        'runs': runs,
        'summary': summarize_benchmark_runs(runs),
        'comparison': compare_latest_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context),
    }


@router.get('/runs.csv')
def export_runs_csv(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    csv_body = export_benchmark_runs_csv(runs)
    return Response(
        content=csv_body,
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="benchmark-runs.csv"'},
    )


@router.get('/runs.junit')
@router.get('/runs.junit.xml')
def export_runs_junit(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    junit_xml = export_benchmark_runs_junit(runs)
    return Response(
        content=junit_xml,
        media_type='application/xml',
        headers={'Content-Disposition': 'attachment; filename="benchmark-runs.junit.xml"'},
    )


@router.get('/runs.jsonl')
def export_runs_jsonl(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    jsonl_body = export_benchmark_runs_jsonl(runs)
    return Response(
        content=jsonl_body,
        media_type='application/x-ndjson',
        headers={'Content-Disposition': 'attachment; filename="benchmark-runs.jsonl"'},
    )


@router.get('/runs.sarif')
@router.get('/runs.sarif.json')
def export_runs_sarif(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    return export_benchmark_runs_sarif(runs)


@router.get('/runs.md')
def export_runs_markdown(
    suite_id: str | None = None,
    scenario_id: str | None = None,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    runs = list_benchmark_runs(db, suite_id=suite_id, scenario_id=scenario_id, run_context=run_context, limit=limit)
    markdown = export_benchmark_runs_markdown(runs)
    return Response(
        content=markdown,
        media_type='text/markdown; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="benchmark-runs.md"'},
    )


@router.get('/runs/{run_id}')
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = get_benchmark_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return run


@router.get('/runs/{run_id}/vcon')
def get_run_vcon(run_id: str, db: Session = Depends(get_db)):
    vcon = get_benchmark_run_vcon(db, run_id)
    if vcon is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return vcon


@router.get('/runs/{run_id}/junit')
def get_run_junit(run_id: str, db: Session = Depends(get_db)):
    junit_xml = get_benchmark_run_junit(db, run_id)
    if junit_xml is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return Response(content=junit_xml, media_type='application/xml')


@router.get('/runs/{run_id}/jsonl')
def get_run_jsonl(run_id: str, db: Session = Depends(get_db)):
    jsonl = get_benchmark_run_jsonl(db, run_id)
    if jsonl is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return Response(content=jsonl, media_type='application/x-ndjson')


@router.get('/runs/{run_id}/sarif')
@router.get('/runs/{run_id}/sarif.json')
def get_run_sarif(run_id: str, db: Session = Depends(get_db)):
    sarif = get_benchmark_run_sarif(db, run_id)
    if sarif is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return sarif


@router.get('/runs/{run_id}/markdown')
def get_run_markdown(run_id: str, db: Session = Depends(get_db)):
    markdown = get_benchmark_run_markdown(db, run_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    return Response(content=markdown, media_type='text/markdown; charset=utf-8')


@router.post('/runs/{run_id}/rerun')
def rerun_saved_run(run_id: str, payload: BenchmarkRerunRequest | None = None, db: Session = Depends(get_db)):
    report = rerun_benchmark_run(db, run_id, payload)
    if report is None:
        raise HTTPException(status_code=404, detail='Benchmark run not found.')
    save_benchmark_run(db, report, report.get('evidence_artifacts'))
    return report


@router.get('/suites/{suite_id}/runs')
def get_suite_runs(
    suite_id: str,
    agent_version: str | None = None,
    prompt_version: str | None = None,
    model_name: str | None = None,
    target_agent_url: str | None = None,
    per_scenario_limit: int = 5,
    db: Session = Depends(get_db),
):
    run_context = {
        key: value
        for key, value in {
            'agent_version': agent_version,
            'prompt_version': prompt_version,
            'model_name': model_name,
            'target_agent_url': target_agent_url,
        }.items()
        if value
    }
    summary = summarize_benchmark_suite_runs(
        db,
        suite_id=suite_id,
        run_context=run_context,
        per_scenario_limit=per_scenario_limit,
    )
    if summary is None:
        raise HTTPException(status_code=404, detail='Benchmark suite not found.')
    return summary


@router.get('/{suite_id}')
@router.get('/suites/{suite_id}')
def get_benchmark_suite(suite_id: str):
    suite = get_suite(suite_id)
    if suite is None:
        raise HTTPException(status_code=404, detail='Benchmark suite not found.')
    return suite


@router.get('/{suite_id}/contract')
@router.get('/suites/{suite_id}/contract')
def get_benchmark_suite_contract(suite_id: str):
    contract = get_suite_contract(suite_id)
    if contract is None:
        raise HTTPException(status_code=404, detail='Benchmark suite not found.')
    return contract


@router.get('/{suite_id}/scenarios')
@router.get('/suites/{suite_id}/scenarios')
def list_benchmark_scenarios(suite_id: str):
    scenarios = list_scenarios(suite_id)
    if scenarios is None:
        raise HTTPException(status_code=404, detail='Benchmark suite not found.')
    return {'suite_id': suite_id, 'scenarios': scenarios}


@router.get('/{suite_id}/scenarios/{scenario_id}/contract')
@router.get('/suites/{suite_id}/scenarios/{scenario_id}/contract')
def get_benchmark_scenario_contract(suite_id: str, scenario_id: str):
    contract = get_scenario_contract(suite_id, scenario_id)
    if contract is None:
        raise HTTPException(status_code=404, detail='Benchmark scenario not found.')
    return contract


@router.post('/run')
def run_benchmark(payload: BenchmarkRunRequest, db: Session = Depends(get_db)):
    try:
        report = run_scenario(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    save_benchmark_run(db, report, report.get('evidence_artifacts'))
    return report


@router.post('/simulate')
def simulate_benchmark(payload: BenchmarkSimulationRequest, db: Session = Depends(get_db)):
    try:
        simulation = simulate_scenario(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    save_benchmark_run(db, simulation['benchmark_report'], simulation['benchmark_report'].get('evidence_artifacts'))
    return simulation


@router.post('/suites/simulate')
def simulate_benchmark_suite(payload: BenchmarkSuiteSimulationRequest, db: Session = Depends(get_db)):
    try:
        suite_run = simulate_suite(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    for simulation in suite_run['simulations']:
        report = simulation['benchmark_report']
        save_benchmark_run(db, report, report.get('evidence_artifacts'))
    return suite_run


@router.post('/suites/{suite_id}/simulate')
def simulate_benchmark_suite_by_id(suite_id: str, payload: BenchmarkSuiteSimulationRequest, db: Session = Depends(get_db)):
    merged_payload = payload.model_dump()
    merged_payload['suite_id'] = suite_id
    try:
        suite_run = simulate_suite(merged_payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    for simulation in suite_run['simulations']:
        report = simulation['benchmark_report']
        save_benchmark_run(db, report, report.get('evidence_artifacts'))
    return suite_run


@router.post('/{suite_id}/scenarios/{scenario_id}/run')
def run_benchmark_scenario(suite_id: str, scenario_id: str, payload: BenchmarkRunRequest, db: Session = Depends(get_db)):
    merged_payload = payload.model_dump()
    merged_payload['suite_id'] = suite_id
    merged_payload['scenario_id'] = scenario_id
    try:
        report = run_scenario(merged_payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    save_benchmark_run(db, report, report.get('evidence_artifacts'))
    return report


@router.post('/{suite_id}/scenarios/{scenario_id}/simulate')
def simulate_benchmark_scenario(suite_id: str, scenario_id: str, payload: BenchmarkSimulationRequest, db: Session = Depends(get_db)):
    merged_payload = payload.model_dump()
    merged_payload['suite_id'] = suite_id
    merged_payload['scenario_id'] = scenario_id
    try:
        simulation = simulate_scenario(merged_payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    save_benchmark_run(db, simulation['benchmark_report'], simulation['benchmark_report'].get('evidence_artifacts'))
    return simulation
