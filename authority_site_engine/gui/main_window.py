"""Tkinter GUI for the Authority Site Engine desktop application."""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional

from ..core.app_config import (
    AppConfig,
    ensure_data_roots,
    get_default_config_path,
    load_app_config,
)
from ..core.deployment_manager import DeploymentError, DeploymentManager
from ..core.models import (
    AffiliateLinkSet,
    AffiliateOffer,
    AutomationSettings,
    BasicSiteInfo,
    CategorySettings,
    CloudflareHostInfo,
    ContentStructureSettings,
    DeploymentSettings,
    HealthMonitoringSettings,
    LinkingRules,
    PostingPreferences,
    ProductLists,
    ProjectData,
    ProjectSummary,
    SchemaSettings,
    ZimmWriterSettings,
    ZimmWriterTemplate,
)
from ..core.project_manager import ProjectManager, slugify
from ..modules.content_sync import ContentSyncModule
from ..modules.log_summary import LogSummaryModule
from ..modules.regeneration import BulkRegenerator
from ..modules.search import GlobalProjectSearch


class BasePanel(ttk.Frame):
    """Common functionality shared by all panels."""

    def __init__(self, master: tk.Widget, app: "AuthoritySiteEngineApp") -> None:
        super().__init__(master, padding=10)
        self.app = app

    def on_show(self) -> None:  # pragma: no cover - UI glue
        """Called whenever the panel becomes visible."""

    def on_project_change(self, project_data: ProjectData) -> None:  # pragma: no cover - UI glue
        """Refresh the panel when the active project changes."""
        self.on_show()

    def get_project_context(self) -> tuple[ProjectData, Path] | tuple[None, None]:
        """Return the current project data/root or notify the user."""

        data = self.app.current_project_data
        root = self.app.get_project_root()
        if not data or root is None:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return None, None
        return data, root


class AuthoritySiteEngineApp(tk.Tk):
    """High-level desktop window with sidebar navigation for all modules."""

    def __init__(
        self,
        manager: ProjectManager,
        *,
        config: AppConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.app_config = config or AppConfig(
            projects_root=self.manager.projects_dir,
            logs_root=self.manager.base_directory / "logs",
        )
        self.config_path = config_path or get_default_config_path()
        self.title("Authority Site Engine")
        self.geometry("1280x820")
        self.minsize(1180, 720)
        self.status_var = tk.StringVar(value="Ready")
        self.active_project_var = tk.StringVar(value="No project selected")
        self.current_project_data: Optional[ProjectData] = None
        self.current_project_summary: Optional[ProjectSummary] = None
        self.active_panel: Optional[BasePanel] = None
        self.panels: Dict[str, BasePanel] = {}
        self._build_layout()
        self.show_panel("Projects")

    def _build_layout(self) -> None:
        top_bar = ttk.Frame(self, padding=(12, 10))
        top_bar.pack(fill="x")
        ttk.Label(top_bar, text="Authority Site Engine", font=("Segoe UI", 16, "bold")).pack(
            side="left"
        )
        ttk.Label(top_bar, textvariable=self.active_project_var).pack(side="right", padx=10)
        ttk.Label(top_bar, textvariable=self.status_var, foreground="#2c7a7b").pack(side="right")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        sidebar = ttk.Frame(container, width=220, padding=(6, 12))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.content_frame = ttk.Frame(container)
        self.content_frame.pack(side="left", fill="both", expand=True)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        module_definitions = [
            ("Projects", ProjectsPanel),
            ("Project Config", ProjectConfigPanel),
            ("Topical Blueprint", TopicalBlueprintPanel),
            ("Posting Engine", PostingPanel),
            ("Internal Linking", InternalLinkingPanel),
            ("Categories & Menu", CategoryMenuPanel),
            ("Affiliate Engine", AffiliatePanel),
            ("Schema Engine", SchemaPanel),
            ("Deployment", DeploymentPanel),
            ("Health Monitor", HealthPanel),
            ("Automation", AutomationPanel),
            ("Logs / Debug", LogsPanel),
            ("Global Search", GlobalSearchPanel),
            ("Global Settings", GlobalSettingsPanel),
        ]

        for name, panel_cls in module_definitions:
            button = ttk.Button(sidebar, text=name, command=lambda n=name: self.show_panel(n))
            button.pack(fill="x", pady=2)
            panel = panel_cls(self.content_frame, self)
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_remove()
            self.panels[name] = panel

    def show_panel(self, name: str) -> None:
        if self.active_panel:
            self.active_panel.grid_remove()
        panel = self.panels[name]
        panel.grid()
        panel.on_show()
        self.active_panel = panel
        self.status_var.set(f"Viewing {name}")

    def select_project(self, summary: ProjectSummary) -> None:
        self.current_project_summary = summary
        self.active_project_var.set(summary.project_name)
        try:
            data = self.manager.load_project(summary.project_name)
        except FileNotFoundError:
            messagebox.showerror("Missing Project", f"Unable to load {summary.project_name}.")
            return
        self.current_project_data = data
        for panel in self.panels.values():
            panel.on_project_change(data)

    def refresh_projects(self) -> None:
        panel = self.panels.get("Projects")
        if isinstance(panel, ProjectsPanel):
            panel.refresh_projects()

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def update_data_root(self, data_root: Path) -> None:
        """Reinitialize the project manager using a new data root."""

        self.app_config.projects_root = data_root / "projects"
        self.app_config.logs_root = data_root / "logs"
        ensure_data_roots(self.app_config)
        self.manager = ProjectManager(base_directory=data_root)
        self.current_project_data = None
        self.current_project_summary = None
        self.active_project_var.set("No project selected")
        self.refresh_projects()

    def show_first_run_dialog(self) -> None:
        """Display a lightweight onboarding dialog during the first launch."""

        dialog = tk.Toplevel(self)
        dialog.title("Welcome to Authority Site Engine")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(
            dialog,
            text=(
                "Choose where your projects and logs should live. "
                "You can change these defaults later from Global Settings."
            ),
            wraplength=420,
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=10, sticky="w")
        ttk.Label(dialog, text="Data directory").grid(row=1, column=0, sticky="e", padx=8, pady=6)
        base_dir_var = tk.StringVar(value=str(self.app_config.projects_root.parent))
        ttk.Entry(dialog, textvariable=base_dir_var, width=45).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )
        ttk.Label(dialog, text="HTTP timeout (seconds)").grid(
            row=2, column=0, sticky="e", padx=8, pady=6
        )
        timeout_var = tk.StringVar(value=str(self.app_config.http_timeout))
        ttk.Entry(dialog, textvariable=timeout_var, width=10).grid(
            row=2, column=1, sticky="w", padx=8, pady=6
        )

        def _apply_defaults() -> None:
            try:
                timeout_value = int(timeout_var.get() or self.app_config.http_timeout)
            except ValueError:
                messagebox.showerror("Invalid Value", "Timeout must be an integer.")
                return
            base_path = Path(base_dir_var.get()).expanduser()
            base_path.mkdir(parents=True, exist_ok=True)
            self.app_config.http_timeout = timeout_value
            self.update_data_root(base_path)
            if self.config_path:
                self.app_config.save(self.config_path)
            dialog.destroy()
            messagebox.showinfo(
                "Setup Complete",
                "Defaults saved. Use the Global Settings panel to make further changes.",
            )

        ttk.Button(dialog, text="Save", command=_apply_defaults).grid(
            row=3, column=0, padx=8, pady=12, sticky="e"
        )
        ttk.Button(dialog, text="Skip", command=dialog.destroy).grid(
            row=3, column=1, padx=8, pady=12, sticky="w"
        )
        dialog.columnconfigure(1, weight=1)

    def get_project_root(self) -> Optional[Path]:
        if self.current_project_summary:
            return Path(self.current_project_summary.project_root)
        if self.current_project_data:
            slug = slugify(self.current_project_data.basic_info.project_name)
            return self.manager.projects_dir / slug
        return None


