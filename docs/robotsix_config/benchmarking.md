# Performance benchmarking

`robotsix-config` ships a small suite of performance benchmarks built on
[`pytest-benchmark`](https://pytest-benchmark.readthedocs.io/). They measure the
cost of the hot public API paths — config loading, dumping, and JSON Schema
generation — so that performance regressions can be caught deliberately rather
than by accident.

This page covers:

- [Running benchmarks locally](#running-benchmarks-locally)
- [Interpreting and evaluating results](#interpreting-and-evaluating-results)
- [Updating performance baselines](#updating-performance-baselines)
- [Adding new benchmarks](#adding-new-benchmarks)
- [How CI treats benchmarks](#how-ci-treats-benchmarks)

## Running benchmarks locally

Benchmarks live in `tests/test_perf_*.py` and are collected like any other
test. They are **disabled by default** so ordinary test runs stay fast: the
root `conftest.py` flips `pytest-benchmark`'s own `benchmark_disable` option on
whenever the plugin is installed and you have not passed `--benchmark-enable`.
When the plugin is *not* installed, the benchmark modules skip themselves via a
top-level `pytest.importorskip("pytest_benchmark")`.

First install the dev dependencies (which include `pytest-benchmark`):

```sh
uv sync --extra dev
```

Then enable and run the benchmarks:

```sh
uv run pytest --benchmark-enable tests/test_perf_*.py
```

!!! note "Benchmarks require the `dev` extra"
    `pytest-benchmark` is an optional dev dependency, so it is not present in a
    plain install. Without it, `tests/test_perf_*.py` skip rather than fail, and
    `--benchmark-enable` is rejected as an unknown flag. Always run benchmarks
    from an environment synced with `--extra dev`.

Useful flags when running locally:

- `--benchmark-only` — run *only* the benchmark tests, skipping the rest of the
  suite.
- `--benchmark-group-by=group` — group results by the benchmark group name
  (loading, dumping, schema generation) rather than by test id.
- `--benchmark-columns=min,median,mean,stddev,iqr` — control which statistics
  are printed.
- `--benchmark-sort=mean` — sort the results table by a chosen column.
- `-k <expr>` — run a subset, e.g. `-k load_config`.

Disable parallelism when benchmarking. `pytest-xdist` (`-n auto`) distributes
tests across workers, which adds scheduling noise and makes timings
unreproducible. Run benchmarks single-process.

## Interpreting and evaluating results

A benchmark run prints a table similar to:

```
------------------------------------------- benchmark: load_config -------------------------------------------
Name (time in us)              Min        Max       Mean    StdDev     Median       IQR   Outliers  Rounds
--------------------------------------------------------------------------------------------------------------
test_load_config[1]        10.1234    15.6789    10.9876    0.5432    10.8765    0.3210        5;12   48000
test_load_config[10]       42.3456    55.1234    44.1234    1.2345    43.9876    0.9876        8;20   12000
test_load_config[100]     410.123    480.456    420.789   10.1234   418.456     7.6543       12;30    2000
--------------------------------------------------------------------------------------------------------------
```

How to read it:

- **Median** is the most robust single-number summary — prefer it over the mean,
  which outliers skew. The **min** approximates the best achievable time with no
  interference, and is the most stable number across machines.
- **StdDev** / **IQR** measure spread. Large spread relative to the median means
  the run was noisy (background load, thermal throttling) and the numbers should
  not be trusted for comparison — re-run on a quiet machine.
- **Outliers** (`a;b`) counts samples outside 1 and 1.5 IQRs. A high outlier
  count is another noise signal.
- **Rounds** is how many calibrated iterations ran; `pytest-benchmark` picks this
  automatically to reach a stable estimate.

Scaling matters more than absolute numbers. The benchmarks are parametrized over
input sizes (1, 10, 100). Watch that time scales the way the algorithm should
(roughly linearly here) — a size-100 case that is >>10× the size-10 case points
to accidental quadratic behaviour.

**Absolute timings are machine-specific.** Numbers from your laptop are not
comparable to numbers from a CI runner or a colleague's machine. Only compare
runs taken on the *same* machine under the *same* conditions (see baselines
below).

## Updating performance baselines

`pytest-benchmark` can save a run and compare later runs against it. This is how
you evaluate a change for regressions and how you intentionally move the
baseline when a performance change is expected and accepted.

Save a baseline from a known-good checkout:

```sh
uv run pytest --benchmark-enable --benchmark-only \
  --benchmark-save=baseline tests/test_perf_*.py
```

Saved runs are stored under `.benchmarks/` (keyed by machine and Python
version). `.benchmarks/` is a local, machine-specific artifact — it is **not**
committed to the repository.

Compare your working changes against the saved baseline and fail the run if any
benchmark regresses beyond a threshold:

```sh
uv run pytest --benchmark-enable --benchmark-only \
  --benchmark-compare=baseline \
  --benchmark-compare-fail=median:10% tests/test_perf_*.py
```

`--benchmark-compare-fail=median:10%` fails if the median is more than 10%
slower than the baseline. Use `mean:…` or an absolute value (`min:5us`) as
appropriate.

**When to intentionally update a baseline:**

- A deliberate change makes an operation slower but is accepted for other
  reasons (correctness, a new feature, better defaults). Record the new,
  expected timings as the baseline so future comparisons start from reality.
- A deliberate optimization makes an operation faster — re-baseline so the gain
  is locked in and any later regression is measured against the improved number.
- You move to new hardware or a new Python version — old baselines are no longer
  comparable.

Do **not** re-baseline to silence an *unexplained* regression. First understand
why the number moved; only update the baseline once the change is understood and
intended.

To refresh a baseline, re-run the `--benchmark-save` command above on the
accepted checkout, under quiet conditions, and note in your PR/commit why the
baseline moved (e.g. the expected cost of a new validation step).

## Adding new benchmarks

Benchmarks are ordinary pytest tests that take the `benchmark` fixture. Follow
the existing conventions in `tests/test_perf_load.py`:

1. **Name the module `tests/test_perf_*.py`.** This is the glob the project uses
   to identify benchmarks; the default-disable logic and docs assume it.

2. **Guard the import.** Because `pytest-benchmark` is an optional dev
   dependency, put a top-level `pytest.importorskip` at the top of the module so
   it skips cleanly when the plugin is absent (this also avoids breaking
   collection):

   ```python
   import pytest

   pytest.importorskip("pytest_benchmark")
   ```

   Ruff does not flag `E402` for imports placed after a top-level
   `pytest.importorskip(...)`, so no `# noqa` is needed.

3. **Benchmark one operation per test.** Pass the callable (and its args) to the
   `benchmark` fixture so the fixture controls iteration and calibration:

   ```python
   def test_dump_config_benchmark(benchmark, tmp_path):
       benchmark(dump_config, SampleConfig(), tmp_path / "config.toml")
   ```

   Do not call the operation yourself and wrap timing manually — let the fixture
   do it.

4. **Keep setup out of the measured region.** Build models, paths, and fixtures
   *before* calling `benchmark(...)`. Only the operation under test should be
   inside it. For per-round setup use `benchmark.pedantic(...)` with a `setup`
   callable.

5. **Group related benchmarks** with `@pytest.mark.benchmark(group=...)` (or the
   `benchmark.group` convention already used) so the results table groups
   loading, dumping, and schema generation sensibly.

6. **Parametrize over input size** (e.g. `@pytest.mark.parametrize("size", [1,
   10, 100])`) when the operation's cost depends on input size, so scaling is
   visible.

7. **Only benchmark public API.** Measure the exported surface
   (`load_config`, `dump_config`, `config_schema_json`, …) so the benchmarks
   track what consumers actually pay for.

After adding a benchmark, verify it runs with
`uv run pytest --benchmark-enable tests/test_perf_your_module.py` and confirm it
still *skips* (not errors) under a plain `uv run pytest`.

## How CI treats benchmarks

Benchmarks are a **developer-run tool**, not a CI gate. CI installs the `dev`
extra (so `pytest-benchmark` is present), but it never passes
`--benchmark-enable`, so the conditional default in `conftest.py` keeps
benchmarks **disabled** on every CI job. CI therefore collects the
`tests/test_perf_*.py` modules but does not time them, keeping test runs fast
and deterministic.

There is intentionally **no automated performance-comparison job** in CI:
benchmark timings depend heavily on the runner hardware, which varies between
jobs and is far noisier than a developer's quiet local machine, so a CI
threshold would produce false regressions. Performance evaluation is instead
done locally with the save/compare workflow described in
[Updating performance baselines](#updating-performance-baselines).

If you suspect a change affects performance, run the benchmarks locally against a
saved baseline before and after your change, and include the comparison in your
pull request description so reviewers can see the measured impact.
