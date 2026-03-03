# Testing Patterns

**Analysis Date:** 2025-03-02

## Test Framework

**Runner:**
- pytest (version not pinned in pyproject.toml, but >6.0 implied by fixtures)
- Config: No pytest.ini or setup.cfg found — uses defaults

**Assertion Library:**
- pandas.testing.assert_series_equal() for Series comparison
- numpy.testing.assert_allclose() for numerical arrays
- Standard assert statements for booleans and counts

**Run Commands:**
```bash
python -m pytest python_pipeline/tests/ -v              # Run all tests
python -m pytest python_pipeline/tests/ -k test_name    # Run specific test
python -m pytest python_pipeline/tests/ --tb=short      # Shorter traceback
python -m pytest python_pipeline/tests/ -x              # Stop on first failure
```

Note: 54 tests pass without pymer4 installed (unit tests only, no integration tests requiring R).

## Test File Organization

**Location:**
- Co-located in `python_pipeline/tests/` subdirectory
- Pattern: `test_*.py` for each major module

**Files:**
- `python_pipeline/tests/test_domains.py` — Domain assignment logic
- `python_pipeline/tests/test_preprocessing.py` — Data loading, transformations
- `python_pipeline/tests/test_corrections.py` — Statistical corrections
- `python_pipeline/tests/__init__.py` — Empty marker file

**Naming:**
- Module: `test_{feature}.py`
- Classes: `Test{FeatureName}` (e.g., `TestAssignDomain`, `TestWinsorizeColumn`)
- Functions: `test_descriptive_name` (e.g., `test_no_outliers_unchanged`, `test_metadata_lookup_takes_priority`)

## Test Structure

**Suite Organization:**
```python
# test_domains.py structure

@pytest.fixture(scope="module")
def domain_specs():
    return load_domain_config(_DEFAULT_YAML)

class TestLoadDomainConfig:
    def test_returns_list(self, domain_specs):
        assert isinstance(domain_specs, list)

class TestAssignDomain:
    def test_cognition(self, domain_specs):
        assert assign_domain("nihtbx_flanker_agecorrected", domain_specs) == "Cognition"
```

**Patterns:**

1. **Fixtures (setup/teardown):**
   - Module-scope fixtures for expensive/shared setup: `@pytest.fixture(scope="module")`
   - Function-scope fixtures for test-local data: `@pytest.fixture()` (default)
   - Example from `test_preprocessing.py` (lines 35–44):
     ```python
     @pytest.fixture()
     def small_series():
         """A small non-skewed series."""
         return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

     @pytest.fixture()
     def skewed_series():
         """A series with extreme outlier to induce skewness."""
         return pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 100.0])
     ```

2. **Class-based organization:**
   - Each logical feature gets a test class: `class TestWinsorizeColumn`, `class TestAssignDomain`
   - Fixtures are passed as method arguments
   - No test inheritance — each class is independent

3. **Assertion patterns:**
   - Equality: `assert result == expected`
   - Containment: `assert "Cognition" in result`
   - Length: `assert len(results) == 3`
   - DataFrame equality: `pd.testing.assert_series_equal(result, expected)`
   - Numerical tolerance: `np.testing.assert_allclose(result, expected, atol=1e-10)`

## Mocking

**Framework:** No explicit mocking library (no unittest.mock, pytest-mock)

**Approach:**
- **Test data in fixtures**: Use real data structures, not mocks
  - Example: `test_preprocessing.py` creates test Series/DataFrames directly
- **File I/O testing**: Use `tmp_path` fixture for temporary files
  - Example from `test_preprocessing.py` (lines 264–269):
    ```python
    def test_load_cluster_labels(self, tmp_path):
        csv = tmp_path / "clusters.csv"
        csv.write_text("subjectkey,cluster\ns1,0\ns2,1\ns3,2\n")
        df = load_cluster_labels(str(csv))
    ```

**What to Mock:**
- Not done in current tests — pure functions tested with real input/output
- If needed in future: External API calls, R/pymer4 calls (via monkeypatch)

**What NOT to Mock:**
- Data transformations (test with real Series/DataFrames)
- File I/O (use tmp_path for temporary test files)
- Mathematical operations (verify against scipy/numpy)

## Fixtures and Factories

**Test Data Patterns:**

1. **Fixture-based (recommended approach):**
   ```python
   @pytest.fixture()
   def df_with_clusters():
       return pd.DataFrame({
           "subjectkey": ["s1", "s2", "s3", "s4", "s5", "s6"],
           "cluster": ["0", "0", "1", "1", "2", "2"],
       })
   ```

2. **Inline test data:**
   ```python
   def test_known_values(self):
       x = pd.Series([1.0, 2.0, 3.0, 4.0])
       result = inverse_normal_transform(x)
       expected = norm.ppf(np.array([0.125, 0.375, 0.625, 0.875]))
   ```

