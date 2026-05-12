import yaml
import os
from datetime import datetime, timedelta
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, VerticalScroll
from textual.widgets import Header, Footer, Static, Label, Input, Button, ListView, ListItem
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.reactive import reactive
from textual.message import Message

TASKS_FILE = os.path.expanduser("~/.local/share/punch/tasks.txt")
CATEGORIES_FILE = os.path.expanduser("~/.config/punch/punch.yaml")
DEFAULT_CATEGORIES = {"General": {"short": "gen"}}
DEFAULT_START_TIME = "08:30"

# --- Helper: Load Categories ---

def parse_config(config_file):
    if not os.path.exists(config_file):
        return {}
    try:
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
            return data
    except:
        return {}


# --- Helper: Get Sunday ---
def get_current_week_sunday():
    today = datetime.now().date()
    idx = (today.isoweekday() % 7) 
    return today - timedelta(days=idx)

# --- CUSTOM LIST ITEM (For Suggestions) ---
class SuggestionListItem(ListItem):
    def __init__(self, text: str):
        super().__init__(Label(text))
        self.text_value = text

# --- CUSTOM LIST ITEM (For Categories) ---
class CategoryListItem(ListItem):
    def __init__(self, text: str):
        super().__init__(Label(text))
        self.text_value = text

# --- Confirmation Modal ---
class ConfirmationModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    def compose(self) -> ComposeResult:
        with Container(id="modal-dialog"):
            yield Label("Delete this time card?", id="modal-label")
            with Horizontal(id="modal-buttons"):
                yield Button("Yes", variant="error", id="yes-btn")
                yield Button("No", variant="primary", id="no-btn")
    def action_cancel(self): self.dismiss(False)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-btn": self.dismiss(True)
        else: self.dismiss(False)