class ProjectsPanel(BasePanel):
    """Default overview screen showing all configured projects."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.tree = ttk.Treeview(
            self,
            columns=("project", "domain", "niche", "status", "health", "automation"),
            show="headings",
            height=12,
        )
        headings = [
            ("project", "Project"),
            ("domain", "Domain"),
            ("niche", "Niche"),
            ("status", "Deployment"),
            ("health", "Health"),
            ("automation", "Automation"),
        ]
        for key, label in headings:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=140 if key != "project" else 160)
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._update_summary())

        action_frame = ttk.Frame(self)
        action_frame.pack(side="right", fill="y", padx=10)
        ttk.Button(action_frame, text="Create New Project", command=self._create_new).pack(fill="x", pady=4)
        ttk.Button(action_frame, text="Open / Edit", command=self._open_selected).pack(fill="x", pady=4)
        ttk.Button(action_frame, text="Select", command=self._select_active).pack(fill="x", pady=4)
        ttk.Button(action_frame, text="Delete", command=self._delete_selected).pack(fill="x", pady=4)
        ttk.Button(action_frame, text="Refresh", command=self.refresh_projects).pack(fill="x", pady=4)

        summary = ttk.LabelFrame(self, text="Project Summary", padding=10)
        summary.pack(fill="x", expand=False, pady=10)
        self.summary_vars = {
            "domain": tk.StringVar(value="Domain: -"),
            "niche": tk.StringVar(value="Niche: -"),
            "status": tk.StringVar(value="Deployment: -"),
            "health": tk.StringVar(value="Health: -"),
            "automation": tk.StringVar(value="Automation: -"),
        }
        for var in self.summary_vars.values():
            ttk.Label(summary, textvariable=var).pack(anchor="w")
        self.project_cache: List[ProjectSummary] = []

    def refresh_projects(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.project_cache = self.app.manager.list_projects()
        for summary in self.project_cache:
            self.tree.insert(
                "",
                "end",
                iid=summary.project_name,
                values=(
                    summary.project_name,
                    summary.domain,
                    summary.niche,
                    summary.status,
                    summary.health_status or "-",
                    "Yes" if summary.automation_enabled else "No",
                ),
            )
        self._update_summary()

    def _get_selected_summary(self) -> Optional[ProjectSummary]:
        selection = self.tree.selection()
        if not selection:
            return None
        project_name = selection[0]
        for summary in self.project_cache:
            if summary.project_name == project_name:
                return summary
        return None

    def _update_summary(self) -> None:
        summary = self._get_selected_summary()
        if not summary:
            for key, var in self.summary_vars.items():
                var.set(f"{key.title()}: -")
            return
        self.summary_vars["domain"].set(f"Domain: {summary.domain or '-'}")
        self.summary_vars["niche"].set(f"Niche: {summary.niche or '-'}")
        self.summary_vars["status"].set(f"Deployment: {summary.status or '-'}")
        health = summary.health_status or "No data"
        if summary.last_health_check:
            health = f"{health} (last {summary.last_health_check})"
        self.summary_vars["health"].set(f"Health: {health}")
        self.summary_vars["automation"].set(
            f"Automation: {'Enabled' if summary.automation_enabled else 'Disabled'}"
        )

    def _create_new(self) -> None:
        config_panel = self.app.panels.get("Project Config")
        if isinstance(config_panel, ProjectConfigPanel):
            config_panel.clear_form()
        self.app.show_panel("Project Config")
        self.app.set_status("Creating new project configuration")

    def _open_selected(self) -> None:
        summary = self._get_selected_summary()
        if not summary:
            messagebox.showinfo("Select Project", "Please choose a project to edit.")
            return
        self.app.select_project(summary)
        self.app.show_panel("Project Config")

    def _select_active(self) -> None:
        summary = self._get_selected_summary()
        if not summary:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return
        self.app.select_project(summary)
        self.app.set_status(f"Active project set to {summary.project_name}")

    def _delete_selected(self) -> None:
        summary = self._get_selected_summary()
        if not summary:
            messagebox.showinfo("Select Project", "Choose a project to delete.")
            return
        if not messagebox.askyesno(
            "Delete Project", f"Are you sure you want to delete {summary.project_name}?"
        ):
            return
        self.app.manager.delete_project(summary.project_name)
        self.refresh_projects()
        self.app.set_status(f"Deleted {summary.project_name}")

    def on_show(self) -> None:
        self.refresh_projects()


class ProjectConfigPanel(BasePanel):
    """Panel for editing project configuration (Part 1)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.current_project_name = ""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self._build_basic_info_tab()
        self._build_cloudflare_tab()
        self._build_structure_tab()
        self._build_category_tab()
        self._build_product_tab()
        self._build_affiliate_tab()
        self._build_posting_tab()
        self._build_zimmwriter_tab()
        self._build_linking_tab()
        self._build_health_tab()
        self._build_deployment_tab()
        self._build_automation_tab()

        action_bar = ttk.Frame(self)
        action_bar.pack(fill="x", pady=8)
        ttk.Button(action_bar, text="Save Project Config", command=self._save_project).pack(side="right")
        self.form_status = tk.StringVar(value="Unsaved changes")
        ttk.Label(action_bar, textvariable=self.form_status).pack(side="left")

    def _build_basic_info_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Basic Info")
        labels = [
            "Project Name",
            "Niche / Topic",
            "Domain Name",
            "WordPress Admin URL",
            "WordPress Username",
            "WordPress Password",
        ]
        self.basic_vars: List[tk.StringVar] = [tk.StringVar() for _ in labels]
        for i, (label, var) in enumerate(zip(labels, self.basic_vars)):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            show = "*" if "Password" in label else None
            ttk.Entry(frame, textvariable=var, show=show).grid(row=i, column=1, sticky="ew", padx=8, pady=4)
        frame.columnconfigure(1, weight=1)

    def _build_cloudflare_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Cloudflare & Host")
        labels = [
            "Cloudflare Email",
            "Cloudflare Global API Key",
            "SSH Host (optional)",
            "SSH Username",
            "SSH Password",
        ]
        self.cloudflare_vars: List[tk.StringVar] = [tk.StringVar() for _ in labels]
        for i, (label, var) in enumerate(zip(labels, self.cloudflare_vars)):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            show = "*" if "Password" in label else None
            ttk.Entry(frame, textvariable=var, show=show).grid(row=i, column=1, sticky="ew", padx=8, pady=4)
        frame.columnconfigure(1, weight=1)

    def _build_structure_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Content Structure")
        labels = [
            ("Pillar Posts", 12),
            ("Supporting Posts per Pillar", 10),
            ("Informational Posts", 300),
            ("Affiliate Product Posts", 40),
            ("Amazon Roundup Posts", 20),
            ("Custom Product Posts", 20),
        ]
        self.structure_vars: List[tk.StringVar] = []
        for i, (label, default) in enumerate(labels):
            var = tk.StringVar(value=str(default))
            self.structure_vars.append(var)
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            ttk.Spinbox(frame, from_=0, to=1000, textvariable=var).grid(row=i, column=1, sticky="w", padx=8, pady=4)

    def _build_category_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Categories")
        self.category_vars = [tk.StringVar() for _ in range(4)]
        for i, var in enumerate(self.category_vars):
            ttk.Label(frame, text=f"Category {i + 1}").grid(row=i, column=0, sticky="w", padx=8, pady=4)
            ttk.Entry(frame, textvariable=var, width=40).grid(row=i, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(frame, text="Suggest", command=self._apply_category_suggestions).grid(
            row=5, column=0, columnspan=2, pady=8
        )
        frame.columnconfigure(1, weight=1)

    def _build_product_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Product Lists")
        ttk.Label(frame, text="Paste one product per line for each list").pack(anchor="w", padx=8, pady=4)
        self.affiliate_products_text = tk.Text(frame, height=6)
        self.amazon_products_text = tk.Text(frame, height=6)
        self.custom_products_text = tk.Text(frame, height=6)
        self.product_notes = tk.Text(frame, height=4)
        widgets = [
            ("Affiliate Product List", self.affiliate_products_text),
            ("Amazon Product List", self.amazon_products_text),
            ("Custom Product List", self.custom_products_text),
        ]
        for label, widget in widgets:
            ttk.Label(frame, text=label).pack(anchor="w", padx=8, pady=2)
            widget.pack(fill="x", padx=8, pady=2)
        ttk.Label(frame, text="Notes").pack(anchor="w", padx=8, pady=2)
        self.product_notes.pack(fill="x", padx=8, pady=2)

    def _build_affiliate_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Affiliate Links")
        self.cpa_text = tk.Text(frame, height=4)
        self.amazon_text = tk.Text(frame, height=4)
        self.custom_text = tk.Text(frame, height=4)
        self.geo_text = tk.Text(frame, height=4)
        self.backup_var = tk.StringVar()
        widgets = [
            ("CPA Links", self.cpa_text),
            ("Amazon Links", self.amazon_text),
            ("Custom External Links", self.custom_text),
            ("Geo Targeted Links (COUNTRY=URL)", self.geo_text),
        ]
        for label, widget in widgets:
            ttk.Label(frame, text=label).pack(anchor="w", padx=8, pady=2)
            widget.pack(fill="x", padx=8, pady=2)
        ttk.Label(frame, text="Backup URL").pack(anchor="w", padx=8, pady=2)
        ttk.Entry(frame, textvariable=self.backup_var).pack(fill="x", padx=8, pady=2)

    def _build_posting_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Posting & Scheduling")
        self.post_immediately = tk.BooleanVar(value=True)
        self.drip_posting = tk.BooleanVar(value=True)
        self.interval_var = tk.StringVar(value="24")
        self.sequence_var = tk.StringVar(value="pillar,supporting,affiliate,informational")
        ttk.Checkbutton(frame, text="Post Immediately", variable=self.post_immediately).grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Checkbutton(frame, text="Drip Posting", variable=self.drip_posting).grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Label(frame, text="Scheduling Interval (hours)").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frame, textvariable=self.interval_var).grid(row=2, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frame, text="Publish Sequence (comma separated)").grid(
            row=3, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Entry(frame, textvariable=self.sequence_var).grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        frame.columnconfigure(1, weight=1)

    def _build_zimmwriter_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="ZimmWriter CSV")
        self.template_entries: List[tuple[tk.StringVar, tk.StringVar, tk.StringVar]] = []
        defaults = [
            ("Pillar Posts", "pillar_template.csv", "Long-form pillar content"),
            ("Supporting Posts", "supporting_template.csv", "Supporting articles"),
            ("Informational Posts", "info_template.csv", "Answer questions"),
            ("Product Reviews", "product_reviews.csv", "Product reviews"),
            ("Amazon Roundups", "amazon_roundups.csv", "Roundup of products"),
        ]
        for i, (name, path, desc) in enumerate(defaults):
            name_var = tk.StringVar(value=name)
            path_var = tk.StringVar(value=path)
            desc_var = tk.StringVar(value=desc)
            self.template_entries.append((name_var, path_var, desc_var))
            base = i * 3
            ttk.Label(frame, text=f"Template {i + 1} Name").grid(row=base, column=0, sticky="w", padx=8, pady=2)
            ttk.Entry(frame, textvariable=name_var).grid(row=base, column=1, sticky="ew", padx=8, pady=2)
            ttk.Label(frame, text="File Name").grid(row=base + 1, column=0, sticky="w", padx=8, pady=2)
            ttk.Entry(frame, textvariable=path_var).grid(row=base + 1, column=1, sticky="ew", padx=8, pady=2)
            ttk.Label(frame, text="Description").grid(row=base + 2, column=0, sticky="w", padx=8, pady=2)
            ttk.Entry(frame, textvariable=desc_var).grid(row=base + 2, column=1, sticky="ew", padx=8, pady=2)
        frame.columnconfigure(1, weight=1)

    def _build_linking_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Linking Rules")
        self.link_vars = {
            "supporting_to_pillar": tk.BooleanVar(value=True),
            "pillar_to_supporting": tk.BooleanVar(value=True),
            "informational_to_pillar": tk.BooleanVar(value=True),
            "informational_to_supporting": tk.BooleanVar(value=True),
            "affiliate_to_pillar": tk.BooleanVar(value=True),
            "affiliate_to_affiliate": tk.BooleanVar(value=False),
            "amazon_roundup_to_pillar": tk.BooleanVar(value=True),
            "allow_cross_topic_links": tk.BooleanVar(value=False),
        }
        for i, (label, var) in enumerate(self.link_vars.items()):
            ttk.Checkbutton(frame, text=label.replace("_", " ").title(), variable=var).grid(
                row=i, column=0, sticky="w", padx=8, pady=2
            )

    def _build_health_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Monitoring")
        self.health_vars = {
            "enable_http_checks": tk.BooleanVar(value=True),
            "enable_ssl_check": tk.BooleanVar(value=True),
            "enable_sitemap_check": tk.BooleanVar(value=True),
            "enable_linking_check": tk.BooleanVar(value=True),
            "enable_content_stats": tk.BooleanVar(value=True),
            "enable_cloudflare_stats": tk.BooleanVar(value=False),
        }
        self.health_sample_var = tk.StringVar(value="3")
        self.health_timeout_var = tk.StringVar(value="15")
        self.health_hours_var = tk.StringVar(value="24")
        row = 0
        for label, var in self.health_vars.items():
            ttk.Checkbutton(frame, text=label.replace("_", " ").title(), variable=var).grid(
                row=row, column=0, sticky="w", padx=8, pady=2
            )
            row += 1
        ttk.Label(frame, text="HTTP Sample Posts").grid(row=row, column=0, sticky="w", padx=8, pady=2)
        ttk.Entry(frame, textvariable=self.health_sample_var, width=10).grid(
            row=row, column=1, sticky="w", padx=8, pady=2
        )
        row += 1
        ttk.Label(frame, text="HTTP Timeout (s)").grid(row=row, column=0, sticky="w", padx=8, pady=2)
        ttk.Entry(frame, textvariable=self.health_timeout_var, width=10).grid(
            row=row, column=1, sticky="w", padx=8, pady=2
        )
        row += 1
        ttk.Label(frame, text="Cloudflare Window (hours)").grid(row=row, column=0, sticky="w", padx=8, pady=2)
        ttk.Entry(frame, textvariable=self.health_hours_var, width=10).grid(
            row=row, column=1, sticky="w", padx=8, pady=2
        )

    def _build_deployment_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Deployment")
        self.deployment_flags = {
            "configure_cloudflare": tk.BooleanVar(value=True),
            "enforce_https": tk.BooleanVar(value=True),
            "install_wordpress": tk.BooleanVar(value=False),
            "install_theme": tk.BooleanVar(value=True),
            "install_plugins": tk.BooleanVar(value=True),
            "deploy_content": tk.BooleanVar(value=True),
            "run_category_builder": tk.BooleanVar(value=True),
            "run_internal_linking": tk.BooleanVar(value=True),
            "run_affiliate": tk.BooleanVar(value=True),
            "run_schema": tk.BooleanVar(value=True),
            "ping_sitemaps": tk.BooleanVar(value=True),
            "strict_mode": tk.BooleanVar(value=False),
        }
        checkbox_labels = [
            ("Configure Cloudflare", "configure_cloudflare"),
            ("Enforce HTTPS", "enforce_https"),
            ("Install WordPress", "install_wordpress"),
            ("Install Theme", "install_theme"),
            ("Install Plugins", "install_plugins"),
            ("Deploy Content", "deploy_content"),
            ("Run Category Builder", "run_category_builder"),
            ("Run Internal Linking", "run_internal_linking"),
            ("Run Affiliate Engine", "run_affiliate"),
            ("Run Schema Engine", "run_schema"),
            ("Ping Sitemaps", "ping_sitemaps"),
            ("Strict Mode (stop on failure)", "strict_mode"),
        ]
        for i, (label, key) in enumerate(checkbox_labels):
            ttk.Checkbutton(frame, text=label, variable=self.deployment_flags[key]).grid(
                row=i, column=0, columnspan=2, sticky="w", padx=8, pady=2
            )
        self.theme_slug_var = tk.StringVar()
        self.theme_zip_var = tk.StringVar()
        self.wp_cli_var = tk.StringVar(value="wp")
        self.site_title_var = tk.StringVar()
        self.deployment_admin_email = tk.StringVar()
        self.timezone_var = tk.StringVar(value="UTC")
        self.permalink_var = tk.StringVar(value="/%postname%/")
        self.site_url_var = tk.StringVar()
        self.rest_username_var = tk.StringVar()
        self.app_password_var = tk.StringVar()
        self.wp_api_base_var = tk.StringVar()
        entries = [
            ("Live Site URL", self.site_url_var, None),
            ("WP REST Username", self.rest_username_var, None),
            ("WP Application Password", self.app_password_var, "*"),
            ("WP API Base URL", self.wp_api_base_var, None),
            ("Theme Slug", self.theme_slug_var, None),
            ("Theme ZIP URL", self.theme_zip_var, None),
            ("WP-CLI Path", self.wp_cli_var, None),
            ("Site Title", self.site_title_var, None),
            ("Admin Email", self.deployment_admin_email, None),
            ("Timezone", self.timezone_var, None),
            ("Permalink Structure", self.permalink_var, None),
        ]
        start = len(checkbox_labels)
        for offset, (label, var, show) in enumerate(entries):
            ttk.Label(frame, text=label).grid(row=start + offset, column=0, sticky="w", padx=8, pady=4)
            ttk.Entry(frame, textvariable=var, show=show).grid(
                row=start + offset, column=1, sticky="ew", padx=8, pady=4
            )
        self.plugin_slugs_text = tk.Text(frame, height=3)
        self.plugin_zip_text = tk.Text(frame, height=3)
        self.sitemap_paths_text = tk.Text(frame, height=3)
        text_widgets = [
            ("Plugin Slugs (one per line)", self.plugin_slugs_text),
            ("Plugin ZIP URLs", self.plugin_zip_text),
            ("Sitemap Paths", self.sitemap_paths_text),
        ]
        row = start + len(entries)
        for label, widget in text_widgets:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", padx=8, pady=4)
            widget.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
            row += 1
        frame.columnconfigure(1, weight=1)

    def _build_automation_tab(self) -> None:
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Automation")
        self.automation_enabled_var = tk.BooleanVar(value=False)
        self.automation_defaults: Dict[str, tuple[bool, str]] = {}
        ttk.Checkbutton(frame, text="Enable Daily Automation", variable=self.automation_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=4
        )
        self.automation_task_vars: Dict[str, tuple[tk.BooleanVar, tk.StringVar]] = {}
        task_rows = [
            ("health_check", "Health Monitor Interval (hours)", True, 24),
            ("affiliate_check", "Affiliate Check Interval (hours)", True, 48),
            ("sitemap_ping", "Sitemap Ping Interval (hours)", False, 168),
            ("linking_maintenance", "Link Maintenance Interval (hours)", False, 168),
            ("content_review", "Content Review Interval (hours)", True, 24),
            ("cloudflare_stats", "Cloudflare Stats Interval (hours)", False, 24),
            ("log_cleanup", "Log Cleanup Interval (hours)", True, 720),
        ]
        for idx, (key, label, enabled, default_hours) in enumerate(task_rows, start=1):
            enabled_var = tk.BooleanVar(value=enabled)
            interval_var = tk.StringVar(value=str(default_hours))
            self.automation_task_vars[key] = (enabled_var, interval_var)
            self.automation_defaults[key] = (enabled, str(default_hours))
            ttk.Checkbutton(frame, text=label, variable=enabled_var).grid(
                row=idx, column=0, sticky="w", padx=8, pady=2
            )
            ttk.Entry(frame, textvariable=interval_var, width=6).grid(
                row=idx, column=1, sticky="w", padx=8, pady=2
            )
        self.automation_throttle_var = tk.StringVar(value="0")
        self.automation_retention_var = tk.StringVar(value="30")
        base = len(task_rows) + 1
        ttk.Label(frame, text="Throttle seconds between tasks").grid(
            row=base, column=0, sticky="w", padx=8, pady=4
        )
        ttk.Entry(frame, textvariable=self.automation_throttle_var, width=8).grid(
            row=base, column=1, sticky="w", padx=8, pady=4
        )
        ttk.Label(frame, text="Log retention (days)").grid(row=base + 1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frame, textvariable=self.automation_retention_var, width=8).grid(
            row=base + 1, column=1, sticky="w", padx=8, pady=4
        )

    # Helper methods -------------------------------------------------
    def _apply_category_suggestions(self) -> None:
        niche = self.basic_vars[1].get()
        suggestions = self.app.manager.suggest_categories(niche)
        for var, suggestion in zip(self.category_vars, suggestions):
            var.set(suggestion)
        self.form_status.set("Category suggestions applied")

    def clear_form(self) -> None:
        for var in self.basic_vars + self.cloudflare_vars + self.category_vars:
            var.set("")
        for var in self.structure_vars:
            var.set("0")
        for widget in [
            self.affiliate_products_text,
            self.amazon_products_text,
            self.custom_products_text,
            self.product_notes,
            self.cpa_text,
            self.amazon_text,
            self.custom_text,
            self.geo_text,
            self.plugin_slugs_text,
            self.plugin_zip_text,
            self.sitemap_paths_text,
        ]:
            widget.delete("1.0", "end")
        self.backup_var.set("")
        self.post_immediately.set(True)
        self.drip_posting.set(True)
        self.interval_var.set("24")
        self.sequence_var.set("pillar,supporting,affiliate,informational")
        for name_var, path_var, desc_var in self.template_entries:
            name_var.set(name_var.get())
            path_var.set(path_var.get())
            desc_var.set(desc_var.get())
        for key, var in self.link_vars.items():
            var.set(key not in {"affiliate_to_affiliate", "allow_cross_topic_links"})
        for key, var in self.health_vars.items():
            var.set(key != "enable_cloudflare_stats")
        self.health_sample_var.set("3")
        self.health_timeout_var.set("15")
        self.health_hours_var.set("24")
        for flag in self.deployment_flags.values():
            flag.set(True)
        self.deployment_flags["install_wordpress"].set(False)
        self.deployment_flags["strict_mode"].set(False)
        self.theme_slug_var.set("")
        self.theme_zip_var.set("")
        self.wp_cli_var.set("wp")
        self.site_title_var.set("")
        self.deployment_admin_email.set("")
        self.timezone_var.set("UTC")
        self.permalink_var.set("/%postname%/")
        self.site_url_var.set("")
        self.rest_username_var.set("")
        self.app_password_var.set("")
        self.wp_api_base_var.set("")
        self.automation_enabled_var.set(False)
        for key, (enabled_var, interval_var) in self.automation_task_vars.items():
            default_enabled, default_interval = self.automation_defaults.get(key, (True, interval_var.get()))
            enabled_var.set(default_enabled)
            interval_var.set(default_interval)
        self.automation_throttle_var.set("0")
        self.automation_retention_var.set("30")
        self.form_status.set("Ready for new project")

    def load_project(self, project_data: ProjectData) -> None:
        self.current_project_name = project_data.basic_info.project_name
        basic = project_data.basic_info
        payloads = [
            (
                self.basic_vars,
                [
                    basic.project_name,
                    basic.niche,
                    basic.domain_name,
                    basic.wp_admin_url,
                    basic.wp_username,
                    basic.wp_password,
                ],
            ),
            (
                self.cloudflare_vars,
                [
                    project_data.cloudflare.cloudflare_email,
                    project_data.cloudflare.cloudflare_api_key,
                    project_data.cloudflare.ssh_host,
                    project_data.cloudflare.ssh_username,
                    project_data.cloudflare.ssh_password,
                ],
            ),
        ]
        for vars_, values in payloads:
            for var, value in zip(vars_, values):
                var.set(value)
        structure = project_data.content_structure
        for var, value in zip(
            self.structure_vars,
            [
                structure.pillar_posts,
                structure.supporting_posts_per_pillar,
                structure.informational_posts,
                structure.affiliate_product_posts,
                structure.amazon_roundup_posts,
                structure.custom_product_posts,
            ],
        ):
            var.set(str(value))
        for var, value in zip(self.category_vars, project_data.categories.categories):
            var.set(value)
        self._set_text_widget(self.affiliate_products_text, project_data.product_lists.affiliate_products)
        self._set_text_widget(self.amazon_products_text, project_data.product_lists.amazon_products)
        self._set_text_widget(self.custom_products_text, project_data.product_lists.custom_products)
        self.product_notes.delete("1.0", "end")
        self.product_notes.insert("1.0", project_data.product_lists.notes)
        affiliate = project_data.affiliate_links
        self._set_text_widget(self.cpa_text, affiliate.cpa_links)
        self._set_text_widget(self.amazon_text, affiliate.amazon_links)
        self._set_text_widget(self.custom_text, affiliate.custom_links)
        self.geo_text.delete("1.0", "end")
        for country, url in affiliate.geo_targeted.items():
            self.geo_text.insert("end", f"{country}={url}\n")
        self.backup_var.set(affiliate.backup_url)
        posting = project_data.posting_preferences
        self.post_immediately.set(posting.post_immediately)
        self.drip_posting.set(posting.drip_posting)
        self.interval_var.set(str(posting.scheduling_interval_hours))
        self.sequence_var.set(",".join(posting.publish_sequence))
        for tpl, template in zip(self.template_entries, project_data.zimmwriter.templates):
            tpl[0].set(template.name)
            tpl[1].set(template.template_path)
            tpl[2].set(template.description)
        for key, var in self.link_vars.items():
            var.set(getattr(project_data.linking_rules, key, False))
        health = project_data.health
        for key, var in self.health_vars.items():
            var.set(getattr(health, key))
        self.health_sample_var.set(str(health.http_sample_size))
        self.health_timeout_var.set(str(health.http_timeout))
        self.health_hours_var.set(str(health.cloudflare_hours))
        deployment = project_data.deployment
        for key, flag in self.deployment_flags.items():
            flag.set(getattr(deployment, key, False))
        self.theme_slug_var.set(deployment.theme_slug)
        self.theme_zip_var.set(deployment.theme_zip_url)
        self.wp_cli_var.set(deployment.wp_cli_path)
        self.site_title_var.set(deployment.site_title)
        self.deployment_admin_email.set(deployment.admin_email)
        self.timezone_var.set(deployment.timezone)
        self.permalink_var.set(deployment.permalink_structure)
        self.site_url_var.set(deployment.site_url)
        self.rest_username_var.set(deployment.wp_rest_username)
        self.app_password_var.set(deployment.wp_app_password)
        self.wp_api_base_var.set(deployment.wp_api_base_url)
        self._set_text_widget(self.plugin_slugs_text, deployment.plugin_slugs)
        self._set_text_widget(self.plugin_zip_text, deployment.plugin_zip_urls)
        self._set_text_widget(self.sitemap_paths_text, deployment.sitemap_paths)
        automation = project_data.automation
        self.automation_enabled_var.set(automation.automation_enabled)
        for key, (enabled_var, interval_var) in self.automation_task_vars.items():
            config = getattr(automation, key)
            enabled_var.set(config.enabled)
            interval_var.set(str(config.interval_hours))
        self.automation_throttle_var.set(str(automation.throttle_seconds))
        self.automation_retention_var.set(str(automation.log_retention_days))
        self.form_status.set(f"Loaded {project_data.basic_info.project_name}")

    def _set_text_widget(self, widget: tk.Text, values: List[str]) -> None:
        widget.delete("1.0", "end")
        for value in values:
            widget.insert("end", f"{value}\n")

    def _lines_from_text(self, widget: tk.Text) -> List[str]:
        return [line.strip() for line in widget.get("1.0", "end").splitlines() if line.strip()]

    def _geo_dict_from_text(self, widget: tk.Text) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for line in widget.get("1.0", "end").splitlines():
            if "=" in line:
                country, url = line.split("=", 1)
                mapping[country.strip()] = url.strip()
        return mapping

    def _gather_data(self) -> ProjectData:
        basic = BasicSiteInfo(
            project_name=self.basic_vars[0].get().strip(),
            niche=self.basic_vars[1].get().strip(),
            domain_name=self.basic_vars[2].get().strip(),
            wp_admin_url=self.basic_vars[3].get().strip(),
            wp_username=self.basic_vars[4].get().strip(),
            wp_password=self.basic_vars[5].get().strip(),
        )
        cloudflare = CloudflareHostInfo(
            cloudflare_email=self.cloudflare_vars[0].get().strip(),
            cloudflare_api_key=self.cloudflare_vars[1].get().strip(),
            ssh_host=self.cloudflare_vars[2].get().strip(),
            ssh_username=self.cloudflare_vars[3].get().strip(),
            ssh_password=self.cloudflare_vars[4].get().strip(),
        )
        content_structure = ContentStructureSettings(
            *[int(var.get() or 0) for var in self.structure_vars]
        )
        categories = [var.get().strip() for var in self.category_vars if var.get().strip()]
        suggestions = self.app.manager.suggest_categories(basic.niche)
        category_settings = CategorySettings(suggestions=suggestions, categories=categories)
        product_lists = ProductLists(
            affiliate_products=self._lines_from_text(self.affiliate_products_text),
            amazon_products=self._lines_from_text(self.amazon_products_text),
            custom_products=self._lines_from_text(self.custom_products_text),
            notes=self.product_notes.get("1.0", "end").strip(),
        )
        affiliate_links = AffiliateLinkSet(
            cpa_links=self._lines_from_text(self.cpa_text),
            amazon_links=self._lines_from_text(self.amazon_text),
            custom_links=self._lines_from_text(self.custom_text),
            geo_targeted=self._geo_dict_from_text(self.geo_text),
            backup_url=self.backup_var.get().strip(),
        )
        posting_preferences = PostingPreferences(
            post_immediately=self.post_immediately.get(),
            scheduling_interval_hours=int(self.interval_var.get() or 0),
            drip_posting=self.drip_posting.get(),
            publish_sequence=[segment.strip() for segment in self.sequence_var.get().split(",") if segment.strip()],
        )
        templates = [
            ZimmWriterTemplate(name=name.get(), template_path=path.get(), description=desc.get())
            for name, path, desc in self.template_entries
            if name.get().strip()
        ]
        zimmwriter = ZimmWriterSettings(templates=templates)
        linking_rules = LinkingRules(**{key: var.get() for key, var in self.link_vars.items()})
        deployment = DeploymentSettings(
            configure_cloudflare=self.deployment_flags["configure_cloudflare"].get(),
            enforce_https=self.deployment_flags["enforce_https"].get(),
            install_wordpress=self.deployment_flags["install_wordpress"].get(),
            install_theme=self.deployment_flags["install_theme"].get(),
            install_plugins=self.deployment_flags["install_plugins"].get(),
            deploy_content=self.deployment_flags["deploy_content"].get(),
            run_category_builder=self.deployment_flags["run_category_builder"].get(),
            run_internal_linking=self.deployment_flags["run_internal_linking"].get(),
            run_affiliate=self.deployment_flags["run_affiliate"].get(),
            run_schema=self.deployment_flags["run_schema"].get(),
            ping_sitemaps=self.deployment_flags["ping_sitemaps"].get(),
            theme_slug=self.theme_slug_var.get().strip(),
            theme_zip_url=self.theme_zip_var.get().strip(),
            plugin_slugs=self._lines_from_text(self.plugin_slugs_text),
            plugin_zip_urls=self._lines_from_text(self.plugin_zip_text),
            sitemap_paths=self._lines_from_text(self.sitemap_paths_text) or ["/wp-sitemap.xml"],
            wp_cli_path=self.wp_cli_var.get().strip() or "wp",
            strict_mode=self.deployment_flags["strict_mode"].get(),
            site_title=self.site_title_var.get().strip(),
            admin_email=self.deployment_admin_email.get().strip(),
            timezone=self.timezone_var.get().strip() or "UTC",
            permalink_structure=self.permalink_var.get().strip() or "/%postname%/",
            site_url=self.site_url_var.get().strip(),
            wp_rest_username=self.rest_username_var.get().strip(),
            wp_app_password=self.app_password_var.get().strip(),
            wp_api_base_url=self.wp_api_base_var.get().strip(),
        )
        health = HealthMonitoringSettings(
            enable_http_checks=self.health_vars["enable_http_checks"].get(),
            http_sample_size=int(self.health_sample_var.get() or 0),
            enable_ssl_check=self.health_vars["enable_ssl_check"].get(),
            enable_sitemap_check=self.health_vars["enable_sitemap_check"].get(),
            enable_linking_check=self.health_vars["enable_linking_check"].get(),
            enable_content_stats=self.health_vars["enable_content_stats"].get(),
            enable_cloudflare_stats=self.health_vars["enable_cloudflare_stats"].get(),
            http_timeout=int(self.health_timeout_var.get() or 15),
            cloudflare_hours=int(self.health_hours_var.get() or 24),
        )
        automation = AutomationSettings(
            automation_enabled=self.automation_enabled_var.get(),
            throttle_seconds=float(self.automation_throttle_var.get() or 0),
            log_retention_days=int(self.automation_retention_var.get() or 30),
        )
        for key, (enabled_var, interval_var) in self.automation_task_vars.items():
            config = getattr(automation, key)
            config.enabled = enabled_var.get()
            try:
                interval = int(interval_var.get() or config.interval_hours)
            except ValueError:
                interval = config.interval_hours
            config.interval_hours = max(0, interval)
        return ProjectData(
            basic_info=basic,
            cloudflare=cloudflare,
            content_structure=content_structure,
            categories=category_settings,
            product_lists=product_lists,
            affiliate_links=affiliate_links,
            posting_preferences=posting_preferences,
            zimmwriter=zimmwriter,
            linking_rules=linking_rules,
            schema=SchemaSettings(),
            deployment=deployment,
            health=health,
            automation=automation,
        )

    def _save_project(self) -> None:
        try:
            data = self._gather_data()
            project_path = self.app.manager.create_project(data)
            self.app.set_status(f"Project saved to {project_path}")
            self.form_status.set(f"Saved to {project_path}")
            self.app.refresh_projects()
        except Exception as exc:  # pragma: no cover - UI safety
            messagebox.showerror("Error", str(exc))
            self.form_status.set(f"Error: {exc}")

    def on_project_change(self, project_data: ProjectData) -> None:
        self.load_project(project_data)


