<h1 align="center">- ZhiXue Lite -</h1>

<p align="center">
<img src="https://img.shields.io/github/license/amakerlife/ZhiXue-Lite-backend" alt="License" />
<img src="https://img.shields.io/github/last-commit/amakerlife/ZhiXue-Lite-backend">
</p>
<p align="center">
    <img src="https://socialify.git.ci/amakerlife/ZhiXue-Lite-backend/image?description=1&forks=1&issues=1&language=1&name=1&owner=1&pulls=1&stargazers=1&theme=Light">
</p>

对接智学网官方 API 的轻量 Web 应用。

---

## 快速开始

```bash
git clone https://github.com/amakerlife/ZhiXue-Lite-backend
cd ZhiXue-Lite-backend
mv ./example.env ./.env
vim ./.env
pip install .
flask run
```

## Todo List

get_user api 管理员返回是否在 su 模式

拉取联考分数数据时，可以选择拉取某些学校的数据

支持选择学校（后端返回学校列表）

考试数据库存储考试年级、级别、学校(list)等详细信息

学生、教师自动选择合适的登录方式，并保存

在数据库层面使用 limit 和 offset 分页

成绩详情返回各科总参考人数

## 提示

使用本项目前，请确保拥有目标学校具有查看至少校级报告权限的教师账号。如需全部功能，请添加校长/管理员账号。本项目不会提供验证码 API，请自行解决。
