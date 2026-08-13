from app.scripts.pipeline_benchmark import run_benchmark


def test_pipeline_benchmark_emits_machine_readable_reports(tmp_path):
    report = run_benchmark(1, tmp_path)
    assert report["runs"] == 2
    assert report["successful_runs"] == 2
    assert report["failure_rate"] == 0
    assert (tmp_path / "pipeline_benchmark.json").is_file()
    assert (tmp_path / "pipeline_benchmark.csv").is_file()
