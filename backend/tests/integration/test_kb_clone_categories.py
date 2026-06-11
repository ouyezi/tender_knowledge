from sqlalchemy import select

from src.models.product_category import ProductCategory
from src.services import kb_service
from src.services.kb_clone_service import clone_kb
from src.services.product_category_service import create_category


def test_clone_kb_copies_product_categories(db_session):
    source = kb_service.create_kb(db_session, "source-with-cats")
    target = kb_service.create_kb(db_session, "target-empty")

    create_category(
        db_session,
        source.kb_id,
        category_name="福利产品",
        category_code="welfare",
        aliases=["员工福利"],
    )

    clone_kb(
        db_session,
        source.kb_id,
        target.kb_id,
        operator_id="admin",
        trace_id="trace-clone",
    )

    cloned = list(
        db_session.scalars(
            select(ProductCategory).where(ProductCategory.kb_id == target.kb_id)
        ).all()
    )
    assert len(cloned) == 1
    assert cloned[0].category_name == "福利产品"
    assert len(cloned[0].aliases) == 1
