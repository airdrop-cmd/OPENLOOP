#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from art import text2art
from colorama import Fore, init
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
import questionary
from questionary import Style
import glob
import shutil

init(autoreset=True)
console = Console()

MODULES = (
    "Registration",
    "Tasks",
    "Farm",
    "Exit",
)
MODULES_DATA = {
    "🔑 Registration": "main.py",
    "📝 Tasks": "task.py",
    "🔮 Farm": "farm.py",
    "❌ Exit": "exit",
}

custom_style = Style([
    ('selected', 'fg:magenta bold'),
    ('pointer', 'fg:magenta bold'),
    ('question', ''),
    ('answer', ''),
    ('separator', ''),
])

DATA_DIR = "data"

def count_lines(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f if _.strip())

def file_size(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return "0 B"
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} B"
    elif size < 1024*1024:
        return f"{size//1024} KB"
    else:
        return f"{size//(1024*1024)} MB"

def show_logo():
    title = text2art("AIRDROP", font="BIG")
    balloons = "🔮" * 28 + "\n"
    styled_title = Text(title + balloons, style="purple")
    version_line = " VERSION: 1.1                   https://t.me/serversdrop"
    version_telegram = Text(version_line, style="#FFD700")
    dev_panel = Panel(
        Text.assemble(
            styled_title,
            "\n",
            version_telegram
        ),
        border_style="purple",
        expand=False,
        title="",
        subtitle="[italic]AirDrop[/italic]",
    )
    console.print(dev_panel)
    print()
    # Вернем ширину ascii-art для нижней рамки
    return max(len(line) for line in title.splitlines())

def show_config_table(panel_width):
    openloop_title = text2art("OPENLOOP", font="BIG")
    console.print(Text(openloop_title, style="bold cyan"))
    table = Table(
        title="",
        box=box.ROUNDED,
        border_style="#FF4500",
        padding=(0, 1),
        show_lines=False,
    )
    table.add_column("Parameter", style="#875fd7")
    table.add_column("Value", style="#af5faf")
    table.add_row("Emails", str(count_lines("email.txt")))
    table.add_row("Proxies", str(count_lines("proxies.txt")))
    table.add_row("Invite codes", str(count_lines("invitecode.txt")))
    table.add_row("Failed registrations", str(count_lines("failed_reg.txt")))
    table.add_row("Failed logins", str(count_lines("failed_login.txt")))
    table.add_row("Failed tasks", str(count_lines("failed_task.txt")))
    table.add_row("ProxyFarm", str(count_lines("proxyFarm.txt")))
    panel = Panel(
        table,
        expand=False,
        border_style="purple",
        subtitle="",
        padding=(0, 2),
        width=panel_width + 8
    )
    console.print(panel)
    print()  # Одна пустая строка после таблицы

def select_module():
    answer = questionary.select(
        "",
        choices=[
            "🔑 Registration",
            "📝 Tasks",
            "🔮 Farm",
            "❌ Exit"
        ],
        style=Style([
            ('selected', 'fg:magenta bold'),
            ('pointer', 'fg:magenta bold'),
            ('question', ''),
            ('answer', ''),
            ('separator', ''),
        ]),
        qmark="",
        pointer="»",
        instruction="Menu:",
    ).ask()
    return answer

def run_selected_module(module):
    if module == "❌ Exit":
        sys.exit(0)
    script = MODULES_DATA[module]
    process = subprocess.Popen([sys.executable, script], stdout=sys.stdout, stderr=sys.stderr)
    process.wait()
    input(Fore.LIGHTBLACK_EX + "Нажмите Enter для возврата в меню...")
    os.system("cls" if os.name == "nt" else "clear")

def clear_below():
    print("\033[J", end='')

def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        panel_width = show_logo()
        show_config_table(panel_width)
        clear_below()  # Очищаем только область ниже таблицы
        module = select_module()
        if module:
            run_selected_module(module)
        else:
            break

if __name__ == "__main__":
    main()