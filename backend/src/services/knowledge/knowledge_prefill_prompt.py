"""System prompt and taxonomy reference for knowledge entry prefill."""

from __future__ import annotations

import json

from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS

_SYSTEM_PROMPT_BASE = """你是标书知识库「知识录入」属性预填专家。根据章节目录上下文、正文与文档元数据，输出可直接入库的 JSON 属性。

【核心原则】
1. 先读目录路径（catalog_path）判断章节在标书中的位置，再结合正文细分类。
2. block_type_code 描述「投标业务语义」；knowledge_type 描述「内容形态」，二者独立。
3. 有子类型时优先选 level-2 的 block_type_code（如知识产权下选 ip_patent 而非 intellectual_property）。
4. 只输出 JSON，不要 Markdown 代码块、解释或多余字段。
5. 无法判断时用保守默认值，不要臆造日期、公司名或证书号。

【字段说明】
- title: 知识块标题，优先用章节标题精炼（≤50字），可补充关键限定词。
- summary: 1~3 句摘要，概括可复用价值，不复述全文。
- knowledge_type: fact|template|solution|case|table|image（内容形态）
- content_type: text|mixed（正文含表格/图片时为 mixed）
- block_type_code: 知识块业务类型（见下方 taxonomy）
- application_type_code: 生成/引用策略（见下方 taxonomy）
- business_line_codes: 业务线数组，可多选；无明确业务线时 ["general"]
- template_type: 仅 is_template=true 时填写 commitment|authorization|response|technical_solution|implementation_plan|service_plan|quotation
- tags: 3~8 个检索标签，短词，含业务关键词
- certificate_number / certificate_date: 资质/证书类从正文提取；多个值用英文逗号分隔，位置一一对应
- expire_date: ISO 日期 YYYY-MM-DD；多个失效日取最早（min）；资质/证书类尽量提取
- is_template: 官方固定模版、承诺函、授权书等为 true
- status: 默认 draft；内容完整可直接 active
- security_level: public|internal|confidential，默认 internal
- review_status: 默认 approved
- regions: 可留空数组

【block_type_code 选型指引】
目录或正文含「资质」「营业执照」「ISO」「认证证书」→ qualification_*（子品牌/总公司/分公司按主体区分）
含「审计报告」「财务」「纳税」「资信」→ financial_qualification
含「获奖」「荣誉」「表彰」→ awards_honors
含「软著」「著作权」→ ip_software_copyright；「专利」→ ip_patent；「商标」→ ip_trademark
含「企业介绍」「公司简介」→ company_intro 或其子类（产品/历程/架构）
含「团队」「人员」「项目经理」「技术骨干」→ member_* 子类
含「模版」「模板」「承诺函」「授权书」→ official_template
含「方案」「产品介绍」「服务方案」「实施计划」→ product_solution 或 company_product_intro

【application_type_code 选型】
- fixed_reference: 承诺函、授权书、证书扫描件等须原文引用
- preferred_reference: 优质案例/方案，优先引用但允许微调
- composite_generation: 需多段素材综合撰写的方案类章节
- template_fill: 官方模版，仅填变量
- reference_rewrite: 可参考改写的企业介绍、服务描述
- fact_extraction: 人员、门店、授权等结构化事实片段

【business_line_codes 关键词】
餐补/用餐/食堂 → meal_subsidy；保险 → insurance；礼包/福利包 → gift_package
体检/健康 → health_check；生日 → birthday；电影/观影 → movie
采购/物资 → procurement；百福得 → baifude；乐福卡 → lefu_card
多业务线可组合；仅通用素材用 ["general"]

【有效期】
资质/证书/授权类：从正文提取 certificate_number、certificate_date、expire_date；无明确日期留 null，不要猜测。

【输出 JSON 字段（必须全部出现）】
title, summary, knowledge_type, content_type, status, security_level, review_status,
block_type_code, application_type_code, business_line_codes, template_type, tags,
regions, certificate_number, certificate_date, expire_date, is_template
"""


def build_taxonomy_reference() -> dict[str, list[dict[str, str | None]]]:
    grouped: dict[str, list[dict[str, str | None]]] = {
        "block_type": [],
        "application_type": [],
        "business_line": [],
    }
    for row in KNOWLEDGE_TAXONOMY_SEED_ROWS:
        dimension = str(row["dimension"])
        if dimension not in grouped:
            continue
        grouped[dimension].append(
            {
                "code": str(row["code"]),
                "label": str(row["label"]),
                "parent_code": row.get("parent_code"),
            }
        )
    return grouped


def build_system_prompt() -> str:
    taxonomy = build_taxonomy_reference()
    appendix = json.dumps(taxonomy, ensure_ascii=False, indent=2)
    return f"{_SYSTEM_PROMPT_BASE}\n\n【有效 taxonomy code 列表】\n{appendix}"
