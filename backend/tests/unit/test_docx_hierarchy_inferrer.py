from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import infer_hierarchy
from src.services.docx_tree_materializer import materialize_outline_nodes


def _block(index: int, text: str, style_name: str | None = "Normal") -> RawBlock:
    return RawBlock(index=index, block_type="paragraph", text=text, style_name=style_name, has_image=False)


def test_response_letter_body_paragraphs_not_headings():
    blocks = [
        _block(0, "二、参选响应函", "Heading 1"),
        _block(1, "致  鼎信数智技术集团股份有限公司 （比选人名称）：", "Body Text"),
        _block(
            2,
            "1. 根据贵方“鼎信数智技术集团股份有限公司2026-2029年度职工工作餐服务项目（项目名称）”（DXZB202604002（项目编号））的比选文件，经我方仔细研究，本",
            "Normal",
        ),
        _block(3, "2. 我方的参选文件包括下列内容：", "Normal"),
        _block(4, "三、参选响应表", "Heading 1"),
    ]
    inferred = infer_hierarchy(blocks)
    nodes = materialize_outline_nodes(inferred, blocks)
    titles = [n.title for n in nodes]
    assert "二、参选响应函" in titles
    assert "三、参选响应表" in titles
    assert not any(t.startswith("1. 根据贵方") for t in titles)
    assert not any(t.startswith("2. 我方的参选文件") for t in titles)


def test_nested_section_body_paragraphs_not_headings():
    blocks = [
        _block(0, "6.1.3库存管理", "Heading 4"),
        _block(1, "库存管理是餐饮供应链保障能力的核心环节。", "Normal"),
        _block(2, "（一）采购验收管理（餐饮供应链源头库存保障）", "Normal"),
        _block(
            3,
            "1. 自营餐饮食材采购验收：针对平台自营餐饮相关选品，在严格执行准入资质审查的基础上，由采购部、仓储物流部及品控部门协同，在采购验收环节开展",
            "Normal",
        ),
        _block(4, "（二）仓储管理规范（餐饮供应链中间库存保障）", "Normal"),
    ]
    inferred = infer_hierarchy(blocks)
    nodes = materialize_outline_nodes(inferred, blocks)
    titles = [n.title for n in nodes]
    assert "6.1.3库存管理" in titles
    assert any("采购验收管理" in t for t in titles)
    assert not any(t.startswith("1. 自营餐饮食材采购验收") for t in titles)


def test_chinese_list_under_deep_section_nests_correctly():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "3.3.3仓储物流能力介绍", "Heading 4"),
        _block(2, "食品仓储管理说明段落。", "Normal"),
        _block(3, "一、温度控制", "Normal"),
        _block(4, "二、分类储存", "Normal"),
    ]
    inferred = infer_hierarchy(blocks)
    nodes = materialize_outline_nodes(inferred, blocks)
    by_title = {n.title: n for n in nodes}
    assert by_title["3.3.3仓储物流能力介绍"].level == 4
    temp = by_title["一、温度控制"]
    storage = by_title["3.3.3仓储物流能力介绍"]
    classify = by_title["二、分类储存"]
    assert temp.level == 5
    assert classify.level == 5
    assert temp.parent_temp_id == storage.temp_id
    assert classify.parent_temp_id == storage.temp_id


def test_heading_style_numeric_section_kept():
    blocks = [
        _block(0, "三、技术方案", "Heading 1"),
        _block(1, "1.参选人业绩", "Heading 2"),
    ]
    inferred = infer_hierarchy(blocks)
    nodes = materialize_outline_nodes(inferred, blocks)
    assert any(n.title == "1.参选人业绩" for n in nodes)