class TopicalBlueprintPanel(BasePanel):
    """Panel presenting blueprint stats and controls (Part 2)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        controls = ttk.Frame(self)
        controls.pack(fill="x")
        ttk.Button(controls, text="Generate Blueprint", command=self._generate).pack(side="left", padx=4)
        ttk.Button(controls, text="Regenerate (overwrite)", command=self._regenerate).pack(side="left", padx=4)
        ttk.Button(controls, text="Export CSVs", command=self._open_csv_folder).pack(side="left", padx=4)
        self.status_var = tk.StringVar(value="No blueprint loaded")
        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", pady=6)
        self.stats_vars = {
            "pillar": tk.StringVar(value="Pillars: 0"),
            "supporting": tk.StringVar(value="Supporting: 0"),
            "info": tk.StringVar(value="Informational: 0"),
            "reviews": tk.StringVar(value="Affiliate Reviews: 0"),
            "roundups": tk.StringVar(value="Amazon Roundups: 0"),
        }
        stats_frame = ttk.LabelFrame(self, text="Topic Counts", padding=10)
        stats_frame.pack(fill="x", pady=6)
        for var in self.stats_vars.values():
            ttk.Label(stats_frame, textvariable=var).pack(anchor="w")
        self.graph_preview = tk.Text(self, height=12)
        self.graph_preview.pack(fill="both", expand=True, pady=6)

    def _generate(self) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            BulkRegenerator(project, root).rebuild_blueprint()
        except Exception as exc:
            messagebox.showerror("Blueprint", str(exc))
            return
        messagebox.showinfo("Blueprint", "Blueprint generated.")
        self.on_show()

    def _regenerate(self) -> None:
        self._generate()

    def _open_csv_folder(self) -> None:
        root = self.app.get_project_root()
        if not root:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return
        csv_dir = root / "outputs" / "csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        self.status_var.set(f"CSV directory: {csv_dir}")

    def on_show(self) -> None:
        root = self.app.get_project_root()
        if not root:
            self.status_var.set("Select a project to view blueprint stats")
            return
        graph_path = root / "outputs" / "content" / "topic_graph.json"
        if not graph_path.exists():
            self.status_var.set("No topic graph found. Generate the blueprint.")
            self.graph_preview.delete("1.0", "end")
            return
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        self.stats_vars["pillar"].set(f"Pillars: {len(data.get('pillars', []))}")
        supporting = sum(len(p.get("supporting", [])) for p in data.get("pillars", []))
        self.stats_vars["supporting"].set(f"Supporting: {supporting}")
        self.stats_vars["info"].set(f"Informational: {len(data.get('informational', []))}")
        self.stats_vars["reviews"].set(f"Affiliate Reviews: {len(data.get('affiliate_reviews', []))}")
        self.stats_vars["roundups"].set(f"Amazon Roundups: {len(data.get('amazon_roundups', []))}")
        self.graph_preview.delete("1.0", "end")
        self.graph_preview.insert("1.0", json.dumps(data, indent=2))
        self.status_var.set(f"Loaded blueprint from {graph_path}")


class PostingPanel(BasePanel):
    """Panel summarizing posting status and scheduling controls (Part 3)."""

    ACTION_MAP = {
        "Post Pillar Content": "pillar",
        "Post Supporting Content": "supporting",
        "Post Affiliate Reviews": "affiliate_review",
        "Post Amazon Roundups": "amazon_roundup",
        "Post Informational Content": "info",
    }

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.publish_mode = tk.StringVar(value="schedule")
        ttk.Radiobutton(self, text="Publish Immediately", variable=self.publish_mode, value="publish").pack(
            anchor="w"
        )
        ttk.Radiobutton(self, text="Use Scheduling Preferences", variable=self.publish_mode, value="schedule").pack(
            anchor="w"
        )
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=6)
        for label in [
            "Post Pillar Content",
            "Post Supporting Content",
            "Post Affiliate Reviews",
            "Post Amazon Roundups",
            "Post Informational Content",
        ]:
            ttk.Button(buttons, text=label, command=lambda l=label: self._trigger_posting(l)).pack(
                side="left", padx=4
            )
        ttk.Button(self, text="Sync from WordPress", command=self._sync_from_wordpress).pack(
            anchor="w", pady=4
        )
        self.csv_status = ttk.Treeview(
            self,
            columns=("csv", "available"),
            show="headings",
            height=5,
        )
        self.csv_status.heading("csv", text="CSV")
        self.csv_status.heading("available", text="Status")
        self.csv_status.pack(fill="x", pady=6)
        self.post_stats = tk.Text(self, height=10)
        self.post_stats.pack(fill="both", expand=True)

    def _trigger_posting(self, label: str) -> None:
        post_type = self.ACTION_MAP.get(label)
        if not post_type:
            return
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            manager = DeploymentManager(project, root)
            publish_now = self.publish_mode.get() == "publish"
            report = manager.publish_posts_from_csv(
                post_type,
                publish_immediately=publish_now,
            )
        except DeploymentError as exc:
            messagebox.showerror("Posting", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("Posting", str(exc))
            return
        summary = f"Created {report.created} {post_type} posts"
        if report.errors:
            summary += f" ({len(report.errors)} errors)"
        messagebox.showinfo("Posting", summary)
        self.app.set_status(summary)
        self.on_show()

    def _sync_from_wordpress(self) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            sync = ContentSyncModule(project, root)
            synced = len(sync.sync())
        except Exception as exc:
            messagebox.showerror("Content Sync", str(exc))
            return
        messagebox.showinfo("Content Sync", f"Synced {synced} posts from WordPress.")
        self.on_show()

    def on_show(self) -> None:
        root = self.app.get_project_root()
        for row in self.csv_status.get_children():
            self.csv_status.delete(row)
        csv_names = [
            "pillar_posts.csv",
            "supporting_posts.csv",
            "info_posts.csv",
            "affiliate_product_reviews.csv",
            "amazon_roundups.csv",
        ]
        if not root:
            return
        csv_dir = root / "outputs" / "csv"
        for name in csv_names:
            status = "Yes" if (csv_dir / name).exists() else "Missing"
            self.csv_status.insert("", "end", values=(name, status))
        post_map = root / "outputs" / "content" / "post_map.json"
        self.post_stats.delete("1.0", "end")
        if post_map.exists():
            data = json.loads(post_map.read_text(encoding="utf-8"))
            counts: Dict[str, int] = {}
            for entry in data:
                post_type = entry.get("post_type", "unknown")
                counts[post_type] = counts.get(post_type, 0) + 1
            for key, value in counts.items():
                self.post_stats.insert("end", f"{key}: {value}\n")


class InternalLinkingPanel(BasePanel):
    """Panel summarizing linking health and controls (Part 4)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Dry Run", command=lambda: self._notify("Dry run only")).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Apply Links", command=lambda: self._notify("Live linking")) .pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Rebuild Link Map", command=lambda: self._notify("Rebuild map")).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Full Rebuild", command=lambda: self._regenerate_links("full")).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Fix Missing", command=lambda: self._regenerate_links("missing")).pack(
            side="left", padx=4
        )
        settings = ttk.LabelFrame(self, text="Rules", padding=10)
        settings.pack(fill="x", pady=6)
        self.max_links_var = tk.IntVar(value=8)
        self.min_links_var = tk.IntVar(value=2)
        ttk.Label(settings, text="Max links per post").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(settings, from_=0, to=30, textvariable=self.max_links_var).grid(row=0, column=1, padx=4)
        ttk.Label(settings, text="Min links per post").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(settings, from_=0, to=10, textvariable=self.min_links_var).grid(row=1, column=1, padx=4)
        self.cross_pillar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text="Allow cross-pillar links", variable=self.cross_pillar_var).grid(
            row=2, column=0, columnspan=2, sticky="w"
        )
        self.info_affiliate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text="Allow info → affiliate", variable=self.info_affiliate_var).grid(
            row=3, column=0, columnspan=2, sticky="w"
        )
        self.stats_text = tk.Text(self, height=12)
        self.stats_text.pack(fill="both", expand=True, pady=6)

    def _notify(self, message: str) -> None:
        self.app.set_status(f"Internal linking: {message}")

    def _regenerate_links(self, mode: str) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            regen = BulkRegenerator(project, root)
            regen.rebuild_internal_links(mode=mode, dry_run=False)
        except Exception as exc:
            messagebox.showerror("Internal Linking", str(exc))
            return
        message = "Rebuilt all links" if mode == "full" else "Updated missing links"
        messagebox.showinfo("Internal Linking", message)
        self.app.set_status(message)

    def on_show(self) -> None:
        root = self.app.get_project_root()
        self.stats_text.delete("1.0", "end")
        if not root:
            return
        link_map = root / "outputs" / "content" / "link_map.json"
        if not link_map.exists():
            self.stats_text.insert("1.0", "No link map available. Run the linking engine.\n")
            return
        data = json.loads(link_map.read_text(encoding="utf-8"))
        self.stats_text.insert("1.0", f"Total links: {len(data)}\n")


