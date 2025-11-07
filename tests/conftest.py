"""
pytest 配置文件

这个文件定义了测试中使用的 fixtures（测试夹具）
fixtures 是测试的"准备工作"，在测试运行前自动执行
"""
import os
import pytest


# 在导入 app 之前设置测试环境变量，防止加载生产配置
os.environ["FLASK_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # 使用内存数据库
os.environ["TURNSTILE_ENABLED"] = "False"
os.environ["CAPTCHA_URL"] = "http://fake-captcha.test"
os.environ["FONT_PATH"] = "/fake/font/path"

from app import create_app
from app.database import db as _db


@pytest.fixture(scope="session")
def app():
    """
    创建测试用的 Flask 应用实例

    scope="session" 表示整个测试会话只创建一次
    这样可以提高测试效率
    """
    # 创建应用实例，会自动加载 TestingConfig
    app = create_app()

    return app


@pytest.fixture(scope="function")
def db(app):
    """
    创建测试用的数据库

    scope="function" 表示每个测试函数运行前都会重新创建
    这样保证了测试之间的独立性
    """
    with app.app_context():
        _db.create_all()  # 创建所有表
        yield _db  # 在这里暂停，让测试函数使用数据库
        _db.session.remove()  # 清理会话
        _db.drop_all()  # 删除所有表


@pytest.fixture
def client(app, db):
    """
    创建测试客户端

    test client 可以模拟 HTTP 请求，就像用浏览器访问一样
    但它不需要真的启动服务器
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    创建 CLI 测试运行器

    用于测试 Flask 的命令行命令
    """
    return app.test_cli_runner()


def pytest_sessionfinish(session, exitstatus):
    """
    pytest 钩子：测试会话结束后自动清理

    这个函数会在所有测试运行完成后自动执行
    用于清理测试过程中产生的临时文件
    """
    import shutil
    from pathlib import Path

    # flask_session 目录路径（在项目根目录）
    flask_session_dir = Path(__file__).parent.parent / "flask_session"

    # 如果目录存在，删除它
    if flask_session_dir.exists():
        shutil.rmtree(flask_session_dir)
        print(f"\n[Test Cleanup] Removed flask_session directory: {flask_session_dir}")
