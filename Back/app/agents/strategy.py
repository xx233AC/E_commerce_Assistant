from app.llm.client import generate


def run(kind, input_data, config):
    if kind != "ad_recommendation":
        raise ValueError("Unsupported strategy task")
    return generate(kind, input_data, config)
