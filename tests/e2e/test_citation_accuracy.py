"""
End-to-end tests for citation accuracy using test catalogue.

Tests validate that the chat service returns correct citations
by comparing against a ground truth test catalogue.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

import pytest


def load_test_catalogue() -> List[Dict[str, Any]]:
    """Load test catalogue with expected citations."""
    catalogue_path = Path(__file__).parent / "test_catalogue.json"
    with open(catalogue_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_citations(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract citations from chat response and normalize page numbers.
    
    Decrements page numbers by 1 to match 0-indexed expectations.
    Expected format: {"citations": [{"url": "...", "page": 1}, ...]}
    """
    citations = response_data.get("citations", [])
    
    # Normalize citations: extract url and page, decrement page by 1
    normalized = []
    for citation in citations:
        if "url" in citation and "page" in citation:
            normalized.append({
                "url": citation["url"],
                "page": citation["page"] - 1  # Decrement page by 1
            })
    
    return normalized


def normalize_citation(citation: Dict[str, Any]) -> tuple:
    """Normalize citation for comparison (url, page)."""
    return (citation.get("url", "").strip(), citation.get("page"))


def calculate_citation_metrics(
    expected: List[Dict[str, Any]], 
    actual: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Calculate citation accuracy metrics.
    
    Returns:
        - precision: What % of returned citations are correct
        - recall: What % of expected citations were found
        - f1_score: Harmonic mean of precision and recall
    """
    expected_set = {normalize_citation(c) for c in expected}
    actual_set = {normalize_citation(c) for c in actual}
    
    true_positives = len(expected_set & actual_set)
    false_positives = len(actual_set - expected_set)
    false_negatives = len(expected_set - actual_set)
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


class TestCitationAccuracy:
    """Test citation accuracy using test catalogue."""
    
    @pytest.mark.skip(reason="Requires OPENAI_API_KEY and indexed documents")
    def test_citation_accuracy_from_catalogue(self, chat_client):
        """
        Test citation accuracy for all queries in test catalogue.
        
        This test:
        1. Loads test catalogue with expected citations
        2. Sends each query to chat service
        3. Extracts citations from response
        4. Compares against expected citations
        5. Reports accuracy metrics
        """
        test_catalogue = load_test_catalogue()
        
        results = []
        total_metrics = {
            "precision": [],
            "recall": [],
            "f1_score": [],
        }
        
        for test_case in test_catalogue:
            query = test_case["query"]
            expected_citations = test_case["expected_citations"]
            
            # Send query to chat service
            response = chat_client.post("/chat", json={"query": query})
            
            assert response.status_code == 200, f"Chat request failed for query: {query}"
            
            # Extract citations from response
            actual_citations = extract_citations(response.json())
            
            # Calculate metrics
            metrics = calculate_citation_metrics(expected_citations, actual_citations)
            
            results.append({
                "query": query,
                "expected": expected_citations,
                "actual": actual_citations,
                "metrics": metrics,
            })
            
            total_metrics["precision"].append(metrics["precision"])
            total_metrics["recall"].append(metrics["recall"])
            total_metrics["f1_score"].append(metrics["f1_score"])
        
        # Calculate average metrics
        avg_precision = sum(total_metrics["precision"]) / len(total_metrics["precision"])
        avg_recall = sum(total_metrics["recall"]) / len(total_metrics["recall"])
        avg_f1 = sum(total_metrics["f1_score"]) / len(total_metrics["f1_score"])
        
        # Print detailed results
        print("\n" + "="*80)
        print("CITATION ACCURACY TEST RESULTS")
        print("="*80)
        
        for result in results:
            print(f"\nQuery: {result['query']}")
            print(f"  Expected: {result['expected']}")
            print(f"  Actual:   {result['actual']}")
            print(f"  Metrics:  P={result['metrics']['precision']:.2f}, "
                  f"R={result['metrics']['recall']:.2f}, "
                  f"F1={result['metrics']['f1_score']:.2f}")
        
        print("\n" + "="*80)
        print(f"AVERAGE METRICS (over {len(test_catalogue)} test cases)")
        print(f"  Precision: {avg_precision:.2%}")
        print(f"  Recall:    {avg_recall:.2%}")
        print(f"  F1 Score:  {avg_f1:.2%}")
        print("="*80 + "\n")
        
        # Assert minimum 90% accuracy (recall - finding expected citations)
        assert avg_recall >= 0.90, f"Citation accuracy too low: {avg_recall:.2%} < 90%"
    
    @pytest.mark.skip(reason="Requires OPENAI_API_KEY and indexed documents")
    @pytest.mark.parametrize("test_case_index", range(5))  # Test first 5 cases individually
    def test_individual_citation_cases(self, chat_client, test_case_index):
        """Test individual citation cases for easier debugging."""
        test_catalogue = load_test_catalogue()
        
        if test_case_index >= len(test_catalogue):
            pytest.skip(f"Test case {test_case_index} does not exist")
        
        test_case = test_catalogue[test_case_index]
        query = test_case["query"]
        expected_citations = test_case["expected_citations"]
        
        # Send query to chat service
        response = chat_client.post("/chat", json={"query": query})
        
        assert response.status_code == 200
        
        # Extract citations
        actual_citations = extract_citations(response.json())
        
        # Calculate metrics
        metrics = calculate_citation_metrics(expected_citations, actual_citations)
        
        # Print results for debugging
        print(f"\nQuery: {query}")
        print(f"Expected: {expected_citations}")
        print(f"Actual: {actual_citations}")
        print(f"Metrics: {metrics}")
        
        # Assert 90% citation accuracy (recall)
        assert metrics["true_positives"] > 0, "No correct citations found"
        assert metrics["recall"] >= 0.90, f"Citation accuracy too low: {metrics['recall']:.2%} < 90%"


class TestCitationFormat:
    """Test citation format and structure."""
    
    def test_citation_response_structure(self, chat_client):
        """Test that chat response includes citations in expected format."""
        # This test doesn't need indexed documents, just checks response structure
        response = chat_client.post("/chat", json={"query": "test query"})
        
        if response.status_code == 200:
            data = response.json()
            
            # Check response structure
            assert "answer" in data or "response" in data, "Response missing answer field"
            
            # Check citations field exists (may be empty)
            # Adjust field name based on your actual API
            assert "citations" in data or "sources" in data or "references" in data, \
                "Response missing citations field"
