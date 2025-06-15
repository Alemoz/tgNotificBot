async def clear_chat(state, bot, chat_id, messages: list):
    for msg_id in messages:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    await state.clear()
