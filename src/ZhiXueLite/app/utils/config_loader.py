import json
from pathlib import Path
from fnmatch import fnmatch
from typing import Dict, List, Optional


class ConfigLoader:
    """
    配置加载器，用于加载和处理配置文件
    """
    DEFAULT_PATH = Path(__file__).parent.parent / "config" / "config.json"

    def __init__(self, config_path: Path = DEFAULT_PATH):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径，默认为相对路径 "config/config.json"
        """
        if config_path is not None:
            self.config_path = Path(config_path)

        self._load_config()

    def _load_config(self) -> None:
        """加载配置文件并将配置项设置为类属性"""
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                config_data = json.load(f)
                self._validate_config(config_data)

                self.version = config_data.get("version", "1.0")
                self.captcha_api = config_data.get("captcha_api", "")
                self.font_path = config_data.get("font_path", "")
                self.teachers = config_data.get("teachers", [])
                self.permissions = config_data.get("permissions", {})

                self._config = config_data
        except Exception as e:
            raise Exception(f"Error loading config file: {e}")

    def _validate_config(self, config_data: Dict) -> None:
        """
        验证配置是否包含所有必需的字段

        Args:
            config_data: 配置数据字典

        Raises:
            ValueError: 当缺少必填项时
        """
        required_fields = ["captcha_api", "font_path", "teachers", "permissions"]
        missing_fields = [field for field in required_fields if not config_data.get(field)]

        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # 验证教师账号信息是否完整
        for i, teacher in enumerate(config_data["teachers"]):
            teacher_required = ["username", "password", "method"]
            teacher_missing = [field for field in teacher_required if field not in teacher]
            if teacher_missing:
                raise ValueError(f"Missing required fields in teacher {i}: {', '.join(teacher_missing)}")
            if teacher["method"] not in ["changyan", "zhixue"]:
                raise ValueError(f"Invalid method for teacher {i}: {teacher['method']}")

        # 验证权限系统配置
        permissions = config_data["permissions"]
        if "roles" not in permissions:
            raise ValueError("Missing 'roles' in permissions configuration")

        # 验证角色配置
        for i, role in enumerate(permissions.get("roles", [])):
            role_required = ["name", "commands", "users"]
            role_missing = [field for field in role_required if field not in role]
            if role_missing:
                raise ValueError(f"Missing required fields in role {i}: {', '.join(role_missing)}")

    def reload_config(self) -> None:
        """重新加载配置文件"""
        self._load_config()

    def get_role_permissions(self, role_name: str) -> List[str]:
        """
        获取角色权限列表

        Args:
            role_name: 角色名称

        Returns:
            该角色可执行的命令列表
        """
        roles = self.permissions.get("roles", [])
        for role in roles:
            if role.get("name") == role_name:
                return role.get("commands", [])
        return []

    def get_user_role(self, user_id: int) -> Optional[str]:
        """
        获取用户角色

        Args:
            user_id: 用户ID

        Returns:
            用户角色名称，如果用户没有角色则返回 None
        """
        roles = self.permissions.get("roles", [])
        for role in roles:
            if user_id in role.get("users", []):
                return role.get("name")
        return None

    def get_user_permissions(self, user_id: int) -> Dict[str, List[str]]:
        """
        获取用户特定的权限

        Args:
            user_id: 用户 ID

        Returns:
            包含白名单和黑名单的字典
        """
        users = self.permissions.get("users", [])
        for user in users:
            if user.get("user") == user_id:
                return {
                    "whitelist": user.get("whitelist", []),
                    "blacklist": user.get("blacklist", [])
                }
        return {"whitelist": [], "blacklist": []}

    def check_permission(self, user_id: int, command: str) -> bool:
        """
        检查用户是否有执行某命令的权限

        Args:
            user_id: 用户 ID
            command: 命令名称

        Returns:
            是否有权限
        """
        # 获取用户角色和对应的权限
        role = self.get_user_role(user_id)
        role_permissions = self.get_role_permissions(role or "guest")

        # 获取用户特定的权限
        user_permissions = self.get_user_permissions(user_id)

        # 检查用户黑名单 - 优先级最高
        for pattern in user_permissions["blacklist"]:
            if fnmatch(command, pattern):
                return False

        # 检查用户白名单 - 第二优先级
        for pattern in user_permissions["whitelist"]:
            if fnmatch(command, pattern):
                return True

        # 检查角色权限 - 第三优先级
        for pattern in role_permissions:
            if fnmatch(command, pattern):
                return True

        return False


# 创建一个全局的配置加载器实例
config = ConfigLoader()
