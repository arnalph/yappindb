"""
SQL Candidate Generator - generates multiple SQL variants and selects the best one.
"""

import re
from typing import List, Optional, Tuple

from rag_agent.model import get_generator


def generate_sql_candidates(question: str, schema: str, db_type: str = "sqlite", evidence: str = "", count: int = 3) -> List[str]:
    """
    Generate multiple SQL candidates using different approaches.
    
    Args:
        question: Natural language question
        schema: Database schema
        db_type: Database type
        evidence: Optional hint/evidence
        count: Number of candidates to generate
        
    Returns:
        List of SQL candidate strings
    """
    generator = get_generator()
    candidates = []
    
    # Generate with different temperatures for diversity
    temps = [0.0, 0.2, 0.4][:count]
    
    for i, temp in enumerate(temps):
        try:
            sql = generator.generate_sql(
                question=question,
                schema=schema,
                db_type=db_type,
                evidence=evidence,
                temperature=temp
            )
            if sql and sql.strip():
                candidates.append(sql.strip())
        except Exception:
            pass
    
    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        normalized = c.lower().replace(" ", "").replace("\n", "")
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(c)
    
    return unique_candidates


def score_sql_candidate(sql: str, question: str, schema: str) -> float:
    """
    Score a SQL candidate based on heuristics.
    
    Args:
        sql: SQL query string
        question: Original question
        schema: Database schema
        
    Returns:
        Score (higher is better)
    """
    score = 0.0
    
    # Check if SQL is valid
    sql_upper = sql.upper()
    if not sql_upper.startswith("SELECT"):
        return -1.0
    
    # Prefer shorter SQL (Occam's razor)
    sql_length = len(sql.split())
    if sql_length < 10:
        score += 2.0
    elif sql_length < 20:
        score += 1.0
    elif sql_length > 50:
        score -= 1.0
    
    # Check for key question terms in SQL
    question_words = set(question.lower().split())
    sql_lower = sql.lower()
    
    # Bonus for using relevant tables/columns
    for table in re.findall(r'CREATE TABLE (\w+)', schema, re.IGNORECASE):
        if table.lower() in sql_lower:
            score += 0.5
    
    # Penalty for complex subqueries unless needed
    if sql_lower.count('select') > 3:
        score -= 1.0
    
    # Bonus for having WHERE clause if question has conditions
    if any(word in question_lower for word in ['where', 'which', 'that', 'who', 'how many']):
        if 'where' in sql_lower or 'having' in sql_lower:
            score += 1.0
    
    # Bonus for aggregation if question asks for count/sum/avg
    if any(word in question_words for word in ['count', 'total', 'sum', 'average', 'avg', 'ratio']):
        if any(func in sql_lower for func in ['count(', 'sum(', 'avg(', 'max(', 'min(']):
            score += 2.0
    
    # Bonus for ORDER BY if question asks for "top" or "most"
    if any(word in question_words for word in ['top', 'most', 'highest', 'lowest', 'first', 'last']):
        if 'order by' in sql_lower:
            score += 1.0
        if 'limit' in sql_lower:
            score += 1.0
    
    # Bonus for GROUP BY if question implies grouping
    if any(word in question_words for word in ['per', 'each', 'by', 'group', 'per']):
        if 'group by' in sql_lower:
            score += 1.0
    
    return score


def select_best_sql(candidates: List[str], question: str, schema: str) -> Optional[str]:
    """
    Select the best SQL candidate based on scoring.
    
    Args:
        candidates: List of SQL candidates
        question: Original question
        schema: Database schema
        
    Returns:
        Best SQL candidate or None
    """
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    scored = []
    for sql in candidates:
        score = score_sql_candidate(sql, question, schema)
        scored.append((score, sql))
    
    # Return highest scoring candidate
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def generate_and_select(question: str, schema: str, db_type: str = "sqlite", evidence: str = "", count: int = 3) -> Optional[str]:
    """
    Generate multiple SQL candidates and select the best one.
    
    Args:
        question: Natural language question
        schema: Database schema
        db_type: Database type
        evidence: Optional hint/evidence
        count: Number of candidates to generate
        
    Returns:
        Best SQL candidate
    """
    candidates = generate_sql_candidates(question, schema, db_type, evidence, count)
    return select_best_sql(candidates, question, schema)