3. **Parametrized data (for multiple test cases of same function):**
   - Not used currently but pattern would be:
   ```python
   @pytest.mark.parametrize("input,expected", [
       (1.0, "low"),
       (100.0, "high"),
   ])
   def test_classifier(self, input, expected):
       assert classify(input) == expected
   ```

**Location:**
- Fixtures live in the same test file as the tests using them
- Module-level fixtures defined at top (lines 26–50 in test files)
- Method-level fixtures defined within test classes

## Coverage

**Requirements:** None enforced — no coverage configuration found

**View Coverage:**
```bash
pytest --cov=python_pipeline python_pipeline/tests/
pytest --cov=python_pipeline --cov-report=html python_pipeline/tests/
```

## Test Types

**Unit Tests (all tests in repo):**
- **Scope**: Single function in isolation
- **Data**: Synthetic test fixtures
- **Speed**: <100ms per test
- **Examples**:
  - `test_cognition()` — Verify domain assignment for one variable
  - `test_no_outliers_unchanged()` — Winsorize with no outliers should be identity
  - `test_fdr_values_match_statsmodels()` — Compare FDR output to scipy reference

**Integration Tests:**
- Not present in current codebase
- Would test: end-to-end pipeline with real data, multi-step workflows
- Would require: pymer4/R installation, actual phenotype files

**E2E Tests:**
- Not present in current codebase
- Would test: Full CLI invocation with real input/output files

## Common Patterns

**Async Testing:**
- Not applicable — no async code in pipeline

**Error Testing:**
- Verify exceptions are raised for invalid inputs
- Example from `test_preprocessing.py` (lines 222–224):
  ```python
  def test_invalid_reference_raises(self, df_with_clusters):
      with pytest.raises(ValueError, match="not found"):
          create_cluster_dummies(df_with_clusters, "cluster", reference_cluster="9")
  ```

- Example from `test_preprocessing.py` (lines 254–256):
  ```python
  def test_invalid_stratum_raises(self, df_with_sex):
      with pytest.raises(ValueError, match="sex_stratum must be"):
          filter_by_sex(df_with_sex, "sex", "other")
  ```

**Data Immutability Testing:**
- Verify functions don't mutate input (return new DataFrame instead)
- Example from `test_preprocessing.py` (lines 180–184):
  ```python
  def test_original_df_not_mutated(self):
      df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
      original_values = df["a"].copy()
      preprocess_continuous_phenotypes(df, ["a"])
      pd.testing.assert_series_equal(df["a"], original_values)
  ```

- Example from `test_domains.py` (lines 87–91):
  ```python
  def test_original_df_not_mutated(self, domain_specs):
      df = pd.DataFrame({"phenotype": ["nihtbx_flanker"]})
      original_cols = list(df.columns)
      assign_domains_to_results(df, domain_specs)
      assert list(df.columns) == original_cols
  ```

**Numerical Precision Testing:**
- Use `atol=` parameter for floating-point comparisons
- Example from `test_preprocessing.py` (lines 99–103):
  ```python
  def test_known_values(self):
      x = pd.Series([1.0, 2.0, 3.0, 4.0])
      result = inverse_normal_transform(x)
      expected = norm.ppf(np.array([0.125, 0.375, 0.625, 0.875]))
      np.testing.assert_allclose(result.values, expected, atol=1e-10)
  ```

**NaN Handling Testing:**
- Verify NaN values are preserved through transformations
- Example from `test_preprocessing.py` (lines 88–90):
  ```python
  def test_nan_positions_preserved(self, series_with_nan):
      result = inverse_normal_transform(series_with_nan)
      assert np.isnan(result.iloc[2])
  ```

**Test Organization by Feature:**
```
test_domains.py
├── TestLoadDomainConfig          # Configuration loading
├── TestAssignDomain              # Core domain assignment logic
├── TestAssignDomainsToResults    # Batch operations on DataFrames
├── TestHelpers                   # Helper functions (get_domain_order, get_color_map)
└── TestMetadataLookup            # Metadata + year-suffix stripping

test_preprocessing.py
├── TestWinsorizeColumn           # Outlier clipping
├── TestInverseNormalTransform    # INT transformation
├── TestZscoreColumn              # Z-score normalization
├── TestSkewness                  # Skewness computation
├── TestPreprocessContinuousPhenotypes  # Full pipeline on continuous vars
├── TestCreateClusterDummies      # k-1 cluster dummy creation
├── TestFilterBySex               # Sex stratification
└── TestClusterIO                 # Load/merge cluster labels

test_corrections.py
└── TestApplyMultipleCorrections  # FDR and Bonferroni corrections
    ├── Per-contrast corrections
    ├── NaN handling
    └── Output validation
```

---

*Testing analysis: 2025-03-02*
