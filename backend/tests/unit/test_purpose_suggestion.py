from src.models.file_import import FilePurpose
from src.services.purpose_suggestion import suggest_from_filename


def test_template_keyword():
    r = suggest_from_filename("餐补模板.docx", "docx")
    assert r.suggested_purpose == FilePurpose.template_file


def test_actual_bid_keyword():
    r = suggest_from_filename("某项目投标文件.pdf", "pdf")
    assert r.suggested_purpose == FilePurpose.actual_bid


def test_qualification_keyword():
    r = suggest_from_filename("企业资质汇编.pdf", "pdf")
    assert r.suggested_purpose == FilePurpose.qualification
