import os
import shutil
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="bid-platform-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.db'}"
os.environ["FILE_STORAGE_PATH"] = str(TEST_ROOT / "files")
os.environ["TASKS_SYNC"] = "true"
os.environ["AI_ENABLED"] = "false"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "TestAdminPassword!123"
os.environ["SESSION_SECURE"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app, migrate_database
from app.models.user import User

migrate_database()


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(TEST_ROOT / "files", ignore_errors=True)
    (TEST_ROOT / "files").mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        db.add(
            User(
                username="admin",
                display_name="管理员",
                global_role="admin",
                password_hash=hash_password("TestAdminPassword!123"),
            )
        )
        db.commit()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "TestAdminPassword!123"}
        )
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture()
def published_config(client):
    company = client.post("/api/v1/companies", json={"code": "C1", "name": "测试企业"}).json()
    company_revision = client.post(
        f"/api/v1/companies/{company['id']}/revisions",
        json={
            "fields_json": {
                "公司名称": "测试供应商有限公司",
                "法定代表人": "张三",
                "注册地址": "测试地址",
            }
        },
    ).json()
    assert (
        client.post(f"/api/v1/company-revisions/{company_revision['id']}:publish").status_code
        == 200
    )
    product = client.post("/api/v1/products", json={"code": "P1", "name": "测试产品"}).json()
    product_revision = client.post(
        f"/api/v1/products/{product['id']}/revisions",
        json={
            "fields_json": {"产品名称": "测试产品"},
            "technical_fields_json": {"部署方式": "本地化"},
        },
    ).json()
    assert (
        client.post(f"/api/v1/product-revisions/{product_revision['id']}:publish").status_code
        == 200
    )
    redline = client.post(
        "/api/v1/redline-rules",
        json={
            "scope_type": "company",
            "scope_id": company["id"],
            "category": "付款方式",
            "position": "预付款不低于 20%",
            "condition_json": {"minimum_prepayment": 0.2},
            "action": "negotiate",
            "legal_review": False,
        },
    ).json()
    assert client.post(f"/api/v1/redline-rules/{redline['id']}:publish").status_code == 200
    nodes = [
        {
            "title": "技术方案",
            "content_json": [{"type": "paragraph", "text": "企业补充技术说明。"}],
            "children": [],
        }
    ]
    template = client.post(
        "/api/v1/templates",
        json={"name": "默认模板", "project_type": "service", "nodes_json": nodes},
    ).json()
    revisions = client.get(f"/api/v1/templates/{template['id']}/revisions").json()
    template_revision = revisions[0]
    assert (
        client.post(f"/api/v1/template-revisions/{template_revision['id']}:publish").status_code
        == 200
    )
    asset = client.post(
        "/api/v1/assets",
        json={
            "code": "A1",
            "title": "技术方案素材",
            "asset_type": "technical",
            "scope": "company",
            "section_key": "技术方案",
        },
    ).json()
    variant = client.post(
        f"/api/v1/assets/{asset['id']}/variants", json={"code": "standard", "name": "标准方案"}
    ).json()
    asset_revision = client.post(
        f"/api/v1/variants/{variant['id']}/revisions",
        json={"content_json": [{"type": "paragraph", "text": "已发布技术方案素材。"}]},
    ).json()
    assert client.post(f"/api/v1/asset-revisions/{asset_revision['id']}:publish").status_code == 200
    return {
        "company": company,
        "company_revision_id": company_revision["id"],
        "product": product,
        "product_revision_id": product_revision["id"],
        "template": template,
        "template_revision_id": template_revision["id"],
        "redline": redline,
        "asset": asset,
        "variant": variant,
        "asset_revision": asset_revision,
    }


@pytest.fixture()
def project(client, published_config):
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "示例服务项目",
            "code": "PRJ-001",
            "customer_name": "示例客户",
            "procurement_type": "公开招标",
            "industry": "education",
            "project_type": "service",
            "company_revision_id": published_config["company_revision_id"],
            "product_revision_id": published_config["product_revision_id"],
            "template_revision_id": published_config["template_revision_id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
