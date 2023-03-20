import tkinter as tk
from pathlib import Path
from threading import Thread
from tkinter import ttk, filedialog
from tkinter.messagebox import showerror
from typing import Callable, Any

import sv_ttk

from core import detect_missing_commands, get_video_id, download
from preferences import Preferences


class BackgroundTask:
    def __init__(
            self,
            op: Callable[[], Any | None],
            on_completed: Callable[[Exception | None], None]
    ) -> None:
        """
        Run op in background.

        :param op: Operation to run in background.
        :param on_completed: Called when op completes or when exception occurs.
        """
        self._exception = None

        def run() -> None:
            # noinspection PyBroadException
            try:
                op()
            except Exception as exception:
                on_completed(exception)
            finally:
                on_completed(None)

        self._thread = Thread(target=run)

    def start(self) -> None:
        self._thread.start()


WINDOW_WIDTH = 225
WINDOW_HEIGHT = 300

ICON_PATH = 'icon.ico'
WINDOW_TITLE = 'YouTube DL'


def bind(preferences: Preferences, variable: tk.Variable, key: str) -> None:
    if (value := preferences.get(key, default=None)) is not None:
        variable.set(value)

    variable.trace_add(mode='write', callback=lambda *_: preferences.set(key, value=variable.get()))


class MainWindow(ttk.Frame):
    CONFIG_PATH = Path('preferences.json')
    CONFIG_DOWNLOAD_FOLDER = 'download_folder'
    ENTRY_WIDTH = 50

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._config = Preferences(self.CONFIG_PATH)

        self.url = tk.StringVar()
        self.url.trace_add(mode='write', callback=self._url_changed)

        self.status = tk.StringVar()

        self.download_folder = tk.StringVar()

        self.video_id: str | None = None

        self._populate()

        self.url.set(value='')
        self.status.set(value='No URL')

        bind(self._config, self.download_folder, self.CONFIG_DOWNLOAD_FOLDER)

    def _populate(self) -> None:
        self.grid_columnconfigure(index=0, weight=4)
        self.grid_columnconfigure(index=1, weight=1)

        row = iter(range(1_000))
        ttk.Label(self, text='Video URL').grid(row=next(row), column=0, columnspan=2, sticky=tk.W)
        ttk.Entry(self, textvariable=self.url, width=self.ENTRY_WIDTH).grid(row=next(row), column=0, columnspan=2)

        ttk.Label(self, text='Download folder').grid(row=next(row), column=0, columnspan=2, sticky=tk.W)
        current_row = next(row)
        ttk.Entry(self, textvariable=self.download_folder, justify=tk.LEFT) \
            .grid(row=current_row, column=0, sticky=tk.EW)
        ttk.Button(self, text='Change', command=self._change_download_folder_pressed) \
            .grid(row=current_row, column=1, sticky=tk.EW)

        ttk.Label(self, textvariable=self.status).grid(row=next(row), column=0, columnspan=2)

        self.download_button = ttk.Button(self, text='Download', command=lambda *_: self._download_pressed())
        self.download_button.grid(row=next(row), column=0, columnspan=2, sticky=tk.EW)

        for child in self.children.values():
            child.grid_configure(padx=2, pady=2)

    def _toggle_input(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for child in self.children.values():
            if isinstance(child, (ttk.Button, ttk.Entry)):
                child.config(state=state)

    def _url_changed(self, *_) -> None:
        self.video_id = get_video_id(self.url.get())

        self.download_button.config(state=tk.NORMAL if self.video_id is not None else tk.DISABLED)
        self.status.set(value='Can download' if self.video_id is not None else 'Invalid URL')

    def _download_folder_changed(self, *_) -> None:
        self._config.set(self.CONFIG_DOWNLOAD_FOLDER, value=self.download_folder.get())

    def _change_download_folder_pressed(self, *_) -> None:
        self.download_folder.set(
            value=filedialog.askdirectory(
                initialdir=self.download_folder.get(),
                parent=self,
                mustexist=True
            )
        )

    def _download_pressed(self, *_) -> None:
        self._toggle_input(enabled=False)

        BackgroundTask(
            op=lambda: download(
                video_id=self.video_id,
                download_folder=Path(self.download_folder.get()),
                status_changed=self._status_changed
            ),
            on_completed=self._download_completed
        ).start()

    def _status_changed(self, new_status: str) -> None:
        self.status.set(value=new_status)

    def _download_completed(self, exception: Exception | None) -> None:
        if exception is not None:
            showerror(title='Error occurred', message=str(exception))
            self.status.set(value='Error')

        self._toggle_input(enabled=True)


def show() -> None:
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.iconbitmap(ICON_PATH)

    # style = ttk.Style()
    # style.theme_use('xpnative')
    sv_ttk.set_theme('light')

    MainWindow(root).pack(expand=True, anchor=tk.CENTER, fill=tk.BOTH)

    root.mainloop()


def main() -> None:
    missing_commands = detect_missing_commands()

    if missing_commands:
        message = f'{", ".join(missing_commands)} {"is" if 1 == len(missing_commands) else "are"} ' \
                  f'required for this program to run. Install it and try again.'
        showerror(title=f'Missing dependencies', message=message)
        return

    show()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        showerror(title='Unhandled exception occurred', message=str(e))
