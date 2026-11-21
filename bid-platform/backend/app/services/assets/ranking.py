from datetime import UTC, datetime

from app.models.asset import Asset, AssetRevision
from app.models.project import Project
from app.services.structure.rules import titles_match


def asset_matches(
    asset: Asset, project: Project, product_id: str, section_title: str, section_key: str
) -> bool:
    today = datetime.now(UTC).date()
    if asset.status != "published":
        return False
    if asset.valid_from and asset.valid_from > today or asset.valid_to and asset.valid_to < today:
        return False
    if asset.customer_name and asset.customer_name != project.customer_name:
        return False
    if asset.product_id and asset.product_id != product_id:
        return False
    if asset.industry and asset.industry != project.industry:
        return False
    if asset.project_type and asset.project_type != project.project_type:
        return False
    if asset.scope == "customer" and asset.customer_name != project.customer_name:
        return False
    if asset.scope == "product" and asset.product_id != product_id:
        return False
    if asset.scope == "industry" and asset.industry != project.industry:
        return False
    if asset.section_key:
        return titles_match(asset.section_key, section_key) or titles_match(
            asset.section_key, section_title
        )
    return titles_match(asset.title, section_title) or asset.asset_type in {"general", "shared"}


def rank_asset(
    asset: Asset, revision: AssetRevision, project: Project, product_id: str
) -> tuple[float, list[str]]:
    score = 40.0
    reasons = ["企业通用且当前有效"]
    if asset.industry and asset.industry == project.industry:
        score += 10
        reasons = ["行业范围匹配且当前有效"]
    if asset.product_id and asset.product_id == product_id:
        score += 20
        reasons = ["产品线匹配且当前有效"]
        if asset.industry and asset.industry == project.industry:
            score += 10
            reasons = ["同产品、同行业且当前有效"]
    if asset.customer_name == project.customer_name:
        score += 30
        reasons = ["同客户专属素材"]
        if asset.product_id == product_id:
            score += 10
            reasons = ["同客户且同产品的专属素材"]
    if revision.published_at:
        published_at = revision.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        score += published_at.timestamp() / 1_000_000_000_000
    return score, reasons
