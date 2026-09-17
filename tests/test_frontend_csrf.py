"""Template wiring only: no application startup, DB or repository mutations."""
from pathlib import Path
import re
from html.parser import HTMLParser

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attrs, "inputs": []}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None:
            self.current["inputs"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


def test_all_scoped_post_forms_have_session_token_and_keep_action():
    paths = [TEMPLATES / "base.html", *TEMPLATES.glob("books/**/*.html"), *TEMPLATES.glob("dashboard/**/*.html")]
    count = 0
    for path in paths:
        source = path.read_text()
        for block in re.findall(r"<form\b[\s\S]*?</form>", source):
            parser = Forms()
            parser.feed(block)
            form = parser.forms[0]
            if form["attrs"].get("method", "get").lower() != "post":
                assert not any(item.get("name") == "csrf_token" for item in form["inputs"])
                continue
            count += 1
            assert form["attrs"].get("action"), path
            tokens = [item for item in form["inputs"] if item.get("name") == "csrf_token"]
            assert len(tokens) == 1, path
            assert tokens[0]["type"] == "hidden"
            assert tokens[0]["value"] == "{{ csrf_token(request) }}"
    assert count == 10  # 8 book/editor forms plus both logout controls


def test_template_compilation_and_base_meta_script_order():
    env = Environment(loader=FileSystemLoader(TEMPLATES))
    for name in env.list_templates():
        if name == "base.html" or name.startswith(("books/", "dashboard/")):
            env.get_template(name)
    source = (TEMPLATES / "base.html").read_text()
    assert '<meta name="csrf-token" content="{{ csrf_token(request) }}" />' in source
    assert source.index('src="/static/js/csrf.js"') < source.index('src="/static/js/editor.js"')
    assert 'href="/logout"' not in source
    parser = Forms()
    parser.feed(source)
    assert len([f for f in parser.forms if f["attrs"].get("action") == "/logout"]) == 2
    assert source.count('<button class="button button-tonal" type="submit">') == 2


def test_rendered_detail_editor_and_creation_forms():
    from types import SimpleNamespace as Obj
    from jinja2 import ChainableUndefined
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True, undefined=ChainableUndefined)
    env.globals["csrf_token"] = lambda request: "rendered-session-token"
    user = Obj(id=1, full_name="Docente", global_role=Obj(value="admin"))
    context = dict(
        request=Obj(url=Obj(path="/books/1")), user=user,
        book=Obj(id=1, title="Libro", course="Primaria", subject="Lengua", summary=""),
        document=Obj(toc=[], pages=[], total_pages=0),
        version_context=Obj(active_branch_label="Personal", available_schools=[], available_courses=[],
                            can_manage_selected_version=True, approved_branch="main"),
        selected_branch="users/id-1/base/primaria", edit_branch="users/id-1/base/primaria",
        can_create_proposal=True, proposal_head_branch="users/id-1/base/primaria", proposal_base_branch="main",
        comment_entries=[Obj(comment=Obj(id=2, author=user, author_id=1, body="Comentario", anchor=""), branch_label="Personal")],
        review_entries=[], content="# Borrador", save_action="/books/1/edit",
    )
    expected = {
        "books/detail.html": {"/books/1/worksheets/new", "/books/1/comments", "/books/1/comments/2/delete",
                              "/books/1/issues", "/books/1/pull-requests", "/books/1/approve-version"},
        "books/editor.html": {"/books/1/edit"},
        "books/form.html": {"/books/new"},
    }
    for template, actions in expected.items():
        rendered = env.get_template(template).render(**context)
        parser = Forms()
        parser.feed(rendered)
        posts = [form for form in parser.forms if form["attrs"].get("method") == "post"]
        assert {form["attrs"]["action"] for form in posts} == actions | {"/logout"}
        for form in posts:
            assert [item["value"] for item in form["inputs"] if item.get("name") == "csrf_token"] == ["rendered-session-token"]
        assert 'content="rendered-session-token"' in rendered


def test_fetch_sites_opt_in_without_patching_global_fetch():
    for path in [ROOT / "app/static/js/editor.js", ROOT / "frontend/editor/index.js", ROOT / "frontend/editor/controls.mjs"]:
        lines = [line for line in path.read_text().splitlines() if "await fetch(" in line]
        assert lines
        assert all("LibreLibrosCSRF.options(" in line for line in lines)
    helper = (ROOT / "app/static/js/csrf.js").read_text()
    assert "window.fetch =" not in helper
    assert 'mode: "same-origin"' in helper
    assert (ROOT / "app/static/js/editor-rich.js").read_text().count("LibreLibrosCSRF.options(") == 2
