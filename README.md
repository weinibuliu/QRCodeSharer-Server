# QRCodeSharer-Server

这是 [QRCodeSharer](https://github.com/weinibuliu/QRCodeSharer)的一个后端实现。提供其所需的 [API 接口](#api-接口)。

项目默认使用 SQLite3 数据库，但受益于 [SQLModel](https://sqlmodel.tiangolo.com/)，你可以轻松地迁移到其他数据库，比如 MySQL 。

项目提供了 [uvicorn](./startup.py) 与 [gunicorn](./startup.sh) 两种启动方式，请根据需要选择。

## SQLite3 注意事项

项目默认启用了以下设置

```python
with engine.connect() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL") # 启用WAL模式
    conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
    conn.exec_driver_sql("PRAGMA busy_timeout=30000")  # 30秒忙等待
    conn.exec_driver_sql("PRAGMA wal_autocheckpoint=1000")  # 每1000页自动checkpoint
```

## API 接口

### 测试连接

```bash
GET /
```

| 参数 | 类型   | 说明         |
| ---- | ------ | ------------ |
| id   | int    | 用户 ID      |
| auth | string | 用户认证密钥 |

### 获取二维码内容

```bash
GET /code/get
```

| 参数           | 类型   | 说明          |
| -------------- | ------ | ------------- |
| follow_user_id | int    | 订阅的用户 ID |
| id             | int    | 当前用户 ID   |
| auth           | string | 用户认证密钥  |

响应：

```json
{
  "content": "https://example.com",
  "update_at": 1703577600
}
```

### 更新二维码内容

```bash
PATCH /code/patch
```

| 参数 | 类型   | 说明         |
| ---- | ------ | ------------ |
| id   | int    | 用户 ID      |
| auth | string | 用户认证密钥 |

请求体：

```json
{
  "content": "https://example.com"
}
```

### 获取用户信息

```bash
GET /user/get
```

## 鸣谢

- FastAPI
- SQLModel
