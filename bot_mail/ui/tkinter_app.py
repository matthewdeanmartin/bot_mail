"""Tkinter desktop UI for bot_mail (Slowmail).

Layout (spec section 3.4):

* Left pane: conversation list.
* Main pane: message thread.
* Bottom pane: compose box.
* Status bar: SMTP status, bot/backend, pending jobs.

The UI only talks to :class:`MailboxService` and the :class:`App` lifecycle; it
never touches the database directly. It refreshes on a Tk timer so replies from
the slow background bot appear on their own.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from bot_mail.app import App
from bot_mail.domain.models import Conversation, Message, Role
from bot_mail.mail.composer import build_references, reply_subject
from bot_mail.mail.local_client import send_local

_REFRESH_MS = 1000


class MailChatUI:
    """The main Tkinter window."""

    def __init__(self, app: App) -> None:
        """Build the widget tree and bind events."""
        self._app = app
        self._mailbox = app.mailbox
        self._selected_conversation_id: int | None = None
        self._conv_index: dict[str, int] = {}
        self._last_thread_len = -1

        self.root = tk.Tk()
        self.root.title("Slowmail — local email-backed chat")
        self.root.geometry("900x600")
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_refresh()

    # -- layout ------------------------------------------------------------

    def _build_widgets(self) -> None:
        """Construct panes, lists, the thread view, compose box, and status bar."""
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: conversation list + "New" button.
        left = ttk.Frame(paned, width=240)
        paned.add(left, weight=1)

        ttk.Button(left, text="New conversation", command=self._new_conversation).pack(fill=tk.X, padx=4, pady=4)
        self.conv_list = tk.Listbox(left, exportselection=False)
        self.conv_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.conv_list.bind("<<ListboxSelect>>", self._on_select_conversation)

        # Right: thread view + compose box.
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        self.thread_view = tk.Text(right, wrap=tk.WORD, state=tk.DISABLED)
        self.thread_view.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.thread_view.tag_configure("user", foreground="#1a4d8f", spacing1=6)
        self.thread_view.tag_configure("assistant", foreground="#2e7d32", spacing1=6)
        self.thread_view.tag_configure("meta", foreground="#888888")

        compose = ttk.Frame(right)
        compose.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.compose_text = tk.Text(compose, height=4, wrap=tk.WORD)
        self.compose_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.compose_text.bind("<Control-Return>", self._on_send_event)
        ttk.Button(compose, text="Send", command=self._send).pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))

        # Status bar.
        self.status_var = tk.StringVar(value="starting…")
        status = ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W, relief=tk.SUNKEN)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    # -- actions -----------------------------------------------------------

    def _new_conversation(self) -> None:
        """Deselect any conversation so the next send starts a fresh thread."""
        self.conv_list.selection_clear(0, tk.END)
        self._selected_conversation_id = None
        self._render_thread([])
        self.compose_text.focus_set()

    def _on_send_event(self, _event: tk.Event) -> str:
        """Handle Ctrl+Enter in the compose box."""
        self._send()
        return "break"

    def _send(self) -> None:
        """Send the composed text as a user message via the local SMTP server."""
        body = self.compose_text.get("1.0", tk.END).strip()
        if not body:
            return
        try:
            if self._selected_conversation_id is None:
                subject = self._derive_subject(body)
                send_local(self._app.config, body, subject=subject)
            else:
                # Reply within the selected conversation: thread off its latest message.
                parent = self._mailbox.messages.latest_in_conversation(self._selected_conversation_id)
                conv = self._mailbox.conversations.get(self._selected_conversation_id)
                send_local(
                    self._app.config,
                    body,
                    subject=reply_subject(conv.subject if conv else "Re:"),
                    in_reply_to=parent.message_id_header if parent else None,
                    references=build_references(parent),
                )
        except OSError as exc:
            messagebox.showerror("Send failed", f"Could not reach local SMTP server:\n{exc}")
            return
        self.compose_text.delete("1.0", tk.END)
        # Refresh soon so the just-sent message appears promptly.
        self.root.after(200, self._refresh)

    @staticmethod
    def _derive_subject(body: str) -> str:
        """Use the first line (truncated) of a new message as its subject."""
        first = body.strip().splitlines()[0] if body.strip() else "New conversation"
        return first[:60] if first else "New conversation"

    # -- selection & rendering --------------------------------------------

    def _on_select_conversation(self, _event: tk.Event) -> None:
        """Track the selected conversation and render its thread."""
        selection = self.conv_list.curselection()  # type: ignore[no-untyped-call]
        if not selection:
            return
        label = self.conv_list.get(selection[0])
        self._selected_conversation_id = self._conv_index.get(label)
        self._last_thread_len = -1  # force re-render
        self._refresh()

    def _refresh_conversations(self) -> list[Conversation]:
        """Repopulate the conversation list, preserving selection."""
        conversations = self._mailbox.list_conversations()
        labels = [self._conv_label(c) for c in conversations]
        current = list(self.conv_list.get(0, tk.END))
        if labels != current:
            self.conv_list.delete(0, tk.END)
            self._conv_index.clear()
            for conv, label in zip(conversations, labels, strict=True):
                self.conv_list.insert(tk.END, label)
                self._conv_index[label] = conv.id  # type: ignore[assignment]
            # Restore highlight on the selected conversation.
            if self._selected_conversation_id is not None:
                for idx, conv in enumerate(conversations):
                    if conv.id == self._selected_conversation_id:
                        self.conv_list.selection_set(idx)
                        break
        return conversations

    @staticmethod
    def _conv_label(conversation: Conversation) -> str:
        """Format a conversation list entry."""
        return f"{conversation.subject}  ·  #{conversation.id}"

    def _render_thread(self, messages: list[Message]) -> None:
        """Render a conversation thread into the read-only text view."""
        self.thread_view.configure(state=tk.NORMAL)
        self.thread_view.delete("1.0", tk.END)
        for msg in messages:
            who = "You" if msg.role == Role.USER else self._app.config.bot_address
            tag = "user" if msg.role == Role.USER else "assistant"
            self.thread_view.insert(tk.END, f"{who}  ", tag)
            self.thread_view.insert(tk.END, f"({msg.status.value})\n", "meta")
            self.thread_view.insert(tk.END, f"{msg.body_text}\n\n")
        self.thread_view.configure(state=tk.DISABLED)
        self.thread_view.see(tk.END)

    # -- periodic refresh --------------------------------------------------

    def _schedule_refresh(self) -> None:
        """Arrange the next periodic refresh."""
        self.root.after(_REFRESH_MS, self._refresh_tick)

    def _refresh_tick(self) -> None:
        """Periodic refresh callback; reschedules itself."""
        self._refresh()
        self._schedule_refresh()

    def _refresh(self) -> None:
        """Refresh conversation list, thread view, and status bar."""
        self._refresh_conversations()
        if self._selected_conversation_id is not None:
            thread = self._mailbox.thread(self._selected_conversation_id)
            if len(thread) != self._last_thread_len:
                self._render_thread(thread)
                self._last_thread_len = len(thread)
        self._update_status()

    def _update_status(self) -> None:
        """Update the status bar text."""
        smtp_state = "up" if self._app.smtp.running else "down"
        pending = self._mailbox.jobs.count_active()
        self.status_var.set(
            f"SMTP {self._app.config.smtp_host}:{self._app.config.smtp_port} [{smtp_state}]  ·  "
            f"backend: {self._app.backend.name}  ·  model: {self._app.config.ollama_model}  ·  "
            f"pending jobs: {pending}"
        )

    # -- lifecycle ---------------------------------------------------------

    def _on_close(self) -> None:
        """Stop background services and close the window."""
        try:
            self._app.stop()
        finally:
            self.root.destroy()

    def run(self) -> None:
        """Enter the Tkinter main loop."""
        self.root.mainloop()


def run_ui(app: App) -> None:
    """Start the app's services and run the Tkinter UI to completion."""
    app.start()
    MailChatUI(app).run()
