from pathlib import Path

NAMES = {
    "diagnosis": "diagnosis", "main_image_plan": "main_image", "video_script": "video_script",
    "title_plan": "title", "ad_recommendation": "advertising", "review_report": "review",
}


def load_prompt(kind, version="v1"):
    if version != "v1" or kind not in NAMES:
        raise ValueError("Unknown prompt version or task")
    return (Path(__file__).parent / "prompts" / version / (NAMES[kind] + ".md")).read_text(encoding="utf-8")

