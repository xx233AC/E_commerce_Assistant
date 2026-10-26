from app.llm.client import generate


def run(kind, input_data, config):
    if kind not in {"main_image_plan", "video_script", "title_plan"}:
        raise ValueError("Unsupported creative text task")
    return generate(kind, input_data, config)
