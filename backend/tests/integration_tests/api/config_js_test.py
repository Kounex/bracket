import aiohttp
import pytest

from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import TEST_HOST, TEST_PORT, send_request_raw


@pytest.mark.asyncio(loop_scope="session")
async def test_config_js_endpoint(startup_and_shutdown_uvicorn_server: None) -> None:
    response = await send_request_raw(HTTPMethod.GET, "config.js")
    assert 'window.__BRACKET_CONFIG__ = { API_BASE_URL: "" };' in response


@pytest.mark.asyncio(loop_scope="session")
async def test_config_js_endpoint_is_not_cacheable(
    startup_and_shutdown_uvicorn_server: None,
) -> None:
    # config.js carries runtime config; caching it (e.g. by a CDN) breaks deployments.
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://{TEST_HOST}:{TEST_PORT}/config.js") as resp:
            assert resp.headers["Cache-Control"] == "no-store"
