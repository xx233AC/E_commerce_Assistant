from app.llm.client import generate


def run(kind, input_data, config):
    if kind not in {"diagnosis", "review_report"}:
        raise ValueError("Unsupported analysis task")
    return generate(kind, input_data, config)
