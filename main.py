import os
import aiosqlite
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

DB_PATH = os.getenv("DB_PATH", "data.db")

app = FastAPI(title="PizzaDay Inventory Web")

# Подключение шаблонов и статики
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- База данных ----------
async def db_fetchall(sql: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
    return rows


async def db_execute(sql: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(sql, params)
        await db.commit()


# ---------- Таблица при старте ----------
@app.on_event("startup")
async def ensure_table():
    await db_execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            quantity INTEGER,
            expiry_date TEXT,
            category TEXT
        )
    """)


# ---------- Страницы ----------
@app.get("/")
async def index(request: Request):
    rows = await db_fetchall("SELECT id, name, quantity, expiry_date, category FROM items ORDER BY expiry_date")
    items = [dict(r) for r in rows]
    for it in items:
        try:
            d = date.fromisoformat(it["expiry_date"])
            it["days_left"] = (d - date.today()).days
            it["expiry_f"] = d.strftime("%d.%m.%Y")
        except Exception:
            it["days_left"] = None
            it["expiry_f"] = it["expiry_date"]
    return templates.TemplateResponse("index.html", {"request": request, "items": items})


@app.get("/add")
async def add_get(request: Request, category: Optional[str] = None):
    return templates.TemplateResponse("add.html", {"request": request, "category": category or ""})


@app.post("/add")
async def add_post(
    name: str = Form(...),
    quantity: int = Form(...),
    expiry: str = Form(...),
    category: str = Form(...)
):
    try:
        dt = datetime.strptime(expiry, "%d.%m.%Y").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте дд.мм.гггг")

    await db_execute(
        "INSERT INTO items (name, quantity, expiry_date, category) VALUES (?, ?, ?, ?)",
        (name.strip(), int(quantity), dt.isoformat(), category.strip())
    )
    return RedirectResponse("/", status_code=303)


@app.get("/edit/{item_id}")
async def edit_get(request: Request, item_id: int):
    rows = await db_fetchall("SELECT id, name, quantity, expiry_date, category FROM items WHERE id = ?", (item_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Товар не найден")
    it = dict(rows[0])
    try:
        it["expiry_f"] = date.fromisoformat(it["expiry_date"]).strftime("%d.%m.%Y")
    except Exception:
        it["expiry_f"] = it["expiry_date"]
    return templates.TemplateResponse("edit.html", {"request": request, "item": it})


@app.post("/edit/{item_id}")
async def edit_post(
    item_id: int,
    name: str = Form(...),
    quantity: int = Form(...),
    expiry: str = Form(...),
    category: str = Form(...)
):
    try:
        dt = datetime.strptime(expiry, "%d.%m.%Y").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте дд.мм.гггг")

    await db_execute(
        "UPDATE items SET name = ?, quantity = ?, expiry_date = ?, category = ? WHERE id = ?",
        (name.strip(), int(quantity), dt.isoformat(), category.strip(), item_id)
    )
    return RedirectResponse("/", status_code=303)


@app.post("/delete/{item_id}")
async def delete_item(item_id: int):
    await db_execute("DELETE FROM items WHERE id = ?", (item_id,))
    return RedirectResponse("/", status_code=303)


# ---------- API ----------
@app.get("/api/items")
async def api_items():
    rows = await db_fetchall("SELECT id, name, quantity, expiry_date, category FROM items ORDER BY expiry_date")
    return [dict(r) for r in rows]