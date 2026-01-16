"""Textual-based interactive mode for Punch task management."""

import datetime
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Button, Static, ListItem, ListView, Input, Label
from textual.screen import ModalScreen
from rich.console import Console

from punch.tasks import TaskEntry, get_recent_tasks, write_task


class NewTaskScreen(ModalScreen):
    """Modal screen for entering a new task name."""
    
    CSS = """
    NewTaskScreen {
        align: center middle;
    }
    
    #dialog {
        width: 60;
        height: 9;
        border: thick $background 80%;
        background: $surface;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.task_name = None
    
    def compose(self) -> ComposeResult:
        ok_button = Button("OK", id="ok")
        cancel_button = Button("Cancel", id="cancel")
        
        yield Vertical(
            Label("Enter new task name:", classes="question"),
            Input(placeholder="Task name", id="task_input"),
            Horizontal(
                ok_button,
                cancel_button,
                id="buttons",
            ),
            id="dialog",
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            task_input = self.query_one("#task_input", Input)
            self.task_name = task_input.value.strip()
            if self.task_name:
                self.dismiss(self.task_name)
        elif event.button.id == "cancel":
            self.dismiss(None)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.task_name = event.value.strip()
        if self.task_name:
            self.dismiss(self.task_name)


class NotesInputScreen(ModalScreen):
    """Modal screen for entering task notes."""
    
    CSS = """
    NotesInputScreen {
        align: center middle;
    }
    
    #dialog {
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    """
    
    def __init__(self, category: str, task_name: str):
        super().__init__()
        self.category = category
        self.task_name = task_name
        self.notes = ""
    
    def compose(self) -> ComposeResult:
        save_button = Button("Save Task", id="save")
        cancel_button = Button("Cancel", id="cancel")
        
        yield Vertical(
            Label(f"Category: {self.category}", classes="info"),
            Label(f"Task: {self.task_name}", classes="info"),
            Label("Enter notes (optional):", classes="question"),
            Input(placeholder="Notes", id="notes_input"),
            Horizontal(
                save_button,
                cancel_button,
                id="buttons",
            ),
            id="dialog",
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            notes_input = self.query_one("#notes_input", Input)
            self.notes = notes_input.value.strip()
            self.dismiss((self.category, self.task_name, self.notes))
        elif event.button.id == "cancel":
            self.dismiss(None)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.notes = event.value.strip()
        self.dismiss((self.category, self.task_name, self.notes))


class InteractiveApp(App[TaskEntry]):
    """A Textual app for interactive task management."""
    
    CSS = """
    Screen {
        align: center middle;
    }
    
    #main_container {
        width: 80;
        height: 24;
        border: thick $primary;
        background: $surface;
    }
    
    #header {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        content-align: center middle;
    }
    
    #content {
        height: 1fr;
        margin: 1 2;
    }
    
    ListView {
        border: solid $accent;
        margin: 1 0;
    }
    
    ListItem {
        padding: 0 1;
    }
    
    ListItem:hover {
        background: $accent 30%;
    }
    
    Button {
        margin: 1 0;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]
    
    def __init__(self, categories, tasks_file, selected_category=None):
        super().__init__()
        self.categories = categories
        self.tasks_file = tasks_file
        self.selected_category = selected_category
        self.current_stage = "categories" if not selected_category else "tasks"
        self.selected_task = None
        
        # Convert categories to list if it's a dict
        if isinstance(categories, dict):
            self.category_list = list(categories.keys())
        else:
            self.category_list = categories
    
    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Punch - Interactive Mode", id="header"),
            Vertical(id="content"),
            id="main_container"
        )
    
    def on_mount(self) -> None:
        if self.current_stage == "categories":
            self.show_categories()
        else:
            self.show_tasks()
    
    def show_categories(self) -> None:
        content = self.query_one("#content")
        content.remove_children()
        
        content.mount(Static("Select a Category:", classes="question"))
        
        # Create ListView and mount it first
        list_view = ListView()
        content.mount(list_view)
        
        # Now add items after mounting
        for category in self.category_list:
            list_view.mount(ListItem(Static(category)))
        
        # Focus the ListView so user can navigate immediately
        list_view.focus()
    
    def show_tasks(self) -> None:
        content = self.query_one("#content")
        content.remove_children()
        
        content.mount(Static(f"Tasks in '{self.selected_category}':", classes="info"))
        
        # Get recent tasks
        if self.selected_category:
            tasks = get_recent_tasks(self.tasks_file, self.selected_category)
            task_names = [task.task for task in tasks]
        else:
            task_names = []
        
        # Create ListView and mount it first
        list_view = ListView()
        content.mount(list_view)
        
        # Now add items after mounting
        for task_name in task_names:
            list_view.mount(ListItem(Static(task_name)))
        
        # Add "New task" option
        list_view.mount(ListItem(Static("+ Add new task")))
        
        # Focus the ListView so user can navigate immediately
        list_view.focus()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        selected_item = event.list_view.highlighted_child
        if selected_item is None:
            return
            
        index = event.list_view.index
        if index is None:
            return
            
        if self.current_stage == "categories":
            if 0 <= index < len(self.category_list):
                self.selected_category = self.category_list[index]
                self.current_stage = "tasks"
                self.show_tasks()
        elif self.current_stage == "tasks":
            if not self.selected_category:
                return
                
            tasks = get_recent_tasks(self.tasks_file, self.selected_category)
            task_names = [task.task for task in tasks]
            
            if index == len(task_names):  # "Add new task" option
                self.push_screen(NewTaskScreen(), self.on_new_task_result)
            elif 0 <= index < len(task_names):
                self.selected_task = task_names[index]
                if self.selected_task and self.selected_category:
                    self.push_screen(
                        NotesInputScreen(self.selected_category, self.selected_task),
                        self.on_notes_result
                    )
    
    def on_new_task_result(self, task_name: Optional[str]) -> None:
        if task_name and self.selected_category:
            self.selected_task = task_name
            self.push_screen(
                NotesInputScreen(self.selected_category, self.selected_task),
                self.on_notes_result
            )
    
    def on_notes_result(self, result) -> None:
        if result:
            category, task, notes = result
            self.exit(TaskEntry(datetime.datetime.now(), category, task, notes, datetime.timedelta(0)))
        else:
            self.exit()
    
    async def action_quit(self) -> None:
        self.exit()


def run_interactive_mode(categories, tasks_file, selected_category=None):
    """Launch the interactive Textual interface for task entry."""
    app = InteractiveApp(categories, tasks_file, selected_category)
    return app.run()