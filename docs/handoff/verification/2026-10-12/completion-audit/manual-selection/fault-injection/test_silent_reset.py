"""Evidence-only mutation: inject old silent reset into in-memory production JS."""
from test_portal_remaining_ui import page
from test_portal_manual_document_selection_ui import test_unknown_selection_never_falls_back_to_new_or_leaks_id as original_check


def test_existing_unknown_identity_assertion_rejects_silent_new_reset(page, monkeypatch):
    original = page.add_script_tag
    def inject(*args, **kwargs):
        content = kwargs.get('content', '')
        if 'function updateManualDocuments(uploads)' in content:
            assert 'select.value = selected;' in content
            kwargs['content'] = content.replace('select.value = selected;', "select.value = '';", 1)
        return original(*args, **kwargs)
    monkeypatch.setattr(page, 'add_script_tag', inject)
    original_check(page)
