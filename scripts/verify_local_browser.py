"""Local demo-only browser journey. Does not use production credentials."""
from pathlib import Path
import io
import json
from playwright.sync_api import sync_playwright
from pypdf import PdfReader


def main():
    root = max(Path('test_plan').glob('*-local-demo*/demo-access.txt'), key=lambda x: x.stat().st_mtime).parent
    password = (root / 'demo-access.txt').read_text().split('Contraseña: ')[1].strip()
    base = 'http://127.0.0.1:8766'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(base + '/login')
        page.locator('[name=email]').fill('admin@example.org')
        page.locator('[name=password]').fill(password)
        page.locator('button[type=submit]').click()
        page.wait_for_url(base + '/')
        page.locator('.book-card').filter(has_text='Lengua Primaria').first.click()
        book = page.url.split('?')[0]
        page.goto(book + '/edit')
        branch = page.locator('[name=branch_name]').input_value()
        marker = 'Texto importado E2E estricto 17 septiembre'
        page.once('dialog', lambda d: d.accept())
        page.locator('input[type=file][accept=".md,.txt"]').set_input_files({
            'name': 'prueba.md', 'mimeType': 'text/markdown',
            'buffer': ('\n\n## Prueba de importación\n\n' + marker).encode(),
        })
        page.get_by_text('Contenido añadido al borrador.', exact=False).wait_for()
        page.locator('[data-rich-mode-button=preview]').click()
        page.locator('[data-rich-preview]').get_by_text(marker, exact=False).first.wait_for()
        page.locator('[data-rich-mode-button=edit]').click()
        page.locator('[data-open-save-dialog]').click()
        page.get_by_role('button', name='Guardar cambios', exact=True).click()
        page.wait_for_url(lambda url: '/edit' not in url and '/books/' in url)
        assert marker in page.locator('body').inner_text()
        page.reload()
        assert marker in page.locator('body').inner_text()
        pdf = page.context.request.get(book + '/export/pdf', params={'branch': branch})
        assert pdf.status == 200
        assert marker in '\n'.join(x.extract_text() for x in PdfReader(io.BytesIO(pdf.body())).pages)
        (root / 'strict-csrf.pdf').write_bytes(pdf.body())
        page.get_by_role('button', name='Salir', exact=True).click()
        page.wait_for_url(base + '/login')
        assert not errors, errors
        report = dict(login=True, import_markdown=True, preview=True, save_reload=True,
                      pdf_marker=True, logout=True, js_errors=errors, csrf_bypass=False)
        (root / 'strict-e2e.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        print('Artefactos:', root)
        browser.close()


if __name__ == '__main__':
    main()
