import httpx
import pytest

from irrigationd.config import Config, StorageConfig, WebConfig
from irrigationd.web.app import create_app


@pytest.mark.asyncio
async def test_html_urls_include_configured_root_path(tmp_path) -> None:
    app = create_app(
        Config(
            web=WebConfig(root_path="/watering"),
            storage=StorageConfig(path=str(tmp_path / "irrigation.db")),
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/watering/zones")
        assert response.status_code == 200
        assert 'id="zone-create-dialog"' in response.text
        assert 'action="http://test/watering/ui/zones"' in response.text
        assert 'href="http://test/watering/overview"' in response.text
        assert "http://test/watering/static/style.css" in response.text
        assert "http://test/watering/static/dashboard.css" in response.text

        static = await client.get("/watering/static/style.css")
        assert static.status_code == 200

        redirect = await client.get("/watering/", follow_redirects=False)
        assert redirect.headers["location"] == "http://test/watering/zones"


@pytest.mark.parametrize("root_path", ["watering", "/watering/"])
def test_invalid_root_path_is_rejected(root_path: str) -> None:
    with pytest.raises(ValueError):
        WebConfig(root_path=root_path)
