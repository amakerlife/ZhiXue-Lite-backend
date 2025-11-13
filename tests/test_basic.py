"""
基础功能测试

这个文件测试应用的基本功能，不涉及复杂的业务逻辑
是学习单元测试的最佳起点
"""


def test_app_exists(app):
    """
    测试应用实例是否成功创建

    参数 app 来自 conftest.py 中的 app fixture
    """
    assert app is not None


def test_app_is_testing(app):
    """
    测试应用是否处于测试模式

    验证配置是否正确加载
    """
    assert app.config["TESTING"] is True


def test_ping_endpoint(client):
    """
    测试 /ping 健康检查端点
    """
    response = client.get("/ping")

    assert response.status_code == 200

    data = response.get_json()

    assert data["success"] is True
    assert data["message"] == "pong"
    assert "timestamp" in data