class CategoryMenuPanel(BasePanel):
    """Panel for category/menu controls (Part 5)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Auto-generate Categories", command=self._auto_generate).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Push Categories", command=self._push_categories).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Build Main Menu", command=lambda: self._notify("menu")).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Rebuild Categories", command=self._rebuild_categories).pack(
            side="left", padx=4
        )
        self.category_list = tk.Text(self, height=10)
        self.category_list.pack(fill="both", expand=True, pady=6)

    def _auto_generate(self) -> None:
        if not self.app.current_project_data:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return
        suggestions = self.app.manager.suggest_categories(
            self.app.current_project_data.basic_info.niche
        )
        self.category_list.delete("1.0", "end")
        self.category_list.insert("1.0", "\n".join(suggestions))
        self.app.set_status("Category suggestions populated")

    def _notify(self, action: str) -> None:
        self.app.set_status(f"Category/menu action: {action}")

    def _rebuild_categories(self) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            BulkRegenerator(project, root).rebuild_categories()
        except Exception as exc:
            messagebox.showerror("Categories", str(exc))
            return
        messagebox.showinfo("Categories", "Categories and menu rebuilt.")
        self.app.set_status("Categories rebuilt")

    def on_show(self) -> None:
        self.category_list.delete("1.0", "end")
        if self.app.current_project_data:
            categories = self.app.current_project_data.categories.categories or ["(no categories configured)"]
            self.category_list.insert("1.0", "\n".join(categories))

    def _push_categories(self) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            manager = DeploymentManager(project, root)
            report = manager.push_categories()
        except DeploymentError as exc:
            messagebox.showerror("Push Categories", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI safeguard
            messagebox.showerror("Push Categories", str(exc))
            return
        job_name = ""
        if report.details and report.details.get("job_path"):
            job_name = Path(str(report.details["job_path"])).name
        summary = f"Queued {report.total_rows} categories via ASE Connector"
        if job_name:
            summary += f" ({job_name})"
        messagebox.showinfo("Push Categories", summary)
        self.app.set_status(summary)
        self.on_show()


class AffiliatePanel(BasePanel):
    """Panel for affiliate offers and CTA templates (Part 6)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.offer_tree = ttk.Treeview(
            self,
            columns=("offer", "network", "weight"),
            show="headings",
            height=6,
        )
        for heading in ["Offer", "Network", "Weight"]:
            self.offer_tree.heading(heading.lower(), text=heading)
        self.offer_tree.pack(fill="x", pady=4)
        ttk.Button(self, text="Run Affiliate Link Sanity Check", command=self._run_sanity).pack(
            anchor="w", pady=4
        )
        ttk.Button(self, text="Rebuild CTAs", command=lambda: self._rebuild_ctas("full")).pack(
            anchor="w", pady=2
        )
        ttk.Button(self, text="Fix Missing CTAs", command=lambda: self._rebuild_ctas("missing")).pack(
            anchor="w", pady=2
        )
        template_frame = ttk.LabelFrame(self, text="CTA Templates", padding=10)
        template_frame.pack(fill="both", expand=True)
        self.template_widgets: Dict[str, tk.Text] = {}
        for placeholder in ["CTA_TOP", "CTA_BOTTOM", "CTA_INLINE", "AFFILIATE_BOX"]:
            ttk.Label(template_frame, text=placeholder).pack(anchor="w")
            widget = tk.Text(template_frame, height=3)
            widget.pack(fill="x", pady=2)
            self.template_widgets[placeholder] = widget

    def _run_sanity(self) -> None:
        self.app.set_status("Affiliate sanity check requested")

    def _rebuild_ctas(self, mode: str) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            BulkRegenerator(project, root).rebuild_affiliate_ctas(mode=mode)
        except Exception as exc:
            messagebox.showerror("Affiliate", str(exc))
            return
        message = "Rebuilt all CTAs" if mode == "full" else "Updated missing CTAs"
        messagebox.showinfo("Affiliate", message)

    def on_show(self) -> None:
        for row in self.offer_tree.get_children():
            self.offer_tree.delete(row)
        if not self.app.current_project_data:
            return
        for offer in self.app.current_project_data.affiliate_links.offers:
            self.offer_tree.insert(
                "",
                "end",
                values=(offer.name, offer.network_type, offer.weight),
            )
        for placeholder, widget in self.template_widgets.items():
            widget.delete("1.0", "end")
            widget.insert(
                "1.0",
                self.app.current_project_data.affiliate_links.cta_templates.get(placeholder, ""),
            )


