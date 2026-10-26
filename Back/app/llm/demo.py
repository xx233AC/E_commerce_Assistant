"""Explicit, labeled demonstrations only; never selected as a real-model fallback."""
from decimal import Decimal


def demo_outputs(kind, data, count):
    product = data["snapshot"]["product"]
    evidence = [{"kind": "product", "resource_id": product["id"], "resource_version": product["version"],
                 "field": "selling_points", "excerpt": "；".join(product["selling_points"])[:2000]}]
    def reason(text):
        return {"text": "[演示] " + text, "evidence": evidence, "certainty": "hypothesis"}
    if kind == "diagnosis":
        return [{"content": {
            "positioning": "[演示] 基于录入品类：" + product["category"],
            "price_band": "[演示] 当前标价 " + product["price"] + " 元；未验证市场价格带。",
            "audience_insights": [reason("优先验证已录入目标人群是否匹配使用场景。")],
            "pain_points": [reason("通过访谈核实目标用户购买顾虑。")],
            "selling_point_analysis": [reason("将录入卖点转化为可核实的演示内容。")],
            "risks": [reason("当前演示逻辑不构成真实模型分析。")],
            "recommendations": [reason("先验证一种卖点表达，再开展小范围对照。")],
            "missing_information": ["演示输出未调用真实模型", "缺少用户访谈及可验证的转化证据"],
        }}]
    if kind in {"main_image_plan", "video_script", "title_plan"}:
        items = []
        angles = ["产品主体", "使用场景", "细节说明", "购买疑问", "规格展示", "人群需求", "包装展示", "使用步骤", "对比说明", "售后说明"]
        references = [r["id"] for r in data.get("reference_files", [])]
        for index in range(count):
            angle = angles[index]
            if kind == "main_image_plan":
                content = {
                    "layout": "[演示] 以" + angle + "为表达主题，清晰展示真实商品。",
                    "core_copy": product["selling_points"][0],
                    "highlighted_selling_points": product["selling_points"][:3],
                    "generation_prompt": "基于提供的真实商品参考图，以" + angle + "为主题制作简洁主图；不得添加未经验证的功效或认证。",
                    "negative_prompt": "虚构认证、夸大功效、伪造销量", "reference_file_ids": references, "aspect_ratio": "1:1",
                }
            elif kind == "video_script":
                content = {
                    "hook": "[演示] 从" + angle + "介绍商品。",
                    "shots": [{"shot_no": 1, "duration_sec": 5, "visual": "展示真实商品主体", "voiceover": product["name"], "on_screen_text": "商品展示"},
                              {"shot_no": 2, "duration_sec": 5, "visual": "展示与" + angle + "相关的真实细节", "voiceover": product["selling_points"][0], "on_screen_text": "查看商品详情"}],
                    "voiceover": product["name"] + "。" + product["selling_points"][0],
                    "call_to_action": "查看商品详情并核实规格。", "duration_sec": 10, "aspect_ratio": "9:16",
                    "generation_prompt": "展示真实商品与" + angle + "，禁止夸大功效与伪造评价。", "reference_file_ids": references,
                }
            else:
                content = {"text": ("[演示] " + product["name"] + " · " + angle)[:200], "keywords": [product["category"][:50]],
                           "platform": product["platform"], "highlighted_selling_points": product["selling_points"][:3]}
            items.append({"title": "[演示] " + angle + "方案", "content": content,
                          "rationale_text": "演示候选用于验证流程，需要人工审核；不代表真实模型建议。"})
        return items
    if kind == "ad_recommendation":
        request = data["request"]
        total = min(Decimal(request["budget_cap"]), Decimal(request["daily_cap"]) * request["duration_days"])
        daily = min(Decimal(request["daily_cap"]), total)
        title = data.get("title_plan")
        tests = [{"asset": {"id": a["id"], "version": a["version"]},
                  "title_plan": {"id": title["id"], "version": title["version"]} if title else None,
                  "hypothesis": "[演示] 待验证素材能否清晰传达已录入卖点。", "comparison_dimension": "creative",
                  "success_metric": "ctr", "target_value": "0.01"} for a in data["assets"]]
        return [{"content": {
            "summary_text": "[演示] 待人工确认的流程演示建议，不自动投放。", "objective_text": request["objective"],
            "audience_segments": [{"name": "录入目标人群", "description": product["target_audience"], "rationale": "基于商品资料，需要人工验证。"}],
            "budget_plan": {"currency": "CNY", "total_amount": format(total, ".2f"), "daily_cap": format(daily, ".2f"),
                            "duration_days": request["duration_days"], "allocations": [{"name": "演示测试", "amount": format(total, ".2f"), "rationale": "用于流程演示，不执行实际花费。"}]},
            "creative_tests": tests, "bid_strategy": "[演示] 出价由运营在平台人工评估设置。",
            "risk_controls": ["演示结果禁止当作真实分析或效果承诺"], "next_steps": ["人工核实素材、预算与目标"],
            "evidence": evidence, "missing_information": ["未调用真实策略模型", "缺少实际投放验证"],
        }}]
    if kind == "review_report":
        return [{"content": {"summary_text": "[演示] 指标由实际输入记录确定性计算；此说明未调用真实模型。",
                              "insights": [], "problem_judgments": [reason("现有数据不足以建立素材与效果之间的因果关系。")],
                              "next_actions": [{"action": "补充对照证据后开展下一轮诊断", "reason": "演示输出只用于验证业务闭环。",
                                                "priority": "high", "target_stage": "diagnosis", "evidence": evidence}],
                              "limitations": ["演示分析不构成真实结论"] + data.get("warnings", [])}}]
    raise ValueError("Unknown demo task")
