from aiogram import Router
from aiogram import F
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query(F.data.startswith("delete_event_"))
async def delete_event(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    delete_event(event_id)
    await callback.answer("Удалено")
    await callback.message.edit_text("Ивент удален.")

@router.callback_query(F.data == "hide_events")
async def hide_events(callback: CallbackQuery):
    await callback.message.delete()
