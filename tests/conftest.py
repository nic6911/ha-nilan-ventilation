import pytest
import pytest_socket

# The test harness disables sockets for hermetic tests. This suite talks to a
# real controller on the LAN, and on Windows asyncio needs a socketpair for its
# event loop, so keep sockets enabled.
pytest_socket.disable_socket = lambda *args, **kwargs: None
pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
