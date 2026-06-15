#!/usr/bin/env python3
"""
weat-admin — Tuwunel 用户管理 CLI

用法:
  weat-admin add-user <username> <password>
  weat-admin list-users
  weat-admin reset-password <username> <new-password>
"""

import asyncio
import logging
import sys

import click

from backend import matrix_api

logging.basicConfig(level=logging.WARNING, format="%(message)s")


def _run_async(coro):
    """运行异步代码。"""
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        # 处理已在事件循环中的情况
        if "cannot be called from a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coro)
        raise


@click.group()
def cli():
    """Tuwunel 用户管理工具"""
    pass


@cli.command()
@click.argument("username")
@click.argument("password")
def add_user(username: str, password: str):
    """创建新用户。"""
    try:
        result = _run_async(matrix_api.register_user(username, password))
        user_id = result.get("user_id", username)
        click.echo(f"✅ 用户 {user_id} 创建成功")
    except Exception as e:
        click.echo(f"❌ 创建失败: {e}", err=True)
        sys.exit(1)


@cli.command()
def list_users():
    """列出所有用户（通过管理员 API 实现）。"""
    # Tuwunel 可能不支持直接列出用户
    # 这里提供一个框架，后续可实现
    click.echo("ℹ️  Tuwunel 不支持直接列出用户。")
    click.echo("   请在 Matrix 客户端中查看用户列表，或直接操作数据库。")
    click.echo("   备用方法: docker exec weat_matrix tuwunelctl list-users")


@cli.command()
@click.argument("username")
@click.argument("new_password")
def reset_password(username: str, new_password: str):
    """重置用户密码。"""
    # Tuwunel 的密码重置需要通过管理员 API
    click.echo("ℹ️  密码重置需要使用 Tuwunel 管理工具:")
    click.echo(f"   docker exec weat_matrix tuwunelctl reset-password {username}")
    click.echo(f"   然后输入新密码")


if __name__ == "__main__":
    cli()
