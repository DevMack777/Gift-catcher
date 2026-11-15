from aiogram.types import InlineKeyboardButton as B, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Каталог", callback_data="catalog:0")
    return kb.as_markup()


def catalog_kb(items: list, selected: set[str], page: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    pages = max(1, -(-len(items) // config.PAGE_SIZE))
    page = min(max(page, 0), pages - 1)
    for r in items[page * config.PAGE_SIZE:(page + 1) * config.PAGE_SIZE]:
        mark = "✅" if r["slug"] in selected else "▫️"
        kb.row(B(text=f"{mark} {r['name']} · {r['slug']}", callback_data=f"tog:{r['slug']}:{page}"))
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"catalog:{page - 1}"))
    nav.append(B(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(B(text="▶️", callback_data=f"catalog:{page + 1}"))
    kb.row(*nav)
    kb.row(B(text="Выбрать все 1.1.1", callback_data=f"all:{page}"),
           B(text="Модель", callback_data="model"))
    kb.row(B(text="Роя (А–Я)", callback_data="alpha"),
           B(text="🔎 Идти / Поиск", callback_data="go"))
    kb.row(B(text="⬅️ Назад", callback_data="back"))
    return kb.as_markup()


def models_kb(slug: str, models: list[str], current: str | None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(B(text=("✅ " if current is None else "") + "Портфель (все модели)",
             callback_data=f"mdl:{slug}:*"))
    for i, m in enumerate(models):
        kb.row(B(text=("✅ " if current == m else "") + m, callback_data=f"mdl:{slug}:{i}"))
    kb.row(B(text="⬅️ Назад", callback_data="catalog:0"))
    return kb.as_markup()
