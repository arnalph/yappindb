"""
Unit tests for the Bird-SQL benchmark integration.

Run with:
    pytest tests/test_bird_benchmark.py -v
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestBirdBenchmark:
    """Test BirdBenchmark class."""
    
    def test_benchmark_imports(self):
        """Test that benchmark module can be imported."""
        from rag_agent import benchmark
        assert hasattr(benchmark, 'BirdBenchmark')
        assert hasattr(benchmark, 'main')
    
    def test_benchmark_initialization(self):
        """Test that BirdBenchmark can be instantiated."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "dataset_source": "bird",
                    "dataset_name": "birdsql/bird-critic-1.0-sqlite",
                    "dataset_subset": "dev",
                    "queries_file": "data/bird_dev.json",
                    "databases_dir": "data/bird_databases",
                    "output_dir": "benchmark_results",
                    "threshold": 0.70
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                
                assert bench.dataset_source == "bird"
                assert bench.dataset_name == "birdsql/bird-critic-1.0-sqlite"
                assert bench.dataset_subset == "dev"
                assert bench.threshold == 0.70
    
    def test_benchmark_disabled_exits(self):
        """Test that disabled benchmark exits gracefully."""
        from rag_agent.benchmark import BirdBenchmark
        import sys
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {"enabled": False}
            }
            
            with pytest.raises(SystemExit) as exc_info:
                BirdBenchmark()
            
            assert exc_info.value.code == 0
    
    def test_get_db_path(self):
        """Test database path construction."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "databases_dir": "/tmp/dbs",
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                bench.databases_dir = Path("/tmp/dbs")
                
                path = bench.get_db_path("test_db")
                
                assert path == Path("/tmp/dbs/test_db/test_db.sqlite")
    
    def test_load_dataset_file_not_found(self):
        """Test graceful handling when dataset file is missing."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "queries_file": "nonexistent.json",
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                bench.queries_file = Path("nonexistent.json")
                
                with pytest.raises(SystemExit) as exc_info:
                    bench.load_dataset()
                
                assert exc_info.value.code == 1
    
    def test_load_dataset_success(self, tmp_path):
        """Test successful dataset loading."""
        from rag_agent.benchmark import BirdBenchmark
        
        # Create test dataset file
        test_data = [
            {
                "question": "What is the average revenue?",
                "SQL": "SELECT AVG(revenue) FROM sales;",
                "db_id": "test_db"
            }
        ]
        
        queries_file = tmp_path / "test_dataset.json"
        queries_file.write_text(json.dumps(test_data))
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "queries_file": str(queries_file),
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                bench.queries_file = queries_file
                
                data = bench.load_dataset()
                
                assert len(data) == 1
                assert data[0]["question"] == "What is the average revenue?"
                assert data[0]["SQL"] == "SELECT AVG(revenue) FROM sales;"
    
    def test_run_single_test_db_not_found(self):
        """Test handling when database is not found."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "databases_dir": "/tmp/nonexistent",
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                bench.databases_dir = Path("/tmp/nonexistent")
                
                result = bench.run_single_test(
                    question="Test question",
                    gold_sql="SELECT * FROM test;",
                    db_id="missing_db"
                )
                
                assert result["db_available"] is False
                assert "Database not found" in result["error"]
                assert result["execution_accuracy"] is False
    
    def test_calculate_summary(self):
        """Test summary calculation."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "threshold": 0.70,
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                
                # Simulate results
                bench.results = [
                    {"execution_accuracy": True, "exact_match": True, "latency": 2.5, "db_available": True},
                    {"execution_accuracy": True, "exact_match": False, "latency": 3.0, "db_available": True},
                    {"execution_accuracy": False, "exact_match": False, "latency": 1.5, "db_available": True},
                ]
                
                bench._calculate_summary()
                
                assert bench.summary["total"] == 3
                assert bench.summary["execution_accuracy"] == pytest.approx(2/3)
                assert bench.summary["exact_match"] == pytest.approx(1/3)
                assert bench.summary["avg_latency"] == pytest.approx(2.333, abs=0.01)
    
    def test_env_var_override(self):
        """Test that environment variables override config."""
        from rag_agent.benchmark import BirdBenchmark
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "threshold": 0.70,
                    "output_dir": "benchmark_results"
                }
            }
            
            with patch.dict(os.environ, {"BENCHMARK_THRESHOLD": "0.85"}):
                with patch.object(Path, 'mkdir'):
                    bench = BirdBenchmark()
                    
                    assert bench.threshold == 0.85


class TestPromptfooIntegration:
    """Test promptfoo configuration generation."""
    
    def test_generate_promptfoo_config(self, tmp_path):
        """Test promptfoo config generation."""
        pytest.importorskip("yaml")
        
        from rag_agent.benchmark import BirdBenchmark
        
        # Create test dataset
        test_data = [
            {
                "question": "Test question 1",
                "SQL": "SELECT * FROM test;",
                "db_id": "test_db"
            }
        ]
        
        queries_file = tmp_path / "test.json"
        queries_file.write_text(json.dumps(test_data))
        
        with patch('rag_agent.benchmark.get_config') as mock_config:
            mock_config.return_value.config = {
                "benchmark": {
                    "enabled": True,
                    "queries_file": str(queries_file),
                    "output_dir": str(tmp_path / "results")
                }
            }
            
            with patch.object(Path, 'mkdir'):
                bench = BirdBenchmark()
                bench.queries_file = queries_file
                
                config_path = bench.generate_promptfoo_config()
                
                assert config_path.exists()
                
                # Verify YAML content
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                
                assert "providers" in config
                assert "tests" in config
                assert len(config["tests"]) == 1
                assert config["tests"][0]["vars"]["question"] == "Test question 1"
