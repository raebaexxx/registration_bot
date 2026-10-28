from aiogram.fsm.state import State, StatesGroup


class EventCreate(StatesGroup):
    waiting_date = State()


class EventRename(StatesGroup):
    waiting_title = State()


class GameCreate(StatesGroup):
    waiting_title = State()
    waiting_time = State()
    waiting_capacity = State()
    waiting_place = State()
    waiting_description = State()


class GameLimit(StatesGroup):
    waiting_value = State()
