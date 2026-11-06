"""Final scoreboard printed after an eval script finishes every golden row."""


def print_eval_report(title, results):
    """Print one report for the whole run.

    Each result is a dict:
        id: case id
        metrics: list of {name, score, passed, reason}
    Returns True when every metric on every case passed.
    """
    if not results:
        print("\n" + "=" * 72)
        print(title)
        print("No cases ran.")
        print("=" * 72)
        return False

    metric_names = []
    for result in results:
        for metric in result["metrics"]:
            if metric["name"] not in metric_names:
                metric_names.append(metric["name"])

    case_width = max(32, *(len(result["id"]) for result in results))
    cell_width = max(22, *(len(name) for name in metric_names))

    def cell(score, status):
        return f"{score:>12} {status:>8}".rjust(cell_width)

    header = f"{'case':<{case_width}}" + "".join(
        f"  {name:>{cell_width}}" for name in metric_names
    )
    rule = "=" * len(header)
    print("\n" + rule)
    print(title)
    print(rule)
    print(header)
    print("-" * len(header))

    totals = {name: [] for name in metric_names}
    passes = {name: 0 for name in metric_names}
    counts = {name: 0 for name in metric_names}

    for result in results:
        scores = {metric["name"]: metric for metric in result["metrics"]}
        line = f"{result['id']:<{case_width}}"
        for name in metric_names:
            metric = scores.get(name)
            counts[name] += 1
            if metric is None or metric["score"] is None:
                line += "  " + cell("—", "")
                continue
            totals[name].append(metric["score"])
            if metric["passed"]:
                passes[name] += 1
            mark = "pass" if metric["passed"] else "fail"
            line += "  " + cell(f"{metric['score']:.3f}", mark)
        print(line)

    print("-" * len(header))
    average = f"{'average':<{case_width}}"
    for name in metric_names:
        scores = totals[name]
        avg = sum(scores) / len(scores) if scores else 0
        average += "  " + cell(f"{avg:.3f}", f"{passes[name]}/{counts[name]}")
    print(average)

    failed = []
    for result in results:
        for metric in result["metrics"]:
            if not metric["passed"]:
                failed.append((result["id"], metric))

    cases_passed = sum(
        all(metric["passed"] for metric in result["metrics"]) for result in results
    )
    print()
    print(f"Cases passed: {cases_passed}/{len(results)}")

    if failed:
        print("\nFailed checks:")
        for case_id, metric in failed:
            score = "n/a" if metric["score"] is None else f"{metric['score']:.3f}"
            print(f"  {case_id}  {metric['name']}  {score}")
            if metric.get("reason"):
                print(f"    {metric['reason']}")

    print(rule)
    return cases_passed == len(results)
