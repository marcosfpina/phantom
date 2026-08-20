#!/usr/bin/env python3
"""GTK4 desktop shell for the Phantom Writer Sandbox."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from phantom.writer import BrainDump, Distillation, Draft, WriterService  # noqa: E402

APP_ID = "dev.phantom.Writer"


class PhantomWriterWindow(Adw.ApplicationWindow):
    """Single-window GTK4 interface for dump, distill, write, and export."""

    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Phantom Writer Sandbox")
        self.service = WriterService()
        self.workspace = self._ensure_workspace()
        self.current_dump: BrainDump | None = None
        self.current_distillation: Distillation | None = None
        self.current_draft: Draft | None = None

        self.set_default_size(1280, 820)
        self.set_content(self._build_layout())

    def _ensure_workspace(self):
        workspaces = self.service.list_workspaces()
        if workspaces:
            return workspaces[0]
        return self.service.create_workspace("Default Writer Workspace")

    def _build_layout(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        header = Adw.HeaderBar()
        title = Gtk.Label(label="Phantom Writer")
        title.add_css_class("title")
        header.set_title_widget(title)
        root.append(header)

        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=10,
            margin_bottom=10,
            margin_start=12,
            margin_end=12,
        )
        workspace_label = Gtk.Label(
            label=f"Workspace: {self.workspace.name}",
            xalign=0,
        )
        workspace_label.set_hexpand(True)
        toolbar.append(workspace_label)

        save_dump = Gtk.Button(label="Save Dump")
        save_dump.connect("clicked", self._on_save_dump)
        toolbar.append(save_dump)

        distill = Gtk.Button(label="Distill")
        distill.connect("clicked", self._on_distill)
        toolbar.append(distill)

        save_draft = Gtk.Button(label="Save Draft")
        save_draft.connect("clicked", self._on_save_draft)
        toolbar.append(save_draft)

        export = Gtk.Button(label="Export")
        export.connect("clicked", self._on_export)
        toolbar.append(export)
        root.append(toolbar)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_wide_handle(True)
        paned.set_start_child(self._build_dump_panel())
        paned.set_end_child(self._build_write_panel())
        root.append(paned)

        self.status = Gtk.Label(label="Ready", xalign=0)
        self.status.add_css_class("dim-label")
        self.status.set_margin_start(12)
        self.status.set_margin_end(12)
        self.status.set_margin_top(8)
        self.status.set_margin_bottom(8)
        root.append(self.status)

        return root

    def _build_dump_panel(self) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=12,
            margin_end=8,
            margin_top=8,
            margin_bottom=8,
        )
        box.set_hexpand(True)
        box.set_vexpand(True)

        label = Gtk.Label(label="Dump", xalign=0)
        label.add_css_class("heading")
        box.append(label)

        self.dump_title = Gtk.Entry()
        self.dump_title.set_placeholder_text("Optional dump title")
        box.append(self.dump_title)

        self.dump_view = Gtk.TextView()
        self.dump_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.dump_view.set_monospace(False)
        self.dump_view.set_vexpand(True)
        dump_scroll = Gtk.ScrolledWindow()
        dump_scroll.set_child(self.dump_view)
        dump_scroll.set_vexpand(True)
        box.append(dump_scroll)

        distill_label = Gtk.Label(label="Distill", xalign=0)
        distill_label.add_css_class("heading")
        box.append(distill_label)

        self.distill_view = Gtk.TextView()
        self.distill_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.distill_view.set_editable(False)
        self.distill_view.set_vexpand(True)
        distill_scroll = Gtk.ScrolledWindow()
        distill_scroll.set_child(self.distill_view)
        distill_scroll.set_vexpand(True)
        box.append(distill_scroll)

        return box

    def _build_write_panel(self) -> Gtk.Widget:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=8,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        box.set_hexpand(True)
        box.set_vexpand(True)

        label = Gtk.Label(label="Write", xalign=0)
        label.add_css_class("heading")
        box.append(label)

        self.draft_title = Gtk.Entry()
        self.draft_title.set_placeholder_text("Draft title")
        box.append(self.draft_title)

        self.draft_view = Gtk.TextView()
        self.draft_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.draft_view.set_monospace(True)
        self.draft_view.set_vexpand(True)
        draft_scroll = Gtk.ScrolledWindow()
        draft_scroll.set_child(self.draft_view)
        draft_scroll.set_vexpand(True)
        box.append(draft_scroll)

        return box

    def _on_save_dump(self, _button: Gtk.Button) -> None:
        text = self._get_text(self.dump_view).strip()
        if not text:
            self._set_status("Dump is empty.")
            return

        title = self.dump_title.get_text().strip() or None
        self.current_dump = self.service.create_dump(
            self.workspace.id,
            raw_markdown=text,
            title=title,
        )
        self._set_status(f"Saved dump: {self.current_dump.title}")

    def _on_distill(self, _button: Gtk.Button) -> None:
        if self.current_dump is None:
            self._on_save_dump(_button)
        if self.current_dump is None:
            return

        self.current_distillation = self.service.distill_dump(
            self.workspace.id,
            self.current_dump.id,
        )
        rendered = self._render_distillation(self.current_distillation)
        self._set_text(self.distill_view, rendered)

        if not self.draft_title.get_text().strip():
            first_candidate = self.current_distillation.draft_candidates[0]
            self.draft_title.set_text(first_candidate)
        if not self._get_text(self.draft_view).strip():
            self._set_text(
                self.draft_view,
                self._draft_from_distillation(self.current_distillation),
            )
        self._set_status("Distillation generated.")

    def _on_save_draft(self, _button: Gtk.Button) -> None:
        title = self.draft_title.get_text().strip()
        markdown = self._get_text(self.draft_view).strip()
        if not title or not markdown:
            self._set_status("Draft title and body are required.")
            return

        source_ids = [self.current_dump.id] if self.current_dump else []
        if self.current_draft:
            self.current_draft = self.service.update_draft(
                self.workspace.id,
                self.current_draft.id,
                markdown=markdown,
                title=title,
            )
        else:
            self.current_draft = self.service.create_draft(
                self.workspace.id,
                title=title,
                markdown=markdown,
                source_dump_ids=source_ids,
            )
        self._set_status(f"Saved draft: {self.current_draft.title}")

    def _on_export(self, _button: Gtk.Button) -> None:
        if self.current_draft is None:
            self._on_save_draft(_button)
        if self.current_draft is None:
            return

        result = self.service.export_draft(self.workspace.id, self.current_draft.id)
        self._set_status(f"Exported: {result.output_path}")

    def _render_distillation(self, distillation: Distillation) -> str:
        sections = [
            "# Summary",
            distillation.summary or "No summary available.",
            "",
            "# Topics",
            "\n".join(f"- {topic}" for topic in distillation.topics) or "- None",
            "",
            "# Questions",
            "\n".join(f"- {question}" for question in distillation.questions)
            or "- None",
            "",
            "# Tasks",
            "\n".join(f"- {task}" for task in distillation.tasks) or "- None",
            "",
            "# Draft candidates",
            "\n".join(f"- {candidate}" for candidate in distillation.draft_candidates)
            or "- None",
        ]
        return "\n".join(sections)

    def _draft_from_distillation(self, distillation: Distillation) -> str:
        title = distillation.draft_candidates[0]
        topics = ", ".join(distillation.topics[:5]) or "notes"
        return (
            f"# {title}\n\n"
            f"{distillation.summary}\n\n"
            "## Notes\n\n"
            f"- Topics: {topics}\n\n"
            "## Open questions\n\n"
            + "\n".join(f"- {question}" for question in distillation.questions[:5])
        ).rstrip()

    def _get_text(self, view: Gtk.TextView) -> str:
        buffer = view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, True)

    def _set_text(self, view: Gtk.TextView, text: str) -> None:
        view.get_buffer().set_text(text)

    def _set_status(self, message: str) -> None:
        self.status.set_text(message)


class PhantomWriterApplication(Adw.Application):
    """GTK application entrypoint."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = PhantomWriterWindow(self)
        window.present()


def main() -> int:
    app = PhantomWriterApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