class SchemaPanel(BasePanel):
    """Panel managing schema toggles (Part 7)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.schema_vars = {
            "article": tk.BooleanVar(value=True),
            "product": tk.BooleanVar(value=False),
            "review": tk.BooleanVar(value=False),
            "faq": tk.BooleanVar(value=False),
            "breadcrumb": tk.BooleanVar(value=True),
        }
        toggles = ttk.LabelFrame(self, text="Schema Types", padding=10)
        toggles.pack(side="left", fill="y", padx=6)
        for label, var in self.schema_vars.items():
            ttk.Checkbutton(toggles, text=label.title(), variable=var).pack(anchor="w")
        meta_frame = ttk.LabelFrame(self, text="Site Metadata", padding=10)
        meta_frame.pack(side="left", fill="both", expand=True)
        self.site_name_var = tk.StringVar()
        self.logo_url_var = tk.StringVar()
        self.author_name_var = tk.StringVar()
        for idx, (label, var) in enumerate(
            [
                ("Site/brand name", self.site_name_var),
                ("Publisher logo URL", self.logo_url_var),
                ("Default author name", self.author_name_var),
            ]
        ):
            ttk.Label(meta_frame, text=label).grid(row=idx, column=0, sticky="w", padx=6, pady=4)
            ttk.Entry(meta_frame, textvariable=var).grid(row=idx, column=1, sticky="ew", padx=6, pady=4)
        meta_frame.columnconfigure(1, weight=1)
        ttk.Button(self, text="Generate Schema", command=lambda: self.app.set_status("Schema run requested")) .pack(
            anchor="w", pady=6
        )
        ttk.Button(self, text="Rebuild Schema", command=lambda: self._rebuild_schema("full")).pack(
            anchor="w", pady=2
        )
        ttk.Button(self, text="Fix Missing Schema", command=lambda: self._rebuild_schema("missing")).pack(
            anchor="w", pady=2
        )

    def on_show(self) -> None:
        if not self.app.current_project_data:
            return
        schema = self.app.current_project_data.schema
        self.site_name_var.set(schema.site_name)
        self.logo_url_var.set(schema.publisher_logo_url)
        self.author_name_var.set(schema.default_author_name)

    def _rebuild_schema(self, mode: str) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            BulkRegenerator(project, root).rebuild_schema(mode=mode)
        except Exception as exc:
            messagebox.showerror("Schema", str(exc))
            return
        label = "Rebuilt schema" if mode == "full" else "Updated missing schema"
        messagebox.showinfo("Schema", label)


class DeploymentPanel(BasePanel):
    """Panel summarizing deployment status (Part 8)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        connection = ttk.LabelFrame(self, text="WordPress Connection", padding=10)
        connection.pack(fill="x", pady=4)
        self.connection_vars = {
            "site_url": tk.StringVar(),
            "username": tk.StringVar(),
            "password": tk.StringVar(),
        }
        fields = [
            ("Site URL", "site_url", None),
            ("WP Username", "username", None),
            ("WP App Password", "password", "*"),
        ]
        for row, (label, key, show) in enumerate(fields):
            ttk.Label(connection, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
            ttk.Entry(
                connection,
                textvariable=self.connection_vars[key],
                show=show,
                state="readonly",
            ).grid(row=row, column=1, sticky="ew", padx=6, pady=2)
        ttk.Button(connection, text="Test Connection", command=self._test_connection).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", padx=6, pady=4
        )
        connection.columnconfigure(1, weight=1)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        for label in [
            "Configure Cloudflare",
            "Install/Configure WordPress",
            "Install Theme & Plugins",
            "Run Full Deployment",
            "Deploy Content Only",
        ]:
            ttk.Button(buttons, text=label, command=lambda l=label: self.app.set_status(f"Deployment action: {l}")).pack(
                side="left", padx=4
            )
        self.status_text = tk.Text(self, height=12)
        self.status_text.pack(fill="both", expand=True, pady=6)

    def on_show(self) -> None:
        self._refresh_connection_info()
        self.status_text.delete("1.0", "end")
        root = self.app.get_project_root()
        if not root:
            return
        status_path = root / "outputs" / "content" / "deployment_status.json"
        if status_path.exists():
            self.status_text.insert("1.0", status_path.read_text(encoding="utf-8"))
        else:
            self.status_text.insert("1.0", "No deployment run recorded.\n")

    def _refresh_connection_info(self) -> None:
        data = self.app.current_project_data
        if not data:
            for var in self.connection_vars.values():
                var.set("")
            return
        deployment = data.deployment
        defaults = {
            "site_url": deployment.site_url or data.basic_info.wp_admin_url,
            "username": deployment.wp_rest_username or data.basic_info.wp_username,
            "password": deployment.wp_app_password or data.basic_info.wp_password,
        }
        for key, value in defaults.items():
            self.connection_vars[key].set(value or "")

    def _test_connection(self) -> None:
        context = self.get_project_context()
        if not all(context):
            return
        project, root = context
        try:
            manager = DeploymentManager(project, root)
            manager.test_connection()
        except DeploymentError as exc:
            messagebox.showerror("WordPress Connection", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI guard
            messagebox.showerror("WordPress Connection", str(exc))
            return
        messagebox.showinfo("WordPress Connection", "Connection successful.")
        self.app.set_status("WordPress connection verified")


class HealthPanel(BasePanel):
    """Panel showing health monitor results (Part 9)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        ttk.Button(self, text="Run Health Check Now", command=self._run_health).pack(anchor="w", pady=4)
        self.health_summary = tk.Text(self, height=14)
        self.health_summary.pack(fill="both", expand=True, pady=6)

    def _run_health(self) -> None:
        self.app.set_status("Health check requested")

    def on_show(self) -> None:
        self.health_summary.delete("1.0", "end")
        root = self.app.get_project_root()
        if not root:
            return
        status_path = root / "outputs" / "content" / "health_status.json"
        if status_path.exists():
            self.health_summary.insert("1.0", status_path.read_text(encoding="utf-8"))
        else:
            self.health_summary.insert("1.0", "No health status available.\n")


class AutomationPanel(BasePanel):
    """Panel showing automation scheduler configuration (Part 10)."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Enable automation for this project", variable=self.enabled_var).pack(
            anchor="w"
        )
        self.task_tree = ttk.Treeview(
            self,
            columns=("task", "enabled", "interval", "last_run", "status"),
            show="headings",
        )
        for col in ["task", "enabled", "interval", "last_run", "status"]:
            self.task_tree.heading(col, text=col.title())
        self.task_tree.pack(fill="both", expand=True, pady=6)
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x")
        ttk.Button(action_frame, text="Run All Tasks Now", command=lambda: self.app.set_status("Running all tasks")) .pack(
            side="left", padx=4
        )
        ttk.Button(action_frame, text="Run Selected Task", command=lambda: self.app.set_status("Running selected task")) .pack(
            side="left", padx=4
        )

    def on_show(self) -> None:
        for row in self.task_tree.get_children():
            self.task_tree.delete(row)
        if not self.app.current_project_data:
            return
        automation = self.app.current_project_data.automation
        self.enabled_var.set(automation.automation_enabled)
        mapping = {
            "health_check": "Health Monitor",
            "affiliate_check": "Affiliate Check",
            "sitemap_ping": "Sitemap Ping",
            "linking_maintenance": "Link Maintenance",
            "content_review": "Content Review",
            "cloudflare_stats": "Cloudflare Stats",
            "log_cleanup": "Log Cleanup",
        }
        for key, label in mapping.items():
            config = getattr(automation, key)
            self.task_tree.insert(
                "",
                "end",
                values=(label, "Yes" if config.enabled else "No", f"{config.interval_hours}h", "-", "-"),
            )


