"""
Headline Metric 2: Quality Scoring & Statistical Significance CLI.
Computes SQuAD-style EM, F1, document recall, all-gold-found share, document precision,
citation precision, LLM-judged correctness, 10,000 bootstrap 95% CIs, McNemar paired tests,
and 2Wiki question-type breakdowns.
"""

import os
import sys
import re
import json
import string
import argparse
import logging
import collections
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "ai_service"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(AI_SERVICE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("score_quality")


def normalize_answer(s: str) -> str:
    """SQuAD standard normalization: lowercase, strip punctuation and articles."""
    def remove_articles(text: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text: str) -> str:
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def compute_exact_match(prediction: str, ground_truth: str) -> float:
    """Computes exact match score after normalization."""
    return 1.0 if normalize_answer(prediction) == normalize_answer(ground_truth) else 0.0


def compute_f1(prediction: str, ground_truth: str) -> float:
    """Computes token-level F1 score after normalization."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(ground_truth).split()

    if len(pred_tokens) == 0 or len(gold_tokens) == 0:
        return 1.0 if pred_tokens == gold_tokens else 0.0

    common = collections.Counter(pred_tokens) & collections.Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0

    precision = 1.0 * num_same / len(pred_tokens)
    recall = 1.0 * num_same / len(gold_tokens)
    return (2 * precision * recall) / (precision + recall)


def judge_answer_llm(
    question: str,
    gold_answer: str,
    prediction: str,
    llm_client: Any,
    judge_model: str = "gpt-4o-mini",
) -> int:
    """
    LLM-as-a-Judge correctness evaluator per Step 6.3.
    Returns 1 if answer contains the correct fact, 0 otherwise.
    """
    judge_prompt = f"""You are an objective judge evaluating answer correctness for multi-hop question answering.

Question:
{question}

Ground Truth Reference:
{gold_answer}

Candidate System Prediction:
{prediction}

Instructions:
Does the Candidate System Prediction correctly state or convey the factual answer given in the Ground Truth Reference?
Answer with [[1]] if correct, or [[0]] if incorrect.
"""
    try:
        if llm_client is not None and getattr(llm_client, "openai_client", None) is not None:
            resp = llm_client.generate(
                prompt=judge_prompt,
                model=judge_model,
                temperature=0.0,
                max_tokens=10,
            )
            match = re.search(r"\[\[([01])\]\]", resp)
            if match:
                return int(match.group(1))
            if "1" in resp[:5]:
                return 1
            return 0
    except Exception as e:
        logger.warning(f"Judge API call failed ({e}); evaluating with normalized heuristic.")

    # Fallback heuristic: check substring or high F1
    norm_gold = normalize_answer(gold_answer)
    norm_pred = normalize_answer(prediction)
    if norm_gold in norm_pred or compute_f1(prediction, gold_answer) >= 0.5:
        return 1
    return 0


def bootstrap_ci(
    values: List[float],
    n_bootstraps: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Tuple[float, float]:
    """Computes non-parametric bootstrap 95% confidence intervals."""
    if not values:
        return 0.0, 0.0
    rng = np.random.RandomState(seed)
    n = len(values)
    boot_means = [float(np.mean(rng.choice(values, size=n, replace=True))) for _ in range(n_bootstraps)]
    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_means, 100.0 * alpha))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha)))
    return round(low, 4), round(high, 4)


def mcnemar_test(b: int, c: int) -> Tuple[float, float]:
    """
    Performs McNemar's paired contingency test with Edwards continuity correction.
    b: Arm 1 correct, Arm 2 incorrect
    c: Arm 1 incorrect, Arm 2 correct
    """
    total = b + c
    if total == 0:
        return 0.0, 1.0

    # With continuity correction
    stat = ((abs(b - c) - 1.0) ** 2) / float(total)

    # Approximate p-value from chi-square distribution with 1 DOF
    try:
        from scipy.stats import chi2
        p_val = float(1.0 - chi2.cdf(stat, df=1))
    except ImportError:
        # Standard normal approximation of chi2(1)
        z = np.sqrt(stat)
        from math import erf, sqrt
        p_val = 1.0 - erf(z / sqrt(2.0))

    return round(stat, 4), round(float(p_val), 4)


def paired_bootstrap_diff(
    vals_1: List[float],
    vals_2: List[float],
    n_bootstraps: int = 10000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, Any]:
    """Computes paired difference bootstrap (Arm 1 minus Arm 2)."""
    assert len(vals_1) == len(vals_2)
    diffs = np.array(vals_1) - np.array(vals_2)
    mean_diff = float(np.mean(diffs))

    rng = np.random.RandomState(seed)
    n = len(diffs)
    boot_diffs = [float(np.mean(rng.choice(diffs, size=n, replace=True))) for _ in range(n_bootstraps)]

    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_diffs, 100.0 * alpha))
    high = float(np.percentile(boot_diffs, 100.0 * (1.0 - alpha)))
    # Empirical one-tailed p-value: fraction of resamples <= 0
    p_val = float(np.mean(np.array(boot_diffs) <= 0.0))

    return {
        "mean_diff": round(mean_diff, 4),
        "ci_95": [round(low, 4), round(high, 4)],
        "p_value_one_tailed": round(p_val, 4),
    }


def score_records(
    records: List[Dict[str, Any]],
    llm_client: Optional[Any] = None,
    judge_model: str = "gpt-4o-mini",
    n_bootstraps: int = 10000,
) -> Dict[str, Any]:
    """Scores all JSONL question records across arms and computes full statistical report."""
    arms = sorted(list(set(r["arm"] for r in records)))
    qids = sorted(list(set(r["qid"] for r in records)))

    logger.info(f"Scoring {len(records)} records across arms {arms} on {len(qids)} questions...")

    # Organize by (qid, arm)
    by_arm_qid: Dict[str, Dict[str, Dict[str, Any]]] = collections.defaultdict(dict)
    for r in records:
        by_arm_qid[r["arm"]][r["qid"]] = r

    per_arm_metrics = {}
    per_arm_arrays = collections.defaultdict(lambda: collections.defaultdict(list))

    for arm in arms:
        arm_records = [by_arm_qid[arm][qid] for qid in qids if qid in by_arm_qid[arm]]

        for r in arm_records:
            gold_ans = r.get("gold_answer", "")
            pred_ans = r.get("answer", "")
            gold_docs = set(r.get("gold_docs", []))
            ret_docs = set(r.get("retrieved_docs", []))
            cited_docs = set(r.get("cited_docs", []))

            # Document Recall
            doc_rec = len(gold_docs & ret_docs) / max(1, len(gold_docs)) if gold_docs else 1.0
            # All Gold Found
            all_found = 1.0 if gold_docs and gold_docs.issubset(ret_docs) else 0.0
            # Document Precision
            doc_prec = len(gold_docs & ret_docs) / max(1, len(ret_docs)) if ret_docs else 0.0
            # Exact Match
            em = compute_exact_match(pred_ans, gold_ans)
            # F1
            f1 = compute_f1(pred_ans, gold_ans)
            # LLM Judge
            judge = judge_answer_llm(
                question=r.get("question", ""),
                gold_answer=gold_ans,
                prediction=pred_ans,
                llm_client=llm_client,
                judge_model=judge_model,
            )
            # Citation Precision
            cite_prec = len(gold_docs & cited_docs) / max(1, len(cited_docs)) if cited_docs else 0.0

            ctx_chars = r.get("context_chars", len(r.get("context", "")))
            ctx_words = r.get("context_words", len(r.get("context", "").split()))
            n_nodes = r.get("n_nodes", 0)

            # Store in arrays
            per_arm_arrays[arm]["doc_recall"].append(doc_rec)
            per_arm_arrays[arm]["all_gold_found"].append(all_found)
            per_arm_arrays[arm]["doc_precision"].append(doc_prec)
            per_arm_arrays[arm]["exact_match"].append(em)
            per_arm_arrays[arm]["f1"].append(f1)
            per_arm_arrays[arm]["judged_correctness"].append(float(judge))
            per_arm_arrays[arm]["citation_precision"].append(cite_prec)
            per_arm_arrays[arm]["context_chars"].append(ctx_chars)
            per_arm_arrays[arm]["context_words"].append(ctx_words)
            per_arm_arrays[arm]["n_nodes"].append(n_nodes)

        # Compute summary and CIs for each metric in this arm
        arm_summary = {}
        for m_name in [
            "doc_recall",
            "all_gold_found",
            "doc_precision",
            "exact_match",
            "f1",
            "judged_correctness",
            "citation_precision",
        ]:
            vals = per_arm_arrays[arm][m_name]
            mean_val = float(np.mean(vals))
            ci_low, ci_high = bootstrap_ci(vals, n_bootstraps=n_bootstraps)
            arm_summary[m_name] = {
                "mean": round(mean_val, 4),
                "ci_95": [ci_low, ci_high],
            }

        arm_summary["context_chars_median"] = float(np.median(per_arm_arrays[arm]["context_chars"]))
        arm_summary["context_words_median"] = float(np.median(per_arm_arrays[arm]["context_words"]))
        arm_summary["nodes_median"] = float(np.median(per_arm_arrays[arm]["n_nodes"]))
        arm_summary["num_questions"] = len(arm_records)

        per_arm_metrics[arm] = arm_summary

    # Paired Statistical Tests: Arm C vs Arm A, Arm C vs Arm D, Arm C vs Arm B
    paired_tests = {}
    if "C" in per_arm_arrays:
        for other_arm in ["A", "B", "D"]:
            if other_arm in per_arm_arrays:
                pair_key = f"Arm_C_vs_Arm_{other_arm}"
                c_judged = per_arm_arrays["C"]["judged_correctness"]
                o_judged = per_arm_arrays[other_arm]["judged_correctness"]
                c_all_found = per_arm_arrays["C"]["all_gold_found"]
                o_all_found = per_arm_arrays[other_arm]["all_gold_found"]

                # McNemar on Judged Correctness
                b_judge = sum(1 for c_j, o_j in zip(c_judged, o_judged) if c_j == 1 and o_j == 0)
                c_judge = sum(1 for c_j, o_j in zip(c_judged, o_judged) if c_j == 0 and o_j == 1)
                stat_judge, p_judge = mcnemar_test(b_judge, c_judge)

                # McNemar on All-Gold-Found
                b_gold = sum(1 for c_g, o_g in zip(c_all_found, o_all_found) if c_g == 1 and o_g == 0)
                c_gold = sum(1 for c_g, o_g in zip(c_all_found, o_all_found) if c_g == 0 and o_g == 1)
                stat_gold, p_gold = mcnemar_test(b_gold, c_gold)

                # Paired bootstrap difference on F1 and Document Recall
                f1_diff = paired_bootstrap_diff(
                    per_arm_arrays["C"]["f1"],
                    per_arm_arrays[other_arm]["f1"],
                    n_bootstraps=n_bootstraps,
                )
                rec_diff = paired_bootstrap_diff(
                    per_arm_arrays["C"]["doc_recall"],
                    per_arm_arrays[other_arm]["doc_recall"],
                    n_bootstraps=n_bootstraps,
                )

                paired_tests[pair_key] = {
                    "mcnemar_judged_correctness": {
                        "b_only_C": b_judge,
                        "c_only_other": c_judge,
                        "chi2": stat_judge,
                        "p_value": p_judge,
                    },
                    "mcnemar_all_gold_found": {
                        "b_only_C": b_gold,
                        "c_only_other": c_gold,
                        "chi2": stat_gold,
                        "p_value": p_gold,
                    },
                    "f1_difference_bootstrap": f1_diff,
                    "doc_recall_difference_bootstrap": rec_diff,
                }

    # Question Type Breakdown
    types_found = sorted(list(set(r.get("type", "unknown") for r in records)))
    breakdown_by_type = {}
    for q_type in types_found:
        breakdown_by_type[q_type] = {}
        for arm in arms:
            sub_records = [
                by_arm_qid[arm][qid]
                for qid in qids
                if qid in by_arm_qid[arm] and by_arm_qid[arm][qid].get("type") == q_type
            ]
            if not sub_records:
                continue

            recalls = []
            all_founds = []
            f1s = []
            judgeds = []
            for r in sub_records:
                g_docs = set(r.get("gold_docs", []))
                r_docs = set(r.get("retrieved_docs", []))
                recalls.append(len(g_docs & r_docs) / max(1, len(g_docs)) if g_docs else 1.0)
                all_founds.append(1.0 if g_docs and g_docs.issubset(r_docs) else 0.0)
                f1s.append(compute_f1(r.get("answer", ""), r.get("gold_answer", "")))
                judgeds.append(float(judge_answer_llm(
                    question=r.get("question", ""),
                    gold_answer=r.get("gold_answer", ""),
                    prediction=r.get("answer", ""),
                    llm_client=llm_client,
                    judge_model=judge_model,
                )))

            breakdown_by_type[q_type][arm] = {
                "num_questions": len(sub_records),
                "mean_doc_recall": round(float(np.mean(recalls)), 4),
                "all_gold_found_share": round(float(np.mean(all_founds)), 4),
                "mean_f1": round(float(np.mean(f1s)), 4),
                "mean_judged_correctness": round(float(np.mean(judgeds)), 4),
            }

    return {
        "per_arm_metrics": per_arm_metrics,
        "paired_statistical_tests": paired_tests,
        "question_type_breakdown": breakdown_by_type,
    }


def print_markdown_tables(scores: Dict[str, Any]):
    """Prints GitHub-Flavored Markdown tables for report integration."""
    per_arm = scores.get("per_arm_metrics", {})
    print("\n### Table 3: Quality Across Retrieval Arms (50 Eval Questions)\n")
    print("| Arm | Method | Doc Recall (95% CI) | All-Gold Found (95% CI) | Answer EM | Answer F1 (95% CI) | Judged Corr. | Cite Prec. | Med Words |")
    print("|---|---|---|---|---|---|---|---|---|")

    arm_desc = {
        "A": "Naive Chunk RAG",
        "B": "Top-k Entity Nodes",
        "C": "KONNECT: PCST + GNN",
        "D": "PCST + Text Emb.",
    }

    for arm, d in per_arm.items():
        desc = arm_desc.get(arm, arm)
        rec = f"{d['doc_recall']['mean']*100:.1f}% [{d['doc_recall']['ci_95'][0]*100:.1f}, {d['doc_recall']['ci_95'][1]*100:.1f}]"
        all_g = f"{d['all_gold_found']['mean']*100:.1f}% [{d['all_gold_found']['ci_95'][0]*100:.1f}, {d['all_gold_found']['ci_95'][1]*100:.1f}]"
        em = f"{d['exact_match']['mean']*100:.1f}%"
        f1 = f"{d['f1']['mean']*100:.1f}% [{d['f1']['ci_95'][0]*100:.1f}, {d['f1']['ci_95'][1]*100:.1f}]"
        judge = f"{d['judged_correctness']['mean']*100:.1f}%"
        cite = f"{d['citation_precision']['mean']*100:.1f}%"
        words = f"{int(d['context_words_median'])}"
        print(f"| {arm} | {desc} | {rec} | {all_g} | {em} | {f1} | {judge} | {cite} | {words} |")

    print("\n### Table 4: Breakdown by 2WikiMultihopQA Question Type\n")
    print("| Question Type | Arm | Questions | Doc Recall | All-Gold Found | Answer F1 | Judged Correctness |")
    print("|---|---|---|---|---|---|---|")
    breakdown = scores.get("question_type_breakdown", {})
    for q_type, arms_data in breakdown.items():
        for arm, vals in arms_data.items():
            print(
                f"| {q_type} | {arm} | {vals['num_questions']} | "
                f"{vals['mean_doc_recall']*100:.1f}% | {vals['all_gold_found_share']*100:.1f}% | "
                f"{vals['mean_f1']*100:.1f}% | {vals['mean_judged_correctness']*100:.1f}% |"
            )

    paired = scores.get("paired_statistical_tests", {})
    if paired:
        print("\n### Table 5: Paired Significance Tests (Arm C vs Baselines)\n")
        print("| Comparison | McNemar Judged p-value | McNemar All-Gold p-value | F1 Diff (95% CI) | F1 Diff p-value |")
        print("|---|---|---|---|---|")
        for pair_name, p_data in paired.items():
            m_j_p = p_data["mcnemar_judged_correctness"]["p_value"]
            m_g_p = p_data["mcnemar_all_gold_found"]["p_value"]
            f1_diff = p_data["f1_difference_bootstrap"]
            f1_ci = f"{f1_diff['mean_diff']*100:+.1f}% [{f1_diff['ci_95'][0]*100:+.1f}, {f1_diff['ci_95'][1]*100:+.1f}]"
            f1_p = f1_diff["p_value_one_tailed"]
            print(f"| {pair_name} | {m_j_p:.4f} | {m_g_p:.4f} | {f1_ci} | {f1_p:.4f} |")


def main():
    parser = argparse.ArgumentParser(description="Score KONNECT Quality Benchmark Results")
    parser.add_argument("input_file", type=str, default="results/quality_midsem.jsonl", help="Input JSONL file")
    parser.add_argument("--judge-model", type=str, default="gpt-4o-mini", help="Judge model name")
    parser.add_argument("--out", type=str, default="results/quality_scores.json", help="Output JSON path")
    parser.add_argument("--bootstraps", type=int, default=10000, help="Number of bootstrap resamples")
    parser.add_argument("--config", type=str, default="bench/config.json", help="Path to config.json")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.is_absolute():
        input_path = REPO_ROOT / input_path

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logger.info(f"Loaded {len(records)} records from {input_path}")

    # Initialize LLMClient for judging if available
    llm_client = None
    try:
        from app.llm.client import LLMClient
        llm_client = LLMClient()
    except Exception as e:
        logger.warning(f"Could not initialize LLMClient for judge ({e}). Using normalized heuristic.")

    scores = score_records(
        records=records,
        llm_client=llm_client,
        judge_model=args.judge_model,
        n_bootstraps=args.bootstraps,
    )

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2)

    logger.info(f"Quality scores successfully written to {out_path}")
    print_markdown_tables(scores)


if __name__ == "__main__":
    main()
