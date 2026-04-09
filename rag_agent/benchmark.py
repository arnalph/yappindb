"""
Bird-SQL Benchmark for YappinDB

Evaluates SQL generation accuracy using the Bird-SQL dataset.
Supports both native execution and promptfoo integration.

Usage:
    python -m rag_agent.benchmark                    # Run native benchmark
    python -m rag_agent.benchmark --limit 50         # Run with limit
    python -m rag_agent.benchmark --promptfoo        # Generate promptfoo config
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from rag_agent.config import get_config
from rag_agent.db import DatabaseManager
from rag_agent.graph import run_agent


class BirdBenchmark:
    """Evaluate YappinDB on Bird-SQL dataset."""
    
    def __init__(self):
        self.config = get_config()
        self.bench_cfg = self._load_benchmark_config()
        
        if not self.bench_cfg.get("enabled", True):
            print("Benchmark disabled in config.json")
            sys.exit(0)
        
        # Dataset settings
        self.dataset_source = self.bench_cfg.get("dataset_source", "bird")
        self.dataset_name = self.bench_cfg.get("dataset_name", "birdsql/bird-critic-1.0-sqlite")
        self.dataset_subset = self.bench_cfg.get("dataset_subset", "dev")
        self.queries_file = Path(self.bench_cfg.get("queries_file", "data/bird_dev.json"))
        self.databases_dir = Path(self.bench_cfg.get("databases_dir", "data/bird_databases"))
        
        # Output settings
        self.output_dir = Path(self.bench_cfg.get("output_dir", "benchmark_results"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Threshold
        self.threshold = float(self.bench_cfg.get("threshold", 0.70))
        
        # Results storage
        self.results = []
        self.summary = {}
    
    def _load_benchmark_config(self) -> Dict:
        """Load benchmark config from config.json, with env var overrides."""
        bench = self.config.config.get("benchmark", {})
        
        # Environment variables override config.json
        env_overrides = {
            "enabled": os.getenv("BENCHMARK_ENABLED"),
            "dataset_source": os.getenv("BENCHMARK_DATASET_SOURCE"),
            "dataset_name": os.getenv("BENCHMARK_DATASET_NAME"),
            "dataset_subset": os.getenv("BENCHMARK_DATASET_SUBSET"),
            "queries_file": os.getenv("BENCHMARK_QUERIES_FILE"),
            "databases_dir": os.getenv("BENCHMARK_DATABASES_DIR"),
            "output_dir": os.getenv("BENCHMARK_OUTPUT_DIR"),
            "threshold": os.getenv("BENCHMARK_THRESHOLD"),
        }
        
        for key, value in env_overrides.items():
            if value is not None:
                bench[key] = value
        
        return bench
    
    def load_dataset(self) -> List[Dict]:
        """Load Bird-SQL JSON file (dev.json or train.json)."""
        if not self.queries_file.exists():
            print(f"Dataset file not found: {self.queries_file}")
            print("Run: python scripts/download_bird.py")
            sys.exit(1)
        
        with open(self.queries_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"Loaded {len(data)} test cases from {self.queries_file}")
        return data
    
    def get_db_path(self, db_id: str) -> Path:
        """Construct path to SQLite database for given db_id.
        
        Expected structure:
            databases_dir/{db_id}/{db_id}.sqlite
        """
        return self.databases_dir / db_id / f"{db_id}.sqlite"
    
    def run_single_test(self, question: str, gold_sql: str, db_id: str, evidence: str = "") -> Dict:
        """Run one test case and return results."""
        db_path = self.get_db_path(db_id)
        
        # Check if database exists
        db_available = db_path.exists()
        if not db_available:
            return {
                "question": question,
                "gold_sql": gold_sql,
                "db_id": db_id,
                "generated_sql": "",
                "execution_accuracy": False,
                "exact_match": False,
                "db_available": False,
                "error": f"Database not found: {db_path}",
                "latency": 0
            }
        
        start_time = time.time()
        
        try:
            result = run_agent(
                question=question,
                db_source=str(db_path),
                db_type="sqlite",
                evidence=evidence
            )
        except Exception as e:
            return {
                "question": question,
                "gold_sql": gold_sql,
                "db_id": db_id,
                "generated_sql": "",
                "execution_accuracy": False,
                "exact_match": False,
                "db_available": True,
                "error": f"Agent exception: {str(e)}",
                "latency": time.time() - start_time
            }
        
        latency = time.time() - start_time
        generated_sql = result.get("sql", "")
        error = result.get("error")
        
        # Evaluate accuracy
        execution_ok = False
        exact_match = False
        
        if generated_sql and not error:
            try:
                db_mgr = DatabaseManager(str(db_path), "sqlite")
                
                # Execute gold SQL
                gold_result = db_mgr.execute_query(gold_sql)
                
                # Execute generated SQL
                gen_result = db_mgr.execute_query(generated_sql)
                
                # Compare result sets (order-independent)
                if len(gold_result) == len(gen_result):
                    # Convert to comparable format
                    gold_set = [tuple(sorted(row.items())) for row in gold_result]
                    gen_set = [tuple(sorted(row.items())) for row in gen_result]
                    execution_ok = set(gold_set) == set(gen_set)
                
                # Exact string match (normalized)
                exact_match = (
                    generated_sql.strip().lower().replace(" ", "").replace("\n", "") ==
                    gold_sql.strip().lower().replace(" ", "").replace("\n", "")
                )
                
            except Exception as e:
                execution_ok = False
                error = str(e)
        
        return {
            "question": question,
            "gold_sql": gold_sql,
            "db_id": db_id,
            "generated_sql": generated_sql,
            "execution_accuracy": execution_ok,
            "exact_match": exact_match,
            "db_available": True,
            "latency": latency,
            "error": error
        }
    
    def run_all(self, limit: Optional[int] = None):
        """Run all test cases."""
        dataset = self.load_dataset()
        
        if limit:
            dataset = dataset[:limit]
            print(f"Running first {limit} test cases...")
        else:
            print(f"Running all {len(dataset)} test cases...")
        
        from tqdm import tqdm
        
        for item in tqdm(dataset, desc="Evaluating"):
            res = self.run_single_test(
                question=item["question"],
                gold_sql=item["SQL"],
                db_id=item["db_id"],
                evidence=item.get("evidence", "")
            )
            self.results.append(res)
        
        # Calculate summary
        self._calculate_summary()
        
        # Save reports
        self.save_reports()
        
        # Print summary
        self.print_summary()
        
        # Return exit code
        exec_acc = self.summary.get("execution_accuracy", 0)
        return 0 if exec_acc >= self.threshold else 1
    
    def _calculate_summary(self):
        """Calculate aggregate metrics."""
        total = len(self.results)
        if total == 0:
            self.summary = {"total": 0}
            return
        
        exec_ok = sum(1 for r in self.results if r.get("execution_accuracy", False))
        exact_ok = sum(1 for r in self.results if r.get("exact_match", False))
        db_available = sum(1 for r in self.results if r.get("db_available", False))
        errors = sum(1 for r in self.results if r.get("error"))
        
        latencies = [r.get("latency", 0) for r in self.results if r.get("latency", 0) > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        self.summary = {
            "total": total,
            "db_available": db_available,
            "execution_accuracy": exec_ok / total,
            "exact_match": exact_ok / total,
            "avg_latency": avg_latency,
            "errors": errors,
            "threshold": self.threshold,
            "passed": exec_ok / total >= self.threshold
        }
    
    def save_reports(self):
        """Save detailed results in multiple formats."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON results (detailed)
        results_json = {
            "metadata": {
                "dataset": self.dataset_name,
                "subset": self.dataset_subset,
                "timestamp": timestamp,
                "threshold": self.threshold
            },
            "summary": self.summary,
            "results": self.results
        }
        
        results_path = self.output_dir / f"bird_results_{timestamp}.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_json, f, indent=2, ensure_ascii=False)
        
        # HTML report
        html = self._generate_html_report(timestamp)
        (self.output_dir / f"bird_report_{timestamp}.html").write_text(html, encoding="utf-8")
        
        # CSV summary
        csv_path = self.output_dir / f"bird_summary_{timestamp}.csv"
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("question,db_id,gold_sql,generated_sql,execution_accuracy,exact_match,latency,error\n")
            for r in self.results:
                # Escape CSV fields
                question = f'"{r["question"].replace(chr(34), chr(34)*2)}"'
                gold = f'"{r["gold_sql"].replace(chr(34), chr(34)*2)}"'
                gen = f'"{r["generated_sql"].replace(chr(34), chr(34)*2)}"'
                error = f'"{str(r.get("error", "")).replace(chr(34), chr(34)*2)}"'
                f.write(f"{question},{r['db_id']},{gold},{gen},{r['execution_accuracy']},{r['exact_match']},{r['latency']:.2f},{error}\n")
        
        print(f"\nReports saved to: {self.output_dir}")
    
    def _generate_html_report(self, timestamp: str) -> str:
        """Create HTML report with pass/fail indicators."""
        s = self.summary
        
        # Build result rows
        rows = []
        for i, r in enumerate(self.results):
            exec_class = "pass" if r.get("execution_accuracy") else "fail"
            exact_class = "pass" if r.get("exact_match") else "fail"
            
            error_text = r.get('error') if r.get('error') else ''
            gold_sql = r.get('gold_sql', '')[:200] if r.get('gold_sql') else ''
            gen_sql = r.get('generated_sql', '')[:200] if r.get('generated_sql') else ''
            
            rows.append(f"""
            <tr class="{exec_class}">
                <td>{i+1}</td>
                <td title="{r['question']}">{r['question'][:80]}{'...' if len(r['question']) > 80 else ''}</td>
                <td>{r['db_id']}</td>
                <td class="{exec_class}">{'YES' if r['execution_accuracy'] else 'NO'}</td>
                <td class="{exact_class}">{'YES' if r['exact_match'] else 'NO'}</td>
                <td>{r['latency']:.2f}s</td>
                <td><details><summary>View SQL</summary>
                    <pre class="sql-block">Gold: {gold_sql}
Generated: {gen_sql}</pre>
                </details></td>
                <td>{error_text[:100]}</td>
            </tr>
            """)
        
        passed = "PASSED" if s.get("passed") else "FAILED"
        passed_class = "pass" if s.get("passed") else "fail"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>YappinDB Bird-SQL Benchmark Report</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #1a73e8; }}
        .metric-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .pass {{ background-color: #d4edda !important; color: #155724; }}
        .fail {{ background-color: #f8d7da !important; color: #721c24; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; font-size: 13px; }}
        th {{ background: #1a73e8; color: white; padding: 12px 8px; text-align: left; position: sticky; top: 0; }}
        td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .sql-block {{ font-family: monospace; font-size: 11px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; }}
        .status {{ padding: 4px 12px; border-radius: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>YappinDB Bird-SQL Benchmark Report</h1>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{s.get('total', 0)}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric">
                <div class="metric-value">{s.get('execution_accuracy', 0):.1%}</div>
                <div class="metric-label">Execution Accuracy</div>
            </div>
            <div class="metric">
                <div class="metric-value">{s.get('exact_match', 0):.1%}</div>
                <div class="metric-label">Exact Match</div>
            </div>
            <div class="metric">
                <div class="metric-value">{s.get('avg_latency', 0):.2f}s</div>
                <div class="metric-label">Avg Latency</div>
            </div>
            <div class="metric">
                <div class="metric-value {passed_class}">{passed}</div>
                <div class="metric-label">Threshold: {self.threshold:.0%}</div>
            </div>
        </div>
        
        <p><strong>Dataset:</strong> {self.dataset_name} ({self.dataset_subset})</p>
        <p><strong>Generated:</strong> {timestamp}</p>
        
        <table>
            <tr>
                <th>#</th>
                <th>Question</th>
                <th>DB</th>
                <th>Exec Acc</th>
                <th>Exact</th>
                <th>Latency</th>
                <th>SQL Comparison</th>
                <th>Error</th>
            </tr>
            {''.join(rows)}
        </table>
    </div>
</body>
</html>"""
    
    def print_summary(self):
        """Print summary to console."""
        s = self.summary
        
        print(f"\n{'='*60}")
        print(f"  Bird-SQL Benchmark Summary")
        print(f"{'='*60}")
        print(f"  Dataset:         {self.dataset_name} ({self.dataset_subset})")
        print(f"  Total Tests:     {s.get('total', 0)}")
        print(f"  DB Available:    {s.get('db_available', 0)}")
        print(f"  Errors:          {s.get('errors', 0)}")
        print(f"{'─'*60}")
        print(f"  Execution Acc:   {s.get('execution_accuracy', 0):.1%}")
        print(f"  Exact Match:     {s.get('exact_match', 0):.1%}")
        print(f"  Avg Latency:     {s.get('avg_latency', 0):.2f}s")
        print(f"{'─'*60}")
        
        passed = s.get("passed", False)
        if passed:
            print(f"  Result:          PASSED (threshold: {self.threshold:.0%})")
        else:
            print(f"  Result:          FAILED (threshold: {self.threshold:.0%})")
        
        print(f"{'='*60}")
        print(f"  Reports: {self.output_dir}")
        print(f"{'='*60}\n")
    
    def generate_promptfoo_config(self):
        """Generate promptfoo configuration file for Bird-SQL benchmark."""
        if not HAS_YAML:
            print("Error: PyYAML not installed. Run: pip install pyyaml")
            sys.exit(1)
        
        dataset = self.load_dataset()
        
        # Limit to first 20 for promptfoo (can be adjusted)
        limit = min(20, len(dataset))
        print(f"Generating promptfoo config for {limit} test cases...")
        
        tests = []
        for item in dataset[:limit]:
            tests.append({
                "vars": {
                    "question": item["question"],
                    "gold_sql": item["SQL"]
                },
                "assert": [
                    {
                        "type": "contains-json",
                        "value": '"sql"',
                        "description": "Response must contain SQL"
                    },
                    {
                        "type": "python",
                        "value": "output.sql is not None and len(output.sql) > 0",
                        "description": "SQL must not be empty"
                    }
                ]
            })
        
        promptfoo_config = {
            "description": f"YappinDB Bird-SQL Benchmark ({self.dataset_subset})",
            "providers": [
                {
                    "http": {
                        "url": "http://localhost:8000/chat",
                        "method": "POST",
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": {
                            "question": "{{question}}"
                        },
                        "responseParser": "json"
                    }
                }
            ],
            "prompts": ["{{question}}"],
            "tests": tests,
            "outputPath": str(self.output_dir / "promptfoo_output.json")
        }
        
        config_path = Path("promptfooconfig.yaml")
        with open(config_path, "w") as f:
            yaml.dump(promptfoo_config, f, default_flow_style=False)
        
        print(f"Generated: {config_path}")
        print(f"\nTo run promptfoo:")
        print(f"  1. Start server: uvicorn rag_agent.api:app --port 8000")
        print(f"  2. Run: promptfoo eval -c promptfooconfig.yaml")
        
        return config_path


def main():
    """Main entry point for benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="YappinDB Bird-SQL Benchmark")
    parser.add_argument("--limit", type=int, help="Limit number of test cases")
    parser.add_argument("--promptfoo", action="store_true", help="Generate promptfoo config only")
    parser.add_argument("--dataset", type=str, help="Override dataset name")
    parser.add_argument("--queries", type=str, help="Override queries file path")
    args = parser.parse_args()
    
    bench = BirdBenchmark()
    
    # Apply overrides
    if args.dataset:
        bench.dataset_name = args.dataset
    if args.queries:
        bench.queries_file = Path(args.queries)
    
    if args.promptfoo:
        bench.generate_promptfoo_config()
        sys.exit(0)
    else:
        exit_code = bench.run_all(limit=args.limit)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