class LogsPanel(BasePanel):
    """Panel for reading log files."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        self.log_choice = tk.StringVar()
        ttk.Label(self, text="Select log file").pack(anchor="w")
        self.log_select = ttk.Combobox(
            self,
            textvariable=self.log_choice,
            values=[
                "posting_engine.log",
                "internal_linking.log",
                "affiliate_engine.log",
                "schema_engine.log",
                "health_monitor.log",
                "automation.log",
                "deployment_engine.log",
            ],
        )
        self.log_select.pack(anchor="w", pady=4)
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", pady=2)
        ttk.Button(control_frame, text="Refresh", command=self._load_log).pack(
            side="left", padx=4
        )
        ttk.Button(control_frame, text="Summarize", command=self._summarize_log).pack(
            side="left", padx=4
        )
        self.log_view = tk.Text(self, height=18)
        self.log_view.pack(fill="both", expand=True)

    def _load_log(self) -> None:
        root = self.app.get_project_root()
        if not root:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return
        log_name = self.log_choice.get()
        if not log_name:
            messagebox.showinfo("Select Log", "Choose a log from the dropdown.")
            return
        log_path = root / "outputs" / "logs" / log_name
        if log_path.exists():
            self.log_view.delete("1.0", "end")
            self.log_view.insert("1.0", log_path.read_text(encoding="utf-8"))
        else:
            self.log_view.delete("1.0", "end")
            self.log_view.insert("1.0", f"Log {log_name} not found.\n")

    def on_show(self) -> None:
        self.log_view.delete("1.0", "end")

    def _summarize_log(self) -> None:
        root = self.app.get_project_root()
        if not root:
            messagebox.showinfo("Select Project", "Choose a project first.")
            return
        log_name = self.log_choice.get()
        if not log_name:
            messagebox.showinfo("Select Log", "Choose a log from the dropdown.")
            return
        log_path = root / "outputs" / "logs" / log_name
        summary = LogSummaryModule().summarize([log_path])
        self.log_view.delete("1.0", "end")
        self.log_view.insert("1.0", json.dumps(summary, indent=2))


class GlobalSearchPanel(BasePanel):
    """Panel for running cross-project searches."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        ttk.Label(self, text="Search projects").pack(anchor="w")
        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill="x", pady=4)
        self.query_var = tk.StringVar()
        ttk.Entry(entry_frame, textvariable=self.query_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_frame, text="Search", command=self._run_search).pack(side="left", padx=4)
        self.results = ttk.Treeview(
            self,
            columns=("project", "context"),
            show="headings",
            height=12,
        )
        self.results.heading("project", text="Project")
        self.results.heading("context", text="Match")
        self.results.pack(fill="both", expand=True)
        ttk.Button(self, text="Open Selected Project", command=self._open_selected).pack(
            anchor="e", pady=4
        )

    def _run_search(self) -> None:
        searcher = GlobalProjectSearch(self.app.manager.projects_dir)
        matches = searcher.search(self.query_var.get())
        for row in self.results.get_children():
            self.results.delete(row)
        for match in matches:
            self.results.insert("", "end", values=(match.project_name, match.match_context))
        if not matches:
            self.app.set_status("No results found")

    def _open_selected(self) -> None:
        selection = self.results.selection()
        if not selection:
            messagebox.showinfo("Select Result", "Choose a project from the table.")
            return
        project_name = self.results.item(selection[0], "values")[0]
        for summary in self.app.manager.list_projects():
            if summary.project_name == project_name:
                self.app.select_project(summary)
                self.app.show_panel("Project Config")
                return
        messagebox.showinfo("Not Found", "Project could not be loaded.")