def test_embedded_document_skipped_and_main_outline_resumes():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "6.2资金安全保障方案", "Heading 3"),
        _block(2, "6.2.3资金存管及风险预警", "Heading 4"),
        _block(3, "我司具备完善的风险预警系统：", "Normal"),
        _block(4, "第一章 总则", "Normal"),
        _block(5, "1.1 手册目的", "Normal (Web)"),
        _block(6, "第七章 文档与应急管理", "Normal"),
        _block(7, "7.2 应急预案", "Normal (Web)"),
        _block(8, "6.3服务持续保障方案", "Heading 3"),
        _block(9, "6.3.1仓储能力介绍", "Heading 4"),
    ]
    inferred = infer_hierarchy(blocks)
    titles = [h.title for h in inferred.headings]
    assert "6.2.3资金存管及风险预警" in titles
    assert "6.3服务持续保障方案" in titles
    assert "第一章 总则" not in titles
    assert "7.2 应急预案" not in titles
    assert len(inferred.embedded_regions) == 1
    assert inferred.embedded_regions[0].resume_title == "6.3服务持续保障方案"

    by_title = {h.title: h for h in inferred.headings}
    resume = by_title["6.3服务持续保障方案"]
    fund_parent = by_title["6.2资金安全保障方案"]
    assert resume.parent_block_index == fund_parent.parent_block_index
    assert resume.parent_block_index == by_title["六、服务方案"].block_index


def test_embedded_start_after_chinese_list_section():
    blocks = [
        _block(0, "8.9食物中毒突发事件应急预案", "Heading 3"),
        _block(1, "（一）应急组织", "Normal"),
        _block(2, "第一章 总则", "Normal"),
        _block(3, "1.1 手册目的", "Normal (Web)"),
        _block(4, "8.10本项目应急预案工作小组", "Heading 3"),
    ]
    inferred = infer_hierarchy(blocks)
    titles = [h.title for h in inferred.headings]
    assert "第一章 总则" not in titles
    assert "8.10本项目应急预案工作小组" in titles


def test_extreme_weather_section_nests_chinese_paren_children():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "8.应急预案", "Heading 2"),
        _block(2, "8.5极端天气应急响应方案", "Heading 3"),
        _block(3, "一、方案总则", "Normal"),
        _block(4, "（一）编制目的", "Normal"),
        _block(5, "（二）适用范围", "Normal"),
        _block(6, "二、组织架构及职责分工", "Normal"),
    ]
    inferred = infer_hierarchy(blocks)
    by_title = {h.title: h for h in inferred.headings}
    section = by_title["8.5极端天气应急响应方案"]
    general = by_title["一、方案总则"]
    purpose = by_title["（一）编制目的"]
    scope = by_title["（二）适用范围"]
    org = by_title["二、组织架构及职责分工"]
    assert general.parent_block_index == section.block_index
    assert purpose.parent_block_index == general.block_index
    assert scope.parent_block_index == general.block_index
    assert org.parent_block_index == section.block_index
    assert purpose.level == 5
    assert org.level == 4


def test_embedded_island_resumes_at_chinese_list_sibling():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "8.应急预案", "Heading 2"),
        _block(2, "8.4特殊防疫时期的食品安全管控及实施方案", "Heading 3"),
        _block(3, "一、管理制度", "Normal"),
        _block(4, "第一章 总则", "Normal"),
        _block(5, "第二章 平台管理责任与组织", "Normal"),
        _block(6, "二、实施情况", "Normal"),
        _block(7, "（一）组织架构与职责分工", "Normal"),
        _block(8, "8.5极端天气应急响应方案", "Heading 3"),
    ]
    inferred = infer_hierarchy(blocks)
    titles = [h.title for h in inferred.headings]
    assert "二、实施情况" in titles
    assert "（一）组织架构与职责分工" in titles
    assert "第一章 总则" not in titles
    by_title = {h.title: h for h in inferred.headings}
    assert by_title["二、实施情况"].parent_block_index == by_title["8.4特殊防疫时期的食品安全管控及实施方案"].block_index


