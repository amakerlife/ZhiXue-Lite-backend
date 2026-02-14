<h1 align="center">- ZhiXue Lite Backend -</h1>

<p align="center">
<img src="https://img.shields.io/github/license/amakerlife/ZhiXue-Lite-backend" alt="License" />
<img src="https://img.shields.io/github/last-commit/amakerlife/ZhiXue-Lite-backend">
</p>
<p align="center">
    <img src="https://socialify.git.ci/amakerlife/ZhiXue-Lite-backend/image?description=1&forks=1&issues=1&language=1&name=1&owner=1&pulls=1&stargazers=1&theme=Light">
</p>

对接智学网官方 API 的轻量 Web 后端应用。

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

- [ ] 使用另一个 API 获取总分数据，避免某些问题（可能包括阅卷中）
- [ ] 添加任务优先级（例如发送验证邮件优先级最高），顺序执行
- [ ] 支持选择学校（后端返回学校列表）
- [ ] 添加忘记密码
- [ ] 考试数据库存储考试年级、级别等详细信息
- [ ] 学生、教师自动选择合适的登录方式，并保存
- [ ] 重新拉取成绩在覆盖更新之后，额外做一次比对，把本地有但远端没有的记录标记删除或软删除
- [ ] 基于 Go 重写
- [x] [Go 重写后实现]后台任务异步轮询，启动子进程后立即返回在每次轮询时检查进程状态
- [x] [Go 重写后实现]在任务列表为有权限用户显示详细信息

## 提示

使用本项目前，请确保拥有目标学校具有查看至少校级报告权限的教师账号。如需全部功能，请添加校长/管理员账号。本项目不会提供验证码 API，请自行解决。