class GlobalSettingsPanel(BasePanel):
    """Panel exposing app-wide preferences."""

    def __init__(self, master: tk.Widget, app: AuthoritySiteEngineApp) -> None:
        super().__init__(master, app)
        data_root = self.app.app_config.projects_root.parent
        ttk.Label(self, text="Data directory").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.projects_dir_var = tk.StringVar(value=str(data_root))
        ttk.Entry(self, textvariable=self.projects_dir_var).grid(
            row=0, column=1, sticky="ew", padx=8, pady=4
        )
        ttk.Label(self, text="Default HTTP timeout (s)").grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        self.http_timeout_var = tk.StringVar(value=str(self.app.app_config.http_timeout))
        ttk.Entry(self, textvariable=self.http_timeout_var).grid(
            row=1, column=1, sticky="w", padx=8, pady=4
        )
        ttk.Label(self, text="Max concurrent requests per project").grid(
            row=2, column=0, sticky="w", padx=8, pady=4
        )
        concurrency_default = self.app.app_config.extra.get("max_concurrent_requests", 4)
        self.concurrency_var = tk.StringVar(value=str(concurrency_default))
        ttk.Entry(self, textvariable=self.concurrency_var).grid(
            row=2, column=1, sticky="w", padx=8, pady=4
        )
        ttk.Button(self, text="Save Global Settings", command=self._save_settings).grid(
            row=3, column=0, columnspan=2, pady=10
        )
        self.columnconfigure(1, weight=1)

    def _save_settings(self) -> None:
        data_root = Path(self.projects_dir_var.get()).expanduser()
        data_root.mkdir(parents=True, exist_ok=True)
        try:
            timeout_value = int(self.http_timeout_var.get())
            concurrency_value = int(self.concurrency_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid Value", "Timeout and concurrency must be whole numbers."
            )
            return
        self.app.app_config.http_timeout = timeout_value
        self.app.app_config.extra["max_concurrent_requests"] = concurrency_value
        self.app.update_data_root(data_root)
        if self.app.config_path:
            self.app.app_config.save(self.app.config_path)
        self.app.set_status("Global settings saved")


def run_app() -> None:
    config_path = get_default_config_path()
    first_run = not config_path.exists()
    config = load_app_config(config_path)
    ensure_data_roots(config)
    data_root = config.projects_root.parent
    manager = ProjectManager(base_directory=data_root)
    app = AuthoritySiteEngineApp(manager, config=config, config_path=config_path)
    if first_run:
        app.after(200, app.show_first_run_dialog)
    app.mainloop()


__all__ = ["AuthoritySiteEngineApp", "run_app"]