def test_food_safety_vendor_subsections_under_8_2():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "8.应急预案", "Heading 2"),
        _block(2, "8.2食品安全突发事件应急处理响应方案", "Heading 3"),
        _block(3, "一、东方福利网食品安全突发事件应急预案", "Normal"),
        _block(4, "二、合作方淘宝闪购的应急预案", "Normal"),
        _block(5, "3.2 食品安全事故：是指食源性疾病、食品污染等源于食品，对人体健康有危害或者可能有危害的事故。", "Normal"),
        _block(6, "8.2 进展报告内容：事故发展与变化、处理进程、事故原因等，在进展报告中既要报告新发生的情况，也要对初次报告的情况进行补充和修正。", "Normal"),
        _block(7, "二、合作方京东外卖的应急预案", "Normal"),
        _block(8, "第一章 总则", "Normal"),
        _block(9, "1.1 手册目的", "Normal (Web)"),
        _block(10, "三、合作方美团外卖的应急预案", "Normal"),
        _block(11, "（一）发生单起食品质量突发事件投诉", "Normal"),
        _block(12, "8.3食品安全突发应急处理响应流程", "Heading 3"),
    ]
    inferred = infer_hierarchy(blocks)
    titles = [h.title for h in inferred.headings]
    assert "8.2食品安全突发事件应急处理响应方案" in titles
    assert "一、东方福利网食品安全突发事件应急预案" in titles
    assert "二、合作方淘宝闪购的应急预案" in titles
    assert "二、合作方京东外卖的应急预案" in titles
    assert "三、合作方美团外卖的应急预案" in titles
    assert "8.3食品安全突发应急处理响应流程" in titles
    assert not any(t.startswith("3.2 食品安全事故") for t in titles)
    assert not any(t.startswith("8.2 进展报告内容") for t in titles)
    assert "第一章 总则" not in titles

    by_title = {h.title: h for h in inferred.headings}
    section_82 = by_title["8.2食品安全突发事件应急处理响应方案"]
    for child_title in (
        "一、东方福利网食品安全突发事件应急预案",
        "二、合作方淘宝闪购的应急预案",
        "二、合作方京东外卖的应急预案",
        "三、合作方美团外卖的应急预案",
    ):
        assert by_title[child_title].parent_block_index == section_82.block_index
    assert by_title["8.3食品安全突发应急处理响应流程"].parent_block_index == by_title["8.应急预案"].block_index


def test_heading_section_numeric_micro_outline_nests_under_parent():
    blocks = [
        _block(0, "六、服务方案", "Heading 1"),
        _block(1, "8.应急预案", "Heading 2"),
        _block(2, "8.7系统故障与商家异常应急预案", "Heading 3"),
        _block(3, "1. 总则与目标", "Normal"),
        _block(4, "1.1 目的", "Normal"),
        _block(5, "1.2 适用范围", "Normal"),
        _block(6, "2. 应急组织架构与职责", "Normal"),
        _block(7, "4. 场景化应急处置流程", "Normal"),
        _block(8, "4.1 平台系统故障（服务器宕机、数据库死锁等）", "Normal"),
        _block(9, "8.8意外伤害的应急处理预案", "Heading 3"),
    ]
    inferred = infer_hierarchy(blocks)
    titles = [h.title for h in inferred.headings]
    assert "8.7系统故障与商家异常应急预案" in titles
    assert "1. 总则与目标" in titles
    assert "1.1 目的" in titles
    assert "4.1 平台系统故障（服务器宕机、数据库死锁等）" in titles
    assert "8.8意外伤害的应急处理预案" in titles

    by_title = {h.title: h for h in inferred.headings}
    section = by_title["8.7系统故障与商家异常应急预案"]
    general = by_title["1. 总则与目标"]
    purpose = by_title["1.1 目的"]
    scene = by_title["4. 场景化应急处置流程"]
    platform = by_title["4.1 平台系统故障（服务器宕机、数据库死锁等）"]
    assert general.parent_block_index == section.block_index
    assert purpose.parent_block_index == general.block_index
    assert scene.parent_block_index == section.block_index
    assert platform.parent_block_index == scene.block_index
    assert purpose.level == 5
    assert platform.level == 5

