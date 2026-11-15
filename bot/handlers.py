import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kbs
from db import Database

log = logging.getLogger(__name__)
router = Router()

SEARCH: dict[int, str] = {}      # строка поиска на пользователя (в памяти)

CATALOG_TEXT = ("📚 <b>Каталог</b> (А–Я)\nОтметьте подарки для слежения. "
                "Можно ввести текст сообщением — это поиск по названию/коду.")


async def _edit(cb: CallbackQuery, text: str, markup) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            log.warning("edit failed: %s", e)
    except TelegramAPIError as e:
        log.warning("Telegram error: %s", e)


async def _show_catalog(cb_or_msg, db: Database, uid: int, page: int = 0) -> None:
    q = SEARCH.get(uid, "")
    items = await db.list_collections(q)
    selected = set(await db.get_selected(uid))
    text = CATALOG_TEXT + (f"\n🔎 Поиск: <code>{q}</code>" if q else "")
    if not items:
        text += "\n\nНичего не найдено."
    markup = kbs.catalog_kb(items, selected, page)
    if isinstance(cb_or_msg, CallbackQuery):
        await _edit(cb_or_msg, text, markup)
    else:
        await cb_or_msg.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(CommandStart())
async def start(msg: Message, db: Database):
    u = msg.from_user
    await db.upsert_user(u.id, u.username, u.first_name)
    SEARCH.pop(u.id, None)
    await msg.answer(f"👋 Привет, {u.first_name}! Я <b>Gift Catcher</b> — снайпер NFT-подарков.\n"
                     "Выберите подарки в каталоге, и я пришлю алерт, как только появится новый номер.",
                     reply_markup=kbs.main_menu(), parse_mode="HTML")


@router.callback_query(F.data == "back")
async def back(cb: CallbackQuery):
    SEARCH.pop(cb.from_user.id, None)
    await _edit(cb, "Главное меню", kbs.main_menu())
    await cb.answer()


@router.callback_query(F.data.startswith("catalog:"))
async def catalog(cb: CallbackQuery, db: Database):
    await db.upsert_user(cb.from_user.id, cb.from_user.username, cb.from_user.first_name)
    await _show_catalog(cb, db, cb.from_user.id, int(cb.data.split(":")[1]))
    await cb.answer()


@router.callback_query(F.data.startswith("tog:"))
async def toggle(cb: CallbackQuery, db: Database):
    _, slug, page = cb.data.split(":")
    await db.toggle(cb.from_user.id, slug)
    await _show_catalog(cb, db, cb.from_user.id, int(page))
    await cb.answer()


@router.callback_query(F.data.startswith("all:"))
async def select_all(cb: CallbackQuery, db: Database):
    uid = cb.from_user.id
    slugs = [r["slug"] for r in await db.list_collections(SEARCH.get(uid, ""))]
    selected = set(await db.get_selected(uid))
    await db.set_many(uid, slugs, on=not set(slugs) <= selected)   # все выбраны → снять
    await _show_catalog(cb, db, uid, int(cb.data.split(":")[1]))
    await cb.answer()


@router.callback_query(F.data == "alpha")
async def alpha(cb: CallbackQuery, db: Database):
    """«Роя»: все подарки по алфавиту; строка поиска сохраняется и продолжает работать."""
    await _show_catalog(cb, db, cb.from_user.id, 0)
    await cb.answer("Все подарки по алфавиту. Поиск работает — просто введите текст.")


@router.callback_query(F.data == "go")
async def go(cb: CallbackQuery, db: Database):
    items = await db.list_collections(SEARCH.get(cb.from_user.id, ""))
    selected = set(await db.get_selected(cb.from_user.id))
    lines = [f"{'✅' if r['slug'] in selected else '▫️'} {r['name']} — <code>{r['slug']}</code>"
             for r in items] or ["Ничего не найдено."]
    await cb.message.answer("🔎 <b>Список по алфавиту</b>\n" + "\n".join(lines)
                            + "\n\nСнайпер проверяет новые номера каждые 25 сек.", parse_mode="HTML")
    await cb.answer()


async def _show_models(cb: CallbackQuery, db: Database, slug: str) -> None:
    col = await db.get_collection(slug)
    models = await db.get_models(slug)
    current = await db.get_model_filter(cb.from_user.id, slug)
    text = (f"🎛 <b>Модели: {col['name']}</b>\nТекущий фильтр: "
            f"<b>{current or 'портфель (все модели)'}</b>\n")
    text += "" if models else "\nМодели пока не собраны — они появятся после первых проверок снайпера."
    await _edit(cb, text, kbs.models_kb(slug, models, current))


@router.callback_query(F.data == "model")
async def model(cb: CallbackQuery, db: Database):
    sel = await db.get_selected(cb.from_user.id)
    if not sel:
        await cb.answer("Сначала выберите NFT.", show_alert=True)
        return
    if len(sel) > 1:
        await cb.answer(f"Выбрано {len(sel)} NFT. Модель настраивается только для одного "
                        "подарка — оставьте один.", show_alert=True)
        return
    await _show_models(cb, db, sel[0])
    await cb.answer()


@router.callback_query(F.data.startswith("mdl:"))
async def pick_model(cb: CallbackQuery, db: Database):
    _, slug, idx = cb.data.split(":")
    models = await db.get_models(slug)
    value = None if idx == "*" else (models[int(idx)] if int(idx) < len(models) else None)
    await db.set_model_filter(cb.from_user.id, slug, value)
    await _show_models(cb, db, slug)
    await cb.answer(f"Фильтр: {value or 'все модели'}")


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery):
    await cb.answer()


@router.message(F.text & ~F.text.startswith("/"))
async def search(msg: Message, db: Database):
    SEARCH[msg.from_user.id] = msg.text.strip()
    await _show_catalog(msg, db, msg.from_user.id, 0)