# --- Time Entry Modal ---
class TimeEntryModal(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, categories: dict, history: dict, initial_category: str = None, initial_time: str = "", initial_desc: str = ""):
        super().__init__()
        self.categories = categories
        self.history = history 
        self.initial_category = initial_category
        self.initial_time = initial_time
        self.initial_desc = initial_desc

    def compose(self) -> ComposeResult:
        with Container(id="modal-dialog"):
            yield Label("Select Category:", classes="section-label")
            with VerticalScroll(id="category-container"):
                yield ListView(id="category-list")
            yield Label("Enter Minutes:", classes="section-label")
            yield Input(placeholder="e.g. 60", value=self.initial_time, type="integer", id="time-input")
            yield Label("Description:", classes="section-label")
            yield Input(placeholder="e.g. Ticket #1234", value=self.initial_desc, id="desc-input")
            yield Label("Suggestions (Click to fill):", classes="section-label-small")
            with VerticalScroll(id="suggestions-container"):
                yield ListView(id="suggestions-list")
            with Horizontal(id="modal-buttons"):
                yield Button("Save", variant="success", id="save-btn")
                yield Button("Cancel", variant="error", id="cancel-btn")

    def on_mount(self):
        cat_list = self.query_one("#category-list", ListView)
        target_index = 0
        for idx, cat_name in enumerate(self.categories.keys()):
            item = CategoryListItem(cat_name)
            cat_list.mount(item)
            if cat_name == self.initial_category:
                target_index = idx
        cat_list.index = target_index
        self.call_after_refresh(cat_list.focus)
        if self.categories:
            initial_cat = list(self.categories.keys())[target_index]
            self.update_suggestions(initial_cat)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.control.id == "category-list":
            if isinstance(event.item, CategoryListItem):
                self.update_suggestions(event.item.text_value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.control.id == "category-list":
            self.query_one("#time-input").focus()
        elif event.control.id == "suggestions-list":
            if isinstance(event.item, SuggestionListItem):
                self.query_one("#desc-input").value = event.item.text_value
                self.query_one("#desc-input").focus()

    def update_suggestions(self, category: str):
        list_view = self.query_one("#suggestions-list", ListView)
        list_view.clear()
        options = sorted(list(self.history.get(category, [])))
        if not options:
            list_view.mount(ListItem(Label("-- No history --"), disabled=True))
        else:
            for desc in options:
                list_view.mount(SuggestionListItem(desc))

    def action_cancel(self): self.dismiss(None)
    def on_input_submitted(self, event: Input.Submitted) -> None: self._submit_form()
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn": self._submit_form()
        else: self.dismiss(None)

    def _submit_form(self):
        cat_list = self.query_one("#category-list", ListView)
        if cat_list.index is None:
            self.notify("Please select a category.", severity="error")
            return
        selected_item = cat_list.children[cat_list.index]
        cat_name = selected_item.text_value
        time_inp = self.query_one("#time-input", Input)
        desc_inp = self.query_one("#desc-input", Input)
        if time_inp.value.isdigit():
            self.dismiss((cat_name, int(time_inp.value), desc_inp.value))
        else:
            self.notify("Please enter a valid number for minutes!", severity="error")

# --- Time Card Widget ---
class TimeCard(Static):
    minutes = reactive(0)
    category = reactive("")
    description = reactive("")

    def __init__(self, category: str, minutes: int, description: str = ""):
        super().__init__()
        self.category = category
        self.minutes = minutes
        self.description = description
        self.can_focus = True

    def compose(self) -> ComposeResult:
        yield Label(self._get_label_text())

    def on_click(self) -> None: self.focus()
    def watch_minutes(self, val): self._update_label()
    def watch_category(self, val): self._update_label()
    def watch_description(self, val): self._update_label()

    def _update_label(self):
        try: self.query_one(Label).update(self._get_label_text())
        except: pass

    def _get_label_text(self):
        text = f"{self.category}"
        if self.description:
            text += f"\n{self.description}"
        text += f"\n{self.minutes}m"
        return text

# --- Day Column Widget ---
class DayColumn(Vertical):
    def __init__(self, date_obj, **kwargs):
        super().__init__(**kwargs)
        self.date_obj = date_obj
        self.total_minutes = 0
        self.can_focus = True 

    def compose(self) -> ComposeResult:
        with Vertical(classes="day-header"):
            yield Label(self.date_obj.strftime("%Y-%m-%d"), classes="date-label")
            yield Label("0 min", classes="day-total-label")
        yield Vertical(classes="cards-container")

    def add_entry(self, category: str, minutes: int, description: str = ""):
        container = self.query_one(".cards-container")
        card = TimeCard(category, minutes, description)
        container.mount(card)
        card.scroll_visible()
        self.update_total()
    
    def clear_entries(self):
        container = self.query_one(".cards-container")
        for child in list(container.children):
            child.minutes = 0
            child.remove()
        self.total_minutes = 0
        self.query_one(".day-total-label", Label).update("0 min")
        self.post_message(self.StatsUpdated())

    def update_total(self):
        cards = self.query(TimeCard)
        self.total_minutes = sum(c.minutes for c in cards)
        self.query_one(".day-total-label", Label).update(f"{self.total_minutes} min")
        self.post_message(self.StatsUpdated())

    class StatsUpdated(Message):
        pass

# --- Main Application ---
class WeeklyEditorApp(App):
    CSS = """
    Screen { align: center middle; }
    #week-grid { height: 100%; width: 100%; align: center top; }
    DayColumn { width: 1fr; height: 100%; border-right: solid $primary-background-lighten-2; }
    DayColumn:focus { background: $surface-lighten-1; border: thick $accent; }
    .day-header { height: auto; background: $accent; color: $text; align: center middle; padding: 1; text-align: center; text-style: bold; }
    .cards-container { height: 1fr; padding: 0 1; }
    TimeCard { height: auto; min-height: 3; margin-bottom: 0; background: $panel; border: solid $background; content-align: center middle; padding: 1; text-align: center; }
    TimeCard:focus { border: solid $success; background: $surface; }
    #modal-dialog { grid-size: 2; grid-gutter: 1; grid-rows: auto auto auto auto 1fr auto; padding: 1 2; width: 60; height: 85%; border: thick $background 80%; background: $surface; }
    .section-label { width: 100%; margin-top: 1; text-style: bold; }
    .section-label-small { width: 100%; margin-top: 1; color: $text-muted; text-style: italic; }
    #category-container { height: auto; max-height: 10; background: $surface-darken-1; border: solid $primary-background; margin-bottom: 1; }
    #suggestions-container { height: 1fr; background: $surface-darken-1; border: solid $primary-background; margin-bottom: 1; }
    #modal-buttons { align: center bottom; height: auto; margin-top: 1; }
    Button { margin: 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("down", "focus_next", "Next", show=False),      
        Binding("up", "focus_previous", "Prev", show=False),    
        Binding("left", "move_left", "Left"),
        Binding("right", "move_right", "Right"),
        Binding("a", "add_card", "Add Card"),
        Binding("enter", "handle_enter", "Select/Edit"),
        Binding("d", "delete_card", "Delete Card"),
        Binding("e", "edit_card", "Edit Card"),
    ]

    total_week_minutes = reactive(0)
    current_week_start = reactive(get_current_week_sunday) 
    categories = {}
    description_history = {} 

    def __init__(self, tasks_file=TASKS_FILE, config_file=CATEGORIES_FILE):
        super().__init__()
        self.tasks_file = tasks_file
        self.config_file = config_file

    def on_load(self):
        config = parse_config(self.config_file)
        self.categories = config.get("categories", DEFAULT_CATEGORIES)
        if not self.categories:
            self.categories = DEFAULT_CATEGORIES
        
        self.start_time = config.get("start_time", DEFAULT_START_TIME)

    def compose(self) -> ComposeResult:
        yield Header()
        columns = []
        for i in range(7):
            current_date = self.current_week_start + timedelta(days=i)
            columns.append(DayColumn(current_date, id=f"day-{i}"))
        yield Horizontal(*columns, id="week-grid")
        yield Footer()

    def on_mount(self):
        self.query_one("#day-1").focus()
        self.load_data()

    def watch_current_week_start(self, new_start):
        for i in range(7):
            try:
                col = self.query_one(f"#day-{i}", DayColumn)
                col.clear_entries()
                col.date_obj = new_start + timedelta(days=i)
                col.query_one(".date-label", Label).update(col.date_obj.strftime("%Y-%m-%d"))
            except:
                pass 
        self.load_data()
        self.sub_title = f"Week of {new_start.strftime('%Y-%m-%d')} | Total: {self.total_week_minutes} mins"

    def load_data(self):
        if not os.path.exists(self.tasks_file): return
        with open(self.tasks_file, 'r') as f: lines = f.readlines()

        data_by_date = {}
        self.description_history = {} 

        for line in lines:
            parts = line.strip().split('|')
            if len(parts) < 2: continue
            try:
                dt_obj = datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M")
                date_key = dt_obj.strftime("%Y-%m-%d")
            except ValueError: continue

            cat = parts[1].strip()
            desc = parts[2].strip() if len(parts) > 2 else ""

            if cat not in self.description_history: self.description_history[cat] = set()
            if desc: self.description_history[cat].add(desc)

            if date_key not in data_by_date: data_by_date[date_key] = []
            data_by_date[date_key].append({"dt": dt_obj, "cat": cat, "desc": desc})

        for col in self.query(DayColumn):
            col_date_str = col.date_obj.strftime("%Y-%m-%d")
            if col_date_str in data_by_date:
                entries = sorted(data_by_date[col_date_str], key=lambda x: x["dt"])
                start_time_str = getattr(self, "start_time", DEFAULT_START_TIME)
                last_time = datetime.strptime(f"{col_date_str} {start_time_str}", "%Y-%m-%d %H:%M")
                for entry in entries:
                    if entry["cat"].lower() == "start":
                        last_time = entry["dt"]
                        continue
                    duration = int((entry["dt"] - last_time).total_seconds() / 60)
                    if duration > 0: col.add_entry(entry["cat"], duration, entry["desc"])
                    last_time = entry["dt"]
            col.update_total()

    def save_data(self):
        visible_dates = set()
        columns = self.query(DayColumn)
        for col in columns: visible_dates.add(col.date_obj.strftime("%Y-%m-%d"))

        preserved_lines = []
        original_start_times = {}
        if os.path.exists(self.tasks_file):
            with open(self.tasks_file, 'r') as f:
                for line in f:
                    parts = line.split('|')
                    if not parts or not parts[0].strip():
                        continue
                    date_time_str = parts[0].strip()
                    date_key = date_time_str[:10]
                    # Record earliest timestamp per visible date before discarding its lines
                    if date_key in visible_dates:
                        try:
                            dt_obj = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            dt_obj = None
                        if dt_obj is not None:
                            if date_key not in original_start_times or dt_obj < original_start_times[date_key]:
                                original_start_times[date_key] = dt_obj
                    else:
                        preserved_lines.append(line.strip())

        new_lines = []
        for col in columns:
            cards = col.query(TimeCard)
            if not cards: continue
            date_str = col.date_obj.strftime("%Y-%m-%d")
            # Use the original start time for this date if available; otherwise fall back to DEFAULT_START_TIME
            if date_str in original_start_times:
                current_time = original_start_times[date_str]
            else:
                current_time = datetime.strptime(f"{date_str} {DEFAULT_START_TIME}", "%Y-%m-%d %H:%M")
            new_lines.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} | start")
            for card in cards:
                current_time += timedelta(minutes=card.minutes)
                line = f"{current_time.strftime('%Y-%m-%d %H:%M')} | {card.category} | "
                if card.description:
                    line += f"{card.description}"

                if card.description:
                    if card.category not in self.description_history: self.description_history[card.category] = set()
                    self.description_history[card.category].add(card.description)
                new_lines.append(line)

        all_lines = preserved_lines + new_lines
        all_lines.sort()
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
        with open(self.tasks_file, 'w') as f:
            for line in all_lines: f.write(line + "\n")

    def on_day_column_stats_updated(self, message: DayColumn.StatsUpdated):
        total = sum(col.total_minutes for col in self.query(DayColumn))
        self.total_week_minutes = total

    def watch_total_week_minutes(self, value: int):
        self.sub_title = f"Week of {self.current_week_start.strftime('%Y-%m-%d')} | Total: {value} mins"

    def action_handle_enter(self):
        focused = self.screen.focused
        if isinstance(focused, TimeCard): self.action_edit_card()
        elif isinstance(focused, DayColumn): self.action_add_card()

    def action_add_card(self):
        focused = self.screen.focused
        if not focused: return
        target_column = None
        if isinstance(focused, DayColumn): target_column = focused
        elif isinstance(focused, TimeCard): target_column = focused.parent.parent
        
        if target_column:
            def check_result(result):
                if result:
                    cat, mins, desc = result
                    target_column.add_entry(cat, mins, desc)
                    self.save_data()
                    self.notify(f"Added {cat}: {mins}m", title="Saved")
            self.push_screen(TimeEntryModal(self.categories, self.description_history), check_result)

    def action_edit_card(self):
        focused = self.screen.focused
        if isinstance(focused, TimeCard):
            column = focused.parent.parent
            def check_result(result):
                if result:
                    cat, mins, desc = result
                    focused.category = cat
                    focused.minutes = mins
                    focused.description = desc
                    column.update_total()
                    self.save_data()
                    self.notify("Updated & Saved")
            self.push_screen(TimeEntryModal(self.categories, self.description_history, focused.category, str(focused.minutes), focused.description), check_result)

    def action_delete_card(self):
        focused = self.screen.focused
        if isinstance(focused, TimeCard):
            def check_confirm(should_delete: bool):
                if should_delete:
                    column = focused.parent.parent
                    focused.remove()
                    column.update_total()
                    self.save_data()
                    self.notify("Deleted entry", severity="warning")
            self.push_screen(ConfirmationModal(), check_confirm)

    def action_move_left(self): self.move_column(-1)
    def action_move_right(self): self.move_column(1)

    def move_column(self, direction):
        focused = self.screen.focused
        current_idx = 0
        if focused:
            current_col = None
            if isinstance(focused, DayColumn): current_col = focused
            elif isinstance(focused, TimeCard): current_col = focused.parent.parent
            if current_col:
                try: current_idx = int(current_col.id.split("-")[1])
                except: pass

        new_idx = current_idx + direction

        if new_idx < 0:
            self.current_week_start -= timedelta(days=7)
            self.call_after_refresh(lambda: self.query_one("#day-6").focus())
            self.notify(f"Switched to previous week", timeout=1)
        elif new_idx > 6:
            self.current_week_start += timedelta(days=7)
            self.call_after_refresh(lambda: self.query_one("#day-0").focus())
            self.notify(f"Switched to next week", timeout=1)
        else:
            self.query_one(f"#day-{new_idx}").focus()

if __name__ == "__main__":
    app = WeeklyEditorApp()
    app.run()