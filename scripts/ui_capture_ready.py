"""Capture readiness checks for real charts, not a fixed loading delay."""
def trends_ready(page, timeout=45000):
    saved = page.locator('main').evaluate('(e)=>e.scrollTop')
    for panel_id in ['pTs1', 'pScore', 'pCe', 'pSp', 'pAlerts']:
        panel = page.locator('#' + panel_id)
        panel.scroll_into_view_if_needed()
        frame = panel.element_handle().content_frame()
        if panel_id == 'pAlerts':
            frame.wait_for_selector('[role=table]', timeout=timeout)
            assert '경보 유형' in frame.locator('body').inner_text()
        else:
            frame.wait_for_function('''() => {
                const c=document.querySelector('.uplot canvas');
                return c && c.width>0 && c.height>0 &&
                  c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3 && v>0);
            }''', timeout=timeout)
        assert not frame.locator('[data-testid="data-testid Panel status message"]').count(), panel_id
    page.locator('main').evaluate('(e,top)=>e.scrollTop=top',saved)
