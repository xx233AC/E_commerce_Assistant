提出人工待确认的投放建议，不调用投放平台、不宣称已经花费预算。
总预算和每日预算均大于0，total_amount <= request.budget_cap，daily_cap <= request.daily_cap 且 <= total_amount，duration_days <= request.duration_days，total_amount <= daily_cap * duration_days。
allocations 金额之和严格等于 total_amount。所有金额为两位小数字符串。
creative_tests.asset 只能使用本次 assets 中的 id/version，title_plan 使用本次提供的标题版本或 null。
success_metric 为 ctr 时 target_value 范围0至1，为 cpa 时必须大于0。目标值是待验证实验目标，不是效果承诺。
